"""Flash Results' web pages of a race: its splits and its results (the Prefontaine Classic, 2017
to 2019).

Flash Results timed the Prefontaine Classic until 2019 and published each race as web pages,
not PDFs: a *splits* page (``006-1-01.htm``) and a *results* page (``006-1_compiled.htm``). Both
open with the meeting, its venue and dates, the event with the day and time it was scheduled
for, the records at stake, and the results::

    Prefontaine Classic
    Historic Hayward Field - Eugene (USA) | May 25-26, 2018
    Women 800 M USATF HP (Finals)
    Friday 7:35 PM
    Results: Women 800 M USATF HP (Finals)
    Pl  Ln  Athlete          Affiliation    Time     400m                800m
    1   7   Natoya GOULE     30 Mar 1991    Jamaica  2:00.84  1:00.36 [1:00.36]  2:00.84 [1:00.48]
    DNF 8   McKayla FRICKER  19 Apr 1992    United States  -  59.17 [59.17]

The splits page times every athlete at each lap, cumulatively, the lap's time in brackets, and
prints the actual start time at its foot (``Actual Start Time: 19:35:05``). The results page
gives the places and record marks (``PB``, ``FR`` for the stadium's record, ``DL``), without
lanes or splits; its ``Sec (pl)`` column, the section and the place in it, is not read::

    Place  Athlete         Affiliation   Time
    1      Caster SEMENYA  7 Jan 1991    South Africa  1:55.70  FR MR
           Chrishuna WILLIAMS  31 Mar 1993  United States  DNF

The pages are read as the grid of their tables' cells (:mod:`splits.pdf.webpage`), each value
from its column under the table's heading. Names are printed given name first, the family name
in capitals, and countries in full (``Great Britain & NI``); the birth date, in a column of its
own without a heading, is missing in 2017. ``Ln`` is a lane in races run in lanes (to 800 m),
and otherwise a place on the start line, which is not read. The day is the one of the meeting's
dates with the weekday printed (the ``Friday`` of ``May 25-26, 2018``).

Splits are labelled in metres, those at the laps of a mile or two miles rounded down to the
metre (``409m`` is the 409.344 m point, three laps from the finish of a mile), and the finish
by the race's distance (``800m``) or name (``Mile``, ``2 Mile``). A steeplechase's labels are
the flat track's (``200m``, ``600m`` ...), not where its shorter laps end, so steeplechases are
not read. The weather under the results is not read either: it is the weather when the page was
last updated, often the next morning.
"""

import re
from collections.abc import Callable, Sequence
from datetime import date, time, timedelta
from decimal import Decimal

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
from splits.formats.common import RECORD_TAG
from splits.formats.omega_grid import LAP
from splits.model import BirthDate, DisciplineKind, PersonName, Sourced, TimingPoint
from splits.model.ids import format_id
from splits.pdf.layout import DocumentView, Line, LineMatch
from splits.pdf.textlayer import Word
from splits.pdf.webpage import COLUMN

HEADING = re.compile(
    r"^Results: (?P<race>(?P<sex>Men|Women) "
    r"(?P<discipline>\d+ M(?:eter)?(?: Hurdles| Steeplechase)?|[12] Mile)(?: Run)?"
    r"(?: (?P<name>[A-Z][A-Za-z']+(?: [A-Z][A-Za-z']+)*))? \((?P<round>Finals?)\))$"
)
"""The heading of the results table: ``Results: Women 800 M USATF HP (Finals)``. A race may be
named for its sponsor or field (``Men 1 Mile Run Bowerman``, ``Men 1 Mile Run Int'l``)."""
DATES = re.compile(
    r"(?P<dates>(?P<month>[A-Z][a-z]+) (?P<first>\d{1,2})(?:-(?P<last>\d{1,2}))?, (?P<year>\d{4}))$"
)
"""The meeting's dates, after its venue: ``May 25-26, 2018``, ``June 30, 2019``."""
SCHEDULED = re.compile(
    r"^(?P<weekday>Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) "
    r"(?P<time>\d{1,2}:\d{2}(?: [AP]M)?)$"
)
"""When the race was scheduled for, in the event's table: ``Friday 7:35 PM``, ``Sunday 13:47``."""
STARTED = re.compile(r"\bActual Start Time: (?P<time>\d{1,2}:\d{2}:\d{2})\b")
LABEL = re.compile(r"(?P<distance>\d+)m|(?P<miles>[12] )?Mile")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
IN_LANES = Decimal(800)
"""Races up to this distance start in lanes."""
STATUSES = frozenset({"DNF", "DNS", "DQ", "DSQ"})


def _day(text: str) -> date:
    """The day of ``Friday May 25-26, 2018`` (a weekday, then the meeting's dates)."""
    weekday, _, dates = text.partition(" ")
    found = DATES.fullmatch(dates)
    if weekday not in WEEKDAYS or found is None:
        raise ValueError(f"not a weekday and dates: {text!r}")
    first = parse.day_month_year(f"{found['first']} {found['month']} {found['year']}")
    days = int(found["last"] or found["first"]) - first.day + 1
    matching = [
        first + timedelta(days=offset)
        for offset in range(days)
        if (first + timedelta(days=offset)).weekday() == WEEKDAYS.index(weekday)
    ]
    if len(matching) != 1:
        raise ValueError(f"no {weekday} among {dates}")
    return matching[0]


def _clock(text: str) -> time:
    """A time of day to the second: ``19:35:05``."""
    hours, minutes, seconds = (int(part) for part in text.split(":"))
    return time(hours, minutes, seconds)


def _cells(line: Line) -> dict[int, tuple[Word, ...]]:
    """A line's words by the table cell they were read from."""
    cells: dict[int, list[Word]] = {}
    for word in line.words:
        cells.setdefault(int(word.x0 // COLUMN), []).append(word)
    return {column: tuple(words) for column, words in cells.items()}


def _text(words: Sequence[Word]) -> str:
    return " ".join(word.text for word in words)


class _Page:
    """What both pages print: the heading, the day, and the results table's rows by column."""

    def __init__(self, view: DocumentView, first: str) -> None:
        self.view = view
        self.lines = view.lines(1)
        heading = next(
            (found for line in self.lines if (found := view.match(line, HEADING, "heading"))),
            None,
        )
        if heading is None:
            raise view.error("no results heading such as 'Results: Women 800 M (Final)'", 1)
        self.heading: LineMatch = heading
        at = next(
            (
                i
                for i, line in enumerate(self.lines)
                if line.words[0].font == "th" and line.words[0].text == first
            ),
            None,
        )
        if at is None:
            raise view.error(f"no results table (a heading row starting {first!r})", 1)
        self.columns = {_text(words): column for column, words in _cells(self.lines[at]).items()}
        self.rows: list[Line] = []
        for line in self.lines[at + 1 :]:
            if any(word.font != "td" for word in line.words):
                break
            self.rows.append(line)
        if not self.rows:
            raise view.error("no athlete rows", 1)

    def column(self, name: str) -> int:
        if name not in self.columns:
            raise self.view.error(f"the results table has no {name!r} column", 1)
        return self.columns[name]

    def date(self) -> Sourced[date]:
        """The race's day: the weekday it was scheduled for, among the meeting's dates."""
        dates = next(
            (found for line in self.lines[:5] if (found := self.view.match(line, DATES, "dates"))),
            None,
        )
        scheduled = next(
            (
                found
                for line in self.lines
                if line.words[0].font == "td"
                and (found := self.view.match(_first_cell(line), SCHEDULED, "scheduled"))
            ),
            None,
        )
        if dates is None or scheduled is None:
            raise self.view.error("no meeting dates, or no day the race was scheduled for", 1)
        words = [*scheduled.words("weekday"), *dates.words("dates")]
        text = f"{scheduled['weekday']} {dates['dates']}"
        return self.view.read(1, words, _day, "date", text)

    def heading_reading(self) -> HeadingReading:
        return HeadingReading(
            discipline=self.heading.read("discipline", parse.discipline),
            sex=self.heading.read("sex", parse.sex),
            round=self.heading.read("round", parse.round_name),
            heat=None,
        )


def _first_cell(line: Line) -> Line:
    cells = _cells(line)
    return Line(line.page, cells[min(cells)])


def _cell[T](
    view: DocumentView,
    cells: dict[int, tuple[Word, ...]],
    column: int,
    parse_: Callable[[str], T],
    method: str,
) -> Sourced[T] | None:
    words = cells.get(column)
    return view.read(1, words, parse_, method) if words else None


def _person(
    view: DocumentView, page: _Page, cells: dict[int, tuple[Word, ...]], rule: str
) -> tuple[Sourced[PersonName], Sourced[BirthDate] | None, Sourced[str]]:
    """The athlete's name, birth date (in the column after the name's, if printed) and country."""
    athlete = page.column("Athlete")
    name = _cell(
        view,
        cells,
        athlete,
        lambda text: parse.person_name(text, family_first=False),
        f"{rule}.name",
    )
    country = _cell(view, cells, page.column("Affiliation"), parse.country_name, f"{rule}.country")
    if name is None or country is None:
        raise view.error(f"{rule}: a row without a name or a country", 1)
    born = _cell(view, cells, athlete + 1, parse.full_birth_date, f"{rule}.birth")
    return name, born, country


def _point(text: str, context: ReadContext) -> TimingPoint:
    """The point a label names. A label at the race's distance, or naming it (``Mile``), is the
    finish; a mile's or two miles' laps are printed rounded down to the metre."""
    discipline = context.discipline
    if discipline.kind is DisciplineKind.STEEPLECHASE:
        raise ValueError(
            f"a steeplechase labelled {text!r}: its labels are the flat track's, not where its "
            "laps end"
        )
    found = LABEL.fullmatch(text)
    if found is None:
        raise ValueError(f"not a timing point label: {text!r}")
    finish = discipline.finish()
    if found["distance"] is None:
        named = "2-miles" if found["miles"] == "2 " else "mile"
        if discipline.id != named:
            raise ValueError(f"{text!r} is not the finish of a {discipline.short_name}")
        return finish
    distance = Decimal(found["distance"])
    if distance == finish.distance:
        return finish
    lap = LAP[context.spec.setting or context.competition.setting]
    at_lap = finish.distance - lap * ((finish.distance - distance) / lap).to_integral_value()
    return TimingPoint.at(at_lap if int(at_lap) == distance else distance)


def _split_cell(
    view: DocumentView, words: tuple[Word, ...], point: TimingPoint, previous: TimingPoint
) -> tuple[SplitReading, SegmentReading | None]:
    """A split cell: the time at the point, and the lap's time in brackets."""
    texts = [word.text for word in words]
    if len(words) not in (1, 2) or (len(words) == 2 and not re.fullmatch(r"\[.+\]", texts[1])):
        raise view.error(f"not a split and its lap time: {' '.join(texts)!r}", 1)
    split = SplitReading(
        point=point, time=view.read(1, [words[0]], parse.seconds, "cumulative.time")
    )
    if len(words) == 1:
        return split, None
    segment = SegmentReading(
        start=previous,
        end=point,
        time=view.read(1, [words[1]], lambda text: parse.seconds(text.strip("[]")), "segment.time"),
    )
    return split, segment


class FlashSplits(Format):
    kind = DocumentKind.ANALYSIS
    id = format_id("flash-splits")
    version = "1.0.0"
    media_type = "text/html"
    name = "Flash Results splits (web page)"
    publisher = "Flash Results"
    description = (
        "A race's results with every athlete's time at each lap, as Flash Results published "
        "them on the web: place, lane, birth date, country and result, cumulative splits and "
        "lap times."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        page = _Page(view, "Pl")
        time_column = page.column("Time")
        labels = sorted(
            (column, name) for name, column in page.columns.items() if column > time_column
        )
        try:
            points = [(column, _point(name, context)) for column, name in labels]
        except ValueError as error:
            raise view.error(str(error), 1) from error
        if not points or points[-1][1] != context.discipline.finish():
            raise view.error("the last split column is not the finish", 1)
        in_lanes = context.discipline.distance <= IN_LANES
        entries = [self._entry(view, page, row, points, in_lanes) for row in page.rows]
        started = next(
            (found for line in page.lines if (found := view.match(line, STARTED, "footer"))),
            None,
        )
        return DocumentReading(
            document=view.document,
            format=self.id,
            format_version=self.version,
            pages=len(view.pages),
            title=page.heading.read("race", str),
            heading=page.heading_reading(),
            date=page.date(),
            start_time=started.read("time", _clock) if started else None,
            entries=tuple(entries),
        )

    def _entry(
        self,
        view: DocumentView,
        page: _Page,
        row: Line,
        points: list[tuple[int, TimingPoint]],
        in_lanes: bool,
    ) -> EntryReading:
        cells = _cells(row)
        name, born, country = _person(view, page, cells, "athlete-row")
        place_words = cells.get(page.column("Pl"), ())
        # an athlete who did not finish has the status for a place, and "-" for a time
        status = _text(place_words) in STATUSES
        result_words = place_words if status else cells.get(page.column("Time"), ())
        if not result_words:
            raise view.error(f"no result for {name.value}", 1)
        splits: list[SplitReading] = []
        segments: list[SegmentReading] = []
        previous, missed = TimingPoint.start(), False
        for column, point in points:
            words = cells.get(column)
            if not words:
                missed = True
            elif missed:
                raise view.error(f"{name.value}: a split after a point not timed", 1)
            else:
                split, segment = _split_cell(view, words, point, previous)
                splits.append(split)
                if segment is not None:
                    segments.append(segment)
            previous = point
        return EntryReading(
            row=view.span(1, row.words),
            name=name,
            country=country,
            birth_date=born,
            place=None
            if status
            else _cell(view, cells, page.column("Pl"), int, "athlete-row.place"),
            lane=_cell(view, cells, page.column("Ln"), int, "athlete-row.lane")
            if in_lanes
            else None,
            result=view.read(1, result_words, parse.result, "athlete-row.result"),
            splits=tuple(splits),
            segments=tuple(segments),
        )


class FlashResults(Format):
    kind = DocumentKind.RESULTS
    id = format_id("flash-results")
    version = "1.0.0"
    media_type = "text/html"
    name = "Flash Results results (web page)"
    publisher = "Flash Results"
    description = (
        "A race's results as Flash Results published them on the web: place, birth date, "
        "country, result and record marks."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        page = _Page(view, "Place")
        return DocumentReading(
            document=view.document,
            format=self.id,
            format_version=self.version,
            pages=len(view.pages),
            title=page.heading.read("race", str),
            heading=page.heading_reading(),
            date=page.date(),
            entries=tuple(self._entry(view, page, row) for row in page.rows),
        )

    def _entry(self, view: DocumentView, page: _Page, row: Line) -> EntryReading:
        cells = _cells(row)
        name, born, country = _person(view, page, cells, "results-row")
        result = _cell(view, cells, page.column("Time"), parse.result, "results-row.result")
        if result is None:
            raise view.error(f"no result for {name.value}", 1)
        headed = set(page.columns.values())
        marks = [
            word
            for column, words in sorted(cells.items())
            if column > page.column("Time") and column not in headed
            for word in words
        ]
        records = tuple(
            view.read(1, [word], str, "results-row.record")
            for word in marks
            if RECORD_TAG.fullmatch(word.text)
        )
        remarks = tuple(
            view.read(1, [word], str, "results-row.remark")
            for word in marks
            if not RECORD_TAG.fullmatch(word.text)
        )
        return EntryReading(
            row=view.span(1, row.words),
            name=name,
            country=country,
            birth_date=born,
            place=_cell(view, cells, page.column("Place"), int, "results-row.place"),
            result=result,
            records=records,
            remarks=remarks,
        )
