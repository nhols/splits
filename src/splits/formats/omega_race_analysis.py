"""OMEGA "Race analysis" documents from Diamond League meetings.

OMEGA times the Diamond League and publishes a race analysis for many races on its results site
(omegatiming.com) from 2021; from 2016 to 2022 the Diamond League's results service,
SportResult, published the same documents (static.sportresult.com, now offline and kept by the
Web Archive), timed to the tenth until 2022. Splits are laid out as described in
:mod:`splits.formats.omega_grid`; athlete rows print the family name first::

    Rank Name                     Nat    Result  Time Behind
        50m     100m    150m ...                               checkpoint labels
      1 INGVALDSEN Håvard Bentdal NOR    45.28                 athlete row
        6.32 (4) 11.37 (4) 16.58 (2) ...                       cumulative times (rank)
                 5.05     5.21 ...                             segment times

A Diamond League event is usually a single race, and the heading names no round; an event
run in heats and a final names it (``110m Hurdles Men - Round 1 Heat 1``). Some meetings add a
bib-number column after the rank.
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
from splits.formats.common import (
    CARD,
    OMEGA_HEADING,
    OMEGA_START,
    omega_round,
    read_first,
    read_tail,
    split_band,
)
from splits.formats.omega_grid import TieredGrid
from splits.model.ids import format_id
from splits.pdf.layout import DocumentView, Line

HEADING = OMEGA_HEADING
START = OMEGA_START
TABLE_HEADER = re.compile(r"^Rank (?:Bib )?Name Nat Result")
ATHLETE = re.compile(
    r"(?:(?P<place>\d{1,2}) )?(?:(?P<bib>\d{1,4}) )?(?P<name>\D+?)(?: \(PM\))? "
    rf"(?:(?P<card>{CARD}) )?(?P<country>[A-Z]{{3}}) "
    r"(?P<result>\d{1,2}:\d{2}\.\d{2}|\d{1,3}\.\d{2}|DNF|DNS|DQ)"
    r"(?: (?P<behind>(?:\d{1,2}:)?\d{1,2}\.\d{2}))?(?: (?P<tail>.+))?"
)
TEMPERATURE = re.compile(r"Temperature: (?P<temperature>-?\d+) ?°C")
HUMIDITY = re.compile(r"Humidity: (?P<humidity>\d+) ?%")
CONDITIONS = re.compile(r"Conditions: (?P<conditions>.+)$")
PRINTED = re.compile(r"printed at (?P<printed>[A-Z]{3} \d{1,2} [A-Z]{3} \d{4} \d{1,2}:\d{2})")

COLUMNS_PER_TIER = 10


def _printed(text: str) -> datetime:
    day, _, clock = text.rpartition(" ")
    return datetime.combine(parse.day_month_year(day), parse.clock(clock))


def _is_athlete_row(line: Line) -> bool:
    return ATHLETE.fullmatch(line.text) is not None


class OmegaRaceAnalysis(Format):
    kind = DocumentKind.ANALYSIS
    id = format_id("omega-race-analysis")
    version = "1.6.0"
    name = "OMEGA race analysis (Diamond League)"
    publisher = "OMEGA"
    description = (
        "Race analyses from Diamond League meetings, published on omegatiming.com (and from "
        "2016 to 2022 by SportResult): cumulative time and rank at every checkpoint (10 m for "
        "the 200 m, 50 m for the 400 m, each hurdle for the 400 m hurdles; once, a few "
        "checkpoints or the laps to go) and the segment time between checkpoints."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        first = view.lines(1)
        heading = view.find(first, HEADING, "heading")
        if heading is None:
            raise view.error("no race heading such as '400m Hurdles Men'", 1)
        start = view.find(first, START, "start")
        if start is None:
            raise view.error("no start time and date", 1)

        entries: list[EntryReading] = []
        notes: list[str] = []
        last_lines: list[Line] = []
        for page in view.pages:
            lines = view.lines(page.number)
            last_lines = lines
            table = next((i for i, line in enumerate(lines) if TABLE_HEADER.match(line.text)), None)
            if table is None:
                continue
            grid = TieredGrid.find(
                view, lines[table:], context, unlabelled_finish_after=COLUMNS_PER_TIER
            )
            notes.extend(grid.notes if grid else ())
            for index in range(table + 1, len(lines)):
                row = view.match(lines[index], ATHLETE, "athlete-row", full=True)
                if row is None:
                    continue
                band = split_band(view, lines, index, _is_athlete_row)
                if band and grid is None:
                    raise view.error("split lines but no checkpoint labels", page.number)
                splits, segments = (
                    grid.read(view, band, row["result"]) if grid and band else ((), ())
                )
                records, qualification, remarks = read_tail(view, row)
                card = row.read_opt("card", str)
                entries.append(
                    EntryReading(
                        row=row.span(),
                        place=row.read_opt("place", int),
                        name=row.read(
                            "name", lambda text: parse.person_name(text, family_first=True)
                        ),
                        country=row.read("country", parse.country),
                        result=row.read("result", parse.result),
                        records=records,
                        qualification=qualification,
                        remarks=(card, *remarks) if card else remarks,
                        splits=splits,
                        segments=segments,
                    )
                )
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
            temperature=read_first(
                view, last_lines, TEMPERATURE, "weather", "temperature", parse.signed_decimal
            ),
            humidity=read_first(
                view, last_lines, HUMIDITY, "weather", "humidity", parse.signed_decimal
            ),
            weather=read_first(view, last_lines, CONDITIONS, "weather", "conditions", str),
            issued=read_first(view, first, PRINTED, "footer", "printed", _printed),
            entries=tuple(entries),
            notes=tuple(dict.fromkeys(notes)),
        )
