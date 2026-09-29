"""World Athletics race analysis ("RS5") documents as laid out at the 2015 and 2017 World
Championships, for the 800 m and longer.

The checkpoints are few (400 m in the 800 m; 400, 800 and 1200 m in the 1500 m; every 1000 m
from the 5000 m) and labelled without markers. Under each athlete's row, a line of cumulative
times with ranks sits under the checkpoint labels, then a line of segment times, each in the
column of the checkpoint it ends at, the last one in the column after the last label, which
is the finish; the first stretch, from the start, is the first cumulative time and is not
repeated::

       400m    800m    1200m                               labels
    1 Elijah Motonei MANANGOI  KEN  5 Jan 93  3:33.61      athlete row
       1:01.80(2) 1:57.82(2) 2:53.87(2)                    cumulative times (rank)
                  56.02(3)   56.05(6)   39.74(2)           segment times (rank, from 2017)

Values are placed by their column, never by counting. The athlete row is that of the later
layout (:mod:`splits.formats.wa_rs5`): the place in bold, then the bib, which London 2017 left
out, the name, and a Chinese transcription at Beijing 2015.
"""

import re
from dataclasses import dataclass
from datetime import date

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
from splits.formats.common import mentions_time, read_first, read_tail, time_tokens
from splits.formats.wa_rs5 import (
    HEADING,
    HUMIDITY,
    ISSUED,
    REVISION,
    START,
    TEMPERATURE,
    _athlete_row,
    _issued,
)
from splits.model import Sourced, TimingPoint
from splits.model.ids import format_id
from splits.pdf.layout import Columns, DocumentView, Line, LineMatch

LABELS = re.compile(r"(?:\d+m ?)+")
LABEL = re.compile(r"(?P<distance>\d+)m")
TIMING_BY = re.compile(r"Timing (?:and Measurement )?by (?P<timing>[A-Z][A-Za-z]+)")
COLUMN = 46.5
"""Points between checkpoint columns: the finish's column is this far beyond the last label."""
CUMULATIVE_SIZE = 7.5
"""Cumulative times are set in 8 pt type, segment times in 7 pt."""


@dataclass
class _Athlete:
    row: LineMatch
    band: list[Line]


class WaRs5Of2015(Format):
    kind = DocumentKind.ANALYSIS
    id = format_id("wa-rs5-2015")
    version = "1.0.0"
    name = "World Athletics race analysis (RS5), 2015–2017 layout"
    publisher = "World Athletics"
    description = (
        "Race analysis sheets from the 2015 and 2017 World Championships, for the 800 m and "
        "longer: cumulative time and rank at 400 m (800 m), every 400 m (1500 m) or every "
        "1000 m, and the time of each stretch. Timing by SEIKO."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        lines = view.lines(1)
        heading = view.find(lines, HEADING, "heading")
        if heading is None:
            raise view.error("no race heading such as '800 Metres Men - Final'", 1)
        start = view.find(lines, START, "start")
        if start is None:
            raise view.error("no race date and START TIME", 1)
        race_date = start.read("date", parse.day_month_year)
        footer = [line for line in lines if TIMING_BY.search(line.text)]

        grid: _Grid | None = None
        athletes: list[_Athlete] = []
        for page in view.pages:
            page_lines = view.lines(page.number)
            grid = _Grid.find(view, page_lines, context) or grid
            athlete: _Athlete | None = None
            for line in page_lines:
                row = _athlete_row(view, line)
                if row is not None:
                    athlete = _Athlete(row, [])
                    athletes.append(athlete)
                elif athlete is not None and time_tokens(line):
                    athlete.band.append(line)
                else:
                    if athlete is not None and mentions_time(line):
                        raise view.error(f"unrecognised line of splits: {line.text!r}", line.page)
                    athlete = None
        if not athletes:
            raise view.error("no athlete rows")

        entries = []
        for each in athletes:
            if each.band and grid is None:
                raise view.error("split lines but no checkpoint labels", each.row.line.page)
            splits, segments = grid.read(view, each.band) if grid else ((), ())
            entries.append(_entry(view, each.row, race_date.value, splits, segments))

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
                heat=None,
            ),
            date=race_date,
            start_time=start.read("time", parse.clock),
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


class _Grid:
    """The checkpoint columns, and after them the finish's, one column-width further on."""

    def __init__(self, points: list[TimingPoint], columns: Columns[int]):
        self.points = points
        self.columns = columns

    @classmethod
    def find(cls, view: DocumentView, lines: list[Line], context: ReadContext) -> "_Grid | None":
        header = next((line for line in lines if LABELS.fullmatch(line.text)), None)
        if header is None:
            return None
        points: list[TimingPoint] = []
        centres: list[float] = []
        for found in LABEL.finditer(header.text):
            words = header.words_in(*found.span())
            points.append(TimingPoint.at(parse.seconds(found["distance"])))
            centres.append(sum(word.xc for word in words) / len(words))
        points.append(context.discipline.finish())
        anchors = [*enumerate(centres), (len(centres), centres[-1] + COLUMN)]
        return cls(points, Columns(tuple(anchors), tolerance=COLUMN * 0.4))

    def read(
        self, view: DocumentView, band: list[Line]
    ) -> tuple[tuple[SplitReading, ...], tuple[SegmentReading, ...]]:
        splits: dict[int, SplitReading] = {}
        segments: dict[int, SegmentReading] = {}
        for line in band:
            pairs = time_tokens(line)
            cumulative = min(time.size for time, _ in pairs) > CUMULATIVE_SIZE
            for time_word, rank_word in pairs:
                column = self.columns.assign(time_word)
                if column is None:
                    raise view.error(f"{time_word.text} is under no checkpoint", line.page)
                if cumulative:  # under its checkpoint, with a rank
                    if column == len(self.points) - 1 or column in splits or rank_word is None:
                        raise view.error(f"{time_word.text} is not a cumulative time", line.page)
                    splits[column] = SplitReading(
                        point=self.points[column],
                        time=view.read(line.page, [time_word], parse.seconds, "cumulative.time"),
                        rank=view.read(line.page, [rank_word], parse.rank, "cumulative.rank"),
                    )
                else:  # in the column of the checkpoint it ends at
                    if column in segments:
                        raise view.error("two segment times end at one checkpoint", line.page)
                    segments[column] = SegmentReading(
                        start=self.points[column - 1] if column else TimingPoint.start(),
                        end=self.points[column],
                        time=view.read(line.page, [time_word], parse.seconds, "segment.time"),
                    )
        return (
            tuple(splits[key] for key in sorted(splits)),
            tuple(segments[key] for key in sorted(segments)),
        )
