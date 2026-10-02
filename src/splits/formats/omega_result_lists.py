"""OMEGA "Result lists" from Diamond League meetings: every race's results in one document.

A meeting's result lists print its races one after another, each under its heading with its
start time (and, for the sprints, the wind) on the next line, then the results table as OMEGA
prints a single race's (:mod:`splits.formats.omega_results`), from 2023 with a column for the
para athletes' sport class::

    400m Hurdles Women                                           2023
    Start Time: 14:04
    Rank Name Nat Date of Birth Sport Class Lane Result
    1 BOL Femke NED 23 FEB 2000 6 0.187 51.45 AR DLR MR

    1500m Men                                                    2019
    16 JUN 2019 / 19:11
    Rank Name Nat Date of Birth Order Result

Until 2019 the day is printed with the start time, and a race outside the meeting's programme
is named beside it (``National 16 JUN 2019 / 18:33``); from 2023 the lists print only the
meeting's dates, and the day comes from the race's analysis. The catalog names the pages a race
is printed on, and the reader reads the race of the declared event there, from its heading to
the next race's.
"""

import re

from splits.formats import parse
from splits.formats.base import (
    DocumentKind,
    DocumentReading,
    Format,
    HeadingReading,
    ReadContext,
)
from splits.formats.common import OMEGA_HEADING, omega_round
from splits.formats.omega_results import ATHLETE, read_entry
from splits.model.ids import format_id
from splits.pdf.layout import DocumentView

START = re.compile(
    r"^(?:Start Time: |(?:(?P<label>[A-Z][a-z]+) )?(?P<date>\d{1,2} [A-Z]{3} \d{4}) / )"
    r"(?P<time>\d{1,2}:\d{2})(?: Wind: (?P<wind>[+-]?\d+\.\d) ?m/s)?$"
)
TABLE = re.compile(r"^Rank Name Nat Date of Birth (?:Sport Class )?(?P<column>Lane|Order) Result$")


class OmegaResultLists(Format):
    kind = DocumentKind.RESULTS
    id = format_id("omega-result-lists")
    version = "1.0.0"
    name = "OMEGA result lists (Diamond League)"
    publisher = "OMEGA"
    description = (
        "A Diamond League meeting's results in one document, race after race: place, lane, "
        "reaction time, result and full birth date for every athlete, the start time and the "
        "wind."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        lines = [line for page in view.pages for line in view.lines(page.number)]
        # every event's results start with its heading, then its start time
        starts = [i - 1 for i, line in enumerate(lines) if i and START.fullmatch(line.text)]
        race = context.spec.race
        sections = []
        for at, end in zip(starts, [*starts[1:], len(lines)], strict=True):
            heading = view.match(lines[at], OMEGA_HEADING, "heading", full=True)
            if heading is None:
                continue  # a field event's, or a relay's
            event = (
                heading.read("discipline", parse.discipline).value,
                heading.read("sex", parse.sex).value,
            )
            if event == (race.discipline, race.sex):
                sections.append((heading, at, end))
        if len(sections) != 1:
            raise view.error(
                f"{len(sections)} races of {race.event} on the pages declared, expected one"
            )
        heading, at, end = sections[0]
        body = lines[at:end]
        start = view.match(body[1], START, "start", full=True)
        if start is None:  # cannot happen: a section is found by its start time
            raise view.error(f"no start time for {heading['race']!r}", body[0].page)
        table = view.find(body, TABLE, "table")
        if table is None:
            raise view.error(f"no results table for {heading['race']!r}", body[0].page)
        in_lanes = table["column"] == "Lane"
        entries = [
            read_entry(view, row, context.competition.start_date, in_lanes, born=True)
            for line in body
            if (row := view.match(line, ATHLETE, "athlete-row", full=True)) is not None
        ]
        if not entries:
            raise view.error(f"no athlete rows for {heading['race']!r}", body[0].page)
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
            date=start.read_opt("date", parse.day_month_year),
            start_time=start.read("time", parse.clock),
            wind=start.read_opt("wind", parse.signed_decimal),
            entries=tuple(entries),
        )
