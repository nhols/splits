"""The dataset: every record of one build, with its integrity rules enforced.

Constructing a :class:`Dataset` proves that IDs are unique, that every reference resolves, and
that every value read from a document was read from a document of the same race. A dataset
that exists is a dataset that is internally consistent.
"""

from collections import Counter
from collections.abc import Iterable, Iterator
from typing import Any, Self

from pydantic import AwareDatetime, model_validator

from splits.model.base import Record
from splits.model.catalog import AnnotationMeaning, Competition
from splits.model.ids import CompetitionId, DisciplineId, SeriesId, race_of
from splits.model.provenance import Sourced, Span
from splits.model.records import (
    Athlete,
    Document,
    Flag,
    Performance,
    Race,
    Segment,
    Split,
)
from splits.model.reference import Discipline, Series
from splits.model.values import NonEmptyStr, PointKind


class BuildInfo(Record):
    built_at: AwareDatetime
    code_version: NonEmptyStr
    """The git commit (and ``-dirty`` if uncommitted changes) the build ran from."""


class Dataset(Record):
    build: BuildInfo
    disciplines: tuple[Discipline, ...]
    series: tuple[Series, ...]
    competitions: tuple[Competition, ...]
    documents: tuple[Document, ...]
    races: tuple[Race, ...]
    athletes: tuple[Athlete, ...]
    performances: tuple[Performance, ...]
    splits: tuple[Split, ...]
    segments: tuple[Segment, ...]
    flags: tuple[Flag, ...] = ()
    annotation_meanings: tuple[AnnotationMeaning, ...] = ()
    """What the marks printed beside results mean (declared in the catalog)."""

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        _unique("discipline", (d.id for d in self.disciplines))
        _unique("series", (s.id for s in self.series))
        _unique("competition", (c.id for c in self.competitions))
        _unique("document", (d.id for d in self.documents))
        _unique("race", (r.id for r in self.races))
        _unique("athlete", (a.id for a in self.athletes))
        _unique("performance", (p.id for p in self.performances))
        _unique("split", (s.id for s in self.splits))
        _unique("segment", (s.id for s in self.segments))

        disciplines: set[DisciplineId] = {d.id for d in self.disciplines}
        series: set[SeriesId] = {s.id for s in self.series}
        competitions: set[CompetitionId] = {c.id for c in self.competitions}
        for competition in self.competitions:
            _refers(competition.id, "series", competition.series, series)

        races = {r.id: r for r in self.races}
        documents = {d.id: d for d in self.documents}
        for race in self.races:
            _refers(race.id, "competition", race.competition, competitions)
            _refers(race.id, "discipline", race.key.discipline, disciplines)
            _read_from_own_race(race.id, race)
        for document in self.documents:
            _refers(document.id, "race", document.race, races)
            if race_of(document.id) != document.race:
                raise ValueError(f"document {document.id} is filed under another race")
            _read_from_own_race(document.race, document)

        athletes = {a.id: a for a in self.athletes}
        performances = {p.id: p for p in self.performances}
        for perf in self.performances:
            _refers(perf.id, "race", perf.race, races)
            _refers(perf.id, "athlete", perf.athlete, athletes)
            if race_of(perf.id) != perf.race:
                raise ValueError(f"performance {perf.id} is filed under another race")
            if athletes[perf.athlete].sex is not races[perf.race].key.sex:
                raise ValueError(f"performance {perf.id}: athlete and race differ in sex")
            _read_from_own_race(perf.race, perf)

        timings: tuple[Split | Segment, ...] = (*self.splits, *self.segments)
        for timing in timings:
            _refers(timing.id, "performance", timing.performance, performances)
            _refers(timing.id, "document", timing.document, documents)
            timed_race = performances[timing.performance].race
            if documents[timing.document].race != timed_race:
                raise ValueError(f"{timing.id} is measured by a document of another race")
            _read_from_own_race(timed_race, timing)
        for split in self.splits:
            if split.point.kind is PointKind.START:
                raise ValueError(f"{split.id}: a split cannot be taken at the start")

        subjects = {
            *races,
            *documents,
            *athletes,
            *performances,
            *(s.id for s in self.splits),
            *(s.id for s in self.segments),
        }
        for flag in self.flags:
            if flag.subject not in subjects:
                raise ValueError(f"flag {flag.check} is about unknown record {flag.subject!r}")
        return self


def _unique(kind: str, ids: Iterable[str]) -> None:
    repeated = sorted(key for key, count in Counter(ids).items() if count > 1)
    if repeated:
        raise ValueError(f"duplicate {kind} ids: {repeated[:5]}")


def _refers(owner: str, kind: str, target: str, known: set[Any] | dict[Any, Any]) -> None:
    if target not in known:
        raise ValueError(f"{owner} refers to unknown {kind} {target!r}")


def sourced_values(record: Record) -> Iterator[tuple[str, Sourced[Any]]]:
    """Every ``Sourced`` value held by a record, with its field name."""
    for name in type(record).model_fields:
        value = getattr(record, name)
        if isinstance(value, Sourced):
            yield name, value
        elif isinstance(value, tuple):
            for item in value:
                if isinstance(item, Sourced):
                    yield name, item


def _read_from_own_race(race: str, record: Record) -> None:
    for name, value in sourced_values(record):
        if isinstance(value.source, Span) and race_of(value.source.document) != race:
            raise ValueError(
                f"{name} of a record of race {race} was read from {value.source.document}"
            )
