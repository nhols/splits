"""The split grid of OMEGA-produced race analyses (Diamond League and Olympic ORIS reports).

Timing points are printed as labelled columns, in one or more *tiers* (rows of labels)::

         10m    20m   ...   100m                  tier 1
        110m   120m   ...   190m   Finish         tier 2

Under each athlete, each tier has a line of cumulative times with ranks, then a line of segment
times, each printed under the point it ends at. Values are assigned to the nearest label of
their tier. Diamond League reports until 2025 do not label the finish column: it follows the
last label, or starts a new tier when the last tier is full. A grid of one label (an 800 m
timed at 400 m alone) has no spacing to place an unlabelled finish by, and gives none.

Diamond League reports of 2016 and 2017 label some races' points by the laps to go
(``3.75 laps to go`` ... ``1/4 lap to go``): so many laps of the track before the finish. A
steeplechase lap is shorter than the track's, by an amount that depends on where the water jump
is, so a steeplechase's laps to go are not placed.

When the timing missed an athlete at every other point, only the finish is printed, in the
finish's tier and column: a lone time equal to the athlete's result is that finish.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise
from statistics import median

from splits.formats import parse
from splits.formats.base import ReadContext, SegmentReading, SplitReading
from splits.formats.common import time_tokens
from splits.model import DisciplineKind, PointKind, Setting, TimingPoint
from splits.pdf.layout import Columns, DocumentView, Line

LABEL = re.compile(
    r"(?P<laps>\d+(?:\.\d+)?|\d/\d) ?laps? ?to ?go"
    r"|(?P<distance>\d+)(?P<unit>m*)(?![\d.:])|Hurdle ?(?P<hurdle>\d+)|(?P<finish>Finish)"
)
"""A timing point's label. A distance whose unit is misprinted (``30`` or ``175mm`` among
``10m`` ... ``90m``) is read as metres, and noted."""
LABEL_LINE = re.compile(rf"(?:(?:{LABEL.pattern}) ?)+")
LAP = {Setting.OUTDOOR: Decimal(400), Setting.INDOOR: Decimal(200)}
"""The length of a lap of the track, by where the race is run."""
ONE_COLUMN_TOLERANCE = 20.0
"""Points. How far a value may be from the label of a grid of one column, which has no spacing
to measure: the tolerance of the most closely spaced grids."""


@dataclass(frozen=True)
class TieredGrid:
    tiers: tuple[Columns[TimingPoint], ...]
    order: tuple[TimingPoint, ...]
    """Every point in race order, for finding where a segment starts."""
    notes: tuple[str, ...] = ()
    """Labels the reader had to interpret: a distance printed without its unit, or with it
    twice."""

    @classmethod
    def find(
        cls,
        view: DocumentView,
        lines: list[Line],
        context: ReadContext,
        *,
        unlabelled_finish_after: int | None = None,
    ) -> "TieredGrid | None":
        """The grid whose labels are the first run of label lines in ``lines``.

        ``unlabelled_finish_after``: for layouts that do not label the finish, the number of
        columns in a full tier.
        """
        start = next((i for i, line in enumerate(lines) if _is_label_line(line)), None)
        if start is None:
            return None
        rows: list[list[tuple[TimingPoint, float]]] = []
        notes: list[str] = []
        for line in lines[start:]:
            if not _is_label_line(line):
                break
            row = []
            for found in LABEL.finditer(line.text):
                words = line.words_in(*found.span())
                try:
                    point = _point(found, context)
                except ValueError as error:
                    raise view.error(str(error), line.page) from error
                if found["distance"] and found["unit"] != "m":
                    notes.append(f"timing point label {found[0]!r} read as {point.label}")
                row.append((point, sum(w.xc for w in words) / len(words)))
            rows.append(row)

        first_row = [x for _, x in rows[0]]
        if len(first_row) < 2:
            if len(rows) > 1:
                raise view.error("cannot measure column spacing from one label", lines[start].page)
            only = Columns(tuple(rows[0]), tolerance=ONE_COLUMN_TOLERANCE)
            return cls((only,), (rows[0][0][0],), tuple(notes))
        pitch = median(b - a for a, b in pairwise(first_row))
        finish = context.discipline.finish()
        labelled = any(point == finish for row in rows for point, _ in row)
        if unlabelled_finish_after is not None and not labelled:
            if len(rows[-1]) < unlabelled_finish_after:
                rows[-1].append((finish, rows[-1][-1][1] + pitch))
            else:
                rows.append([(finish, first_row[0])])

        order = tuple(point for row in rows for point, _ in row)
        if any(a.order >= b.order for a, b in pairwise(order)):
            raise view.error("timing point labels are not in race order", lines[start].page)
        tiers = tuple(Columns(tuple(row), tolerance=pitch * 0.4) for row in rows)
        return cls(tiers, order, tuple(notes))

    def _untimed_first_stretch(self) -> bool:
        return _untimed_first_stretch_of(self.order)

    def read(
        self, view: DocumentView, band: list[Line], result: str | None = None
    ) -> tuple[tuple[SplitReading, ...], tuple[SegmentReading, ...]]:
        """Read an athlete's split lines. Each cumulative line starts a tier; a segment line
        belongs to the tier of the cumulative line above it, or starts one if there is none.
        ``result`` is the athlete's result as printed, to recognise a finish printed alone."""
        finish_tier = next(
            (
                i
                for i, columns in enumerate(self.tiers)
                if any(point.kind is PointKind.FINISH for point, _ in columns.anchors)
            ),
            None,
        )
        splits: dict[TimingPoint, SplitReading] = {}
        segments: dict[TimingPoint, SegmentReading] = {}
        tier, previous_was_cumulative = -1, False
        for line in band:
            pairs = time_tokens(line)
            # Cumulative times are ranked, segment times are not; a document may leave out a
            # rank or two, or print a meaningless one ("(=0)"): those ranks are unknown.
            ranked = sum(rank is not None for _, rank in pairs)
            cumulative = ranked * 2 > len(pairs)
            if ranked and not cumulative:
                raise view.error(
                    f"a line mixes ranked and unranked times: {line.text!r}", line.page
                )
            if cumulative or not previous_was_cumulative:
                tier += 1
            if (
                cumulative
                and finish_tier is not None
                and len(pairs) == 1
                and pairs[0][0].text == result
            ):
                tier = finish_tier
            previous_was_cumulative = cumulative
            if tier >= len(self.tiers):
                raise view.error(
                    f"more split lines than labelled tiers at {line.text!r}", line.page
                )
            for time_word, rank_word in pairs:
                point = self.tiers[tier].assign(time_word)
                if point is None:
                    raise view.error(f"{time_word.text} is under no label", line.page)
                if cumulative:
                    if point in splits:
                        raise view.error(f"two cumulative times at {point.label}", line.page)
                    splits[point] = SplitReading(
                        point=point,
                        time=view.read(line.page, [time_word], parse.seconds, "cumulative.time"),
                        rank=view.read(line.page, [rank_word], parse.rank, "cumulative.rank")
                        if rank_word is not None and rank_word.text not in ("(0)", "(=0)")
                        else None,
                    )
                else:
                    if point in segments:
                        raise view.error(f"two segment times ending at {point.label}", line.page)
                    index = self.order.index(point)
                    if index == 0 and self._untimed_first_stretch():
                        continue  # from a point the grid does not time: its start is unknown
                    segments[point] = SegmentReading(
                        start=self.order[index - 1] if index else TimingPoint.start(),
                        end=point,
                        time=view.read(line.page, [time_word], parse.seconds, "segment.time"),
                    )
        return (
            tuple(sorted(splits.values(), key=lambda split: split.point.order)),
            tuple(sorted(segments.values(), key=lambda segment: segment.end.order)),
        )


def _is_label_line(line: Line) -> bool:
    """Whether ``line`` holds only timing point labels, at least one of them printed in full (a
    line of bare numbers is not a grid's)."""
    return LABEL_LINE.fullmatch(line.text) is not None and any(
        found["unit"] == "m" or found["hurdle"] or found["finish"] or found["laps"]
        for found in LABEL.finditer(line.text)
    )


def _untimed_first_stretch_of(order: tuple[TimingPoint, ...]) -> bool:
    """Whether the grid's first point lies further from the start than its points from each
    other (a 1000 m timed from 200 m every 100 m): the segment printed under it is then the
    last 100 m before it, from a point the grid does not time, not the stretch from the gun."""
    if len(order) < 2:
        return False
    first, second = order[0].distance, order[1].distance
    return first > (second - first) * Decimal("1.01")


def _point(found: re.Match[str], context: ReadContext) -> TimingPoint:
    """The point a label names. A label at the race's distance (European Athletics prints
    ``400m`` over the last column of a 400 m) is the finish."""
    if found["distance"]:
        distance = parse.seconds(found["distance"])
        finish = context.discipline.finish()
        return finish if distance == finish.distance else TimingPoint.at(distance)
    if found["hurdle"]:
        return context.discipline.hurdle(context.spec.race.sex, int(found["hurdle"]))
    if found["laps"]:
        return _laps_to_go(found["laps"], context)
    return context.discipline.finish()


def _laps_to_go(text: str, context: ReadContext) -> TimingPoint:
    """The point ``text`` laps before the finish (``3.75``, ``1``, ``3/4``)."""
    if context.discipline.kind is DisciplineKind.STEEPLECHASE:
        raise ValueError(
            f"timed at {text} laps to go, which a steeplechase lap does not place in metres"
        )
    numerator, _, denominator = text.partition("/")
    laps = Decimal(numerator) / Decimal(denominator) if denominator else Decimal(numerator)
    lap = LAP[context.spec.setting or context.competition.setting]
    return TimingPoint.at(context.discipline.distance - laps * lap)
