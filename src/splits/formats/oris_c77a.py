"""Olympic "Race Analysis" reports (ORIS report code C77A), from Rio 2016 to Paris 2024.

The Olympic results system (ORIS) publishes a race analysis per race, produced by OMEGA, in
the languages of the Games. Splits are laid out as described in :mod:`splits.formats.omega_grid`.
Athlete rows print the bib, then the family name first, and a card if the athlete was shown
one::

      3  1328 LYLES Noah     YC USA   19.70  0.24
          2.01 (6) 3.01 (3) ...           cumulative times (rank)
                   1.00     0.94 ...      segment times

Paris labels the finish, giving the cumulative time and rank at the line, and prints segment
times. Rio and Tokyo time the 800 m and longer races only, to the tenth, with cumulative times
alone (every 100 m, ten to a line; the 800 m from 200 m), print the start time as
``Start Time: 10:10`` and the report's version as ``1.1`` rather than ``v2.0``.
"""

import re
from datetime import datetime

from splits.formats import parse
from splits.formats.base import (
    DocumentKind,
    DocumentReading,
    EntryReading,
    Format,
    ReadContext,
)
from splits.formats.common import CARD, read_first, read_tail, split_band
from splits.formats.omega_grid import TieredGrid
from splits.formats.oris import FOOTER, find_race, heading
from splits.model import Sourced
from splits.model.ids import format_id
from splits.pdf.layout import DocumentView, Line

TABLE_HEADER = re.compile(r"^(?:Bib )?Code Behind$")
ATHLETE = re.compile(
    rf"(?:(?P<place>\d{{1,2}}) )?(?P<bib>\d{{1,5}}) (?P<name>.+?) (?:(?P<card>{CARD}) )?"
    r"(?P<country>[A-Z]{3}) (?:(?P<birth>\d{1,2} [A-Z]{3} \d{4}) )?"
    r"(?P<result>\d{1,2}:\d{2}\.\d{2}|\d{1,3}\.\d{2}|DNF|DNS|DQ)"
    r"(?: (?P<behind>(?:\d{1,2}:)?\d{1,2}\.\d{2}))?(?: (?P<tail>.+))?"
)


def _created(text: str) -> datetime:
    day, _, clock = text.rpartition(" ")
    return datetime.combine(parse.day_month_year(day), parse.clock(clock))


def _is_athlete_row(line: Line) -> bool:
    return ATHLETE.fullmatch(line.text) is not None


class OrisC77a(Format):
    kind = DocumentKind.ANALYSIS
    id = format_id("oris-c77a")
    version = "1.3.0"
    name = "Olympic race analysis (ORIS C77A)"
    publisher = "Olympic Games organising committee (timing by OMEGA)"
    description = (
        "Race analysis reports from the Olympic Games results system: cumulative time and "
        "rank at every checkpoint (from Paris 2024, 10 m for the 200 m, 50 m for the 400 m, "
        "each hurdle for the 400 m hurdles, up to the finish, with segment times; at Rio 2016 "
        "and Tokyo 2020, every 100 m of the 800 m and longer races, to the tenth)."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        page_one, last_page = view.pages[0].number, view.pages[-1].number  # of a book, perhaps
        race = find_race(view, view.lines(page_one))
        if race is None:
            raise view.error('no race heading such as "Men\'s 400m" with its round', page_one)

        entries: list[EntryReading] = []
        notes: list[str] = []
        for page in view.pages:
            # the footer is no part of the table (Rio's report version, "1.0", looks like a time)
            lines = [line for line in view.lines(page.number) if not FOOTER.search(line.text)]
            table = next((i for i, line in enumerate(lines) if TABLE_HEADER.match(line.text)), None)
            if table is None:
                continue
            grid = TieredGrid.find(view, lines[table:], context)
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
                        bib=row.read("bib", str),
                        name=row.read(
                            "name", lambda text: parse.person_name(text, family_first=True)
                        ),
                        country=row.read("country", parse.country),
                        birth_date=row.read_opt("birth", parse.full_birth_date),
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

        footer = [line for line in view.lines(last_page) if FOOTER.search(line.text)]
        return DocumentReading(
            document=view.document,
            format=self.id,
            format_version=self.version,
            pages=len(view.pages),
            title=Sourced[str](
                value=race.event.found[0], source=race.event.span(), method="heading"
            ),
            heading=heading(race),
            date=race.date.read("date", parse.day_month_year),
            start_time=race.start.read("time", parse.clock) if race.start else None,
            issued=read_first(view, footer, FOOTER, "footer", "created", _created),
            revision=read_first(view, footer, FOOTER, "footer", "version", str),
            entries=tuple(entries),
            notes=tuple(dict.fromkeys(notes)),
        )
