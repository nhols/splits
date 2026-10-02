"""Olympic "Results" reports (ORIS report codes C73), from Rio 2016 to Paris 2024.

The official results from the Olympic results system, in the languages of the Games, beside
the race analysis (C77A). Rows give the bib, the family name first, the full birth date, lane,
reaction time and result; a card shown to the athlete is printed before the result::

      8   1337 NORMAN Michael    USA   3 DEC 1997  4   0.150 YC   45.62

Races not run in lanes all the way have a report of the same layout without reaction times:
the 800 m gives each athlete's lane (``2-1`` when two share it), and from the 1500 m their
order on the start line (``Order``), which is not a lane. Paris reports one race per document
(C73B1, C73C1), naming it ``Heat 3`` or ``2/2`` in the heading. Rio and Tokyo report a final
on its own (C73G) but a whole round in one document (C73H), each race a section headed by its
number and start time (``Heat 2 Start Time: 9:58``, ``SEMIFINAL 1 Start Time: 22:08``); the
reader reads the section of the race declared in the catalog. The format keeps the name of
the Paris report it was first written for.
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
from splits.formats.common import CARD, read_first, read_tail
from splits.formats.oris import FOOTER, OrisRace, find_race, heading
from splits.model import Sourced
from splits.model.ids import format_id
from splits.pdf.layout import DocumentView, Line, LineMatch

TABLE = re.compile(r"^Rank Name Date of Birth (?P<column>Lane|Order)\b")
SECTION = re.compile(
    r"^(?:(?i:heat|semi-?final|final|race) (?P<heat>\d+)|(?P<letter>[A-Z])-(?i:race)) "
    r"Start Time:? (?P<time>\d{1,2}:\d{2})(?: Wind: (?P<wind>[+-]?\d+\.\d) ?m/s)?$"
)
"""The start of one race in a report on a whole round: ``Heat 2``, ``SEMI-FINAL 1``, or
``B-RACE`` (race 2) for a final run in several races."""


def _race_number(section: LineMatch) -> Sourced[int]:
    if section["heat"]:
        return section.read("heat", int)
    return section.read("letter", lambda letter: ord(letter) - ord("A") + 1)


WIND = re.compile(r"^Wind: (?P<wind>[+-]?\d+\.\d) ?m/s$")
TEMPERATURE = re.compile(r"Temperature: (?P<temperature>-?\d+) ?°C")
HUMIDITY = re.compile(r"Humidity: (?P<humidity>\d+) ?%")
CONDITIONS = re.compile(r"Conditions: (?P<conditions>.+)$")
ATHLETE = re.compile(
    r"(?:(?P<place>\d{1,2}) )?(?P<bib>\d{1,5}) (?P<name>.+?) (?P<country>[A-Z]{3}) "
    r"(?P<birth>\d{1,2} [A-Z]{3} \d{4}) (?P<lane>\d{1,2})(?:-\d)? (?:(?P<reaction>-?\d\.\d{3}) )?"
    rf"(?:(?P<card>{CARD}) )?"
    r"(?P<precise>(?P<result>\d{1,2}:\d{2}\.\d{2}|\d{1,3}\.\d{2}|DNF|DNS|DQ)(?: \(\.\d{3}\))?)"
    r"(?: (?P<tail>.+))?"
)


def _created(text: str) -> datetime:
    day, _, clock = text.rpartition(" ")
    return datetime.combine(parse.day_month_year(day), parse.clock(clock))


class OrisC73b1(Format):
    kind = DocumentKind.RESULTS
    id = format_id("oris-c73b1")
    version = "1.3.0"
    name = "Olympic results (ORIS C73)"
    publisher = "Olympic Games organising committee (timing by OMEGA)"
    description = (
        "Official results of each race from the Olympic Games results system: place, lane, "
        "reaction time, result and full birth date for every athlete, the wind and weather."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        page_one = view.pages[0].number  # a page of a results book, perhaps
        lines = [line for page in view.pages for line in view.lines(page.number)]
        named = find_race(view, view.lines(page_one))
        if named is None:
            raise view.error('no race heading such as "Men\'s 400m" with its round', page_one)
        section, race = self._section(view, lines, context.spec.race.heat, named)
        table = view.find(section, TABLE, "table")
        in_lanes = table is None or table["column"] == "Lane"
        entries = [
            _entry(view, row, in_lanes)
            for line in section
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
            title=Sourced[str](
                value=named.event.found[0], source=named.event.span(), method="heading"
            ),
            heading=heading(named, _race_number(race) if race else None),
            date=named.date.read("date", parse.day_month_year),
            start_time=race.read("time", parse.clock)
            if race
            else named.start.read("time", parse.clock)
            if named.start
            else None,
            wind=race.read_opt("wind", parse.signed_decimal)
            if race
            else read_first(view, lines, WIND, "weather", "wind", parse.signed_decimal),
            temperature=read_first(
                view, lines, TEMPERATURE, "weather", "temperature", parse.signed_decimal
            ),
            humidity=read_first(view, lines, HUMIDITY, "weather", "humidity", parse.signed_decimal),
            weather=read_first(view, lines, CONDITIONS, "weather", "conditions", str),
            issued=read_first(view, footer, FOOTER, "footer", "created", _created),
            revision=read_first(view, footer, FOOTER, "footer", "version", str),
            entries=tuple(entries),
        )

    @staticmethod
    def _section(
        view: DocumentView, lines: list[Line], heat: int | None, named: OrisRace
    ) -> tuple[list[Line], LineMatch | None]:
        """The lines of the declared race, and the line that starts it in a report on a whole
        round; the whole report, and no such line, if it is about one race."""
        starts = [
            (i, found)
            for i, line in enumerate(lines)
            if (found := view.match(line, SECTION, "race"))
        ]
        about_one_race = heat is None or any(named.stage[g] for g in ("heat", "of", "race"))
        if not starts:
            if not about_one_race:
                raise view.error(f"a report on a whole round, with no section for race {heat}")
            return lines, None
        for (index, found), end in zip(
            starts, [*(i for i, _ in starts[1:]), len(lines)], strict=True
        ):
            if heat is not None and _race_number(found).value == heat:
                return lines[index:end], found
        raise view.error(f"no section for race {heat} among {len(starts)}", lines[0].page)


def _entry(view: DocumentView, row: LineMatch, in_lanes: bool) -> EntryReading:
    records, qualification, remarks = read_tail(view, row)
    card = row.read_opt("card", str)
    return EntryReading(
        row=row.span(),
        place=row.read_opt("place", int),
        bib=row.read("bib", str),
        name=row.read("name", lambda text: parse.person_name(text, family_first=True)),
        country=row.read("country", parse.country),
        birth_date=row.read("birth", parse.full_birth_date),
        lane=row.read("lane", int) if in_lanes else None,
        reaction_time=row.read_opt("reaction", parse.signed_decimal),
        result=row.read("result", parse.result),
        precise_time=row.read("precise", parse.precise_time)
        if "(" in (row["precise"] or "")
        else None,
        records=records,
        qualification=qualification,
        remarks=(card, *remarks) if card else remarks,
    )
