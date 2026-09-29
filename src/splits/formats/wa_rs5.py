"""World Athletics race analysis ("RS5") documents, from 2019.

World Athletics publishes a race analysis for each race it times at checkpoints at its
championships, with file names like ``AT-400-M-f--1--.RS5.pdf``; timing is by SEIKO. Each
athlete gets a row and, under it, two lines of splits per row of checkpoints::

      ¹ 100 m  ² 200 m  ³ 300 m                                  checkpoint labels
    2 2349 Matthew HUDSON-SMITH    GBR  26 Oct 94   44.31        athlete row
      ¹ 11.08  ² 9.98   ³ 10.91    12.34                         segment times
        11.08(2) 21.06(1) 31.97(1)                               cumulative times (rank)

The small numerals are column markers, printed in Courier and numbered along the race. In the
segment line each time follows the marker of the checkpoint it ends at; the last, unmarked time
runs from the last checkpoint to the finish. Cumulative times sit under their checkpoint's
label. A checkpoint the timing system missed is simply absent, so values are placed by these
cues, never by counting.

Distance races are timed every 100 m, ten checkpoints to a row of labels (``¹¹ 1100 m`` starts
the second), and each athlete then has a segment line and a cumulative line for every row: the
markers of a segment line say which row of labels the cumulative line under it belongs to. A
10,000 m runs to nine pages, with the labels on the first page only.

The athlete row starts with the place, in bold, then the bib; Doha 2019 printed no bibs, and
put an athlete's record tags (``CR``) at the end of their first segment line, under the result.
"""

import re
from dataclasses import dataclass
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
from splits.formats.common import (
    RANK_WORD,
    RECORD_TAG,
    TIME_WORD,
    mentions_time,
    read_first,
    read_tail,
    wind_before_unit,
)
from splits.model import Qualification, Sourced, TimingPoint
from splits.model.ids import format_id
from splits.pdf.layout import DocumentView, Line, LineMatch
from splits.pdf.textlayer import Word

HEADING = re.compile(
    r"(?P<discipline>(?:\d{1,2},\d{3}|\d+)\s*(?:Metres|m)(?:\s+(?:Hurdles|Steeplechase))?)\s+"
    r"(?P<sex>Men|Women)\s+-\s+"
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
_ROW_TAIL = (
    r"(?P<name>.+?)\s+(?P<country>[A-Z]{3})\s+"
    r"(?:(?P<birth>(?:\d{1,2}\s+[A-Z][a-z]{2}\s+)?\d{2})\s+)?"
    r"(?P<result>\d{1,2}:\d{2}\.\d{2}|\d{1,3}\.\d{2}|DNF|DNS|DQ)(?:\s+(?P<tail>.+))?"
)
PLACED = re.compile(rf"(?P<place>\d{{1,2}})\s+(?:(?P<bib>\d{{1,5}})\s+)?{_ROW_TAIL}")
"""An athlete row that starts with a place (printed in bold), then the bib if printed."""
UNPLACED = re.compile(rf"(?:(?P<bib>\d{{1,5}})\s+)?{_ROW_TAIL}")
"""An athlete row without a place (DNF, DQ): the bib, if printed, then the name."""
TIMING_BY = re.compile(r"Timing by (?P<timing>[A-Z][A-Za-z]+)")
REVISION = re.compile(r"\.RS5\.\.(?P<revision>v\d+)")
ISSUED = re.compile(r"Issued at (?P<issued>\d{1,2}:\d{2} on [A-Za-z]+, \d{1,2} [A-Za-z]+ \d{4})")

MARKER_GAP = 30.0
"""Most points between a column marker and the segment time it labels."""
MARKERS_ABOVE = 16.0
"""Most points between a line of cumulative times and the markers of its segment line."""
UNDER_RESULT = 12.0
"""Points left of the result's left edge where annotations printed under it may start."""


def _is_marker(word: Word) -> bool:
    return "courier" in word.font.lower()


def _not_marker(word: Word) -> bool:
    return not _is_marker(word)


def _athlete_row(view: DocumentView, line: Line) -> LineMatch | None:
    """The line as an athlete row: a leading number in bold is the place, a plain one the bib."""
    placed = bool(line.words) and line.words[0].bold and line.words[0].text.isdigit()
    return view.match(line, PLACED if placed else UNPLACED, "athlete-row", full=True)


def _issued(text: str) -> datetime:
    clock, _, day = text.partition(" on ")
    return datetime.combine(parse.day_month_year(day), parse.clock(clock))


@dataclass
class _Athlete:
    row: LineMatch
    band: list[Line]
    """The athlete's split lines, which may continue on the next page."""
    annotations: list[Word]
    """Record tags and qualification marks printed under the result, not on the row."""


class WaRs5(Format):
    kind = DocumentKind.ANALYSIS
    id = format_id("wa-rs5")
    version = "1.1.0"
    name = "World Athletics race analysis (RS5)"
    publisher = "World Athletics"
    description = (
        "Race analysis sheets from World Athletics championships since 2019: cumulative time, "
        "rank and segment time at every checkpoint (every 100 m, or 50 m in the 200 m) for "
        "each athlete. Timing by SEIKO."
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

        grid: _Grid | None = None
        athletes: list[_Athlete] = []
        markers: dict[int, list[Word]] = {}
        for page in view.pages:
            page_lines = view.lines(page.number, keep=_not_marker)
            markers[page.number] = [word for word in page.words if _is_marker(word)]
            finish = context.discipline.finish()
            grid = _Grid.find(view, page_lines, markers[page.number], finish) or grid
            rows = [_athlete_row(view, line) for line in page_lines]
            first = next((i for i, row in enumerate(rows) if row is not None), len(rows))
            # Split lines above a page's first athlete row continue the previous page's last.
            athlete: _Athlete | None = athletes[-1] if athletes else None
            for index, line in enumerate(page_lines):
                row = rows[index]
                if row is not None:
                    athlete = _Athlete(row, [], [])
                    athletes.append(athlete)
                elif athlete is not None and (words := _split_words(athlete, line)):
                    athlete.band.append(Line(line.page, words))
                elif index >= first:
                    if athlete is not None and mentions_time(line):
                        raise view.error(f"unrecognised line of splits: {line.text!r}", line.page)
                    athlete = None  # a line of anything else ends an athlete's splits
        if not athletes:
            raise view.error("no athlete rows")

        entries: list[EntryReading] = []
        notes: list[str] = []
        for each in athletes:
            if each.band and grid is None:
                raise view.error("split lines but no checkpoint labels", each.row.line.page)
            splits, segments, noticed = (
                grid.read(view, each.band, markers) if grid else ((), (), [])
            )
            entries.append(_entry(view, each, race_date.value, splits, segments))
            notes.extend(f"{each.row['name']}: {note}" for note in noticed)

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
            notes=tuple(notes),
        )


def _split_words(athlete: _Athlete, line: Line) -> tuple[Word, ...]:
    """The words of ``line`` if it is one of the athlete's split lines: times and ranks, and on
    the first line, annotations under the result, which are set aside for the row."""
    result_x0 = min(word.x0 for word in athlete.row.words("result"))
    annotations = [
        word
        for word in line.words
        if not athlete.band
        and word.x0 >= result_x0 - UNDER_RESULT
        and (RECORD_TAG.fullmatch(word.text) or word.text in ("Q", "q"))
    ]
    words = tuple(word for word in line.words if word not in annotations)
    if not words or not _tokens(Line(line.page, words)):
        return ()
    athlete.annotations.extend(annotations)
    return words


def _entry(
    view: DocumentView,
    athlete: _Athlete,
    race_date: date,
    splits: tuple[SplitReading, ...],
    segments: tuple[SegmentReading, ...],
) -> EntryReading:
    row = athlete.row
    records, qualification, remarks = read_tail(view, row)
    for word in athlete.annotations:
        method = f"{row.rule}.{'qualification' if word.text in ('Q', 'q') else 'record'}"
        if word.text in ("Q", "q") and qualification is None:
            qualification = view.read(word_page(athlete), [word], Qualification, method)
        else:
            records = (*records, view.read(word_page(athlete), [word], str, method))
    return EntryReading(
        row=row.span(),
        place=row.read_opt("place", int) if "place" in row.found.re.groupindex else None,
        bib=row.read_opt("bib", str),
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


def word_page(athlete: _Athlete) -> int:
    """The page of an athlete's annotations: that of their first split line."""
    return athlete.band[0].page


class _Grid:
    """The checkpoints, numbered as their labels' markers number them."""

    def __init__(self, points: dict[int, TimingPoint], finish: TimingPoint):
        self.points = points
        self.finish = finish
        self.last = max(points)

    @classmethod
    def find(
        cls, view: DocumentView, lines: list[Line], markers: list[Word], finish: TimingPoint
    ) -> "_Grid | None":
        """The checkpoint labels (every line of them, from the first) and their markers."""
        start = next((i for i, line in enumerate(lines) if CHECKPOINTS.fullmatch(line.text)), None)
        if start is None:
            return None
        points: dict[int, TimingPoint] = {}
        for line in lines[start:]:
            if not CHECKPOINTS.fullmatch(line.text):
                break
            for found in CHECKPOINT.finditer(line.text):
                label = line.words_in(*found.span())[0]
                marker = _marker_before(markers, label)
                if marker is None or int(marker.text) in points:
                    raise view.error(f"checkpoint label {found[0]!r} has no marker", line.page)
                points[int(marker.text)] = TimingPoint.at(parse.seconds(found["distance"]))
        return cls(points, finish)

    def read(
        self, view: DocumentView, band: list[Line], markers: dict[int, list[Word]]
    ) -> tuple[tuple[SplitReading, ...], tuple[SegmentReading, ...], list[str]]:
        splits: dict[int, SplitReading] = {}
        segments: dict[int, SegmentReading] = {}
        notes: list[str] = []
        for line in band:
            pairs = _tokens(line)
            if any(rank is not None for _, rank in pairs):
                slots = _markers_above(markers[line.page], line)
                if not slots:
                    raise view.error(f"no markers above {line.text!r} to place it", line.page)
                for time_word, rank_word in pairs:
                    if time_word is None or rank_word is None:
                        if time_word is not None:
                            raise view.error(f"{time_word.text} has no rank", line.page)
                        assert rank_word is not None
                        notes.append(f"a rank {rank_word.text} with no time, p{line.page}")
                        continue
                    key = self._key(view, _slot(slots, time_word), line)
                    if key in splits:
                        raise view.error(f"two cumulative times at marker {key}", line.page)
                    splits[key] = SplitReading(
                        point=self.points[key],
                        time=view.read(line.page, [time_word], parse.seconds, "cumulative.time"),
                        rank=view.read(line.page, [rank_word], parse.rank, "cumulative.rank"),
                    )
                continue
            for index, (time_word, _) in enumerate(pairs):
                assert time_word is not None
                marker = _marker_before(markers[line.page], time_word)
                if marker is None and index < len(pairs) - 1:
                    raise view.error(f"an unmarked time mid-line: {line.text!r}", line.page)
                key = self.last + 1 if marker is None else self._key(view, marker, line)
                if key in segments:
                    raise view.error("two segment times end at one checkpoint", line.page)
                segments[key] = SegmentReading(
                    start=self.points.get(key - 1, TimingPoint.start()),
                    end=self.finish if key > self.last else self.points[key],
                    time=view.read(line.page, [time_word], parse.seconds, "segment.time"),
                )
        return (
            tuple(splits[key] for key in sorted(splits)),
            tuple(segments[key] for key in sorted(segments)),
            notes,
        )

    def _key(self, view: DocumentView, marker: Word | None, line: Line) -> int:
        if marker is None:
            raise view.error(f"no marker names the checkpoint of {line.text!r}", line.page)
        number = int(marker.text)
        if number not in self.points:
            raise view.error(f"column marker {number} has no checkpoint", line.page)
        return number


def _tokens(line: Line) -> list[tuple[Word | None, Word | None]]:
    """Times with their bracketed ranks, if any; a rank printed without a time comes as
    ``(None, rank)``. Anything else makes the line not a split line (an empty list)."""
    pairs: list[tuple[Word | None, Word | None]] = []
    words = list(line.words)
    while words:
        word = words.pop(0)
        if RANK_WORD.fullmatch(word.text):
            pairs.append((None, word))
        elif TIME_WORD.fullmatch(word.text):
            rank = words.pop(0) if words and RANK_WORD.fullmatch(words[0].text) else None
            pairs.append((word, rank))
        else:
            return []
    return pairs if any(time is not None for time, _ in pairs) else []


def _marker_before(markers: list[Word], word: Word) -> Word | None:
    """The column marker printed just left of ``word``, on its line."""
    before = [
        marker
        for marker in markers
        if abs(marker.yc - word.yc) < 6 and 0 <= word.x0 - marker.x1 < MARKER_GAP
    ]
    return max(before, key=lambda marker: marker.x1) if before else None


def _markers_above(markers: list[Word], line: Line) -> list[Word]:
    """The row of column markers just above a line of cumulative times: those of the segment
    line it belongs to."""
    centre = sum(word.yc for word in line.words) / len(line.words)
    above = [marker for marker in markers if 4 < centre - marker.yc < MARKERS_ABOVE]
    if not above:
        return []
    nearest = max(marker.yc for marker in above)
    return sorted((m for m in above if nearest - m.yc < 3), key=lambda m: m.x0)


def _slot(slots: list[Word], time_word: Word) -> Word | None:
    """The marker whose column a cumulative time is printed in: the last one starting left of
    the time's right edge (a long time may start a little left of its marker)."""
    left = [marker for marker in slots if marker.x0 < time_word.x1]
    return left[-1] if left else None
