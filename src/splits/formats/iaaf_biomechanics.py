"""IAAF biomechanics reports: split times measured from video, Berlin 2009.

At the 2009 World Championships a German research team filmed the sprint and hurdles races
from the stands and published, through the IAAF, tables of reaction times and split times for
most runners of every round. A table covers a round, or two (``Semifinal/Final``), of one
event; each athlete has a row per race, the first with their name::

    200m Men                                                          Semifinal/Final
    Round Wind  RT     t      t     Diff.  t        t     t      t       t        t
                       200m   100m         100-200m 150m  0-50m  50-100m 100-150m 150-200m
    Bolt Usain JAM  Fi  -0,3 0,133 19,19 9,92 -0,65 9,27  14,44 5,60   4,32    4,52     4,75
                    Ht 1 0,0 0,177 20,08 10,14 -0,20 9,94 14,86 5,74   4,40    4,72     5,22

Each column is a time ``t`` labelled by a subscript: set small after the ``t`` or on the line
below it, or run into it (``t400m``). A time to a distance (``150m``, or ``0-50m``, timed
from the gun) is a split; a time between two distances (``100-200m``, or ``2. 100m`` in some
repeated headings) is a segment; the time to the finish
distance (or ``end``) is the result. ``Diff.`` (the second half's time less the first's) is
derived and not kept. The 400 m has no wind column.

In the hurdles, the columns are the barriers (``1. H`` ... ``10. H``) and the finish (``end``),
timed at the touchdown after each barrier (the first foot down beyond it; New Studies in
Athletics 1/2 2011, the project's paper). Under each athlete's row a second line gives the
time from each touchdown to the next, a segment, and in the women's 400 m hurdles final a
third line the number of steps between barriers, which is not transcribed.

What a row's round marker means depends on the table. ``Fi`` is the final and ``SF 2`` the
second semi-final. ``Ht 3`` is the third race of the table's round: a heat in ``Round 1``, a
quarter-final in ``Round 2``, a semi-final in ``Semifinal/Final``. The 100 m has a table of
the medal winners, each with every round from the final down (``Fi``, ``SF 1``, then ``Ht 5``
for the quarter-final and ``Ht 9`` for the heat), then the other finalists and semi-finalists.
Names are printed family name first, in mixed case, with nothing to say where the given name
starts; assembly matches them to the names in the race's results. The report does not print
the day of each race.
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
    SegmentReading,
    SplitReading,
)
from splits.model import (
    Discipline,
    PersonName,
    Result,
    Round,
    Sex,
    Sourced,
    TimingPoint,
)
from splits.model.ids import format_id
from splits.pdf.layout import Columns, DocumentView, Line, LineMatch
from splits.pdf.textlayer import Word

TABLE = re.compile(
    r"^(?P<discipline>\d+m(?: Hurdles)?) (?:Männer/)?(?P<sex>Men|Women) "
    r"(?P<rounds>Round [12]|Semifinal/Final|Semifinal|Final|Medal winners)$"
)
NAMED = ("Round", "Wind", "RT", "Diff.")
MARKER = r"(?P<round>Fi|(?:Ht|SF) (?P<heat>\d+))"
ATHLETE = re.compile(rf"^(?P<name>\S+(?: \S+)+?) (?P<country>[A-Z]{{3}}) {MARKER} ")
CONTINUATION = re.compile(rf"^{MARKER} ")
INTERVALS = re.compile(r"^\d{1,2},\d{2}(?: \d{1,2},\d{2})*$")
SPAN = re.compile(r"(?:(?P<start>\d+)-)?(?P<end>\d+)m?")
HURDLE = re.compile(r"(?P<number>\d+)\. ?H")
STRETCH = re.compile(r"(?P<number>\d+)\. (?P<length>\d+)m")
"""The ``number``-th stretch of ``length`` metres (``2. 50m``: from 50 m to 100 m), as a table's
repeated headings sometimes label a segment."""
LABEL = re.compile(r"(?:\d+-)?\d+m?|\d+\.|H|end")
"""A word of a column's label: ``20m``, ``100-200``, ``1.`` and ``H`` (hurdle 1), ``end``."""
ROUNDS = {
    "Round 1": (Round.HEAT,),
    "Round 2": (Round.QUARTER_FINAL,),
    "Semifinal": (Round.SEMI_FINAL,),
    "Final": (Round.FINAL,),
    "Semifinal/Final": (Round.SEMI_FINAL, Round.FINAL),
    "Medal winners": (Round.QUARTER_FINAL, Round.SEMI_FINAL, Round.FINAL),
}
"""The rounds each kind of table reports."""
BELOW_MEDALLISTS = (Round.QUARTER_FINAL, Round.HEAT)
"""The rounds of a medal winner's ``Ht`` rows, in the order the table prints them."""


def _decimal(text: str) -> Decimal:
    """A number with a decimal comma: ``-0,3``, ``0,133``, ``19,19``."""
    return parse.signed_decimal(text.replace(",", "."))


def _seconds(text: str) -> Decimal:
    return parse.seconds(text.replace(",", "."))


def _name(text: str) -> PersonName:
    """``Bolt Usain``: the family name first. Where the given name starts is not printed; the
    last word is taken for it, and assembly matches the whole name to the race's results."""
    *family, given = text.split()
    return PersonName(given=given, family=" ".join(family))


@dataclass(frozen=True)
class _Table:
    heading: LineMatch
    rows: list[Line]
    """The lines under the table's heading, up to the next table's."""

    @property
    def rounds(self) -> tuple[Round, ...]:
        return ROUNDS[self.heading["rounds"] or ""]


class IaafBiomechanics(Format):
    kind = DocumentKind.ANALYSIS
    id = format_id("iaaf-biomechanics")
    version = "2.0.0"
    name = "IAAF biomechanics report"
    compilation = "Biomechanics report"
    publisher = "IAAF, with the German Athletics Federation (DLV)"
    names_unsplit = True
    description = (
        "Reaction and split times measured from video by the biomechanics research project at "
        "the 2009 World Championships in Berlin, for most runners of every round of the "
        "sprints and hurdles."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        declared = context.spec.race
        tables = [table for table in _tables(view) if declared.round in table.rounds]
        if not tables:
            raise view.error(f"no table of the {declared.round} (such as '200m Men Round 1')")
        heading = tables[0].heading
        discipline, sex = context.discipline, declared.sex
        entries, wind = [], None
        for table in tables:
            for row in _rows(view, table, declared.round, declared.heat):
                row_wind = row.values.pop("Wind", None)
                wind = wind or row_wind
                entries.append(_entry(view, row, discipline, sex))
        if not entries:
            raise view.error(f"no rows for {declared} in {heading.line.text!r}")
        return DocumentReading(
            document=view.document,
            format=self.id,
            format_version=self.version,
            pages=len(view.pages),
            title=Sourced[str](value=heading.line.text, source=heading.span(), method="table"),
            heading=HeadingReading(
                discipline=heading.read("discipline", parse.discipline),
                sex=heading.read("sex", parse.sex),
                round=heading.read("rounds", lambda _: declared.round),
                heat=None,
            ),
            date=None,
            wind=wind,
            entries=tuple(entries),
        )


def _tables(view: DocumentView) -> list[_Table]:
    tables: list[_Table] = []
    for page in view.pages:
        for line in view.lines(page.number):
            heading = view.match(line, TABLE, "table")
            if heading is not None:
                tables.append(_Table(heading, []))
            elif tables:
                tables[-1].rows.append(line)
    return tables


@dataclass(frozen=True)
class _Row:
    named: LineMatch
    """The athlete's first row, which names them."""
    row: LineMatch
    """The row of this race: the named one, or a later one of the same athlete."""
    values: dict[str, Sourced[Decimal]]
    columns: Columns[str]
    intervals: Line | None
    """The times between touchdowns, on the line beneath the row, in the hurdles."""


def _rows(view: DocumentView, table: _Table, round_: Round, heat: int | None) -> list[_Row]:
    """The rows of one race."""
    kind = table.heading["rounds"] or ""
    found: list[_Row] = []
    columns: Columns[str] | None = None
    named: LineMatch | None = None
    below_medallist = 0
    lines = table.rows
    for index, line in enumerate(lines):
        if _is_headings(line):
            below = lines[index + 1] if index + 1 < len(lines) else None
            columns = _columns(view, line, below)
            continue
        row = view.match(line, ATHLETE, "athlete-row")
        if row is not None:
            named, below_medallist = row, 0
        else:
            row = view.match(line, CONTINUATION, "athlete-row")
            if row is None:
                continue
        if named is None or columns is None:
            raise view.error(f"a row with no athlete or headings: {line.text!r}", line.page)
        marker = row["round"] or ""
        if marker == "Fi":
            row_round = Round.FINAL
        elif marker.startswith("SF"):
            row_round = Round.SEMI_FINAL
        elif kind == "Medal winners":
            if row is named or below_medallist >= len(BELOW_MEDALLISTS):
                raise view.error(f"a heat row the table does not explain: {line.text!r}")
            row_round = BELOW_MEDALLISTS[below_medallist]
            below_medallist += 1
        elif kind == "Semifinal/Final":
            row_round = Round.SEMI_FINAL
        else:
            row_round = ROUNDS[kind][0]
        row_heat = int(row["heat"]) if row["heat"] else None
        if row_round is not round_ or row_heat != heat:
            continue
        after = lines[index + 1] if index + 1 < len(lines) else None
        intervals = after if after is not None and INTERVALS.fullmatch(after.text) else None
        found.append(_Row(named, row, _values(view, row, columns), columns, intervals))
    return found


def _is_headings(line: Line) -> bool:
    """Whether a line heads the table's columns: ``Round Wind RT t t Diff. ...``, perhaps with
    the subscripts that label each ``t`` on it."""
    return bool(line.words) and line.words[0].text == "Round" and "RT" in line.text.split()


def _columns(view: DocumentView, headings: Line, below: Line | None) -> Columns[str]:
    """Column anchors: Wind, RT and Diff. by their headings; each time column by its ``t``
    and label, found in the heading (``t400m``), set small after it, or on the line below."""
    size = headings.words[0].size  # "Round"
    words = list(headings.words)
    if below is not None and all(LABEL.fullmatch(word.text) for word in below.words):
        words.extend(below.words)
    words.sort(key=lambda word: word.x0)
    anchors: list[tuple[str, float]] = []
    columns: list[tuple[Word, list[Word]]] = []
    for word in words:
        if word.size >= size - 0.5 and word.text in NAMED:
            if word.text != "Round":
                anchors.append((word.text, word.xc))
            columns.append((word, []))
        elif word.size >= size - 0.5 and word.text.startswith("t"):
            columns.append((word, []))
        elif columns and columns[-1][0].text.startswith("t"):
            columns[-1][1].append(word)
        else:
            raise view.error(f"{word.text!r} labels no column", headings.page)
    for t, labels in columns:
        if not t.text.startswith("t"):
            continue
        label = (t.text[1:] + " " + " ".join(word.text for word in labels)).strip()
        if not label:
            raise view.error(f"no label for the column at x={t.x0:.0f}", headings.page)
        x0, x1 = t.x0, max([t.x1, *(word.x1 for word in labels)])
        anchors.append((label, (x0 + x1) / 2))
    return Columns(anchors=tuple(anchors), tolerance=16)


def _values(
    view: DocumentView, row: LineMatch, columns: Columns[str]
) -> dict[str, Sourced[Decimal]]:
    """The row's numbers after its round, by column."""
    values: dict[str, Sourced[Decimal]] = {}
    for word in row.line.words_in(row.found.end("round"), len(row.line.text)):
        column = columns.assign(word)
        if column is None:
            raise view.error(f"{word.text!r} is under no column", row.line.page)
        if column in values:
            raise view.error(f"two values under {column!r}", row.line.page)
        parser = _decimal if column in NAMED else _seconds
        values[column] = view.read(row.line.page, [word], parser, f"athlete-row.{column}")
    return values


def _point(
    view: DocumentView, page: int, label: str, discipline: Discipline, sex: Sex
) -> tuple[TimingPoint, Decimal | None]:
    """The point a column label times to (``end`` is the finish), and the distance its time
    starts from: ``None`` for the gun."""
    finish = discipline.finish()
    if label == "end":
        return finish, None
    hurdle = HURDLE.fullmatch(label)
    if hurdle is not None:
        return discipline.touchdown(sex, int(hurdle["number"])), None
    stretch = STRETCH.fullmatch(label)
    if stretch is not None:
        length, number = Decimal(stretch["length"]), int(stretch["number"])
        label = f"{length * (number - 1)}-{length * number}"
    found = SPAN.fullmatch(label)
    if found is None:
        raise view.error(f"unknown column {label!r}", page)
    end = Decimal(found["end"])
    start = Decimal(found["start"]) if found["start"] else None
    return (finish if end == finish.distance else TimingPoint.at(end)), (start or None)


def _entry(view: DocumentView, row: _Row, discipline: Discipline, sex: Sex) -> EntryReading:
    values = dict(row.values)
    page = row.row.line.page
    reaction = values.pop("RT", None)
    values.pop("Diff.", None)
    result, splits, segments = None, [], []
    for label, value in values.items():
        point, start = _point(view, page, label, discipline, sex)
        if start is None and point == discipline.finish():
            result = value
        elif start is None:
            splits.append(SplitReading(point=point, time=value))
        else:
            segments.append(SegmentReading(start=TimingPoint.at(start), end=point, time=value))
    if row.intervals is not None:
        segments.extend(_intervals(view, row, discipline, sex))
    if result is None:
        raise view.error(f"no finish time in {row.row.line.text!r}", page)
    return EntryReading(
        row=row.row.span(),
        name=row.named.read("name", _name),
        country=row.named.read("country", parse.country),
        result=Sourced[Result](
            value=parse.result(str(result.value)), source=result.source, method=result.method
        ),
        reaction_time=reaction,
        splits=tuple(sorted(splits, key=lambda split: split.point.order)),
        segments=tuple(segments),
    )


def _intervals(
    view: DocumentView, row: _Row, discipline: Discipline, sex: Sex
) -> list[SegmentReading]:
    """The times between touchdowns: each under the touchdown (or the finish) it ends at, and
    starting at the touchdown before."""
    assert row.intervals is not None
    line = row.intervals
    segments = []
    for word in line.words:
        label = row.columns.assign(word) or ""
        hurdle = HURDLE.fullmatch(label)
        if label == "end":
            number = discipline.barriers[sex].count + 1
        elif hurdle is not None and int(hurdle["number"]) > 1:
            number = int(hurdle["number"])
        else:
            raise view.error(f"{word.text!r} ends at no barrier", line.page)
        end, _ = _point(view, line.page, label, discipline, sex)
        segments.append(
            SegmentReading(
                start=discipline.touchdown(sex, number - 1),
                end=end,
                time=view.read(line.page, [word], _seconds, f"intervals.{label}"),
            )
        )
    return segments
