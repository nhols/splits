"""World Athletics statistics handbooks: the results of past finals.

Before each Olympic Games, World Championships and Continental Cup, World Athletics publishes
a statistics handbook, compiled with the Association of Track and Field Statisticians, with
the result of every past final: place, lane, name, country and time, often the time at
halfway ("halves") or the reaction time, and for many finals a table of splits. Pages have
two columns, read left then right. The catalog names the page (or pages) of the race; its block
is the one headed by the competition's city and year::

    Seoul, 29 Sep 1988                                          the city and date
    (1.3) Halves                                                the wind; the extra column
    1, |5| Florence Griffith Joyner USA 21.34 WR 11.18/10.16    place, lane, ..., halves
    ...
    (Competitors: 59; Countries: 42; Finalists: 8)
    Splits 50m 100m 150m
    Griffith Joyner 6.29 11.18 16.10

The line under the title names the column printed after each result: ``Halves`` (the times
for each half of the race), ``Reactions``, a timing point (``300m``, ``1100m``: the time
there), ``Last 300m`` or ``Last lap`` (the time over that last stretch, a lap being 400 m),
or ``Official`` (the official time, where the result column gives the statisticians' estimate
of the actual one); ``Electrics``, ``Electric``, ``Actual`` and ``Adjusted`` times are the
statisticians' unofficial readings of the finish and are not transcribed. The table of splits
names its columns the same way: ``Splits 400m 800m 1200m`` (the times there; ``Manual
Splits`` when timed by hand), ``Halves``,
``Last 200m 400m`` (the time over each last stretch), ``Differential`` (the gap to the
winner, not transcribed). Its rows name athletes by family name, as a final's results name
them, and are matched to the results by it.

Results are marked ``e`` (an estimated time) or ``w`` (wind-assisted); both marks are kept
as remarks. ``=3,`` places two athletes level: the next row, which prints no place, is the
other one. A medallist later disqualified for doping is marked with a ✗ before the title, and
listed after the finishers with their original place in brackets, the rule they broke, and
their time at the line in brackets, on the same line or the next with their halves::

    (7,) |5| Antonio Pettigrew USA DQ (ADR № 10.8)
    (45.42) 22.1/23.3

Older editions print the city and year with the round, date and wind on the next line
(``Berlin 2009`` / ``Final (Aug 20) (-0.3)``), a reaction time after the result
(``1, Usain Bolt JAM 09.58WR 0.146``) with no line naming the column, or no lanes; then a lane
given in the report of the race (``Koch (lane 2) sped through 200m in 22.4. At 300m (34.1)``),
and any splits in the same sentence, are read from the report's words.
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from difflib import SequenceMatcher
from enum import StrEnum

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
from splits.model import (
    DisciplineId,
    PersonName,
    Result,
    Round,
    Sex,
    Sourced,
    TimingPoint,
)
from splits.model.ids import format_id
from splits.pdf.layout import DocumentView, Line, LineMatch, group_lines
from splits.pdf.textlayer import Word

HEADER_BAND = 40.0
"""Points from the top of the page: the running header, in spaced capitals."""

MARKER = "✗"
"""Printed before the title of a final whose medallist was disqualified for doping."""
LAP = Decimal(400)
"""A lap of the track, in metres: ``Last lap`` is the last 400 m."""

TIME = r"(?:\d{1,2}:)?\d{1,2}\.\d{1,2}"
"""A time as the handbooks print it: ``45.9``, ``1:44.06``, ``29:54.66``."""
EVENT_NAME = r"[\d,]+ Metres(?: Hurdles| Steeplechase)?"
TITLE = re.compile(
    rf"(?:{MARKER}+ )?(?:(?P<event>{EVENT_NAME}) )?(?P<city>[^\d,()]+?),? "
    r"(?:(?P<day>\d{1,2}) (?P<month>[A-Z][a-z]{2}) )?(?P<year>(?:18|19|20)\d{2})"
)
EVENT = re.compile(rf"(?P<event>{EVENT_NAME})")
"""A section heading: the event whose finals follow."""
CONTINUED = re.compile(rf"(?:Wo)?[Mm]en[\u02bc\u2019']s (?P<event>{EVENT_NAME}), continued")
"""The first line of a page whose section started on an earlier page."""
ROUND = re.compile(r"\b(?P<round>Final)\b")
DAY = re.compile(r"\((?P<day>[A-Z][a-z]{2} \d{1,2})\)")
MINUS = "\u2212"
"""The minus sign, as some editions print negative winds."""
WIND = re.compile(rf"\((?P<wind>[-+{MINUS}]?\d+\.\d)\)")
RECORD = r"=?(?:WR|OR)"
CODE = r"(?!DNF|DNS)[A-Z]{3}"
"""A country code: the athlete's nation, the team they ran for (``RUS URS``, ``GER/FRG``)."""
ROW = re.compile(
    r"(?:(?P<tie>=)?(?P<place>\d{1,2})(?: ?,)? |\((?P<annulled>\d{1,2}),\) )?"
    r"(?:\|(?P<lane>\d{1,2})\| )?(?P<name>[^\d|()]+?) ?"
    rf"(?:{CODE}[/ ])*(?P<country>{CODE})(?: \((?P<nation>{CODE})\))? "
    rf"(?P<result>{TIME}|DNF|DNS|DQ)(?P<mark>[ew])?(?: ?(?P<record>{RECORD}))?(?P<tail>.*)"
)
"""A result: place (``=3,`` level with the next row), lane, name, country (the last code; the
nation follows in brackets when the team was not one: ``BWI (JAM)``), time or status, and the
extra columns."""
CONTINUATION = re.compile(rf"\((?P<line>{TIME})\)(?P<tail>.*)")
"""The line under a disqualified athlete's row: their time at the line, and halves."""
TOKEN = re.compile(r"\([^)]*\)|\S+")
TABLE_ROW = re.compile(
    rf"(?P<name>[^\d()]+?)(?P<values>(?: (?:{TIME}(?:/{TIME})?|\d+\.\d{{2}} behind|[-–]))+)"
)
"""A row of a table of splits: a name, then times (or halves, or an empty ``-``)."""
RULE = re.compile(r"\((?P<rule>[A-Z]+ № [\d.]+)\)")
"""The rule a disqualified athlete broke: ``(ADR № 10.8)``."""
EVENT_CODE = r"(?:\d{1,2},\d{3}|\d+)m(?:HURDLES|SC|H)?"
"""An event as running headers print it: ``400m``, ``10,000m``, ``3000mSC``."""
SEX_AND_EVENTS = re.compile(
    rf"(?P<sex>WOMEN|MEN)[\u02bc\u2019']S(?P<events>{EVENT_CODE}(?:[,&]{EVENT_CODE})*)"
)
FINALS = re.compile(r"FINALS")
REPORTED_LANE = r"\b{family} \(lane (?P<lane>\d{{1,2}})\)"
REPORTED_SPLITS = (
    re.compile(r"through (?P<distance>\d{2,3})m in (?P<time>\d{1,2}\.\d{1,2})"),
    re.compile(r"\bAt (?P<distance>\d{2,3})m \((?P<time>\d{1,2}\.\d{1,2})\)"),
)


class Kind(StrEnum):
    """What a column holds."""

    SPLIT = "split"  # the time at a point
    HALVES = "halves"  # the times for each half: 21.3/23.4
    LAST = "last"  # the time over the last stretch of the race
    REACTION = "reaction"
    OFFICIAL = "official"  # the official time, beside the statisticians' estimate
    UNREAD = "unread"  # the statisticians' readings of the finish, not transcribed
    DIFFERENTIAL = "differential"  # the gap to the winner: 0.28 behind


@dataclass(frozen=True)
class Column:
    kind: Kind
    distance: Decimal | None = None
    """For a split, where it is taken; for a last stretch, how long it is."""
    anchor: float | None = None
    """In a table, where the header names it: the left edge of its label, from the left edge
    of the text column. Values are set flush left under their label, so a row with a cell
    left blank is read by where its values are."""

    @property
    def method(self) -> str:
        if self.distance is None:
            return str(self.kind)
        return f"{'last-' if self.kind is Kind.LAST else ''}{self.distance}m"

    def fits(self, token: str) -> bool:
        pattern = {
            Kind.SPLIT: TIME,
            Kind.LAST: TIME,
            Kind.HALVES: rf"\(?{TIME}/{TIME}\)?",
            Kind.REACTION: r"-?0\.\d{3}",
            Kind.OFFICIAL: rf"{TIME}(?:{RECORD})?",
            Kind.UNREAD: rf"\(?(?:{TIME}|-)\)?",
            Kind.DIFFERENTIAL: r"\d+\.\d{2}",
        }[self.kind]
        return re.fullmatch(pattern, token) is not None


SHAPES = (Column(Kind.HALVES), Column(Kind.REACTION), Column(Kind.UNREAD))
"""Columns told apart by their shape alone, for editions that print no line naming them."""
EMPTY = ("-", "–")
"""An empty cell of a table."""
ANCHOR_TOLERANCE = 20.0
"""Points a value may stand from its column's label: tables set them flush left, under the
label or under the ``Last`` of ``Last 200m``."""


class Part(StrEnum):
    """What a time read from a row, a table or a report is."""

    SPLIT = "split"  # the time at a point
    FIRST_HALF = "first-half"
    SECOND_HALF = "second-half"
    LAST = "last"  # the time over the last stretch


@dataclass(frozen=True)
class _Time:
    part: Part
    distance: Decimal | None
    """For a split, where it is taken; for a last stretch, how long it is."""
    value: Sourced[Decimal]


class WaHandbook(Format):
    kind = DocumentKind.RESULTS
    id = format_id("wa-handbook")
    version = "1.2.0"
    name = "World Athletics statistics handbook"
    publisher = "World Athletics, with the ATFS"
    description = (
        "The results of past finals in the statistics handbooks World Athletics publishes for "
        "its championships: place, lane, name, country and time, often the time at halfway "
        "or the reaction time, and for many finals a table of splits."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        lines, headers = _reading_order(view)
        city, year = context.competition.venue.city, context.competition.start_date.year
        titles = [
            (index, found)
            for index, line in enumerate(lines)
            if _is_title(line) and (found := view.match(line, TITLE, "title", full=True))
        ]
        ours = [
            (index, found)
            for index, found in titles
            if _fold(found["city"] or "") == _fold(city) and found["year"] == str(year)
        ]
        if len(ours) > 1:  # pages of two events: the one of the race
            ours = [
                (index, found)
                for index, found in ours
                if _event(view, lines[:index], found, headers).value == context.discipline.id
            ]
        if len(ours) != 1:
            raise view.error(f"expected one result headed {city} {year}, found {len(ours)}")
        start, title = ours[0]
        end = next(
            (index for index in range(start + 1, len(lines)) if _ends_block(lines[index])),
            len(lines),
        )
        block = lines[start + 1 : end]

        first = next((i for i, line in enumerate(block) if ROW.fullmatch(line.text)), None)
        if first is None:
            raise view.error(f"no results under {title.line.text!r}", title.line.page)
        intro = block[:first]
        columns = _row_columns(view, intro)
        rows, used = _rows(view, block[first:], columns)
        after = block[first + used :]
        table = _splits_table(view, after)
        report = [line for line in after if not line.words[0].font.startswith("Helvetica")]
        families = [printed for printed, _ in table]

        finish = context.discipline.finish()
        names = [row.found.read("name", lambda text: _split_name(text, families)) for row in rows]
        owners, notes = _attribute(table, [name.value for name in names])
        entries = []
        level: tuple[Sourced[int], Decimal] | None = None
        for index, (row, name) in enumerate(zip(rows, names, strict=True)):
            found = row.found
            timing = _Timing(finish)
            for owned, (_, values) in enumerate(table):
                if owners.get(owned) == index:
                    timing.add(values)
            timing.add(row.values)
            lane = found.read_opt("lane", int)
            if lane is None:
                lane, told = _from_report(view, report, name.value.family)
                timing.add(told)
            result = found.read("result", parse.result)
            if row.official is not None:
                result = row.official
            place = found.read_opt("place", int)
            if place is not None and found["tie"]:
                level = (place, result.value.time) if result.value.time is not None else None
            elif place is None and level is not None and result.value.time == level[1]:
                place = level[0]  # the other athlete of a tie, whose place is printed above
            else:
                level = None
            if row.line_time is not None:
                timing.at_line(row.line_time)
            records = [found.read("record", str)] if found["record"] else []
            records += row.records
            # the mark is the printed time's: an estimate set aside for the official one has none
            marked = found["mark"] and row.official is None
            remarks = [found.read("mark", str)] if marked else []
            remarks += row.remarks
            entries.append(
                EntryReading(
                    row=found.span(),
                    place=place,
                    lane=lane,
                    name=name,
                    country=found.read("country", parse.country),
                    result=result,
                    reaction_time=row.reaction,
                    records=tuple(records),
                    remarks=tuple(remarks),
                    splits=timing.splits(),
                    segments=timing.segments(),
                )
            )
            notes += timing.notes

        page = title.line.page
        sex, finals = _header(view, page, headers[page])
        round_line = view.find(intro, ROUND, "round")
        wind_line = view.find(intro, WIND, "wind")
        return DocumentReading(
            document=view.document,
            format=self.id,
            format_version=self.version,
            pages=len(view.pages),
            title=Sourced[str](value=title.line.text, source=title.span(), method="title"),
            heading=HeadingReading(
                discipline=_event(view, lines[:start], title, headers),
                sex=sex,
                round=round_line.read("round", parse.round_name) if round_line else finals,
                heat=None,
            ),
            date=_date(view, title, view.find(intro, DAY, "date")),
            wind=wind_line.read("wind", _wind) if wind_line else None,
            entries=tuple(entries),
            notes=tuple(notes),
        )


@dataclass
class _Row:
    """A result row, with what its extra columns, and the line under it, give."""

    found: LineMatch
    values: list[_Time]
    reaction: Sourced[Decimal] | None = None
    official: Sourced[Result] | None = None
    line_time: Sourced[Decimal] | None = None
    records: tuple[Sourced[str], ...] = ()
    remarks: tuple[Sourced[str], ...] = ()


class _Timing:
    """An athlete's splits and segments, gathered from the table, the row and the report.

    A point timed twice (the 400m of a table of splits, and the first of the halves) keeps
    both printings, unless they are alike: the more precise as the split if they agree, else
    the first, and the other as the time from the start to the point, which the checks
    compare with the split."""

    def __init__(self, finish: TimingPoint) -> None:
        self.finish = finish
        self.points: dict[TimingPoint, SplitReading] = {}
        self.stretches: dict[tuple[TimingPoint, TimingPoint], SegmentReading] = {}
        self.notes: list[str] = []

    def add(self, times: list[_Time]) -> None:
        half = TimingPoint.at(self.finish.distance / 2)
        for time in times:
            match time.part:
                case Part.SPLIT:
                    assert time.distance is not None
                    self._split(TimingPoint.at(time.distance), time.value)
                case Part.FIRST_HALF:
                    self._split(half, time.value)
                case Part.SECOND_HALF:
                    self._segment(half, self.finish, time.value)
                case Part.LAST:
                    assert time.distance is not None
                    start = TimingPoint.at(self.finish.distance - time.distance)
                    self._segment(start, self.finish, time.value)

    def at_line(self, time: Sourced[Decimal]) -> None:
        self._split(self.finish, time)

    def _split(self, point: TimingPoint, time: Sourced[Decimal]) -> None:
        if point not in self.points:
            self.points[point] = SplitReading(point=point, time=time)
            return
        kept = self.points[point].time
        if str(kept.value) == str(time.value):
            return  # printed alike
        if _agree(kept.value, time.value) and _decimals(time.value) > _decimals(kept.value):
            self.points[point] = SplitReading(point=point, time=time)
            kept, time = time, kept
        self._segment(TimingPoint.start(), point, time)

    def _segment(self, start: TimingPoint, end: TimingPoint, time: Sourced[Decimal]) -> None:
        key = (start, end)
        if key not in self.stretches:
            self.stretches[key] = SegmentReading(start=start, end=end, time=time)
        elif self.stretches[key].time.value != time.value:
            kept = self.stretches[key].time
            self.notes.append(
                f"{start.label}–{end.label}: {kept.value} ({kept.method}) and {time.value} "
                f"({time.method}); the first is kept"
            )

    def splits(self) -> tuple[SplitReading, ...]:
        return tuple(self.points[point] for point in sorted(self.points, key=lambda p: p.order))

    def segments(self) -> tuple[SegmentReading, ...]:
        keys = sorted(self.stretches, key=lambda key: (key[0].order, key[1].order))
        return tuple(self.stretches[key] for key in keys)


def _decimals(value: Decimal) -> int:
    exponent = value.as_tuple().exponent
    return -exponent if isinstance(exponent, int) else 0


def _agree(a: Decimal, b: Decimal) -> bool:
    """Whether two printings of a time agree: the finer one, cut or rounded to the decimals of
    the coarser, is the coarser (51.07 and 51.1)."""
    coarse, fine = sorted((a, b), key=_decimals)
    unit = Decimal(1).scaleb(-_decimals(coarse))
    return coarse in (fine.quantize(unit, ROUND_DOWN), fine.quantize(unit, ROUND_HALF_UP))


def _reading_order(view: DocumentView) -> tuple[list[Line], dict[int, list[Word]]]:
    """The pages' lines, left column then right, and each page's running header."""
    lines: list[Line] = []
    headers: dict[int, list[Word]] = {}
    for page in view.pages:
        middle = page.width / 2
        headers[page.number] = sorted(
            (word for word in page.words if word.top < HEADER_BAND), key=lambda word: word.x0
        )
        body = [word for word in page.words if word.top >= HEADER_BAND]
        lines.extend(group_lines([w for w in body if w.xc < middle], page.number))
        lines.extend(group_lines([w for w in body if w.xc >= middle], page.number))
    return lines, headers


def _is_title(line: Line) -> bool:
    """Results and sections are headed in 12-point bold, after any ✗."""
    words = [word for word in line.words if word.text.strip(MARKER)]
    return bool(words) and words[0].bold and words[0].size >= 11


def _ends_block(line: Line) -> bool:
    """Whether ``line`` starts the next result, section or summary of the event."""
    if not _is_title(line):
        return False
    return bool(
        TITLE.fullmatch(line.text)
        or EVENT.fullmatch(line.text)
        or re.match(r"(?:WO)?MEN[\u02bc\u2019']S ", line.text)
    )


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()


def _bare(text: str) -> str:
    return re.sub(r"\W", "", _fold(text))


def _wind(text: str) -> Decimal:
    return parse.signed_decimal(text.replace(MINUS, "-"))


def _row_columns(view: DocumentView, intro: list[Line]) -> list[Column] | None:
    """The extra columns of the results, as the line under the title names them, or ``None``
    when no line does (older editions)."""
    for line in intro:
        words = list(line.words)
        if words[0].text.startswith("("):  # the wind: (1.3), (Wind: against)
            closing = next(i for i, word in enumerate(words) if word.text.endswith(")"))
            words = words[closing + 1 :]
        columns = _columns(words, table=False, margin=None)
        if columns:
            return columns
    return None


def _columns(words: list[Word], *, table: bool, margin: float | None) -> list[Column] | None:
    """The columns a header names, or ``None`` if ``words`` are not a header. ``margin`` is
    the left edge of the header's text column, from which a table's columns are placed."""
    columns: list[Column] = []
    last: Word | None = None
    for word in words:
        text = word.text
        distance = re.fullmatch(r"(\d+)m", text)
        anchor = None if margin is None else word.x0 - margin
        if text in ("Manual", "Splits") and table and not columns:
            continue  # "Manual Splits": timed by hand
        if (distance or text == "lap") and last is not None:
            if margin is not None and not any(column.kind is Kind.LAST for column in columns):
                anchor = last.x0 - margin  # the first value is set under "Last"
            length = Decimal(distance[1]) if distance else LAP
            columns.append(Column(Kind.LAST, length, anchor))
        elif distance:
            columns.append(Column(Kind.SPLIT, Decimal(distance[1]), anchor))
        elif text == "Last":
            last = word
        elif text == "Halves":
            columns.append(Column(Kind.HALVES, None, anchor))
        elif text == "Reactions" and not table:
            columns.append(Column(Kind.REACTION, None, anchor))
        elif text == "Official" and not table:
            columns.append(Column(Kind.OFFICIAL, None, anchor))
        elif text in ("Electrics", "Electric", "Actual", "Adjusted"):
            columns.append(Column(Kind.UNREAD, None, anchor))
        elif text == "Differential" and table:
            columns.append(Column(Kind.DIFFERENTIAL, None, anchor))
        else:
            return None
    return columns or None


def _rows(
    view: DocumentView, lines: list[Line], columns: list[Column] | None
) -> tuple[list[_Row], int]:
    """The result rows at the start of ``lines``, and how many lines they take."""
    rows: list[_Row] = []
    used = 0
    for line in lines:
        found = view.match(line, ROW, "result-row", full=True)
        if found is not None:
            rows.append(_row(view, found, columns))
        elif rows and rows[-1].found["result"] == "DQ" and rows[-1].line_time is None:
            more = view.match(line, CONTINUATION, "annulled", full=True)
            if more is None:
                break
            row = rows[-1]
            row.line_time = more.read("line", parse.seconds)
            values, _ = _values(view, line, more.found.start("tail"), columns, "annulled")
            row.values += values
        else:
            break
        used += 1
    return rows, used


def _row(view: DocumentView, found: LineMatch, columns: list[Column] | None) -> _Row:
    line = found.line
    start = found.found.start("tail")
    row = _Row(found=found, values=[])
    if found["result"] == "DQ":
        remarks = []
        for token in TOKEN.finditer(line.text, start):
            words = line.words_in(token.start(), token.end())
            rule = RULE.fullmatch(token.group())
            at_line = re.fullmatch(rf"\(({TIME})\)", token.group())
            if rule:
                text = rule["rule"]
                remarks.append(view.read(line.page, words, str, "result-row.rule", text))
            elif at_line:
                text = at_line[1]
                row.line_time = view.read(line.page, words, parse.seconds, "result-row.line", text)
            else:
                raise view.error(f"result-row: cannot read {token.group()!r}", line.page)
        row.remarks = tuple(remarks)
        return row
    values, extras = _values(view, line, start, columns, "result-row")
    row.values = values
    for column, words, text in extras:
        if column.kind is Kind.REACTION:
            row.reaction = view.read(
                line.page, words, parse.signed_decimal, "result-row.reaction", text
            )
        elif column.kind is Kind.OFFICIAL:
            official = re.fullmatch(rf"({TIME})({RECORD})?", text)
            assert official is not None
            row.official = view.read(
                line.page, words, parse.result, "result-row.official", official[1]
            )
            if official[2]:
                row.records = (
                    view.read(line.page, words, str, "result-row.official-record", official[2]),
                )
    return row


def _values(
    view: DocumentView,
    line: Line,
    start: int,
    columns: list[Column] | None,
    rule: str,
    margin: float | None = None,
) -> tuple[list[_Time], list[tuple[Column, tuple[Word, ...], str]]]:
    """The times in the columns of ``line`` from character ``start``, and the other values
    (reaction times, official times) for the caller to read. In a table (``margin`` given:
    the left edge of the row's text column) each value is in the column it is set under; in a
    results row, in the order of its columns, the last of which a row may leave out."""
    tokens = list(TOKEN.finditer(line.text, start))
    times: list[_Time] = []
    extras: list[tuple[Column, tuple[Word, ...], str]] = []
    if columns is not None and margin is not None:
        cells = _by_position(view, line, tokens, columns, rule, margin)
    else:
        cells = _in_order(view, line, tokens, columns, rule)
    for column, token in cells:
        text = token.group().strip("()")
        offset = token.start() + token.group().index(text)
        words = line.words_in(offset, offset + len(text))
        if column.kind is Kind.HALVES:
            first, second = text.split("/")
            for part, at, half in (
                (Part.FIRST_HALF, offset, first),
                (Part.SECOND_HALF, offset + len(first) + 1, second),
            ):
                method = f"{rule}.{part.value.split('-')[0]}"
                value = view.read(
                    line.page, line.words_in(at, at + len(half)), parse.seconds, method, half
                )
                times.append(_Time(part, None, value))
        elif column.kind in (Kind.SPLIT, Kind.LAST):
            part = Part.SPLIT if column.kind is Kind.SPLIT else Part.LAST
            method = f"{rule}.{column.method}"
            value = view.read(line.page, words, parse.seconds, method, text)
            times.append(_Time(part, column.distance, value))
        elif column.kind in (Kind.REACTION, Kind.OFFICIAL):
            extras.append((column, words, text))
    return times, extras


def _by_position(
    view: DocumentView,
    line: Line,
    tokens: list[re.Match[str]],
    columns: list[Column],
    rule: str,
    margin: float,
) -> list[tuple[Column, re.Match[str]]]:
    """Each value with the column it is set under: the one whose label is nearest its left
    edge. A value under no label, or under one already taken, or not the kind its column
    holds, is an error."""
    cells: list[tuple[Column, re.Match[str]]] = []
    for token in tokens:
        if token.group() in EMPTY:
            continue  # an empty cell
        if token.group() == "behind" and cells and cells[-1][0].kind is Kind.DIFFERENTIAL:
            continue  # 0.28 behind
        left = line.words_in(token.start(), token.end())[0].x0 - margin
        column = min(columns, key=lambda column: abs((column.anchor or 0) - left))
        taken = any(column is other for other, _ in cells)
        if abs((column.anchor or 0) - left) > ANCHOR_TOLERANCE or taken:
            raise view.error(f"{rule}: {token.group()!r} is under no column", line.page)
        if not column.fits(token.group()):
            raise view.error(f"{rule}: {token.group()!r} under {column.method}", line.page)
        cells.append((column, token))
    return cells


def _in_order(
    view: DocumentView,
    line: Line,
    tokens: list[re.Match[str]],
    columns: list[Column] | None,
    rule: str,
) -> list[tuple[Column, re.Match[str]]]:
    """Each value with the next of ``columns`` it fits: a row may leave a column out. With no
    line naming the columns (older editions), the columns are told apart by their shape."""
    cells: list[tuple[Column, re.Match[str]]] = []
    expected = iter(columns if columns is not None else SHAPES)
    for token in tokens:
        if token.group() in EMPTY and columns is not None:
            next(expected, None)  # an empty cell
            continue
        column = next((column for column in expected if column.fits(token.group())), None)
        if column is None:
            raise view.error(f"{rule}: cannot read {token.group()!r} in {line.text!r}", line.page)
        cells.append((column, token))
    return cells


def _despaced(
    view: DocumentView, words: list[Word], pattern: re.Pattern[str]
) -> tuple[re.Match[str] | None, list[Word]]:
    """``pattern`` in words set as spaced capitals (``M E N ’ S``), run together."""
    text, owners = "", []
    for index, word in enumerate(words):
        text += word.text
        owners.extend([index] * len(word.text))
    return (pattern.search(text), [words[i] for i in owners]) if text else (None, [])


def _read_spaced[T](
    view: DocumentView,
    page: int,
    found: re.Match[str],
    owners: list[Word],
    group: str | int,
    parse_value: Callable[[str], T],
    method: str,
) -> Sourced[T]:
    """Read a group of a match in spaced capitals: the letters it matched, from the words
    they are printed in."""
    words: list[Word] = []
    for word in owners[found.start(group) : found.end(group)]:
        if not words or words[-1] is not word:
            words.append(word)
    return view.read(page, words, parse_value, method, found[group])


def _header(
    view: DocumentView, page: int, header: list[Word]
) -> tuple[Sourced[Sex], Sourced[Round] | None]:
    """The sex, and the round when the page is in a section of finals, from the running
    header."""
    found, owners = _despaced(view, header, SEX_AND_EVENTS)
    if found is None:
        raise view.error("no running header naming men's or women's events", page)
    sex = _read_spaced(view, page, found, owners, "sex", parse.sex, "header.sex")
    finals, finals_owners = _despaced(view, header, FINALS)
    rounds = (
        _read_spaced(view, page, finals, finals_owners, 0, parse.round_name, "header.round")
        if finals
        else None
    )
    return sex, rounds


def _event(
    view: DocumentView, before: list[Line], title: LineMatch, headers: dict[int, list[Word]]
) -> Sourced[DisciplineId]:
    """The event: in the title, else in the nearest heading before it that names one (a
    section's heading, a title naming its event, or a page's ``continued`` line), else in the
    running header of the first page read, when it carries a single event: with no heading in
    between, the title is in the section that page is in."""
    if title["event"]:
        return title.read("event", parse.discipline)
    for line in reversed(before):
        if _is_title(line):
            earlier = view.match(line, TITLE, "title", full=True)
            if earlier is not None and earlier["event"]:
                return earlier.read("event", parse.discipline)
            heading = view.match(line, EVENT, "heading", full=True)
            if heading is not None:
                return heading.read("event", parse.discipline)
        continued = view.match(line, CONTINUED, "continued", full=True)
        if continued is not None:
            return continued.read("event", parse.discipline)
    page = before[0].page if before else title.line.page
    found, owners = _despaced(view, headers[page], SEX_AND_EVENTS)
    if found is None or len(re.findall(EVENT_CODE, found["events"] or "")) != 1:
        raise view.error("cannot tell which event this page reports", title.line.page)
    return _read_spaced(view, page, found, owners, "events", parse.discipline, "header.event")


def _date(view: DocumentView, title: LineMatch, day: LineMatch | None) -> Sourced[date]:
    """The day of the race: in the title (``Seoul, 29 Sep 1988``), or on the line below it
    (``Final (Aug 20)``) with the year from the title."""
    if title["day"]:
        words = [*title.words("day"), *title.words("month"), *title.words("year")]
        return view.read(title.line.page, words, parse.day_month_year, "title.date")
    if day is None:
        raise view.error(f"no date for {title.line.text!r}", title.line.page)
    month, number = (day["day"] or "").split()
    text = f"{number} {month} {title['year']}"
    return day.read("day", lambda _: parse.day_month_year(text))


def _splits_table(view: DocumentView, lines: list[Line]) -> list[tuple[str, list[_Time]]]:
    """The table of splits after the results, by the names it prints."""
    for index, line in enumerate(lines):
        if not line.words[0].font.startswith("Helvetica"):
            continue
        columns = _columns(list(line.words), table=True, margin=_margin(view, line))
        if columns is None:
            continue
        table = []
        for row_line in lines[index + 1 :]:
            row = TABLE_ROW.fullmatch(row_line.text)
            if row is None or not row_line.words[0].font.startswith("Helvetica"):
                break
            start, margin = row.start("values"), _margin(view, row_line)
            values, _ = _values(view, row_line, start, columns, "splits-table", margin)
            table.append((row["name"].strip(), values))
        return table
    return []


def _margin(view: DocumentView, line: Line) -> float:
    """The left edge of the text column ``line`` is in."""
    page = view.layer.page(line.page)
    left = line.words[0].xc < page.width / 2
    return min(
        word.x0
        for word in page.words
        if word.top >= HEADER_BAND and (word.xc < page.width / 2) == left
    )


def _split_name(text: str, families: list[str]) -> PersonName:
    """Given and family names from a name printed in full: the family name as the table of
    splits prints it, else everything after the first name and any initials (``P. T. Usha``)."""
    for printed in families:
        family = _without_initial(printed)
        if _fold(text).endswith(" " + _fold(family)):
            return PersonName(given=text[: -len(family) - 1], family=text[-len(family) :])
        if _fold(text).startswith(_fold(family) + " "):  # printed family name first: Qu Yunxia
            return PersonName(given=text[len(family) + 1 :], family=text[: len(family)])
    tokens = text.split()
    if len(tokens) < 2:
        raise ValueError(f"expected a given and a family name in {text!r}")
    given = 1
    while given < len(tokens) - 1 and re.fullmatch(r"[A-Z]\.", tokens[given]):
        given += 1
    return PersonName(given=" ".join(tokens[:given]), family=" ".join(tokens[given:]))


def _without_initial(printed: str) -> str:
    """A family name as a table prints it, less an initial telling namesakes apart
    (``K Borlée``)."""
    return printed.split(" ", 1)[1] if re.match(r"[A-Z] ", printed) else printed


def _is(printed: str, name: PersonName) -> bool:
    """Whether a table's name for an athlete (``Van Niekerk``, ``K Borlée``) is ``name``.
    Spaces and punctuation do not count: the text layer splits some names at an accented
    letter (``Puic ă``), and tables run some together (``Chefdhôtel``)."""
    if _bare(_without_initial(printed)) != _bare(name.family):
        return False
    return not re.match(r"[A-Z] ", printed) or name.given.startswith(printed[0])


def _attribute(
    table: list[tuple[str, list[_Time]]], names: list[PersonName]
) -> tuple[dict[int, int], list[str]]:
    """Which result each row of the table of splits is: the one whose family name it prints;
    else, the table following the results' order, the one result between its neighbours' that
    no row names, if their names are alike (a misprint: ``Kukkuaho`` for Kukkoaho). Rows that
    are neither are left out. Both are noted."""
    owners: dict[int, int] = {}
    for row, (printed, _) in enumerate(table):
        for index, name in enumerate(names):
            if index not in owners.values() and _is(printed, name):
                owners[row] = index
                break
    notes = []
    for row, (printed, _) in enumerate(table):
        if row in owners:
            continue
        above = max((owners[other] for other in owners if other < row), default=-1)
        below = min((owners[other] for other in owners if other > row), default=len(names))
        free = [index for index in range(above + 1, below) if index not in owners.values()]
        if len(free) == 1 and _alike(printed, names[free[0]]):
            owners[row] = free[0]
            name = names[free[0]]
            notes.append(f"the table of splits prints {printed!r} for {name.given} {name.family}")
        else:
            notes.append(f"the table of splits names {printed!r}, whom the results do not")
    return owners, notes


def _alike(printed: str, name: PersonName) -> bool:
    table, family = _bare(_without_initial(printed)), _bare(name.family)
    return table in family or family in table or SequenceMatcher(None, table, family).ratio() > 0.75


def _from_report(
    view: DocumentView, report: list[Line], family: str
) -> tuple[Sourced[int] | None, list[_Time]]:
    """The lane the report of the race gives an athlete (``Koch (lane 2)``), and the splits it
    gives in the rest of that line."""
    pattern = re.compile(REPORTED_LANE.format(family=re.escape(family)))
    for line in report:
        found = view.match(line, pattern, "report")
        if found is None:
            continue
        told: list[_Time] = []
        rest = found.found.end()
        for sentence in REPORTED_SPLITS:
            for said in sentence.finditer(line.text, rest):
                words = line.words_in(said.start("time"), said.end("time"))
                time = view.read(line.page, words, parse.seconds, "report.split", said["time"])
                told.append(_Time(Part.SPLIT, Decimal(said["distance"]), time))
        return found.read("lane", int), told
    return None, []
