"""World Athletics biomechanics reports by Leeds Beckett University, 2017 and 2018.

For the 2017 World Championships and the 2018 World Indoor Championships, a team from Leeds
Beckett University filmed the sprints and hurdles and published, through World Athletics, a
report per event. Most of its timings are drawn as charts; two tables give each finalist's
times from the gun, measured from video to the hundredth: the 100 m's cumulative time every
10 m, and the 60 m hurdles' time to each hurdle::

    Table 2.2. Cumulative split times every 10 metres for each athlete.
    Athlete RT    -10 m -20 m ... -100 m
    GATLIN  0.138 1.88  2.90  ... 9.92

    Table 21. Time to each hurdle and the finishing time for each of the finalists.
    Athlete     H1   H2   H3   H4   H5   FINISH
    POZZI       2.51 3.54 4.59 5.58 6.57 7.46

The last column is the finish. Athletes are named by family name alone (a name too long for
its cell wraps round the row: ``MARTINOT-`` above, ``LAGARDE`` below), which assembly finds
among the race's results. The report names the event on its title page and the round in a
section heading ("RESULTS – FINAL") or the table's caption ("the finalists"); it gives no
date. The catalog names the pages to read: the title page, the section heading's, the table's.
"""

import re
from dataclasses import dataclass
from decimal import Decimal

from splits.formats import parse
from splits.formats.base import (
    DocumentKind,
    DocumentReading,
    EntryReading,
    Format,
    HeadingReading,
    ReadContext,
    SplitReading,
)
from splits.model import PersonName, PointKind, Round, Sourced, TimingPoint
from splits.model.ids import format_id
from splits.pdf.layout import Columns, DocumentView, Line
from splits.pdf.textlayer import Word

TITLE = re.compile(r"^(?P<discipline>\d+ (?:m|Metres)(?: Hurdles)?) (?P<sex>Men|Women)(?:['’]s)?$")
FINAL = re.compile(r"^RESULTS [–-] (?P<final>FINAL)$|(?P<finalists>finalists)")
CAPTION = re.compile(r"^Table \d+(?:\.\d+)?\. (?:Cumulative split times|Time to each hurdle)")
LABEL = re.compile(r"(?P<rt>RT)|-(?P<distance>\d+) m|H(?P<hurdle>\d+)|(?P<finish>FINISH)")
LABELS = re.compile(rf"^(?:Athlete )?(?:(?:{LABEL.pattern}) ?)+$")
VALUE = re.compile(r"\d{1,2}\.\d{2,3}")
NAME = re.compile(r"[A-ZÀ-Ý][A-ZÀ-Ý'-]*")
TOLERANCE = 12.0
"""Points between a value's centre and its column label's."""


@dataclass
class _Row:
    name: list[Word]
    name_text: str
    """The name as printed, rejoined where it wraps round the row."""
    values: Line


class WaBiomechanics(Format):
    kind = DocumentKind.ANALYSIS
    id = format_id("wa-biomechanics")
    version = "1.0.0"
    name = "World Athletics biomechanics report (Leeds Beckett University)"
    publisher = "World Athletics"
    description = (
        "Biomechanics reports on the finals of the 2017 World Championships and the 2018 "
        "World Indoor Championships: each finalist's time from the gun every 10 m (100 m) or "
        "at each hurdle (60 m hurdles), measured from video, and the reaction time."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        lines = [line for page in view.pages for line in view.lines(page.number)]
        title = view.find(lines, TITLE, "title")
        if title is None:
            raise view.error("no report title such as '100 m Men’s'", view.pages[0].number)
        final = view.find(lines, FINAL, "round")
        caption = next((i for i, line in enumerate(lines) if CAPTION.search(line.text)), None)
        if caption is None:
            raise view.error("no table of times from the gun")
        header = next(
            (i for i in range(caption + 1, len(lines)) if LABELS.fullmatch(lines[i].text)), None
        )
        if header is None:
            raise view.error("no column labels under the table's caption", lines[caption].page)
        columns, reaction = self._columns(view, lines[header], context)

        entries = [
            self._entry(view, row, columns, reaction, context)
            for row in _rows(view, lines[header + 1 :])
        ]
        if not entries:
            raise view.error("no athlete rows", lines[header].page)
        return DocumentReading(
            document=view.document,
            format=self.id,
            format_version=self.version,
            pages=len(view.pages),
            title=Sourced[str](value=title.found[0], source=title.span(), method="title"),
            heading=HeadingReading(
                discipline=title.read("discipline", parse.discipline),
                sex=title.read("sex", parse.sex),
                round=final.read(final.found.lastgroup or "final", lambda _: Round.FINAL)
                if final
                else None,
                heat=None,
            ),
            date=None,
            entries=tuple(entries),
        )

    @staticmethod
    def _columns(
        view: DocumentView, header: Line, context: ReadContext
    ) -> tuple[Columns[TimingPoint], float | None]:
        """The columns of times, and where the reaction time's is (if there is one)."""
        anchors: list[tuple[TimingPoint, float]] = []
        reaction: float | None = None
        finish = context.discipline.finish()
        for found in LABEL.finditer(header.text):
            words = header.words_in(*found.span())
            centre = sum(word.xc for word in words) / len(words)
            if found["rt"]:
                reaction = centre
            elif found["distance"]:
                distance = parse.seconds(found["distance"])
                point = finish if distance == finish.distance else TimingPoint.at(distance)
                anchors.append((point, centre))
            elif found["hurdle"]:
                anchors.append(
                    (context.discipline.hurdle(context.spec.race.sex, int(found["hurdle"])), centre)
                )
            else:
                anchors.append((finish, centre))
        if not anchors or anchors[-1][0] != finish:
            raise view.error("the last column is not the finish", header.page)
        return Columns(tuple(anchors), TOLERANCE), reaction

    @staticmethod
    def _entry(
        view: DocumentView,
        row: _Row,
        columns: Columns[TimingPoint],
        reaction: float | None,
        context: ReadContext,
    ) -> EntryReading:
        page = row.values.page
        splits: list[SplitReading] = []
        reaction_time: Sourced[Decimal] | None = None
        finish: Word | None = None
        for word in row.values.words:
            if reaction is not None and abs(word.xc - reaction) <= TOLERANCE:
                reaction_time = view.read(page, [word], parse.signed_decimal, "reaction")
                continue
            point = columns.assign(word)
            if point is None:
                raise view.error(f"{word.text} is under no column", page)
            if point.kind is PointKind.FINISH:
                finish = word
            splits.append(
                SplitReading(point=point, time=view.read(page, [word], parse.seconds, "time"))
            )
        if finish is None:
            raise view.error(f"no finishing time for {row.name_text}", page)
        return EntryReading(
            row=view.span(page, [*row.name, *row.values.words]),
            name=view.read(page, row.name, _family_only, "name", row.name_text),
            country=None,
            result=view.read(page, [finish], parse.result, "finish"),
            reaction_time=reaction_time,
            splits=tuple(splits),
        )


def _family_only(text: str) -> PersonName:
    """A name printed as the family name alone: ``BOLT``, ``TA LOU``, ``MARTINOT-LAGARDE``."""
    return PersonName(given="", family=text)


def _rows(view: DocumentView, lines: list[Line]) -> list[_Row]:
    """The table's rows, down to its note: a name then its times, or times with the name
    wrapped round them, its first part above ending in a hyphen and the rest below."""
    rows: list[_Row] = []
    for index, line in enumerate(lines):
        if line.text.startswith("Note"):
            break
        names = [word for word in line.words if NAME.fullmatch(word.text)]
        values = [word for word in line.words if VALUE.fullmatch(word.text)]
        if not values:
            continue
        if len(names) + len(values) != len(line.words):
            raise view.error(f"unrecognised row: {line.text!r}", line.page)
        if names:
            text = " ".join(word.text for word in names)
            rows.append(_Row(names, text, Line(line.page, tuple(values))))
            continue
        above, below = (
            (lines[index - 1] if index else None),
            (lines[index + 1] if index + 1 < len(lines) else None),
        )
        if (
            above is None
            or below is None
            or not above.text.endswith("-")
            or not all(NAME.fullmatch(word.text) for word in (*above.words, *below.words))
        ):
            raise view.error(f"times with no name: {line.text!r}", line.page)
        wrapped = [*above.words, *below.words]
        text = above.text + below.text  # "MARTINOT-" + "LAGARDE"
        rows.append(_Row(wrapped, text, Line(line.page, tuple(values))))
    return rows
