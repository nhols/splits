"""Assemble document readings into the canonical records.

This is where the catalog's declarations meet the documents' attestations:

1. Each document must confirm the race the catalog says it reports: its heading has to name
   the same discipline, sex, round and heat. A mismatch stops the build.
2. Readings of the same race are combined. For one fact given by two documents, the value of
   the results document is kept (it is the official record) and any disagreement is kept as
   a :class:`Conflict`, which a check reports. Measurements (splits, segments) are never
   combined: each stays attributed to its own document.
3. Printed names are resolved to athletes (see :mod:`splits.assemble.identity`). A document
   that names a race's athletes by family name alone is matched to the athletes its more
   authoritative documents name, when exactly one fits.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from splits.assemble.identity import Identity, IdentityResolver, display_family, fold
from splits.formats import FORMATS
from splits.formats.base import DocumentKind, DocumentReading, EntryReading
from splits.model import (
    Athlete,
    AthleteId,
    BirthDate,
    Catalog,
    Document,
    DocumentSpec,
    Performance,
    PerformanceId,
    Race,
    RaceId,
    Segment,
    Sourced,
    Split,
)
from splits.model.ids import performance_id


class AssemblyError(ValueError):
    """Readings contradict the catalog or each other."""


@dataclass(frozen=True)
class DocumentRead:
    """A catalog document together with what its reader transcribed."""

    spec: DocumentSpec
    reading: DocumentReading


@dataclass(frozen=True)
class Conflict:
    """Two documents of a race give different values for one fact. The first (from the more
    authoritative document) is kept; the other is reported."""

    subject: str
    field: str
    kept: Sourced[Any]
    other: Sourced[Any]


@dataclass(frozen=True)
class Assembled:
    documents: tuple[Document, ...]
    races: tuple[Race, ...]
    athletes: tuple[Athlete, ...]
    performances: tuple[Performance, ...]
    splits: tuple[Split, ...]
    segments: tuple[Segment, ...]
    conflicts: tuple[Conflict, ...] = ()


class _Merger:
    """Combines the values several documents give for one fact."""

    def __init__(self) -> None:
        self.conflicts: list[Conflict] = []

    def one[T](
        self, subject: str, field: str, values: Sequence[Sourced[T] | None]
    ) -> Sourced[T] | None:
        """The first value given; any different one is recorded as a conflict."""
        present = [value for value in values if value is not None]
        if not present:
            return None
        kept = present[0]
        for other in present[1:]:
            if other.value != kept.value:
                self.conflicts.append(Conflict(subject, field, kept, other))
        return kept

    def birth_date(
        self, subject: str, values: Sequence[Sourced[BirthDate] | None]
    ) -> Sourced[BirthDate] | None:
        """The most precise birth date; a year alone agrees with a full date in that year."""
        present = sorted(
            (value for value in values if value is not None),
            key=lambda v: (v.value.month is None, v.value.day is None),
        )
        if not present:
            return None
        kept = present[0]
        for other in present[1:]:
            if not kept.value.refines(other.value):
                self.conflicts.append(Conflict(subject, "birth_date", kept, other))
        return kept

    @staticmethod
    def every[T](values: Sequence[Sourced[T]]) -> tuple[Sourced[T], ...]:
        """Each distinct value once, as first given (a PB printed by both documents is one)."""
        seen: set[object] = set()
        kept: list[Sourced[T]] = []
        for value in values:
            if value.value not in seen:
                seen.add(value.value)
                kept.append(value)
        return tuple(kept)


def _authority(read: "DocumentRead") -> int:
    """Results documents first: where documents disagree on a result, theirs stands."""
    return 0 if FORMATS[read.spec.format].kind is DocumentKind.RESULTS else 1


def assemble(catalog: Catalog, reads: Sequence[DocumentRead]) -> Assembled:
    for read in reads:
        confirm_heading(read)

    by_race: dict[RaceId, list[DocumentRead]] = defaultdict(list)
    for read in sorted(reads, key=_authority):
        by_race[read.spec.race_id].append(read)
    merger = _Merger()

    resolver = IdentityResolver(catalog.athletes)
    resolver.learn(
        (entry.name.value, _value(entry.country))
        for read in reads
        for entry in read.reading.entries
    )
    races: list[Race] = []
    documents: list[Document] = []
    performances: list[Performance] = []
    splits: list[Split] = []
    segments: list[Segment] = []
    identities: dict[AthleteId, Identity] = {}
    for race_id, race_reads in by_race.items():
        races.append(_race(catalog, race_id, race_reads, merger))
        documents.extend(_document(read) for read in race_reads)
        entries: dict[PerformanceId, list[tuple[DocumentRead, EntryReading]]] = defaultdict(list)
        athlete_of: dict[PerformanceId, AthleteId] = {}
        family_of: dict[AthleteId, str] = {}
        for read in race_reads:
            seen: set[PerformanceId] = set()
            for entry in read.reading.entries:
                identity = _identify(resolver, read, entry, family_of, identities)
                identities.setdefault(identity.athlete, identity)
                family_of.setdefault(identity.athlete, fold(entry.name.value.family))
                perf_id = performance_id(race_id, identity.athlete)
                if perf_id in seen:
                    raise AssemblyError(f"{read.spec.id}: {perf_id} appears twice")
                seen.add(perf_id)
                athlete_of[perf_id] = identity.athlete
                entries[perf_id].append((read, entry))
        for perf_id, perf_entries in entries.items():
            performances.append(
                _performance(perf_id, race_id, athlete_of[perf_id], perf_entries, merger)
            )
            for read, entry in perf_entries:
                splits.extend(
                    Split(
                        performance=perf_id,
                        document=read.spec.id,
                        point=reading.point,
                        time=reading.time,
                        rank=reading.rank,
                    )
                    for reading in entry.splits
                )
                segments.extend(
                    Segment(
                        performance=perf_id,
                        document=read.spec.id,
                        start=reading.start,
                        end=reading.end,
                        time=reading.time,
                    )
                    for reading in entry.segments
                )
    resolver.check()

    race_by_id = {race.id: race for race in races}
    athletes = _athletes(performances, race_by_id, identities, catalog)
    return Assembled(
        documents=tuple(documents),
        races=tuple(races),
        athletes=athletes,
        performances=tuple(performances),
        splits=tuple(splits),
        segments=tuple(segments),
        conflicts=tuple(merger.conflicts),
    )


def _identify(
    resolver: IdentityResolver,
    read: DocumentRead,
    entry: EntryReading,
    family_of: dict[AthleteId, str],
    identities: dict[AthleteId, Identity],
) -> Identity:
    """The athlete an entry names. A report that names finalists by family name alone, with no
    country (a biomechanics report), names the one athlete of that family name among those the
    race's more authoritative documents have named; if there is not exactly one, the build
    stops."""
    name, country = entry.name.value, _value(entry.country)
    if country is not None or name.given:
        return resolver.resolve(name, country)
    family = fold(name.family)
    matches = [athlete for athlete, other in family_of.items() if other == family]
    if len(matches) != 1:
        raise AssemblyError(
            f"{read.spec.id}: {name.family} names {len(matches)} athletes of the race's other "
            "documents, not one"
        )
    return identities[matches[0]]


def confirm_heading(read: DocumentRead) -> None:
    """The document must name the race the catalog says it reports."""
    declared, heading = read.spec.race, read.reading.heading
    found: list[tuple[str, Any, Sourced[Any] | None]] = [
        ("discipline", declared.discipline, heading.discipline),
        ("sex", declared.sex, heading.sex),
        ("round", declared.round, heading.round),
        ("heat", declared.heat, heading.heat),
    ]
    for part, expected, printed in found:
        if printed is None:
            continue  # the document does not state this part
        if printed.value != expected:
            raise AssemblyError(
                f"{read.spec.id}: the catalog ({read.spec.declared.file}:"
                f"{read.spec.declared.line}) declares {part} {expected!s}, but the document "
                f"says {printed.value!s} ({printed.span.text!r}, page {printed.span.page})"
            )


def _value[T](sourced: Sourced[T] | None) -> T | None:
    return None if sourced is None else sourced.value


def _race(catalog: Catalog, race_id: RaceId, reads: list[DocumentRead], merge: _Merger) -> Race:
    spec = reads[0].spec
    competition = catalog.competitions[spec.competition]
    readings = [read.reading for read in reads]
    title = readings[0].title  # a heading is a label; documents may word it differently
    date = merge.one(race_id, "date", [reading.date for reading in readings])
    if date is None:
        raise AssemblyError(f"{race_id}: none of the race's documents gives its date")
    if not competition.start_date <= date.value <= competition.end_date:
        raise AssemblyError(
            f"{race_id}: the document dates the race {date.value}, outside the competition "
            f"({competition.start_date} to {competition.end_date})"
        )
    return Race(
        id=race_id,
        competition=spec.competition,
        key=spec.race,
        setting=spec.setting or competition.setting,
        title=title,
        date=date,
        start_time=merge.one(race_id, "start_time", [r.start_time for r in readings]),
        wind=merge.one(race_id, "wind", [r.wind for r in readings]),
        temperature=merge.one(race_id, "temperature", [r.temperature for r in readings]),
        humidity=merge.one(race_id, "humidity", [r.humidity for r in readings]),
        weather=merge.one(race_id, "weather", [r.weather for r in readings]),
        declared=spec.declared,
    )


def _document(read: DocumentRead) -> Document:
    spec, reading = read.spec, read.reading
    if spec.retrieval is None:
        raise AssemblyError(f"{spec.id} has not been fetched")
    return Document(
        id=spec.id,
        race=spec.race_id,
        format=spec.format,
        format_version=reading.format_version,
        url=spec.url,
        archive_url=spec.archive_url,
        retrieval=spec.retrieval,
        pages=reading.pages,
        issued=reading.issued,
        revision=reading.revision,
        timing_by=reading.timing_by,
        declared=spec.declared,
    )


def _performance(
    perf_id: PerformanceId,
    race_id: RaceId,
    athlete: AthleteId,
    entries: list[tuple[DocumentRead, EntryReading]],
    merge: _Merger,
) -> Performance:
    rows = [entry for _, entry in entries]

    def one(field: str) -> Any:
        return merge.one(perf_id, field, [getattr(row, field) for row in rows])

    result = one("result")
    assert result is not None  # every entry has one
    return Performance(
        id=perf_id,
        race=race_id,
        athlete=athlete,
        name=rows[0].name,
        country=one("country"),
        birth_date=merge.birth_date(perf_id, [row.birth_date for row in rows]),
        bib=one("bib"),
        lane=one("lane"),
        place=one("place"),
        result=result,
        reaction_time=one("reaction_time"),
        precise_time=one("precise_time"),
        qualification=one("qualification"),
        records=merge.every([tag for row in rows for tag in row.records]),
        remarks=merge.every([remark for row in rows for remark in row.remarks]),
    )


def _athletes(
    performances: list[Performance],
    races: dict[RaceId, Race],
    identities: dict[AthleteId, Identity],
    catalog: Catalog,
) -> tuple[Athlete, ...]:
    rules = {rule.id: rule for rule in catalog.athletes}
    by_athlete: dict[AthleteId, list[Performance]] = defaultdict(list)
    for perf in performances:
        by_athlete[perf.athlete].append(perf)

    athletes: list[Athlete] = []
    for athlete, perfs in sorted(by_athlete.items()):
        perfs.sort(key=lambda perf: races[perf.race].date.value)
        names = [perf.name.value for perf in perfs]
        rule = rules.get(athlete)
        given = rule.given if rule else _preferred_given([name.given for name in names])
        family = rule.family if rule else display_family([name.family for name in names])
        countries = [perf.country.value for perf in perfs if perf.country is not None]
        sexes = {races[perf.race].key.sex for perf in perfs}
        if len(sexes) != 1:
            raise AssemblyError(f"athlete {athlete} appears in both men's and women's races")
        athletes.append(
            Athlete(
                id=athlete,
                given_name=given,
                family_name=family,
                sex=sexes.pop(),
                country=countries[-1],
                birth_date=_agreed_birth_date(
                    [perf.birth_date.value for perf in perfs if perf.birth_date is not None]
                ),
                rule=identities[athlete].rule,
            )
        )
    return tuple(athletes)


def _preferred_given(printed: list[str]) -> str:
    mixed = [text for text in printed if any(char.islower() for char in text)]
    return (mixed or printed)[0]


def _agreed_birth_date(dates: list[BirthDate]) -> BirthDate | None:
    """The most precise birth date that every printed one agrees with, if there is one."""
    for candidate in sorted(dates, key=lambda d: (d.month is None, d.day is None)):
        if all(candidate.refines(other) for other in dates):
            return candidate
    return None
