from collections.abc import Sequence

from splits.model import PointKind
from splits.publish.shapes import MIN_RUNS, shape_of, with_start
from splits.publish.site_schema import EventData, EventPerformance, Point, Shape, ShapePoint


def _event(runs: Sequence[Sequence[float | None]], distances: list[float]) -> EventData:
    """A 200 m event whose runs have the given splits (the last value is the finish)."""
    return EventData(
        event="200m-men",
        discipline="200m",
        sex="men",
        points=[
            Point(key=f"{d:g}m", kind=PointKind.DISTANCE, distance=d, hurdle=None, label=f"{d:g}m")
            for d in distances
        ],
        performances=[
            EventPerformance(
                id=f"race-{i // 8}/200m-men/final/runner-{i}",
                race=f"race-{i // 8}/200m-men/final",
                athlete=f"runner-{i}",
                place=None,
                status="finished",
                time=run[-1],
                format=None,
                splits=list(run[:-1]),
                suspect=[],
            )
            for i, run in enumerate(runs)
        ],
    )


def test_the_shape_is_the_median_share_at_the_finest_points_timed_often_enough() -> None:
    # Runs timed every 50 m, and too few every 25 m to be the finest points.
    distances = [25.0, 50.0, 100.0, 150.0]
    fine: list[list[float | None]] = [
        [2.0 + i * 0.01, 3.5, 6.0, 8.5, 11.0] for i in range(MIN_RUNS - 1)
    ]
    coarse = [[None, 3.5 + k, 6.0 + k, 8.5 + k, 11.0 + k] for k in (0.0, 0.5, 1.0)]
    shape = shape_of(_event(fine + coarse, distances), 200.0, {}, 0.15)
    assert shape is not None
    assert [p.distance for p in shape.points] == [50.0, 100.0, 150.0, 200.0]
    assert shape.runs == MIN_RUNS + 2
    # Leaving the blocks at the typical 0.15 s: (3.5 - 0.15) / (11.0 - 0.15).
    assert abs(shape.points[0].share - 3.35 / 10.85) < 1e-4
    assert shape.points[-1].share == 1.0


def test_no_shape_from_too_few_runs_or_misread_ones() -> None:
    few = [[3.5, 6.0, 8.5, 11.0]] * (MIN_RUNS - 1)
    assert shape_of(_event(few, [50.0, 100.0, 150.0]), 200.0, {}, 0.15) is None
    # A run reaching 100 m before 50 m is misread, and does not count.
    backwards = [[6.5, 6.0, 8.5, 11.0]]
    assert shape_of(_event(few + backwards, [50.0, 100.0, 150.0]), 200.0, {}, 0.15) is None


def test_a_first_stretch_is_spread_as_a_finer_event_spreads_it() -> None:
    four = Shape(
        points=[ShapePoint(distance=50.0, share=0.14), ShapePoint(distance=400.0, share=1.0)],
        runs=40,
    )
    two = Shape(
        points=[
            ShapePoint(distance=25.0, share=0.18),
            ShapePoint(distance=50.0, share=0.3),
            ShapePoint(distance=200.0, share=1.0),
        ],
        runs=40,
    )
    started = with_start(four, two)
    assert [p.distance for p in started.points] == [25.0, 50.0, 400.0]
    assert abs(started.points[0].share - 0.14 * 0.18 / 0.3) < 1e-6
