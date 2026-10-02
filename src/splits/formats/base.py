"""The contract between format readers and the rest of the pipeline.

A *format* is one kind of published document, such as World Athletics' RS5 race analysis. Its
reader turns a document's text layer into a :class:`DocumentReading`: a faithful, typed
transcription of what the document says, with every value sourced to the words it was read
from. Readers do not decide identities, merge sources or judge plausibility; the assembly and
check stages do that, the same way for every format.

To add a format, subclass :class:`Format`, implement :meth:`Format.read`, register the class in
``splits/formats/__init__.py``, and add golden tests. See ``docs/adding-a-format.md``.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar

from splits.model import (
    BirthDate,
    Competition,
    Discipline,
    DisciplineId,
    DocumentId,
    DocumentSpec,
    FormatId,
    PersonName,
    Qualification,
    Result,
    Round,
    Sex,
    Sourced,
    Span,
    TimingPoint,
)
from splits.model.base import Record
from splits.model.values import CountryCode, NonEmptyStr, RecordTag, Seconds
from splits.pdf.layout import DocumentView


class HeadingReading(Record):
    """How the document itself names its race, parsed into the parts of a race key.

    The pipeline compares these with the catalog's declaration before using the document.
    A part the document does not state (Diamond League analyses do not name a round) is
    ``None`` and cannot be confirmed.
    """

    discipline: Sourced[DisciplineId]
    sex: Sourced[Sex]
    round: Sourced[Round] | None
    heat: Sourced[int] | None


class SplitReading(Record):
    point: TimingPoint
    time: Sourced[Seconds]
    rank: Sourced[int] | None = None


class SegmentReading(Record):
    start: TimingPoint
    end: TimingPoint
    time: Sourced[Seconds]


class EntryReading(Record):
    """One athlete's row (and split lines) in the document."""

    row: Span
    """The athlete's row, for highlighting."""
    name: Sourced[PersonName]
    country: Sourced[CountryCode] | None
    result: Sourced[Result]
    place: Sourced[int] | None = None
    bib: Sourced[str] | None = None
    lane: Sourced[int] | None = None
    birth_date: Sourced[BirthDate] | None = None
    reaction_time: Sourced[Decimal] | None = None
    """Negative for a false start."""
    precise_time: Sourced[Seconds] | None = None
    """The finishing time to the thousandth, where printed to separate athletes level in
    hundredths: ``20.90 (.893)`` is 20.893."""
    qualification: Sourced[Qualification] | None = None
    records: tuple[Sourced[RecordTag], ...] = ()
    remarks: tuple[Sourced[str], ...] = ()
    splits: tuple[SplitReading, ...] = ()
    segments: tuple[SegmentReading, ...] = ()


class DocumentReading(Record):
    """Everything a reader transcribed from one document."""

    document: DocumentId
    format: FormatId
    format_version: NonEmptyStr
    pages: int
    title: Sourced[str]
    heading: HeadingReading
    date: Sourced[date] | None
    """``None`` when the document does not print the day of the race (a report on a whole
    championships); another document of the race must."""
    start_time: Sourced[time] | None = None
    wind: Sourced[Decimal] | None = None
    temperature: Sourced[Decimal] | None = None
    humidity: Sourced[Decimal] | None = None
    weather: Sourced[str] | None = None
    issued: Sourced[datetime] | None = None
    revision: Sourced[str] | None = None
    timing_by: Sourced[str] | None = None
    entries: tuple[EntryReading, ...]
    notes: tuple[str, ...] = ()
    """Things the reader noticed but could not transcribe, for humans to review."""


class ReadContext(Record):
    """What the catalog says about the document being read."""

    spec: DocumentSpec
    discipline: Discipline
    competition: Competition


class DocumentKind(StrEnum):
    """What a kind of document is for, which decides whose values win when two documents of a
    race disagree: a results document is the official record of the result."""

    RESULTS = "results"  # places, times, lanes, reaction times
    ANALYSIS = "analysis"  # times at points along the race


class Format(ABC):
    """A kind of document, and how to read it."""

    id: ClassVar[FormatId]
    kind: ClassVar[DocumentKind]
    version: ClassVar[str]
    """Bump when the reader's output changes, so rebuilt data can be told apart."""
    name: ClassVar[str]
    compilation: ClassVar[str | None] = None
    """What a document of this format is called when it is not about one race but collects
    many (``Statistics handbook``)."""
    publisher: ClassVar[str]
    description: ClassVar[str]
    names_unsplit: ClassVar[bool] = False
    """Whether the documents print names without showing where the given name ends and the
    family name starts (``Sakari Joy Nakhumicha``). Assembly then matches each name, by all
    its words and the country, to one athlete the race's more authoritative documents name."""

    @property
    def title(self) -> str:
        """What a document of this format is called beside a race: its results, its race
        analysis, or the compilation it is."""
        if self.compilation:
            return self.compilation
        return "Results" if self.kind is DocumentKind.RESULTS else "Race analysis"

    @abstractmethod
    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        """Transcribe the document. Raise :class:`~splits.pdf.layout.ReadError` if the
        document does not have the expected layout; never guess."""
