"""How runners in an event typically spread their time over its distance, for the replay to
move them between their splits (see ``docs/replay-positions.md``).

An event's *shape* is, at each of its finest timing points, the median share of the race (from
leaving the blocks to the finish) a runner has used up on reaching it. Events up to 800 m have
one, built from every clean run timed at those points; above, a typical race means little (one
is run hard throughout, the next is slow until the last lap). The 400 m, timed every 50 m at
best, spreads its first 50 m as the 200 m does.
"""

from collections.abc import Iterable
from itertools import pairwise
from statistics import median

from splits.model import Dataset, Status
from splits.publish.site_schema import EventData, Shape, ShapePoint

SHAPE_UP_TO = 800
"""Metres: the longest event with a shape."""
BLOCKS_UP_TO = 400
"""Metres: the longest event started from blocks, where reaction times are measured."""
MIN_RUNS = 30
"""Runs timed at a set of points before it can be an event's finest."""
START_FROM = {"400m": "200m"}
"""Disciplines whose first stretch is spread as another's, which is timed more finely there."""


def typical_reactions(dataset: Dataset) -> dict[str, float]:
    """The median published reaction time of each event started from blocks."""
    races = {race.id: race for race in dataset.races}
    distance = {d.id: float(d.distance) for d in dataset.disciplines}
    reactions: dict[str, list[float]] = {}
    for perf in dataset.performances:
        race = races[perf.race]
        if perf.reaction_time is None or perf.reaction_time.value <= 0:
            continue
        if distance[race.key.discipline] > BLOCKS_UP_TO:
            continue
        reactions.setdefault(race.key.event, []).append(float(perf.reaction_time.value))
    return {event: round(median(values), 3) for event, values in reactions.items()}


def event_shapes(
    dataset: Dataset, events: Iterable[EventData], reactions: dict[str, float]
) -> dict[str, Shape]:
    """The shape of every event up to 800 m with enough runs timed at its finest points."""
    distance: dict[str, float] = {d.id: float(d.distance) for d in dataset.disciplines}
    reaction_of: dict[str, float] = {
        perf.id: float(perf.reaction_time.value)
        for perf in dataset.performances
        if perf.reaction_time is not None and perf.reaction_time.value > 0
    }
    by_event = {data.event: data for data in events}
    shapes: dict[str, Shape] = {}
    for event, data in by_event.items():
        finish = distance[data.discipline]
        if finish > SHAPE_UP_TO:
            continue
        typical = reactions.get(event, 0.0) if finish <= BLOCKS_UP_TO else 0.0
        shape = shape_of(data, finish, reaction_of, typical)
        if shape is not None:
            shapes[event] = shape
    for event, shape in list(shapes.items()):
        data = by_event[event]
        borrowed = START_FROM.get(data.discipline)
        source = shapes.get(f"{borrowed}-{data.sex}") if borrowed else None
        if source is not None:
            shapes[event] = with_start(shape, source)
    return shapes


def shape_of(
    data: EventData, finish: float, reaction_of: dict[str, float], typical: float
) -> Shape | None:
    """The median share of the race at each of the event's finest points, or None if too few
    runs were timed at any set of points. A runner whose reaction was not published leaves the
    blocks at the ``typical`` one."""
    distances = [point.distance for point in data.points]
    runs: list[tuple[float, float, dict[float, float]]] = []
    for perf in data.performances:
        if perf.status != Status.FINISHED.value or perf.time is None:
            continue
        leave = reaction_of.get(perf.id, typical)
        timed = {
            distances[i]: value
            for i, value in enumerate(perf.splits)
            if value is not None and i not in perf.suspect and distances[i] < finish
        }
        times = [timed[d] for d in sorted(timed)] + [perf.time]
        # A run that goes backwards, or reaches a point before leaving the blocks, is misread.
        if not timed or times[0] <= leave or any(a >= b for a, b in pairwise(times)):
            continue
        runs.append((leave, perf.time, timed))
    grid = _finest(runs)
    if grid is None:
        return None
    on_grid = [run for run in runs if grid <= run[2].keys()]
    points: list[ShapePoint] = []
    for d in sorted(grid):
        share = median((timed[d] - leave) / (end - leave) for leave, end, timed in on_grid)
        # Medians of rising shares rise too, but may tie: a tie adds nothing to the shape.
        if not points or share > points[-1].share:
            points.append(ShapePoint(distance=d, share=round(share, 5)))
    points.append(ShapePoint(distance=finish, share=1.0))
    return Shape(points=points, runs=len(on_grid))


def _finest(runs: list[tuple[float, float, dict[float, float]]]) -> frozenset[float] | None:
    """The most points that at least ``MIN_RUNS`` runs were all timed at (the most runs, among
    sets of as many points)."""
    candidates = {frozenset(timed) for _, _, timed in runs}
    best: tuple[int, int, frozenset[float]] | None = None
    for grid in candidates:
        count = sum(grid <= timed.keys() for _, _, timed in runs)
        if count >= MIN_RUNS and (best is None or (len(grid), count) > best[:2]):
            best = (len(grid), count, grid)
    return best[2] if best else None


def with_start(shape: Shape, source: Shape) -> Shape:
    """``shape`` with its first stretch spread as ``source`` spreads the same stretch."""
    first = shape.points[0]
    at = {point.distance: point.share for point in source.points}
    if first.distance not in at:
        return shape
    start = [
        ShapePoint(distance=p.distance, share=round(first.share * p.share / at[first.distance], 5))
        for p in source.points
        if p.distance < first.distance
    ]
    return Shape(points=start + shape.points, runs=shape.runs)
