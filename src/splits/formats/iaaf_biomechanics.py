"""IAAF biomechanics reports: split times measured from video, Berlin 2009.

At the 2009 World Championships a German research team filmed the sprint and hurdles races
from the stands and published, through the IAAF, tables of reaction times and split times.
One table covers a round (or two) of an event; each athlete has a row per race, the first
with their name::

    200m Men                                                          Semifinal/Final
    Round Wind  RT     t      t     Diff.  t        t     t      t       t        t
                       200m   100m         100-200m 150m  0-50m  50-100m 100-150m 150-200m
    Bolt Usain JAM  Fi  -0,3 0,133 19,19 9,92 -0,65 9,27  14,44 5,60   4,32    4,52     4,75
                    Ht 1 0,0 0,177 20,08 10,14 -0,20 9,94 14,86 5,74   4,40    4,72     5,22

The 100m has a table of the medal winners, each with every round, and beneath it the other
finalists (``100m Men Medal winners``). Values are assigned to columns by position. A time to
a distance (``150m``, and ``0-50m``, timed from the gun) is a split; a time between two
distances is a segment. The report does not print the day of each race.
"""

import re
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
from splits.model import PersonName, Result, Round, Sourced, TimingPoint
from splits.model.ids import format_id
from splits.pdf.layout import Columns, DocumentView, Line, LineMatch

TABLE = re.compile(
    r"(?P<discipline>\d+m(?: Hurdles)?) (?P<sex>Men|Women) (?P<rounds>Medal winners|[A-Za-z/]+)"
)
COLUMNS = re.compile(r"Round Wind RT (?:t |Diff\. )+(?:t|Diff\.)")
HEADINGS = frozenset({"Round", "Wind", "RT", "t", "Diff."})
ATHLETE = re.compile(
    r"(?P<name>[A-Z][\w'-]+(?: [A-Z][\w'-]+)+) (?P<country>[A-Z]{3}) (?P<round>Fi|Ht \d)\b"
)
LABEL = re.compile(r"(?:(?P<start>\d+)-)?(?P<end>\d+)m?")
ROUNDS = {"Fi": Round.FINAL}


def _has_final(rounds: str) -> bool:
    """Whether a table's rounds (``Semifinal/Final``, ``Medal winners``) include the final."""
    return "Final" in rounds or rounds == "Medal winners"


def _rounds(text: str) -> Round:
    return Round.FINAL if _has_final(text) else parse.round_name(text)


def _decimal(text: str) -> Decimal:
    """A number with a decimal comma: ``-0,3``, ``0,133``, ``19,19``."""
    return parse.signed_decimal(text.replace(",", "."))


def _seconds(text: str) -> Decimal:
    return parse.seconds(text.replace(",", "."))


def _name(text: str) -> PersonName:
    """``Bolt Usain``: the family name first, the given name last."""
    *family, given = text.split()
    return PersonName(given=given, family=" ".join(family))


class IaafBiomechanics(Format):
    kind = DocumentKind.ANALYSIS
    id = format_id("iaaf-biomechanics")
    version = "1.1.0"
    name = "IAAF biomechanics report"
    publisher = "IAAF, with the German Athletics Federation (DLV)"
    description = (
        "Reaction and split times measured from video by the biomechanics research project at "
        "the 2009 World Championships in Berlin, for every sprint and hurdles final."
    )

    def read(self, view: DocumentView, context: ReadContext) -> DocumentReading:
        declared = context.spec.race.round
        marker = next((mark for mark, round_ in ROUNDS.items() if round_ is declared), None)
        if marker is None:
            raise view.error(f"reads finals only, not a {declared}")
        lines = [line for page in view.pages for line in view.lines(page.number)]
        table = view.find(lines, TABLE, "table")
        if table is None or not _has_final(table["rounds"] or ""):
            raise view.error("no table of a final, such as '200m Men Semifinal/Final'")
        start = lines.index(table.line)
        header = next((i for i in range(start, len(lines)) if _is_headings(lines[i])), None)
        if header is None:
            raise view.error("no column headings (Round Wind RT t ...)", table.line.page)
        below = lines[header + 1] if header + 1 < len(lines) else None
        columns = _columns(view, lines[header], below)

        finish = context.discipline.finish()
        entries, wind = [], None
        for line in lines[header + 1 :]:
            if _is_headings(line):
                continue  # the headings repeat for the next block of the table
            row = view.match(line, ATHLETE, "athlete-row")
            if row is None or row["round"] != marker:
                continue
            values = _values(view, row, columns)
            row_wind = values.pop("Wind", None)
            wind = wind or row_wind
            entries.append(_entry(view, row, values, finish.distance))
        if not entries:
            raise view.error(
                f"no rows for the final ({marker}) in {table.line.text!r}", table.line.page
            )
        return DocumentReading(
            document=view.document,
            format=self.id,
            format_version=self.version,
            pages=len(view.pages),
            title=Sourced[str](value=table.line.text, source=table.span(), method="table"),
            heading=HeadingReading(
                discipline=table.read("discipline", parse.discipline),
                sex=table.read("sex", parse.sex),
                round=table.read("rounds", _rounds),
                heat=None,
            ),
            date=None,
            wind=wind,
            entries=tuple(entries),
        )


def _is_headings(line: Line) -> bool:
    """Whether a line heads the table's columns: ``Round Wind RT t t Diff. ...``, and perhaps
    the subscripts that label each ``t``."""
    headings = [word for word in line.words if word.text in HEADINGS]
    if not headings or not COLUMNS.fullmatch(" ".join(word.text for word in headings)):
        return False
    size = min(word.size for word in headings)
    return all(word.size < size for word in line.words if word.text not in HEADINGS)


def _columns(view: DocumentView, headings: Line, below: Line | None) -> Columns[str]:
    """Column anchors: Wind, RT and Diff. by their headings; each time column (``t``) by its
    subscript (``t`` with ``20m`` or ``0-50m`` set small after it), which is printed a little
    lower, on the headings' line or just below it."""
    size = min(word.size for word in headings.words if word.text in HEADINGS)
    labels = [word for word in headings.words if word.text not in HEADINGS]
    if below is not None and all(word.size < size for word in below.words):
        labels.extend(below.words)
    anchors: list[tuple[str, float]] = []
    named = [word for word in headings.words if word.text in ("Wind", "RT", "Diff.")]
    anchors.extend((word.text, word.xc) for word in named)
    for column in (word for word in headings.words if word.text == "t"):
        label = min(labels, key=lambda word: abs(word.x0 - column.x1), default=None)
        if label is None or abs(label.x0 - column.x1) > 2:
            raise view.error(f"no label for the column at x={column.x0:.0f}", headings.page)
        anchors.append((label.text, label.xc))
    return Columns(anchors=tuple(anchors), tolerance=16)


def _values(
    view: DocumentView, row: LineMatch, columns: Columns[str]
) -> dict[str, Sourced[Decimal]]:
    """The row's numbers after its round, by column."""
    after = row.found.end("round")
    values: dict[str, Sourced[Decimal]] = {}
    for word in row.line.words_in(after, len(row.line.text)):
        if word.text in (row["round"] or "").split():
            continue
        column = columns.assign(word)
        if column is None:
            raise view.error(f"{word.text!r} is under no column", row.line.page)
        parser = _decimal if column in ("Wind", "RT", "Diff.") else _seconds
        values[column] = view.read(row.line.page, [word], parser, f"athlete-row.{column}")
    return values


def _entry(
    view: DocumentView, row: LineMatch, values: dict[str, Sourced[Decimal]], distance: Decimal
) -> EntryReading:
    reaction = values.pop("RT", None)
    values.pop("Diff.", None)
    result, splits, segments = None, [], []
    for label, value in values.items():
        found = LABEL.fullmatch(label)
        if found is None:
            raise view.error(f"unknown column {label!r}", row.line.page)
        end = Decimal(found["end"])
        start = Decimal(found["start"]) if found["start"] else None
        if end == distance and start is None:
            result = value
        elif start is None or start == 0:
            splits.append(SplitReading(point=TimingPoint.at(end), time=value))
        else:
            finish = end == distance
            segments.append(
                SegmentReading(
                    start=TimingPoint.at(start),
                    end=TimingPoint.finish(end) if finish else TimingPoint.at(end),
                    time=value,
                )
            )
    if result is None:
        raise view.error(f"no {distance}m time for {row['name']!r}", row.line.page)
    return EntryReading(
        row=row.span(),
        name=row.read("name", _name),
        country=row.read("country", parse.country),
        result=Sourced[Result](
            value=parse.result(str(result.value)), source=result.source, method=result.method
        ),
        reaction_time=reaction,
        splits=tuple(sorted(splits, key=lambda split: split.point.distance)),
        segments=tuple(segments),
    )
