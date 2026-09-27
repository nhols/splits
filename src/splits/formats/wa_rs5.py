"""World Athletics race analysis ("RS5") documents.

World Athletics publishes a race analysis for each sprint race at its championships, with file
names like ``AT-400-M-f--1--.RS5.pdf``; timing is by SEIKO. Each athlete gets a row and, when
the race was timed at checkpoints, two lines of splits::

      ¹ 100 m  ² 200 m  ³ 300 m                                  checkpoint labels
    2 2349 Matthew HUDSON-SMITH    GBR  26 Oct 94   44.31        athlete row
      ¹ 11.08  ² 9.98   ³ 10.91    12.34                         segment times
        11.08(2) 21.06(1) 31.97(1)                               cumulative times (rank)

The small numerals are column markers, printed in Courier. In the segment line each time
follows the marker of the checkpoint it ends at; the last, unmarked time runs from the last
checkpoint to the finish. Cumulative times sit under their checkpoint's label. A checkpoint the
timing system missed is simply absent, so values are placed by these cues, never by counting.
"""

import re
from datetime import date, datetime

from splits.formats import parse
from splits.formats.base import (
    DocumentKind,
    DocumentReading,
    EntryReading,
    Format,
    HeadingReading,
    ReadContext,
    SegmentReading,
    SplitReading,
)
from splits.formats.common import read_first, read_tail, split_band, time_tokens, wind_before_unit
from splits.model import Sourced, TimingPoint
from splits.model.ids import format_id
from splits.pdf.layout import Columns, DocumentView, Line, LineMatch
from splits.pdf.textlayer import Word

HEADING = re.compile(
    r"(?P<discipline>\d+\s*(?:Metres|m)(?:\s+Hurdles)?)\s+(?P<sex>Men|Women)\s+-\s+"
    r"(?P<round>Final|Semi-Finals?|Quarter-Finals?|Round\s+\d|Heats?|Repechage(?:\s+Round)?"
    r"|Preliminary\s+Round)\b"
)
HEAT = re.compile(r"^(?:Heat|Final|Semi-Final)\s+(?P<heat>\d+)\b")
"""The race's number within its round: ``Heat 3``, or ``Final 2`` for a final run in races."""
START = re.compile(
    r"(?P<date>\d{1,2}\s+[A-Z][a-z]+\s+\d{4})\s+(?P<time>\d{1,2}:\d{2})\s+START TIME"
)
TEMPERATURE = re.compile(r"(?P<temperature>-?\d+)°\s*C\b")
HUMIDITY = re.compile(r"(?P<humidity>\d+)\s*%")
CHECKPOINTS = re.compile(r"(?:\d+ m ?)+")
CHECKPOINT = re.compile(r"(?P<distance>\d+) m")
ATHLETE = re.compile(
    r"(?:(?P<place>\d{1,2})\s+)?(?P<bib>\d{1,5})\s+(?P<name>.+?)\s+(?P<country>[A-Z]{3})\s+"
    r"(?:(?P<birth>(?:\d{1,2}\s+[A-Z][a-z]{2}\s+)?\d{2})\s+)?"
    r"(?P<result>\d{1,2}:\d{2}\.\d{2}|\d{1,3}\.\d{2}|DNF|DNS|DQ)(?:\s+(?P<tail>.+))?"
)
TIMING_BY = re.compile(r"Timing by (?P<timing>[A-Z][A-Za-z]+)")
REVISION = re.compile(r"\.RS5\.\.(?P<revision>v\d+)")
ISSUED = re.compile(r"Issued at (?P<issued>\d{1,2}:\d{2} on [A-Za-z]+, \d{1,2} [A-Za-z]+ \d{4})")

MARKER_GAP = 30.0
"""Most points between a column marker and the segment time it labels."""
LABEL_TOLERANCE = 18.0
"""Most points between a cumulative time's centre and its checkpoint label's centre."""


def _is_marker(word: Word) -> bool:
    return "courier" in word.font.lower()


def _not_marker(word: Word) -> bool:
    return not _is_marker(word)


def _is_athlete_row(line: Line) -> bool:
    return ATHLETE.fullmatch(line.text) is not None


def _issued(text: str) -> datetime:
    clock, _, day = text.partition(" on ")
    return datetime.combine(parse.day_month_year(day), parse.clock(clock))


class WaRs5(Format):
    kind = DocumentKind.ANALYSIS
    id = format_id("wa-rs5")
    version = "1.0.0"
    name = "World Athletics race analysis (RS5)"
    publisher = "World Athletics"
    description = (
        "Race analysis sheets from World Athletics championships: cumulative time, rank and "
        "segment time at 100 m checkpoints for each athlete. Timing by SEIKO."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        lines = view.lines(1, keep=_not_marker)
        heading = view.find(lines, HEADING, "heading")
        if heading is None:
            raise view.error("no race heading such as '400 Metres Men - Final'", 1)
        start = view.find(lines, START, "start")
        if start is None:
            raise view.error("no race date and START TIME", 1)
        race_date = start.read("date", parse.day_month_year)
        heat = view.find(lines, HEAT, "heat-line")
        footer = [line for line in lines if TIMING_BY.search(line.text)]
        finish = context.discipline.finish()

        entries: list[EntryReading] = []
        grid: _Grid | None = None
        for page in view.pages:
            page_lines = view.lines(page.number, keep=_not_marker)
            grid = _Grid.find(page_lines, finish) or grid
            markers = [word for word in page.words if _is_marker(word)]
            for index, line in enumerate(page_lines):
                row = view.match(line, ATHLETE, "athlete-row", full=True)
                if row is None:
                    continue
                band = split_band(view, page_lines, index, _is_athlete_row)
                if band and grid is None:
                    raise view.error("split lines but no checkpoint labels", page.number)
                splits, segments = grid.read(view, band, markers) if grid else ((), ())
                entries.append(_entry(view, row, race_date.value, splits, segments))
        if not entries:
            raise view.error("no athlete rows")

        return DocumentReading(
            document=view.document,
            format=self.id,
            format_version=self.version,
            pages=len(view.pages),
            title=Sourced[str](value=heading.found[0], source=heading.span(), method="heading"),
            heading=HeadingReading(
                discipline=heading.read("discipline", parse.discipline),
                sex=heading.read("sex", parse.sex),
                round=heading.read("round", parse.round_name),
                heat=heat.read("heat", int) if heat else None,
            ),
            date=race_date,
            start_time=start.read("time", parse.clock),
            wind=wind_before_unit(view, 1),
            temperature=read_first(
                view, [start.line], TEMPERATURE, "weather", "temperature", parse.signed_decimal
            ),
            humidity=read_first(
                view, [start.line], HUMIDITY, "weather", "humidity", parse.signed_decimal
            ),
            issued=read_first(view, footer, ISSUED, "footer", "issued", _issued),
            revision=read_first(view, footer, REVISION, "footer", "revision", str),
            timing_by=read_first(view, footer, TIMING_BY, "footer", "timing", str),
            entries=tuple(entries),
        )


def _entry(
    view: DocumentView,
    row: LineMatch,
    race_date: date,
    splits: tuple[SplitReading, ...],
    segments: tuple[SegmentReading, ...],
) -> EntryReading:
    records, qualification, remarks = read_tail(view, row)
    return EntryReading(
        row=row.span(),
        place=row.read_opt("place", int),
        bib=row.read("bib", str),
        name=row.read("name", lambda text: parse.person_name(text, family_first=False)),
        country=row.read("country", parse.country),
        birth_date=row.read_opt("birth", lambda text: parse.birth_date_short(text, race_date)),
        result=row.read("result", parse.result),
        records=records,
        qualification=qualification,
        remarks=remarks,
        splits=splits,
        segments=segments,
    )


class _Grid:
    """A page's checkpoint columns: their timing points and where their labels are."""

    def __init__(self, points: list[TimingPoint], labels: Columns[int], finish: TimingPoint):
        self.points = points
        self.labels = labels
        self.finish = finish

    @classmethod
    def find(cls, lines: list[Line], finish: TimingPoint) -> "_Grid | None":
        header = next((line for line in lines if CHECKPOINTS.fullmatch(line.text)), None)
        if header is None:
            return None
        points: list[TimingPoint] = []
        anchors: list[tuple[int, float]] = []
        for index, found in enumerate(CHECKPOINT.finditer(header.text)):
            words = header.words_in(*found.span())
            points.append(TimingPoint.at(parse.seconds(found["distance"])))
            anchors.append((index, sum(word.xc for word in words) / len(words)))
        return cls(points, Columns(tuple(anchors), LABEL_TOLERANCE), finish)

    def read(
        self, view: DocumentView, band: list[Line], markers: list[Word]
    ) -> tuple[tuple[SplitReading, ...], tuple[SegmentReading, ...]]:
        splits: dict[int, SplitReading] = {}
        segments: dict[int, SegmentReading] = {}
        for line in band:
            for time_word, rank_word in time_tokens(line):
                if rank_word is not None:
                    column = self.labels.assign(time_word)
                    if column is None or column in splits:
                        raise view.error(
                            f"cumulative time {time_word.text} is not under a free checkpoint",
                            line.page,
                        )
                    splits[column] = SplitReading(
                        point=self.points[column],
                        time=view.read(line.page, [time_word], parse.seconds, "cumulative.time"),
                        rank=view.read(line.page, [rank_word], parse.rank, "cumulative.rank"),
                    )
                else:
                    key = self._segment_key(view, time_word, line.page, markers)
                    if key in segments:
                        raise view.error("two segment times end at one checkpoint", line.page)
                    segments[key] = SegmentReading(
                        start=TimingPoint.start() if key == 0 else self.points[key - 1],
                        end=self.finish if key == len(self.points) else self.points[key],
                        time=view.read(line.page, [time_word], parse.seconds, "segment.time"),
                    )
        return (
            tuple(splits[key] for key in sorted(splits)),
            tuple(segments[key] for key in sorted(segments)),
        )

    def _segment_key(self, view: DocumentView, word: Word, page: int, markers: list[Word]) -> int:
        """Index of the checkpoint a segment time ends at: its marker's number, or the finish
        (one past the last checkpoint) when unmarked."""
        preceding = [
            marker
            for marker in markers
            if abs(marker.yc - word.yc) < 6 and 0 <= word.x0 - marker.x1 < MARKER_GAP
        ]
        if not preceding:
            return len(self.points)
        number = int(max(preceding, key=lambda marker: marker.x1).text)
        if not 1 <= number <= len(self.points):
            raise view.error(f"column marker {number} has no checkpoint", page)
        return number - 1
