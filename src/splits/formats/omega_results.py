"""OMEGA "Results" documents from Diamond League meetings.

The official result of a Diamond League race, published beside its race analysis on OMEGA's
results site. Rows print the family name first, then the full birth date (the year alone before
2022), lane, reaction time
and result, to the thousandth where athletes are level in hundredths; qualification meetings
add the Diamond League points and standing, which are not transcribed::

      Rank Name              Nat  Date of Birth Lane  Reaction time  Result
      1 McMASTER Kyron       IVB  3 JAN 1997    6     0.149          47.27   19  4
      1 ALFRED Julien        LCA  10 JUN 2001   6     0.139          10.70 (.693) NR  23  2
        JOHNSON Alaysha      USA  20 JUL 1996   7     0.153          DQ TR22.6.2  19  5

A disqualification is followed by the rule broken, kept as a remark. Races not started from
blocks give no reaction time, and from 1000 m the start order instead of a lane (``Order``); a
shared 800 m lane prints the starter's position in it (``8-1``); a pacemaker is marked ``(PM)``.
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
from splits.formats.common import OMEGA_HEADING, OMEGA_START, RECORD_TAG, omega_round, read_first
from splits.model import BirthDate, Qualification, Sourced
from splits.model.ids import format_id
from splits.pdf.layout import DocumentView, LineMatch

HEADING = OMEGA_HEADING
START = OMEGA_START
WEATHER = re.compile(r"^(?P<temperature>-?\d+) ?°C (?P<humidity>\d+) ?% (?P<conditions>.+)$")
ATHLETE = re.compile(
    r"(?:(?P<place>\d{1,2}) )?(?P<name>.+?)(?: (?P<pacer>\(PM\)))? (?P<country>[A-Z]{3}) "
    r"(?P<birth>\d{1,2} [A-Z]{3} \d{4}|\d{2}) (?P<lane>\d{1,2})(?:-\d)? "
    r"(?:(?P<reaction>-?\d\.\d{3}) )?"
    r"(?P<precise>(?P<result>\d{1,2}:\d{2}\.\d{2}|\d{1,3}\.\d{2}|DNF|DNS|DQ)"
    r"(?: \(\.\d{3}\))?)(?: (?P<tags>(?:(?:=?[A-Za-z]+|[A-Z]{1,3}\d+(?:\.\d+)+) ?)+?))?"
    r"(?: (?P<points>\d+) (?P<standing>\d+))?"
)
TABLE = re.compile(r"^Rank Name Nat (?:born|Date of Birth) (?P<column>Lane|Order)\b")
"""The table's heading: races from blocks give each athlete's lane, longer races their order on
the start line, which is not a lane."""
PRINTED = re.compile(r"printed at (?P<printed>[A-Z]{3} \d{1,2} [A-Z]{3} \d{4} \d{1,2}:\d{2})")


def _printed(text: str) -> datetime:
    day, _, clock = text.rpartition(" ")
    return datetime.combine(parse.day_month_year(day), parse.clock(clock))


def _full_birth_date(text: str) -> BirthDate:
    day = parse.day_month_year(text)
    return BirthDate(year=day.year, month=day.month, day=day.day)


class OmegaResults(Format):
    kind = DocumentKind.RESULTS
    id = format_id("omega-results")
    version = "1.5.0"
    name = "OMEGA results (Diamond League)"
    publisher = "OMEGA"
    description = (
        "Official results of Diamond League races, published on omegatiming.com: place, "
        "lane, reaction time, result (to the thousandth where needed) and full birth date for "
        "every athlete, and the weather."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        lines = [line for page in view.pages for line in view.lines(page.number)]
        heading = view.find(lines, HEADING, "heading")
        if heading is None:
            raise view.error("no race heading such as '400m Hurdles Men'", 1)
        start = view.find(lines, START, "start")
        if start is None:
            raise view.error("no start time and date", 1)
        weather = view.find(lines, WEATHER, "weather")
        race_date = start.read("date", parse.day_month_year).value
        table = view.find(lines, TABLE, "table")
        in_lanes = table is None or table["column"] == "Lane"
        entries = [
            _entry(view, row, race_date, in_lanes)
            for line in lines
            if (row := view.match(line, ATHLETE, "athlete-row", full=True)) is not None
        ]
        if not entries:
            raise view.error("no athlete rows")
        return DocumentReading(
            document=view.document,
            format=self.id,
            format_version=self.version,
            pages=len(view.pages),
            title=heading.read("race", str),
            heading=HeadingReading(
                discipline=heading.read("discipline", parse.discipline),
                sex=heading.read("sex", parse.sex),
                round=omega_round(heading)[0],
                heat=omega_round(heading)[1],
            ),
            date=start.read("date", parse.day_month_year),
            start_time=start.read("time", parse.clock),
            temperature=weather.read("temperature", parse.signed_decimal) if weather else None,
            humidity=weather.read("humidity", parse.signed_decimal) if weather else None,
            weather=weather.read("conditions", str) if weather else None,
            issued=read_first(view, lines, PRINTED, "footer", "printed", _printed),
            entries=tuple(entries),
        )


def _birth(text: str, on: date) -> BirthDate:
    """A full birth date (``3 JAN 1997``), or in older documents the year alone (``97``)."""
    return _full_birth_date(text) if " " in text else parse.birth_date_short(text, on)


def _entry(view: DocumentView, row: LineMatch, race_date: date, in_lanes: bool) -> EntryReading:
    records: list[Sourced[str]] = []
    remarks: list[Sourced[str]] = []
    qualification: Sourced[Qualification] | None = None
    if row["pacer"]:
        remarks.append(row.read("pacer", lambda text: text.strip("()")))
    for word in row.words("tags") if row["tags"] else ():
        if RECORD_TAG.fullmatch(word.text):
            records.append(view.read(row.line.page, [word], str, "athlete-row.record"))
        elif word.text in ("Q", "q"):
            qualification = view.read(
                row.line.page, [word], Qualification, "athlete-row.qualification"
            )
        else:
            remarks.append(view.read(row.line.page, [word], str, "athlete-row.remark"))
    return EntryReading(
        row=row.span(),
        place=row.read_opt("place", int),
        name=row.read("name", lambda text: parse.person_name(text, family_first=True)),
        country=row.read("country", parse.country),
        birth_date=row.read("birth", lambda text: _birth(text, race_date)),
        lane=row.read("lane", int) if in_lanes else None,
        reaction_time=row.read_opt("reaction", parse.signed_decimal),
        result=row.read("result", parse.result),
        precise_time=row.read("precise", parse.precise_time)
        if "(" in (row["precise"] or "")
        else None,
        records=tuple(records),
        qualification=qualification,
        remarks=tuple(remarks),
    )
