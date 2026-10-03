"""The canonical records: what the dataset says happened.

    Competition ─< Race ─< Performance >─ Athlete
                    │           │
                    └─< Document│─< Split     cumulative time at a timing point
                                └─< Segment   time between two points, as printed

A race is declared in the catalog and attested by one or more documents. Every value a document
reports is a ``Sourced`` value that points back to the exact text it was read from. Splits and
printed segments also record which document measured them: if two documents time the same race
(official timing and a video analysis, say) both series are kept side by side, never blended.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Self

from pydantic import Field, model_validator

from splits.model.base import Record
from splits.model.catalog import Retrieval
from splits.model.ids import (
    AthleteId,
    CheckId,
    CompetitionId,
    DocumentId,
    FormatId,
    PerformanceId,
    RaceId,
    RaceKey,
)
from splits.model.provenance import CatalogRef, Sourced
from splits.model.reference import TimingPoint
from splits.model.values import (
    CountryCode,
    NonEmptyStr,
    PositiveInt,
    Qualification,
    RecordTag,
    Seconds,
    Setting,
    Severity,
    Sex,
    Status,
    Url,
)


class PersonName(Record):
    """A name as printed, split into its parts. The printed text itself is in the source span."""

    given: str
    """Empty for an athlete known by one name."""
    family: NonEmptyStr
    local: NonEmptyStr | None = None
    """The name in another script, when printed alongside (e.g. katakana in Tokyo 2025)."""


class WorldAthleticsAthlete(Record):
    """An athlete of World Athletics, as its results name them: their profile ID and their
    name as World Athletics gives it now (it renames old results when an athlete's name
    changes)."""

    id: PositiveInt
    """The number ending the profile URL, e.g. 14329797. The URL's country and name are
    ignored by World Athletics, so the ID alone finds the profile."""
    name: PersonName
    url_slug: NonEmptyStr
    """The profile's path as World Athletics wrote it then, e.g.
    ``great-britain-ni/georgia-hunter-bell-14329797``."""


class BirthDate(Record):
    """A birth date as printed. Some documents print only the year."""

    year: int = Field(ge=1900, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)

    @model_validator(mode="after")
    def _valid(self) -> Self:
        if self.day is not None and self.month is None:
            raise ValueError("a day needs a month")
        if self.day is not None and self.month is not None:
            date(self.year, self.month, self.day)  # raises if there is no such day
        return self

    def __str__(self) -> str:
        parts = [f"{self.year:04d}", *(f"{p:02d}" for p in (self.month, self.day) if p)]
        return "-".join(parts)

    def refines(self, other: "BirthDate") -> bool:
        """Whether this date agrees with ``other`` and is at least as precise."""
        return all(
            theirs is None or mine == theirs
            for mine, theirs in (
                (self.year, other.year),
                (self.month, other.month),
                (self.day, other.day),
            )
        )


class Result(Record):
    """How a performance ended: a finishing time, or a status with no time."""

    status: Status
    time: Seconds | None = None

    @model_validator(mode="after")
    def _time_iff_finished(self) -> Self:
        if (self.status is Status.FINISHED) != (self.time is not None):
            raise ValueError("a finishing time is required for, and only for, finishers")
        return self


class Document(Record):
    """A document the dataset was read from: what it is, where it was published, which exact
    bytes were read, and what the document says about itself."""

    id: DocumentId
    race: RaceId
    format: FormatId
    format_version: NonEmptyStr
    """Version of the reader that read it; bumped whenever the reader's output changes."""
    url: Url
    archive_url: Url | None
    retrieval: Retrieval
    pages: PositiveInt
    issued: Sourced[datetime] | None
    """When the publisher issued this version, in local time as printed."""
    revision: Sourced[str] | None
    """The document's own version marker, e.g. ``v1`` or ``REVISED``."""
    timing_by: Sourced[str] | None
    """The timing provider the document credits, e.g. ``SEIKO``."""
    declared: CatalogRef


class Race(Record):
    """A single race: one start, one finish."""

    id: RaceId
    competition: CompetitionId
    key: RaceKey
    setting: Setting
    title: Sourced[str]
    """The race heading as printed, e.g. ``400 Metres Men - Final``."""
    date: Sourced[date]
    start_time: Sourced[time] | None
    """Local time of the start."""
    wind: Sourced[Decimal] | None
    """Metres per second; positive is a tailwind."""
    temperature: Sourced[Decimal] | None
    """Degrees Celsius."""
    humidity: Sourced[Decimal] | None
    """Relative humidity, percent."""
    weather: Sourced[str] | None
    """Conditions as described, e.g. ``Mostly cloudy``."""
    declared: CatalogRef


class Athlete(Record):
    """A person, identified across races and documents.

    These fields summarise sourced values stored on the athlete's performances (the printed
    name and birth date of each appearance); ``rule`` records the curated identity decision
    from ``catalog/athletes.yaml`` when one applied.
    """

    id: AthleteId
    number: PositiveInt
    """The athlete's permanent number, which their address on the website starts with
    (``/athletes/1234-georgia-hunter-bell``); see :mod:`splits.catalog.numbers`."""
    former_numbers: tuple[PositiveInt, ...] = ()
    """Numbers given to athletes later found to be this one; their addresses redirect here."""
    given_name: str
    """Empty for an athlete known by one name."""
    family_name: NonEmptyStr
    sex: Sex
    country: CountryCode
    """The country of the athlete's most recent performance."""
    birth_date: BirthDate | None
    """The most precise birth date the athlete's documents agree on."""
    world_athletics: WorldAthleticsAthlete | None = None
    """The athlete's World Athletics profile, from the latest results that name it (or an
    identity rule); its name is the athlete's name."""
    aliases: tuple[AthleteId, ...] = ()
    """Other IDs the athlete is known by: those of other names the documents print (an
    earlier name, another spelling). The site redirects them to the athlete."""
    rule: CatalogRef | None = None

    @property
    def world_athletics_url(self) -> str | None:
        if self.world_athletics is None:
            return None
        return f"https://worldathletics.org/athletes/{self.world_athletics.url_slug}"

    @property
    def name(self) -> str:
        return f"{self.given_name} {self.family_name}".strip()


class Performance(Record):
    """One athlete's run in one race."""

    id: PerformanceId
    race: RaceId
    athlete: AthleteId
    name: Sourced[PersonName]
    country: Sourced[CountryCode] | None
    birth_date: Sourced[BirthDate] | None
    bib: Sourced[str] | None
    lane: Sourced[int] | None
    place: Sourced[int] | None
    result: Sourced[Result]
    reaction_time: Sourced[Decimal] | None
    """Seconds from the gun to the athlete's reaction; negative for a false start."""
    precise_time: Sourced[Seconds] | None
    """The finishing time to the thousandth, where printed to separate athletes level in
    hundredths: ``20.90 (.893)`` is 20.893."""
    qualification: Sourced[Qualification] | None
    records: tuple[Sourced[RecordTag], ...] = ()
    """Record annotations, e.g. ``PB``, ``NR``."""
    remarks: tuple[Sourced[str], ...] = ()
    """Other annotations as printed, e.g. a disqualification rule (``TR17.3.1``) or ``YC``."""
    world_athletics: Sourced[WorldAthleticsAthlete] | None = None
    """The World Athletics athlete of this run: the result World Athletics lists for it, found
    by time, country and name, or declared by an identity rule."""

    @property
    def status(self) -> Status:
        return self.result.value.status

    @property
    def time(self) -> Decimal | None:
        return self.result.value.time


class Split(Record):
    """The time, from the gun, at which an athlete reached a timing point, per one document."""

    performance: PerformanceId
    document: DocumentId
    point: TimingPoint
    time: Sourced[Seconds]
    rank: Sourced[int] | None
    """The athlete's position at this point, as printed."""

    @property
    def id(self) -> str:
        return f"{self.performance}/{self.point.slug}@{self.document.rsplit('/', 1)[1]}"


class Segment(Record):
    """The time an athlete took between two timing points, as printed in one document.

    Segment times can be derived from splits, so a document's printed segments are kept to
    verify its splits, not as a separate measurement. One that starts where the document
    gives no split (the last 400 m of a 1500 m) cannot verify any, and is kept as printed.
    """

    performance: PerformanceId
    document: DocumentId
    start: TimingPoint
    end: TimingPoint
    time: Sourced[Seconds]

    @model_validator(mode="after")
    def _forwards(self) -> Self:
        if self.start.order >= self.end.order:
            raise ValueError(f"segment {self.start.label}-{self.end.label} runs backwards")
        return self

    @property
    def id(self) -> str:
        span = f"{self.start.slug}-{self.end.slug}"
        return f"{self.performance}/{span}@{self.document.rsplit('/', 1)[1]}"


class Flag(Record):
    """A data-quality finding about one record, produced by a named check."""

    check: CheckId
    severity: Severity
    subject: NonEmptyStr
    """The ID of the record the finding is about."""
    field: str | None
    """The field of that record, when the finding is about a single value."""
    message: NonEmptyStr
    suspect: bool
    """Whether analyses should leave the value out (it is probably wrong)."""
    sources: tuple[Sourced[Any], ...] = ()
    """The values the finding is drawn from, where it compares what documents print."""
