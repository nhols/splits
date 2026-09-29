"""World Athletics results documents (round results, files like ``AT-200-M-h----.RS6.pdf``).

One document per round lists every race in it. Each race is a section that starts with its
start time and, for a round of several races, its heat number::

      23 August 2023 12:15 START TIME  33° C  48 %     m/s
      Heat 1 7                                          0.0
      PLACE BIB NAME              COUNTRY DATE of BIRTH LANE RESULT REACTION
      7 2652 Gediminas TRUSKAUSKAS LTU  2 Jan 98       6    20.90 (.893)  0.147

The reader reads only the section of the race declared in the catalog. Results give each
athlete's lane and reaction time, qualification marks (Q, q), and the finishing time to the
thousandth where athletes are level in hundredths. The "intermediate times" under each race
repeat the leader's splits from the race analysis and are not transcribed.

The table's heading names its columns: races from the 1500 m up give each athlete's place in
the start order (``ORDER``), which is not a lane; Doha 2019 and London 2017 printed no bibs.
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
)
from splits.formats.common import read_first, read_tail, wind_before_unit
from splits.model import Sourced
from splits.model.ids import format_id
from splits.pdf.layout import DocumentView, Line, LineMatch

HEADING = re.compile(
    r"(?P<discipline>(?:\d{1,2},\d{3}|\d+)\s*(?:Metres|m)(?:\s+(?:Hurdles|Steeplechase))?)\s+"
    r"(?P<sex>Men|Women)\s+-\s+"
    r"(?P<round>Final|Semi-Finals?|Quarter-Finals?|Round\s+\d|Heats?|Repechage(?:\s+Round)?"
    r"|Preliminary\s+Round)\b"
)
START = re.compile(
    r"(?P<date>\d{1,2}\s+[A-Z][a-z]+\s+\d{4})\s+(?P<time>\d{1,2}:\d{2})\s+START TIME"
)
HEAT = re.compile(r"^(?:Heat|Final|Semi-Final)\s+(?P<heat>\d+)\b")
"""The race's number within its round: ``Heat 3``, or ``Final 2`` for a final run in races."""
TEMPERATURE = re.compile(r"(?P<temperature>-?\d+)°\s*C\b")
HUMIDITY = re.compile(r"(?P<humidity>\d+)\s*%")
TABLE = re.compile(r"^PLACE (?P<bib>BIB )?NAME .*?(?P<column>LANE|ORDER) RESULT\b")
"""The table's heading: whether rows print a bib, and whether the number before the result is
the athlete's lane or their place in the start order."""
_ROW = (
    r"(?:(?P<card>L|Y|YR|R) )?(?P<name>.+?) "
    r"(?P<country>[A-Z]{3}) (?:(?P<birth>(?:\d{1,2} [A-Z][a-z]{2} )?\d{2}) )?(?P<lane>\d{1,2}) "
    r"(?P<precise>(?P<result>\d{1,2}:\d{2}\.\d{2}|\d{1,3}\.\d{2}|DNF|DNS|DQ)"
    r"(?: \(\.\d{3}\))?)(?: (?P<tail>.+?))??(?: (?P<reaction>-?\d\.\d{3}))?(?: (?P<fn>F\d))?"
)
ATHLETE = re.compile(rf"(?:(?P<place>\d{{1,2}}) )?(?P<bib>\d{{1,5}}) {_ROW}")
ATHLETE_NO_BIB = re.compile(rf"(?:(?P<place>\d{{1,2}}) )?{_ROW}")
TIMING_BY = re.compile(r"Timing by (?P<timing>[A-Z][A-Za-z]+)")
REVISION = re.compile(r"\.RS\d\.\.(?P<revision>v\d+)")
# The tail (Q, PB, a rule) is optional and lazy (``??``), so a trailing reaction time is never
# taken for part of it.
ISSUED = re.compile(r"Issued at (?P<issued>\d{1,2}:\d{2} on [A-Za-z]+, \d{1,2} [A-Za-z]+ \d{4})")


def _issued(text: str) -> datetime:
    clock, _, day = text.partition(" on ")
    return datetime.combine(parse.day_month_year(day), parse.clock(clock))


class WaResults(Format):
    kind = DocumentKind.RESULTS
    id = format_id("wa-results")
    version = "1.1.0"
    name = "World Athletics results"
    publisher = "World Athletics"
    description = (
        "Official results of each round at World Athletics championships: place, lane (from "
        "the 1500 m, the start order, not kept), result (to the thousandth where needed), "
        "reaction time and qualification for every athlete in every race of the round. "
        "Timing by SEIKO."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        lines = [line for page in view.pages for line in view.lines(page.number)]
        heading = view.find(lines, HEADING, "heading")
        if heading is None:
            raise view.error("no race heading such as '400 Metres Men - Final'", 1)
        section = self._section(view, lines, context.spec.race.heat)
        start = view.match(section[0], START, "start")
        assert start is not None
        heat = view.find(section[:3], HEAT, "heat-line")
        race_date = start.read("date", parse.day_month_year)
        page = section[0].page
        header_band = (section[0].top - 8, section[0].bottom + 16)
        footer = [line for line in lines if TIMING_BY.search(line.text)]
        table = view.find(section, TABLE, "table")
        if table is None:
            raise view.error("no table heading such as 'PLACE BIB NAME ... LANE RESULT'", page)
        athlete = ATHLETE if table["bib"] else ATHLETE_NO_BIB
        in_lanes = table["column"] == "LANE"

        entries = [
            read_entry(view, row, race_date.value, in_lanes)
            for line in section
            if (row := view.match(line, athlete, "athlete-row", full=True)) is not None
        ]
        if not entries:
            raise view.error(f"no athlete rows for {context.spec.race}", page)
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
            wind=wind_before_unit(view, page, within=header_band),
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

    @staticmethod
    def _section(view: DocumentView, lines: list[Line], heat: int | None) -> list[Line]:
        """The lines of one race: from its start-time line to the next race's."""
        starts = [i for i, line in enumerate(lines) if START.search(line.text)]
        if not starts:
            raise view.error("no race start time")
        sections = [lines[a:b] for a, b in zip(starts, [*starts[1:], len(lines)], strict=True)]
        if heat is None:
            if len(sections) != 1:
                raise view.error(f"{len(sections)} races in the document, but no heat declared")
            return sections[0]
        for section in sections:
            found = view.find(section[:3], HEAT, "heat-line")
            if found is not None and found["heat"] == str(heat):
                return section
        raise view.error(f"no section for heat {heat}")


def read_entry(view: DocumentView, row: LineMatch, race_date: date, in_lanes: bool) -> EntryReading:
    """An athlete row of a results table (also read by `wa_results_2009`)."""
    records, qualification, remarks = read_tail(view, row)
    card = row.read_opt("card", str)
    false_start = row.read_opt("fn", str)  # the "Fn" column: a false start charged to the athlete
    notes = tuple(note for note in (card, *remarks, false_start) if note is not None)
    return EntryReading(
        row=row.span(),
        place=row.read_opt("place", int),
        bib=row.read("bib", str) if "bib" in row.found.re.groupindex else None,
        name=row.read("name", lambda text: parse.person_name(text, family_first=False)),
        country=row.read("country", parse.country),
        birth_date=row.read_opt("birth", lambda text: parse.birth_date_short(text, race_date)),
        lane=row.read("lane", int) if in_lanes else None,
        result=row.read("result", parse.result),
        precise_time=row.read("precise", parse.precise_time)
        if "(" in (row["precise"] or "")
        else None,
        reaction_time=row.read_opt("reaction", parse.signed_decimal),
        records=records,
        qualification=qualification,
        remarks=notes,
    )
