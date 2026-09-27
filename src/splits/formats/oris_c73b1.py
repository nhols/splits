"""Olympic "Results" reports (ORIS report codes C73B1 and C73C1), e.g. from Paris 2024.

The official result of one race from the Olympic results system, bilingual, beside its race
analysis (C77A). Rows give the bib, the family name first, the full birth date, lane,
reaction time and result; a card shown to the athlete is printed before the result::

      8   1337 NORMAN Michael    USA   3 DEC 1997  4   0.150 YC   45.62

Races not run in lanes all the way have a C73C1 report of the same layout, without reaction
times: the 800 m gives each athlete's lane (``2-1`` when two share it), and from the 1500 m
their order on the start line (``Order``), which is not a lane. A round run in several races
names the race as ``Heat 3`` or ``2/2``.
"""

import re
from datetime import datetime

from splits.formats import parse
from splits.formats.base import (
    DocumentKind,
    DocumentReading,
    EntryReading,
    Format,
    HeadingReading,
    ReadContext,
)
from splits.formats.common import read_first, read_tail
from splits.model import BirthDate, Sourced
from splits.model.ids import format_id
from splits.pdf.layout import DocumentView, LineMatch

HEADING = re.compile(
    r"^(?P<sex>Men's|Women's) (?P<discipline>(?:\d{1,2},\d{3}|\d+)m(?: Hurdles| Steeplechase)?)$"
)
DATE_AND_ROUND = re.compile(
    r"^[A-Z]{3} (?P<date>\d{1,2} [A-Z]{3} \d{4}) "
    r"(?P<round>Final|Semi-Final|Round 1|Repechage Round|Repechage|Preliminary Round)"
    r"(?:(?: -)? Heat (?P<heat>\d+)(?:/\d+)?| (?P<of>\d+)/\d+)?$"
)
TABLE = re.compile(r"^Rank Name Date of Birth (?P<column>Lane|Order)\b")
START = re.compile(r"^Start Time (?P<time>\d{1,2}:\d{2})$")
WIND = re.compile(r"^Wind: (?P<wind>[+-]?\d+\.\d)m/s$")
TEMPERATURE = re.compile(r"Temperature: (?P<temperature>-?\d+) ?°C")
HUMIDITY = re.compile(r"Humidity: (?P<humidity>\d+) ?%")
CONDITIONS = re.compile(r"Conditions: (?P<conditions>.+)$")
ATHLETE = re.compile(
    r"(?:(?P<place>\d{1,2}) )?(?P<bib>\d{1,5}) (?P<name>.+?) (?P<country>[A-Z]{3}) "
    r"(?P<birth>\d{1,2} [A-Z]{3} \d{4}) (?P<lane>\d{1,2})(?:-\d)? (?:(?P<reaction>-?\d\.\d{3}) )?"
    r"(?:(?P<card>YC|YRC|RC) )?(?P<result>\d{1,2}:\d{2}\.\d{2}|\d{1,3}\.\d{2}|DNF|DNS|DQ)"
    r"(?: (?P<tail>.+))?"
)
FOOTER = re.compile(
    r"_73(?:B1|C1) (?P<version>v\d+(?:\.\d+)?) Report Created "
    r"(?P<created>[A-Z]{3} \d{1,2} [A-Z]{3} \d{4} \d{1,2}:\d{2})"
)


def _created(text: str) -> datetime:
    day, _, clock = text.rpartition(" ")
    return datetime.combine(parse.day_month_year(day), parse.clock(clock))


def _full_birth_date(text: str) -> BirthDate:
    day = parse.day_month_year(text)
    return BirthDate(year=day.year, month=day.month, day=day.day)


class OrisC73b1(Format):
    kind = DocumentKind.RESULTS
    id = format_id("oris-c73b1")
    version = "1.1.0"
    name = "Olympic results (ORIS C73B1, C73C1)"
    publisher = "Olympic Games organising committee (timing by OMEGA)"
    description = (
        "Official results of each race from the Olympic Games results system: place, lane, "
        "reaction time, result and full birth date for every athlete, the wind and weather."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        lines = [line for page in view.pages for line in view.lines(page.number)]
        heading = view.find(lines, HEADING, "heading")
        if heading is None:
            raise view.error('no race heading such as "Men\'s 400m"', 1)
        date_and_round = view.find(lines, DATE_AND_ROUND, "date-round")
        if date_and_round is None:
            raise view.error("no date and round line such as 'WED 7 AUG 2024 Final'", 1)
        table = view.find(lines, TABLE, "table")
        in_lanes = table is None or table["column"] == "Lane"
        entries = [
            _entry(view, row, in_lanes)
            for line in lines
            if (row := view.match(line, ATHLETE, "athlete-row", full=True)) is not None
        ]
        if not entries:
            raise view.error("no athlete rows")
        footer = [line for line in lines if FOOTER.search(line.text)]
        return DocumentReading(
            document=view.document,
            format=self.id,
            format_version=self.version,
            pages=len(view.pages),
            title=Sourced[str](value=heading.found[0], source=heading.span(), method="heading"),
            heading=HeadingReading(
                discipline=heading.read("discipline", parse.discipline),
                sex=heading.read("sex", parse.sex),
                round=date_and_round.read("round", parse.round_name),
                heat=date_and_round.read_opt("heat", int) or date_and_round.read_opt("of", int),
            ),
            date=date_and_round.read("date", parse.day_month_year),
            start_time=read_first(view, lines, START, "start", "time", parse.clock),
            wind=read_first(view, lines, WIND, "weather", "wind", parse.signed_decimal),
            temperature=read_first(
                view, lines, TEMPERATURE, "weather", "temperature", parse.signed_decimal
            ),
            humidity=read_first(view, lines, HUMIDITY, "weather", "humidity", parse.signed_decimal),
            weather=read_first(view, lines, CONDITIONS, "weather", "conditions", str),
            issued=read_first(view, footer, FOOTER, "footer", "created", _created),
            revision=read_first(view, footer, FOOTER, "footer", "version", str),
            entries=tuple(entries),
        )


def _entry(view: DocumentView, row: LineMatch, in_lanes: bool) -> EntryReading:
    records, qualification, remarks = read_tail(view, row)
    card = row.read_opt("card", str)
    return EntryReading(
        row=row.span(),
        place=row.read_opt("place", int),
        bib=row.read("bib", str),
        name=row.read("name", lambda text: parse.person_name(text, family_first=True)),
        country=row.read("country", parse.country),
        birth_date=row.read("birth", _full_birth_date),
        lane=row.read("lane", int) if in_lanes else None,
        reaction_time=row.read_opt("reaction", parse.signed_decimal),
        result=row.read("result", parse.result),
        records=records,
        qualification=qualification,
        remarks=(card, *remarks) if card else remarks,
    )
