"""Assemble document readings into the canonical records.

This is where the catalog's declarations meet the documents' attestations:

1. Each document must confirm the race the catalog says it reports: its heading has to name
   the same discipline, sex, round and heat. A mismatch stops the build.
2. Readings of the same race are combined. For one fact given by two documents, the value of
   the results document is kept (it is the official record) and any disagreement is kept as
   a :class:`Conflict`, which a check reports. Measurements (splits, segments) are never
   combined: each stays attributed to its own document.
3. Rows are linked to the World Athletics athletes its results list for the competition, where
   exactly one fits (see :mod:`splits.assemble.world_athletics`).
4. Printed names are resolved to athletes (see :mod:`splits.assemble.identity`): by World
   Athletics athlete where linked, else by name and country. A document that names a race's
   athletes by family name alone is matched to the athletes its more authoritative documents
   name, when exactly one fits.
"""

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from splits.assemble.identity import Identity, IdentityResolver, display_family, fold
from splits.assemble.world_athletics import WorldAthleticsResults
from splits.formats import FORMATS
from splits.formats.base import DocumentKind, DocumentReading, EntryReading
from splits.model import (
    Athlete,
    AthleteId,
    BirthDate,
    Catalog,
    Document,
    DocumentId,
    DocumentSpec,
    NumberHolder,
    Performance,
    PerformanceId,
    PersonName,
    Race,
    RaceId,
    Round,
    Segment,
    Sourced,
    Split,
    WorldAthleticsAthlete,
)
from splits.model.ids import athlete_id, performance_id, slugify
from splits.model.provenance import RegistryRef


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
class Unplaced:
    """An athlete a document puts in a race whose more authoritative documents do not name
    them (a report that misprints the heat). Their row is left out of the race and reported."""

    document: DocumentId
    entry: EntryReading


@dataclass(frozen=True)
class Note:
    """Something a reader noticed in a document that its values do not show: a row it had to
    interpret, or one it left out. Reported by a check."""

    document: DocumentId
    text: str


@dataclass(frozen=True)
class Assembled:
    documents: tuple[Document, ...]
    races: tuple[Race, ...]
    athletes: tuple[Athlete, ...]
    performances: tuple[Performance, ...]
    splits: tuple[Split, ...]
    segments: tuple[Segment, ...]
    conflicts: tuple[Conflict, ...] = ()
    unplaced: tuple[Unplaced, ...] = ()
    notes: tuple[Note, ...] = ()


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


Links = dict[tuple[DocumentId, int], Sourced[WorldAthleticsAthlete]]


def assemble(
    catalog: Catalog,
    reads: Sequence[DocumentRead],
    world_athletics: Mapping[str, WorldAthleticsResults] | None = None,
) -> Assembled:
    """``world_athletics`` holds World Athletics' results of the competitions that have them,
    by competition ID."""
    for read in reads:
        confirm_heading(read)
    registry = world_athletics or {}
    links = _links(reads, registry)
    pinned_at = {r.retrieval.sha256: r.retrieval.retrieved_at for r in registry.values()}

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
    entry_of = {
        (read.spec.id, index): entry
        for read in reads
        for index, entry in enumerate(read.reading.entries)
    }
    resolver.learn_profiles(
        (entry_of[key].name.value, _value(entry_of[key].country), link.value.id, link.value.name)
        for key, link in sorted(links.items(), key=lambda item: _pinned(item[1], pinned_at))
    )
    races: list[Race] = []
    documents: list[Document] = []
    performances: list[Performance] = []
    splits: list[Split] = []
    segments: list[Segment] = []
    identities: dict[AthleteId, Identity] = {}
    unplaced: list[Unplaced] = []
    for race_id, race_reads in by_race.items():
        races.append(_race(catalog, race_id, race_reads, merger))
        documents.extend(_document(read) for read in race_reads)
        entries: dict[PerformanceId, list[tuple[DocumentRead, EntryReading]]] = defaultdict(list)
        athlete_of: dict[PerformanceId, AthleteId] = {}
        linked: dict[PerformanceId, list[Sourced[WorldAthleticsAthlete]]] = defaultdict(list)
        family_of: dict[AthleteId, str] = {}
        words_of: dict[AthleteId, tuple[str, str | None]] = {}
        for read in race_reads:
            seen: set[PerformanceId] = set()
            for index, entry in enumerate(read.reading.entries):
                link = links.get((read.spec.id, index))
                profile = None if link is None else link.value.id
                identity = _identify(
                    resolver, read, entry, profile, family_of, words_of, identities
                )
                if identity is None:
                    unplaced.append(Unplaced(read.spec.id, entry))
                    continue
                identities.setdefault(identity.athlete, identity)
                family_of.setdefault(identity.athlete, fold(entry.name.value.family))
                words_of.setdefault(
                    identity.athlete, (_words(entry.name.value), _value(entry.country))
                )
                perf_id = performance_id(race_id, identity.athlete)
                if perf_id in seen:
                    raise AssemblyError(f"{read.spec.id}: {perf_id} appears twice")
                seen.add(perf_id)
                athlete_of[perf_id] = identity.athlete
                entries[perf_id].append((read, entry))
                if link is not None:
                    linked[perf_id].append(link)
        for perf_id, perf_entries in entries.items():
            athlete = athlete_of[perf_id]
            wa_athlete = merger.one(
                perf_id, "world_athletics", linked[perf_id]
            ) or _declared_profile(resolver, catalog, athlete)
            performances.append(
                _performance(perf_id, race_id, athlete, perf_entries, wa_athlete, merger)
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
    athletes = _athletes(performances, race_by_id, identities, catalog, pinned_at)
    return Assembled(
        documents=tuple(documents),
        races=tuple(races),
        athletes=athletes,
        performances=tuple(performances),
        splits=tuple(splits),
        segments=tuple(segments),
        conflicts=tuple(merger.conflicts),
        unplaced=tuple(unplaced),
        notes=tuple(Note(read.spec.id, text) for read in reads for text in read.reading.notes),
    )


def _identify(
    resolver: IdentityResolver,
    read: DocumentRead,
    entry: EntryReading,
    profile: int | None,
    family_of: dict[AthleteId, str],
    words_of: dict[AthleteId, tuple[str, str | None]],
    identities: dict[AthleteId, Identity],
) -> Identity | None:
    """The athlete an entry names. A report that names finalists by family name alone, with no
    country (a biomechanics report), names the one athlete of that family name among those the
    race's more authoritative documents have named. A report whose names do not show where the
    given name ends (``Format.names_unsplit``) names the one athlete with the same words in
    their name, in any order, and the same country, or failing that (a given name spelled
    another way) the one of that family name and country; if there is none, the athlete is not
    in the race (``None``). Otherwise, if there is not exactly one, the build stops."""
    name, country = entry.name.value, _value(entry.country)
    if FORMATS[read.spec.format].names_unsplit:
        words = _words(name)
        found = [athlete for athlete, other in words_of.items() if other == (words, country)]
        if not found:  # a given name spelled differently: the family name alone
            found = [
                athlete
                for athlete, (_, other) in words_of.items()
                if other == country and set(family_of[athlete].split()) <= set(words.split())
            ]
        if len(found) > 1:
            raise AssemblyError(
                f"{read.spec.id}: {name.family} {name.given} ({country}) names "
                f"{len(found)} athletes of the race's other documents, not one"
            )
        return identities[found[0]] if found else None
    if country is not None or name.given:
        return resolver.resolve(name, country, profile)
    family = fold(name.family)
    matches = [athlete for athlete, other in family_of.items() if other == family]
    if len(matches) != 1:
        raise AssemblyError(
            f"{read.spec.id}: {name.family} names {len(matches)} athletes of the race's other "
            "documents, not one"
        )
    return identities[matches[0]]


def _links(reads: Sequence[DocumentRead], registry: Mapping[str, WorldAthleticsResults]) -> Links:
    """The World Athletics athlete of every row World Athletics' results identify. Rows of
    documents that do not show where the given name ends are left to their race's other
    documents."""
    links: Links = {}
    for read in reads:
        results = registry.get(read.spec.competition)
        if results is None or FORMATS[read.spec.format].names_unsplit:
            continue
        found = {
            index: link
            for index, entry in enumerate(read.reading.entries)
            if (link := results.link(entry, read.spec.race.sex)) is not None
        }
        # Two rows of one document are two athletes: a World Athletics athlete both fit
        # identifies neither.
        rows_of = Counter(link.value.id for link in found.values())
        links.update(
            ((read.spec.id, index), link)
            for index, link in found.items()
            if rows_of[link.value.id] == 1
        )
    return links


def _pinned(
    link: Sourced[WorldAthleticsAthlete], pinned_at: Mapping[str, datetime]
) -> tuple[datetime | None, str]:
    """When the results a link was found in were pinned: the latest give the current name."""
    source = link.source
    if isinstance(source, RegistryRef):
        return pinned_at.get(source.sha256), source.sha256
    return None, ""


def _declared_profile(
    resolver: IdentityResolver, catalog: Catalog, athlete: AthleteId
) -> Sourced[WorldAthleticsAthlete] | None:
    """The World Athletics athlete an identity rule declares, for a run its results do not
    list (a race before World Athletics' online results)."""
    profile = resolver.profile_of(athlete)
    rule = next((rule for rule in catalog.athletes if rule.id == athlete), None)
    if profile is None or rule is None:
        return None
    slug = f"{slugify(rule.country)}/{slugify(f'{rule.given} {rule.family}')}-{profile}"
    return Sourced(
        value=WorldAthleticsAthlete(
            id=profile, name=PersonName(given=rule.given, family=rule.family), url_slug=slug
        ),
        source=rule.declared,
        method="declared",
    )


def _words(name: PersonName) -> str:
    """A name's words, folded and sorted: the same whichever order they are printed in."""
    return " ".join(sorted(fold(f"{name.given} {name.family}").split()))


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
        if (
            part == "round"
            and expected is Round.B_RACE
            and printed.value in (Round.HEAT, Round.FINAL)
        ):
            continue  # a B race may be printed as a final, or its heats as the event's
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
    world_athletics: Sourced[WorldAthleticsAthlete] | None,
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
        world_athletics=world_athletics,
    )


def _athletes(
    performances: list[Performance],
    races: dict[RaceId, Race],
    identities: dict[AthleteId, Identity],
    catalog: Catalog,
    pinned_at: Mapping[str, datetime],
) -> tuple[Athlete, ...]:
    rules = {rule.id: rule for rule in catalog.athletes}
    by_athlete: dict[AthleteId, list[Performance]] = defaultdict(list)
    for perf in performances:
        by_athlete[perf.athlete].append(perf)

    found: list[dict[str, Any]] = []
    first_raced: dict[AthleteId, date] = {}
    for athlete, perfs in sorted(by_athlete.items()):
        perfs.sort(key=lambda perf: races[perf.race].date.value)
        first_raced[athlete] = races[perfs[0].race].date.value
        names = [perf.name.value for perf in perfs]
        rule = rules.get(athlete)
        profiles = [perf.world_athletics for perf in perfs if perf.world_athletics is not None]
        profile = (
            max(
                profiles,
                key=lambda link: _pinned(link, pinned_at)[0] or datetime.min.replace(tzinfo=UTC),
            )
            if profiles
            else None
        )
        if rule is not None:
            given, family = rule.given, rule.family
        elif profile is not None:
            given, family = _current_name(profile.value.name, names)
        else:
            given = _preferred_given([name.given for name in names])
            family = display_family([name.family for name in names])
        countries = [perf.country.value for perf in perfs if perf.country is not None]
        sexes = {races[perf.race].key.sex for perf in perfs}
        if len(sexes) != 1:
            raise AssemblyError(f"athlete {athlete} appears in both men's and women's races")
        found.append(
            {
                "id": athlete,
                "given_name": given,
                "family_name": family,
                "sex": sexes.pop(),
                "country": countries[-1],
                "birth_date": _agreed_birth_date(
                    [perf.birth_date.value for perf in perfs if perf.birth_date is not None]
                ),
                "world_athletics": None if profile is None else profile.value,
                "aliases": _aliases(athlete, names, rule),
                "rule": identities[athlete].rule,
            }
        )
    _drop_ambiguous_aliases(found)
    numbers = _numbers(found, first_raced, catalog.athlete_numbers)
    return tuple(Athlete(**fields, **numbers[fields["id"]]) for fields in found)


def _drop_ambiguous_aliases(found: list[dict[str, Any]]) -> None:
    """Keep the aliases that are no athlete's ID and belong to one athlete only."""
    ids = {fields["id"] for fields in found}
    owners: Counter[AthleteId] = Counter(alias for f in found for alias in f["aliases"])
    for fields in found:
        fields["aliases"] = tuple(
            sorted(a for a in fields["aliases"] if a not in ids and owners[a] == 1)
        )


def _numbers(
    found: list[dict[str, Any]],
    first_raced: Mapping[AthleteId, date],
    holders: Mapping[int, NumberHolder],
) -> dict[AthleteId, dict[str, Any]]:
    """Each athlete's number, and the numbers of athletes found to be them (see
    :mod:`splits.catalog.numbers`). A recorded number whose athlete cannot be found stops the
    build: its address would stop working."""
    by_profile = {f["world_athletics"].id: f["id"] for f in found if f["world_athletics"]}
    by_name = {f["id"]: f["id"] for f in found} | {
        alias: f["id"] for f in found for alias in f["aliases"]
    }
    held: dict[AthleteId, list[int]] = defaultdict(list)
    lost: list[str] = []
    for number, holder in sorted(holders.items()):
        owner = (
            by_profile.get(holder.world_athletics) if holder.world_athletics else None
        ) or by_name.get(holder.athlete)
        if owner is None:
            lost.append(f"{number} ({holder.athlete})")
        else:
            held[owner].append(number)
    if lost:
        raise AssemblyError(
            "athlete numbers whose athletes are no longer in the data (their addresses would "
            "stop working; see catalog/athlete-numbers.json): " + ", ".join(lost)
        )
    following = max(holders, default=0) + 1
    for fields in sorted(found, key=lambda f: (first_raced[f["id"]], f["id"])):
        if not held[fields["id"]]:
            held[fields["id"]].append(following)
            following += 1
    return {
        athlete: {"number": numbers[0], "former_numbers": tuple(numbers[1:])}
        for athlete, numbers in held.items()
    }


def number_holders(athletes: Sequence[Athlete]) -> dict[int, NumberHolder]:
    """Whom each number belongs to, to record in ``catalog/athlete-numbers.json``."""
    return {
        number: NumberHolder(
            athlete=athlete.id,
            world_athletics=None if athlete.world_athletics is None else athlete.world_athletics.id,
        )
        for athlete in athletes
        for number in (athlete.number, *athlete.former_numbers)
    }


def _current_name(listed: PersonName, printed: list[PersonName]) -> tuple[str, str]:
    """World Athletics' name for the athlete, spelled as the documents print it where they
    print the same name (World Athletics writes ``HUNTER BELL``, documents ``HUNTER-BELL``)."""
    givens = [name.given for name in printed if fold(name.given) == fold(listed.given)]
    families = [name.family for name in printed if fold(name.family) == fold(listed.family)]
    given = _preferred_given(givens) if givens else listed.given
    return given, display_family(families or [listed.family])


def _aliases(athlete: AthleteId, names: list[PersonName], rule: Any) -> set[AthleteId]:
    """The IDs the athlete's other printed names (and a rule's other spellings) would have."""
    spellings = [(name.given, name.family) for name in names]
    if rule is not None:
        spellings += [(variant.given, variant.family) for variant in rule.also_known_as]
    found = {athlete_id(slugify(f"{given} {family}")) for given, family in spellings}
    found.discard(athlete)
    return found


def _preferred_given(printed: list[str]) -> str:
    mixed = [text for text in printed if any(char.islower() for char in text)]
    return (mixed or printed)[0]


def _agreed_birth_date(dates: list[BirthDate]) -> BirthDate | None:
    """The most precise birth date that every printed one agrees with, if there is one."""
    for candidate in sorted(dates, key=lambda d: (d.month is None, d.day is None)):
        if all(candidate.refines(other) for other in dates):
            return candidate
    return None
