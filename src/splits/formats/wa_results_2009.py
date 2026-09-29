"""World Athletics results documents of 2009 (``AT-100-M-H----.RS6.pdf``; a final's is
``AT-100-M-F--1--.RS1.pdf``), timed by SEIKO and laid out by EPSON.

One document per round lists every race in it. The event and the round head the first page,
on two lines (``100 Metres MEN``, ``1st Round ROUND RESULTS``; later pages repeat them as
``100 Metres Men - 1st Round``). Each race is a section that starts with its date, then its
start time and conditions, then, in a round of several races, its heat number::

    15 August 2009               TIME   TEMPERATURE HUMIDITY WIND
                           Start 11:39     23° C      44 %   -0.4 m/s
    Heat 1
    RANK BIB NAME                  NAT YEAR LANE RESULT   REACTION TIME
    1    660 Michael FRATER        JAM  82    6  10.30 Q  0.144

The rows are those of later World Athletics results (``wa_results``), with the birth year
where those print the date of birth. The first round is ``1st Round``, the second (a quarter
final) ``2nd Round``.
"""

import re
from datetime import datetime

from splits.formats import parse
from splits.formats.base import (
    DocumentKind,
    DocumentReading,
    Format,
    HeadingReading,
    ReadContext,
)
from splits.formats.common import read_first, wind_before_unit
from splits.formats.wa_results import ATHLETE, HEAT, read_entry
from splits.model import Sourced
from splits.model.ids import format_id
from splits.pdf.layout import DocumentView, Line

EVENT = re.compile(r"^(?P<discipline>\d+ Metres(?: Hurdles)?) (?P<sex>MEN|WOMEN)$")
ROUND = re.compile(
    r"^(?P<round>\d(?:st|nd) Round|Quarter-Final|Semi-Final|Final) (?:ROUND )?RESULTS$"
)
DAY = re.compile(r"^(?P<date>\d{1,2} [A-Z][a-z]+ \d{4}) TIME TEMPERATURE\b")
START = re.compile(r"^Start (?P<time>\d{1,2}:\d{2})\b")
TEMPERATURE = re.compile(r"(?P<temperature>-?\d+)° C\b")
HUMIDITY = re.compile(r"(?P<humidity>\d+) %")
TABLE = re.compile(r"^RANK BIB NAME NAT YEAR LANE RESULT REACTION TIME$")
ISSUED = re.compile(r"Issued [A-Za-z]+, (?P<issued>\d{1,2} [A-Za-z]+ \d{4} at \d{1,2}:\d{2})")
TIMING_BY = re.compile(r"Timing and Measurement by (?P<timing>[A-Z][A-Za-z]+)")


def _issued(text: str) -> datetime:
    day, _, clock = text.partition(" at ")
    return datetime.combine(parse.day_month_year(day), parse.clock(clock))


class WaResultsOf2009(Format):
    kind = DocumentKind.RESULTS
    id = format_id("wa-results-2009")
    version = "1.0.0"
    name = "World Athletics results, 2009"
    publisher = "World Athletics"
    description = (
        "Official results of each round at the 2009 World Championships: place, lane, result, "
        "reaction time and qualification for every athlete in every race of the round. Timing "
        "by SEIKO, data processing by EPSON."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        lines = [line for page in view.pages for line in view.lines(page.number)]
        event = view.find(lines, EVENT, "event")
        round_ = view.find(lines, ROUND, "round")
        if event is None or round_ is None:
            raise view.error("no event and round such as '100 Metres MEN', 'Final RESULTS'", 1)
        section = self._section(view, lines, context.spec.race.heat)
        day = view.match(section[0], DAY, "day")
        start = view.find(section[:3], START, "start")
        if day is None or start is None:
            raise view.error("no date and start time at the head of the race", section[0].page)
        heat = view.find(section[:4], HEAT, "heat-line")
        race_date = day.read("date", parse.day_month_year)
        page = start.line.page
        if view.find(section, TABLE, "table") is None:
            raise view.error("no table heading 'RANK BIB NAME NAT YEAR LANE RESULT ...'", page)
        footer = [line for line in lines if ISSUED.search(line.text) or TIMING_BY.search(line.text)]
        entries = [
            read_entry(view, row, race_date.value, in_lanes=True)
            for line in section
            if (row := view.match(line, ATHLETE, "athlete-row", full=True)) is not None
        ]
        if not entries:
            raise view.error(f"no athlete rows for {context.spec.race}", page)
        return DocumentReading(
            document=view.document,
            format=self.id,
            format_version=self.version,
            pages=len(view.pages),
            title=Sourced[str](
                value=f"{event.found[0]} {round_['round']}", source=event.span(), method="event"
            ),
            heading=HeadingReading(
                discipline=event.read("discipline", parse.discipline),
                sex=event.read("sex", parse.sex),
                round=round_.read("round", parse.round_name),
                heat=heat.read("heat", int) if heat else None,
            ),
            date=race_date,
            start_time=start.read("time", parse.clock),
            wind=wind_before_unit(view, page, within=(start.line.top - 4, start.line.bottom + 4)),
            temperature=read_first(
                view, [start.line], TEMPERATURE, "weather", "temperature", parse.signed_decimal
            ),
            humidity=read_first(
                view, [start.line], HUMIDITY, "weather", "humidity", parse.signed_decimal
            ),
            issued=read_first(view, footer, ISSUED, "footer", "issued", _issued),
            timing_by=read_first(view, footer, TIMING_BY, "footer", "timing", str),
            entries=tuple(entries),
        )

    @staticmethod
    def _section(view: DocumentView, lines: list[Line], heat: int | None) -> list[Line]:
        """The lines of one race: from its date line to the next race's."""
        starts = [i for i, line in enumerate(lines) if DAY.search(line.text)]
        if not starts:
            raise view.error("no race date line ('15 August 2009 TIME TEMPERATURE ...')")
        sections = [lines[a:b] for a, b in zip(starts, [*starts[1:], len(lines)], strict=True)]
        if heat is None:
            if len(sections) != 1:
                raise view.error(f"{len(sections)} races in the document, but no heat declared")
            return sections[0]
        for section in sections:
            found = view.find(section[:4], HEAT, "heat-line")
            if found is not None and found["heat"] == str(heat):
                return section
        raise view.error(f"no section for heat {heat}")
