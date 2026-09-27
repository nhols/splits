"""Olympic "Race Analysis" reports (ORIS report code C77A), e.g. from Paris 2024.

The Olympic results system (ORIS) publishes a bilingual race analysis per race, produced by
OMEGA. Splits are laid out as described in :mod:`splits.formats.omega_grid`, with the finish
labelled: the finish column gives the cumulative time and rank at the line. Athlete rows print
the bib, then the family name first, and a card if the athlete was shown one::

      3  1328 LYLES Noah     YC USA   19.70  0.24
          2.01 (6) 3.01 (3) ...           cumulative times (rank)
                   1.00     0.94 ...      segment times

The report's own version ("v2.0") and creation time are in the footer.
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
from splits.formats.common import read_first, read_tail, split_band
from splits.formats.omega_grid import TieredGrid
from splits.model import Sourced
from splits.model.ids import format_id
from splits.pdf.layout import DocumentView, Line

HEADING = re.compile(
    r"^(?P<sex>Men's|Women's) (?P<discipline>(?:\d{1,2},\d{3}|\d+)m(?: Hurdles| Steeplechase)?)$"
)
DATE_AND_ROUND = re.compile(
    r"^[A-Z]{3} (?P<date>\d{1,2} [A-Z]{3} \d{4}) "
    r"(?P<round>Final|Semi-Final|Round 1|Repechage Round|Repechage|Preliminary Round)"
    r"(?:(?: -)? Heat (?P<heat>\d+)(?:/\d+)?| (?P<of>\d+)/\d+)?$"
)
START = re.compile(r"^Start Time (?P<time>\d{1,2}:\d{2})$")
TABLE_HEADER = re.compile(r"^Bib Code Behind$")
ATHLETE = re.compile(
    r"(?:(?P<place>\d{1,2}) )?(?P<bib>\d{1,5}) (?P<name>.+?) (?:(?P<card>YC|YRC|RC) )?"
    r"(?P<country>[A-Z]{3}) (?P<result>\d{1,2}:\d{2}\.\d{2}|\d{1,3}\.\d{2}|DNF|DNS|DQ)"
    r"(?: (?P<behind>(?:\d{1,2}:)?\d{1,2}\.\d{2}))?(?: (?P<tail>.+))?"
)
FOOTER = re.compile(
    r"_77A (?P<version>v\d+(?:\.\d+)?) Report Created "
    r"(?P<created>[A-Z]{3} \d{1,2} [A-Z]{3} \d{4} \d{1,2}:\d{2})"
)


def _created(text: str) -> datetime:
    day, _, clock = text.rpartition(" ")
    return datetime.combine(parse.day_month_year(day), parse.clock(clock))


def _is_athlete_row(line: Line) -> bool:
    return ATHLETE.fullmatch(line.text) is not None


class OrisC77a(Format):
    kind = DocumentKind.ANALYSIS
    id = format_id("oris-c77a")
    version = "1.2.0"
    name = "Olympic race analysis (ORIS C77A)"
    publisher = "Olympic Games organising committee (timing by OMEGA)"
    description = (
        "Race analysis reports from the Olympic Games results system: cumulative time and "
        "rank at every checkpoint (10 m for the 200 m, 50 m for the 400 m, each hurdle for "
        "the 400 m hurdles) up to the finish, and the segment time between checkpoints."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        first = view.lines(1)
        heading = view.find(first, HEADING, "heading")
        if heading is None:
            raise view.error('no race heading such as "Men\'s 400m"', 1)
        date_and_round = view.find(first, DATE_AND_ROUND, "date-round")
        if date_and_round is None:
            raise view.error("no date and round line such as 'WED 7 AUG 2024 Final'", 1)

        entries: list[EntryReading] = []
        for page in view.pages:
            lines = view.lines(page.number)
            table = next((i for i, line in enumerate(lines) if TABLE_HEADER.match(line.text)), None)
            if table is None:
                continue
            grid = TieredGrid.find(view, lines[table:], context)
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
                        bib=row.read("bib", str),
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

        footer = [line for line in view.lines(len(view.pages)) if FOOTER.search(line.text)]
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
            start_time=read_first(view, first, START, "start", "time", parse.clock),
            issued=read_first(view, footer, FOOTER, "footer", "created", _created),
            revision=read_first(view, footer, FOOTER, "footer", "version", str),
            entries=tuple(entries),
        )
