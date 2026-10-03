"""The data-quality check framework.

A check is a named rule that looks at the assembled records and reports findings. Findings
become :class:`~splits.model.Flag` records attached to the value they are about. Checks never
change or delete data: a wrong time printed in an official document stays in the dataset,
marked, so anyone can see both what was published and why it is doubted.

``suspect`` checks mark values that analyses should leave out: values that are probably
wrong, or that do not show how an event is normally run. The others are informational.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from functools import cached_property
from typing import Any

from splits.assemble import Assembled
from splits.formats import FORMATS
from splits.model import (
    Catalog,
    CheckId,
    Discipline,
    Document,
    DocumentId,
    Flag,
    Performance,
    PerformanceId,
    Race,
    RaceId,
    Segment,
    Severity,
    Sourced,
    Split,
    Status,
)
from splits.model.ids import check_id


@dataclass(frozen=True)
class Finding:
    subject: str
    """The ID of the record the finding is about."""
    field: str | None
    message: str
    sources: tuple[Sourced[Any], ...] = ()
    """The values the finding is drawn from, so a reader can look at them where they are
    printed."""


class CheckGroup(StrEnum):
    """What kind of thing a check looks for, as readers see the checks grouped."""

    LOGIC = "Makes logical sense"
    """Times and positions that can't all be right: a split after the finish, a superhuman speed."""
    CONSISTENCY = "Data consistency"
    """Two sources, or two parts of one, that give the same fact and must agree."""
    ANOMALY = "Anomalous splits"
    """Times that could be right but are far out of line with how the event is run."""
    READING = "Reading the documents"
    """What reading a document took judgement over."""


@dataclass(frozen=True)
class Check:
    id: CheckId
    group: CheckGroup
    severity: Severity
    suspect: bool
    title: str
    explanation: str
    """What the check verifies and why, for people reading the data."""
    run: Callable[["Records"], Iterable[Finding]]


CHECKS: list[Check] = []


def check(
    name: str,
    *,
    group: CheckGroup,
    severity: Severity,
    suspect: bool,
    title: str,
    explanation: str,
) -> Callable[[Callable[["Records"], Iterable[Finding]]], Callable[["Records"], Iterable[Finding]]]:
    """Register a check function."""

    def register(
        function: Callable[["Records"], Iterable[Finding]],
    ) -> Callable[["Records"], Iterable[Finding]]:
        CHECKS.append(Check(check_id(name), group, severity, suspect, title, explanation, function))
        return function

    return register


@dataclass(frozen=True)
class Series:
    """One document's splits for one performance, in race order."""

    performance: Performance
    document: DocumentId
    splits: tuple[Split, ...]
    segments: tuple[Segment, ...]


@dataclass(frozen=True)
class Records:
    """The assembled records, indexed for checks."""

    catalog: Catalog
    assembled: Assembled

    @cached_property
    def races(self) -> dict[RaceId, Race]:
        return {race.id: race for race in self.assembled.races}

    @cached_property
    def performances_by_race(self) -> dict[RaceId, list[Performance]]:
        grouped: dict[RaceId, list[Performance]] = defaultdict(list)
        for perf in self.assembled.performances:
            grouped[perf.race].append(perf)
        return grouped

    @cached_property
    def series(self) -> list[Series]:
        splits: dict[tuple[PerformanceId, DocumentId], list[Split]] = defaultdict(list)
        segments: dict[tuple[PerformanceId, DocumentId], list[Segment]] = defaultdict(list)
        for split in self.assembled.splits:
            splits[(split.performance, split.document)].append(split)
        for segment in self.assembled.segments:
            segments[(segment.performance, segment.document)].append(segment)
        performances = {perf.id: perf for perf in self.assembled.performances}
        return [
            Series(
                performance=performances[perf_id],
                document=document,
                splits=tuple(sorted(splits[(perf_id, document)], key=lambda s: s.point.order)),
                segments=tuple(segments[(perf_id, document)]),
            )
            for perf_id, document in sorted({*splits, *segments})
        ]

    @cached_property
    def documents(self) -> dict[DocumentId, Document]:
        return {document.id: document for document in self.assembled.documents}

    def document_title(self, value: Sourced[Any]) -> str:
        """What the document a value was read from is called: Results, Race analysis…"""
        return FORMATS[self.documents[value.span.document].format].title

    def race_of(self, perf: Performance) -> Race:
        return self.races[perf.race]

    def discipline_of(self, perf: Performance) -> Discipline:
        return self.catalog.disciplines[self.race_of(perf).key.discipline]

    @staticmethod
    def finish_time(perf: Performance) -> Decimal | None:
        return perf.time if perf.status is Status.FINISHED else None


def run_checks(catalog: Catalog, assembled: Assembled) -> tuple[Flag, ...]:
    records = Records(catalog, assembled)
    flags = [
        Flag(
            check=registered.id,
            severity=registered.severity,
            subject=finding.subject,
            field=finding.field,
            message=finding.message,
            sources=finding.sources,
            suspect=registered.suspect,
        )
        for registered in CHECKS
        for finding in registered.run(records)
    ]
    return tuple(sorted(flags, key=lambda flag: (flag.subject, flag.check, flag.field or "")))
