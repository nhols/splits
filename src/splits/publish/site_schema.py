"""The shape of the website's data files: the contract between the Python publisher and the
website. ``site/src/data/types.ts`` is generated from these models (``npm run types``), so the
website cannot drift from the data.

Values read from documents are written as ``{"v": value, "s": source}``, where ``s`` indexes
the file's ``sources`` list.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from splits.model import PointKind


class SiteModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, frozen=True, extra="forbid"
    )


# ---- Values with sources -------------------------------------------------------------------


class Source(SiteModel):
    """Where a value came from: a box on a document page, or a line of the catalog."""

    doc: int | None
    """Index into the file's ``documents`` list."""
    page: int | None
    box: tuple[float, float, float, float] | None
    """x0, top, x1, bottom in PDF points from the page's top-left corner."""
    text: str | None
    """The exact text read."""
    method: str
    """The extraction rule that read it."""
    file: str | None
    line: int | None


class SNum(SiteModel):
    v: float
    s: int


class SInt(SiteModel):
    v: int
    s: int


class SStr(SiteModel):
    v: str
    s: int


# ---- Shared shapes ---------------------------------------------------------------------------


class Point(SiteModel):
    key: str
    """Stable key, e.g. ``100m``, ``h3``, ``finish``."""
    kind: PointKind
    distance: float
    hurdle: int | None
    label: str


class FlagOut(SiteModel):
    check: str
    severity: str
    subject: str
    field: str | None
    message: str
    suspect: bool
    sources: list[int]
    """Indexes into the race's sources: the values the finding is drawn from."""


# ---- index.json ------------------------------------------------------------------------------


class Barriers(SiteModel):
    count: int
    first: float
    spacing: float
    height: float


class DisciplineOut(SiteModel):
    id: str
    name: str
    short_name: str
    kind: str
    distance: float
    barriers: dict[str, Barriers]


class SeriesOut(SiteModel):
    id: str
    name: str
    short_name: str
    kind: str


class CompetitionOut(SiteModel):
    id: str
    name: str
    series: str
    start_date: str
    end_date: str
    venue: str
    city: str
    country: str
    setting: str
    results_url: str | None
    races: int
    documents: int
    declared_file: str
    declared_line: int


class FormatOut(SiteModel):
    id: str
    version: str
    name: str
    publisher: str
    description: str
    kind: str
    """``results`` (places, lanes, reaction times) or ``analysis`` (splits)."""
    module: str
    """Repository path of the reader's source code."""
    documents: int


class AnnotationOut(SiteModel):
    """What a mark printed beside results means (``TR16.8``: false start)."""

    value: str
    """The mark as printed."""
    meaning: str


class CheckOut(SiteModel):
    id: str
    severity: str
    suspect: bool
    title: str
    explanation: str
    flags: int


class ShapePoint(SiteModel):
    distance: float
    share: float
    """The median share of the race, from leaving the blocks to the finish, used up on
    reaching ``distance``."""


class Shape(SiteModel):
    """How runners in an event typically spread their time over its distance (see
    ``docs/replay-positions.md``): the replay moves runners this way between their splits."""

    points: list[ShapePoint]
    """In order of distance, ending at the finish (share 1)."""
    runs: int
    """The runs it is the median of: every clean run timed at the event's finest points."""


class EventOut(SiteModel):
    id: str
    """``400m-men``: a discipline contested by one sex."""
    discipline: str
    sex: str
    races: int
    performances: int
    athletes: int
    with_splits: int
    """Performances with at least one split."""
    settings: list[str]
    fastest: float | None
    reaction: float | None = None
    """The median published reaction time, for runners whose own was not published: events
    started from blocks only."""
    shape: Shape | None = None
    """Events up to 800 m with enough runs timed at their finest points."""


class Winner(SiteModel):
    athlete: str
    time: float
    records: list[str] = []
    """The winner's record annotations as printed, e.g. ``WR``."""


class RaceSummary(SiteModel):
    id: str
    competition: str
    discipline: str
    sex: str
    event: str
    round: str
    heat: int | None
    setting: str
    date: str
    title: str
    athletes: int
    winner: Winner | None
    points: list[str]
    """Keys of the timing points with splits, in race order (the finish excluded)."""
    formats: list[str]
    flags: int


class AthleteSummary(SiteModel):
    id: str
    number: int
    """The athlete's permanent number; their address is ``/athletes/<number>-<id>``."""
    former_numbers: list[int]
    """Numbers of athletes later found to be this one; their addresses lead here."""
    name: str
    given_name: str
    family_name: str
    country: str
    sex: str
    birth_date: str | None
    races: int
    events: list[str]
    """Events the athlete ran, e.g. ``400m-men``."""
    bests: dict[str, float]
    """Fastest finishing time per event."""
    world_athletics_url: str | None
    """The athlete's World Athletics profile."""


class BuildOut(SiteModel):
    built_at: str
    code_version: str
    races: int
    performances: int
    athletes: int
    splits: int
    documents: int
    flags: int


class ColumnOut(SiteModel):
    name: str
    type: str
    description: str


class TableOut(SiteModel):
    """A table of the downloadable database."""

    name: str
    description: str
    rows: int
    columns: list[ColumnOut]


class Index(SiteModel):
    build: BuildOut
    disciplines: list[DisciplineOut]
    series: list[SeriesOut]
    competitions: list[CompetitionOut]
    formats: list[FormatOut]
    checks: list[CheckOut]
    annotations: list[AnnotationOut]
    events: list[EventOut]
    races: list[RaceSummary]
    athletes: list[AthleteSummary]
    athlete_aliases: dict[str, str]
    """Other names' IDs of athletes (an earlier name, another spelling), for search:
    alias -> athlete ID."""
    tables: list[TableOut]


# ---- events/<event>.json ---------------------------------------------------------------------


class EventPerformance(SiteModel):
    id: str
    race: str
    athlete: str
    place: int | None
    status: str
    time: float | None
    format: str | None
    """Format of the document the splits come from."""
    splits: list[float | None]
    """Cumulative times at the event's ``points``, in order; null where not timed."""
    suspect: list[int]
    """Indexes of splits that analyses leave out: those a check marked as suspect, and every
    split of a run whose result a check marked (its finish is out of line with its splits)."""


class EventData(SiteModel):
    event: str
    discipline: str
    sex: str
    points: list[Point]
    performances: list[EventPerformance]


# ---- races/<race>.json -----------------------------------------------------------------------


class DocumentOut(SiteModel):
    id: str
    format: str
    format_version: str
    title: str
    """What the document is called beside the race: Results, Race analysis…"""
    url: str
    archive_url: str | None
    sha256: str
    size: int
    retrieved_at: str
    retrieved_from: str
    pages: int
    issued: SStr | None
    revision: SStr | None
    timing_by: SStr | None
    declared_file: str
    declared_line: int


class RaceSplit(SiteModel):
    doc: int
    point: int
    """Index into the race's ``points``."""
    time: SNum
    rank: SInt | None


class RaceSegment(SiteModel):
    doc: int
    start: int | None
    """Index into ``points``; null for the start line."""
    end: int
    time: SNum


class RacePerformance(SiteModel):
    id: str
    athlete: str
    name: SStr
    """The name as printed."""
    given_name: str
    family_name: str
    country: SStr | None
    birth_date: SStr | None
    bib: SStr | None
    lane: SInt | None
    place: SInt | None
    status: str
    time: SNum | None
    result_source: int
    reaction_time: SNum | None
    precise_time: SNum | None
    qualification: SStr | None
    records: list[SStr]
    remarks: list[SStr]
    splits: list[RaceSplit]
    segments: list[RaceSegment]


class RaceData(SiteModel):
    id: str
    competition: str
    discipline: str
    sex: str
    round: str
    heat: int | None
    setting: str
    title: SStr
    date: SStr
    start_time: SStr | None
    wind: SNum | None
    temperature: SNum | None
    humidity: SNum | None
    weather: SStr | None
    documents: list[DocumentOut]
    points: list[Point]
    """Every timing point of the race's documents, in race order, ending at the finish."""
    performances: list[RacePerformance]
    flags: list[FlagOut]
    sources: list[Source]
