"""The data-quality checks.

Each check says in plain words what it verifies. The thresholds are deliberately loose: a
flag should mean "look at this", not "this is unusual".
"""

from collections import defaultdict
from collections.abc import Iterator
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from itertools import pairwise
from statistics import median

from splits.checks.framework import Finding, Records, Series, check
from splits.model import (
    AthleteId,
    PerformanceId,
    PointKind,
    Severity,
    Split,
    Status,
    TimingPoint,
)

ROUNDING = Decimal("0.01")
"""Printed times are rounded to hundredths, so values derived from two of them may differ from
a printed value by this much without either being wrong."""

MAX_SPEED = Decimal("12.6")
"""Metres per second. The fastest 10 m ever timed in a race is about 0.81 s (12.4 m/s)."""

OUTLIER_Z = 5.0
OUTLIER_MIN_SAMPLE = 20


def _fmt(seconds: Decimal) -> str:
    return f"{seconds:.2f}"


def _series_points(series_splits: tuple[Split, ...]) -> list[Split]:
    return [split for split in series_splits if split.point.kind is not PointKind.FINISH]


@check(
    "split-order",
    severity=Severity.ERROR,
    suspect=True,
    title="Splits increase along the race",
    explanation=(
        "An athlete's cumulative time must be later at each timing point than at the one "
        "before. A split that is not is wrong, or belongs to another point."
    ),
)
def split_order(records: Records) -> Iterator[Finding]:
    for series in records.series:
        splits = series.splits
        for before, after in pairwise(splits):
            if after.time.value <= before.time.value:
                yield Finding(
                    after.id,
                    "time",
                    f"{after.point.label} split {_fmt(after.time.value)} is not later than the "
                    f"{before.point.label} split {_fmt(before.time.value)}",
                )


@check(
    "split-before-finish",
    severity=Severity.ERROR,
    suspect=True,
    title="Splits come before the finish",
    explanation=(
        "Every split before the line must be earlier than the athlete's official finishing time."
    ),
)
def split_before_finish(records: Records) -> Iterator[Finding]:
    for series in records.series:
        finish = records.finish_time(series.performance)
        if finish is None:
            continue
        for split in _series_points(series.splits):
            if split.time.value >= finish:
                yield Finding(
                    split.id,
                    "time",
                    f"{split.point.label} split {_fmt(split.time.value)} is not earlier than the "
                    f"finishing time {_fmt(finish)}",
                )


@check(
    "finish-matches-result",
    severity=Severity.ERROR,
    suspect=True,
    title="Timing at the line matches the result",
    explanation=(
        "When a document times athletes at the finish line as well as giving their result, "
        "the two must be the same, to the decimals the time at the line is printed with "
        "(4:07.6 for a result of 4:07.64). An athlete who did not start or did not finish "
        "cannot have a time at the line. A disqualified athlete usually crossed it all the "
        "same (after a lane infringement, say), and has no result to compare the time with, "
        "so it is not checked."
    ),
)
def finish_matches_result(records: Records) -> Iterator[Finding]:
    for series in records.series:
        status = series.performance.status
        if status is Status.DISQUALIFIED:
            continue  # usually crossed the line all the same, with no result to compare
        for split in series.splits:
            if split.point.kind is not PointKind.FINISH:
                continue
            finish = records.finish_time(series.performance)
            if finish is None:
                missed = "start" if status is Status.DID_NOT_START else "finish"
                yield Finding(
                    split.id, "time", f"a time at the line for an athlete who did not {missed}"
                )
            elif not _same_time(split.time.value, finish):
                yield Finding(
                    split.id,
                    "time",
                    f"time at the line {_fmt(split.time.value)} differs from the result "
                    f"{_fmt(finish)}",
                )


def _same_time(printed: Decimal, exact: Decimal) -> bool:
    """Whether ``printed`` is ``exact``, or ``exact`` cut or rounded to fewer decimals."""
    exponent = printed.as_tuple().exponent
    if printed == exact or not isinstance(exponent, int):
        return printed == exact
    exact_exponent = exact.as_tuple().exponent
    if not isinstance(exact_exponent, int) or exponent <= exact_exponent:
        return False
    unit = Decimal(1).scaleb(exponent)
    return printed in (exact.quantize(unit, ROUND_DOWN), exact.quantize(unit, ROUND_HALF_UP))


def _rounding(value: Decimal) -> Decimal:
    """How far a printed time may be from the true time: half its last digit, or a whole tenth
    for a time printed to the tenth, which timing systems cut rather than round (4:07.64 is
    printed 4:07.6, 3:48.08 as 3:48.0). Zero, the start, is exact."""
    exponent = value.as_tuple().exponent
    if value == 0 or not isinstance(exponent, int):
        return Decimal(0)
    return Decimal(1).scaleb(exponent) if exponent >= -1 else Decimal(5).scaleb(exponent - 1)


@check(
    "segment-matches-splits",
    severity=Severity.ERROR,
    suspect=True,
    title="Printed segment times agree with the splits",
    explanation=(
        "Documents print both cumulative times and the time for each segment between timing "
        "points. Each printed segment must equal the difference of the cumulative times at "
        "its ends, give or take the rounding of the times involved (a hundredth, or up to a "
        "tenth each for times cut to the tenth)."
    ),
)
def segment_matches_splits(records: Records) -> Iterator[Finding]:
    for series in records.series:
        at: dict[TimingPoint, Decimal] = {TimingPoint.start(): Decimal(0)}
        at.update({split.point: split.time.value for split in series.splits})
        finish = records.finish_time(series.performance)
        for segment in series.segments:
            start = at.get(segment.start)
            end = at.get(segment.end)
            if segment.end.kind is PointKind.FINISH and end is None:
                end = finish
            if start is None or end is None:
                continue
            expected = end - start
            slack = max(ROUNDING, _rounding(segment.time.value) + _rounding(start) + _rounding(end))
            if abs(segment.time.value - expected) > slack:
                yield Finding(
                    segment.id,
                    "time",
                    f"printed {segment.start.label}–{segment.end.label} segment "
                    f"{_fmt(segment.time.value)} differs from the splits' {_fmt(expected)}",
                )


@check(
    "segment-speed",
    severity=Severity.ERROR,
    suspect=True,
    title="Speeds are humanly possible",
    explanation=(
        "Between consecutive timing points an athlete's average speed cannot exceed "
        f"{MAX_SPEED} m/s; the fastest 10 m ever timed in a race is about 12.4 m/s."
    ),
)
def segment_speed(records: Records) -> Iterator[Finding]:
    for series in records.series:
        points: list[tuple[TimingPoint, Decimal, Split | None]] = [
            (TimingPoint.start(), Decimal(0), None)
        ]
        points += [
            (split.point, split.time.value, split) for split in _series_points(series.splits)
        ]
        finish = records.finish_time(series.performance)
        if finish is not None:
            discipline = records.discipline_of(series.performance)
            points.append((discipline.finish(), finish, None))
        for (a, time_a, split_a), (b, time_b, split_b) in pairwise(points):
            elapsed = time_b - time_a
            if elapsed <= 0:
                continue  # reported by split-order / split-before-finish
            speed = (b.distance - a.distance) / elapsed
            if speed > MAX_SPEED:
                culprit = split_b or split_a
                assert culprit is not None
                yield Finding(
                    culprit.id,
                    "time",
                    f"{a.label}–{b.label} would take {_fmt(elapsed)}, an average of "
                    f"{speed:.1f} m/s",
                )


def _outlier_scores(
    records: Records,
) -> Iterator[tuple[Series, Decimal, dict[str, float], dict[str, float]]]:
    """For each finished series: its finishing time, how far each split's share of that time is
    from the typical share at its timing point (in robust standard deviations), and the typical
    share, by split ID. Only timing points with enough runs to compare are scored."""

    def key(race_key: object, setting: object, point: TimingPoint) -> tuple[object, ...]:
        return (race_key, setting, point.kind, point.distance)

    # The typical share of the finishing time used at each timing point of each event.
    shares: dict[tuple[object, ...], list[float]] = defaultdict(list)
    finished = [s for s in records.series if records.finish_time(s.performance) is not None]
    for series in finished:
        race = records.race_of(series.performance)
        finish = records.finish_time(series.performance)
        assert finish is not None
        for split in _series_points(series.splits):
            event = (race.key.discipline, race.key.sex)
            shares[key(event, race.setting, split.point)].append(float(split.time.value / finish))
    typical: dict[tuple[object, ...], tuple[float, float]] = {}
    for group, values in shares.items():
        if len(values) >= OUTLIER_MIN_SAMPLE:
            centre = median(values)
            spread = 1.4826 * median(abs(value - centre) for value in values)
            if spread > 0:
                typical[group] = (centre, spread)

    for series in finished:
        race = records.race_of(series.performance)
        finish = records.finish_time(series.performance)
        assert finish is not None
        scores: dict[str, float] = {}
        centres: dict[str, float] = {}
        for split in _series_points(series.splits):
            stats = typical.get(key((race.key.discipline, race.key.sex), race.setting, split.point))
            if stats is not None:
                scores[split.id] = (float(split.time.value / finish) - stats[0]) / stats[1]
                centres[split.id] = stats[0]
        yield series, finish, scores, centres


def _lost_late(scores: dict[str, float]) -> bool:
    """Whether a run's splits say it lost time late in the race: every split fast for the
    finishing time, one of them an outlier, and the last two still clearly out of line, so that
    the gap to a normal run lasts to the finish rather than one split being out of step. The
    splits then agree with each other, and it is the finish that is unusual."""
    ordered = list(scores.values())
    return (
        len(ordered) >= 2
        and all(score < 0 for score in ordered)
        and min(ordered) < -OUTLIER_Z
        and all(score < -3 for score in ordered[-2:])
    )


@check(
    "split-outlier",
    severity=Severity.WARNING,
    suspect=True,
    title="Splits look like other athletes' splits",
    explanation=(
        "Across every race of an event, the share of the finishing time an athlete has used "
        "at a timing point varies little: reaching 200 m in a 400 m race takes about 48% of "
        f"it. A split more than {OUTLIER_Z:g} robust standard deviations from the typical "
        "share, when the athlete's other splits are not, is a timing error (a checkpoint "
        "missed or credited to the wrong athlete) or a stretch of the race that went wrong. "
        "The message says which fits the athlete's other splits better. Either way it does "
        "not show how the event is normally run, so analyses leave it out. A run whose every "
        "split is fast for its finish lost time late in the race: see the next check."
    ),
)
def split_outlier(records: Records) -> Iterator[Finding]:
    for series, finish, scores, centres in _outlier_scores(records):
        if _lost_late(scores):
            continue
        for split in _series_points(series.splits):
            z = scores.get(split.id)
            if z is None or abs(z) <= OUTLIER_Z:
                continue
            expected = _fmt(Decimal(centres[split.id]) * finish)
            others = [score for split_id, score in scores.items() if split_id != split.id]
            observed = (
                f"{split.point.label} split {_fmt(split.time.value)} is "
                f"{'slow' if z > 0 else 'fast'} for a {_fmt(finish)} finish (typically "
                f"{expected}; {abs(z):.0f} robust standard deviations out)"
            )
            if others and all(abs(other) < 3 for other in others):
                verdict = "the athlete's other splits are normal, so probably a timing error"
            else:
                verdict = "a timing error or an unusual race"
            yield Finding(split.id, "time", f"{observed}: {verdict}")


@check(
    "time-lost-late",
    severity=Severity.INFO,
    suspect=True,
    title="Time lost late in the race",
    explanation=(
        "When every split is fast for the athlete's finishing time, and still clearly so at "
        "the last two, the splits agree with each other and the time was lost late in the "
        "race: to a fall, an injury, or easing off. The splits and the result "
        "stay as published and the replay shows the race as it was run, but analyses of "
        "typical pacing leave the run out: its shares of the finishing time do not show how "
        "the event is normally run."
    ),
)
def time_lost_late(records: Records) -> Iterator[Finding]:
    reported: set[str] = set()
    for series, finish, scores, centres in _outlier_scores(records):
        if not _lost_late(scores) or series.performance.id in reported:
            continue
        reported.add(series.performance.id)
        last = [split for split in _series_points(series.splits) if split.id in scores][-1]
        expected = _fmt(Decimal(centres[last.id]) * finish)
        yield Finding(
            series.performance.id,
            "result",
            f"every split is fast for a {_fmt(finish)} finish ({last.point.label} in "
            f"{_fmt(last.time.value)}, where {expected} is typical): time was probably lost "
            "late in the race (a fall, an injury, or easing off)",
        )


@check(
    "rank-order",
    severity=Severity.WARNING,
    suspect=False,
    title="Ranks at timing points agree with the times",
    explanation=(
        "Nobody should be ranked ahead of an athlete with a faster time at the same point. "
        "Equal times may be ranked either way (timing systems rank on finer times, and "
        "publishers number ties differently). When ranks disagree with times, the flags go to "
        "the fewest ranks that must be set aside for the rest to agree (where there is a "
        "choice, the slower athlete's): one athlete ranked last at every point by mistake is "
        "one flag, not one for everyone behind them."
    ),
)
def rank_order(records: Records) -> Iterator[Finding]:
    at_point: dict[tuple[object, ...], list[Split]] = defaultdict(list)
    for series in records.series:
        for split in series.splits:
            if split.rank is not None:
                at_point[(series.performance.race, series.document, split.point)].append(split)
    for splits in at_point.values():
        ordered = sorted(splits, key=lambda split: (split.time.value, _rank(split)))
        kept = _agreeing(ordered)
        for index, split in enumerate(ordered):
            if index in kept:
                continue
            by_time = 1 + sum(other.time.value < split.time.value for other in splits)
            yield Finding(
                split.id,
                "rank",
                f"ranked {_rank(split)} at {split.point.label} with {_fmt(split.time.value)}, "
                f"{by_time} of {len(splits)} by time",
            )


def _rank(split: Split) -> int:
    assert split.rank is not None
    return split.rank.value


def _agreeing(ordered: list[Split]) -> set[int]:
    """The positions (in time order) of the longest run of splits whose ranks never go down:
    the ranks that agree with the times. Of equally long runs, the one keeping faster ones."""
    ranks = [_rank(split) for split in ordered]
    length = [1] * len(ranks)
    previous: list[int | None] = [None] * len(ranks)
    for i in range(len(ranks)):
        for j in range(i):
            if ranks[j] <= ranks[i] and length[j] + 1 > length[i]:
                length[i], previous[i] = length[j] + 1, j
    kept: set[int] = set()
    current: int | None = max(range(len(ranks)), key=lambda i: (length[i], -i), default=None)
    while current is not None:
        kept.add(current)
        current = previous[current]
    return kept


@check(
    "place-order",
    severity=Severity.WARNING,
    suspect=False,
    title="Places agree with finishing times",
    explanation="A finisher's place should agree with the finishing times of the others.",
)
def place_order(records: Records) -> Iterator[Finding]:
    for performances in records.performances_by_race.values():
        finishers = [p for p in performances if p.status is Status.FINISHED and p.place]
        for perf in finishers:
            assert perf.place is not None and perf.time is not None
            faster = sum(other.time is not None and other.time < perf.time for other in finishers)
            level = sum(other.time is not None and other.time <= perf.time for other in finishers)
            if not 1 + faster <= perf.place.value <= level:
                yield Finding(
                    perf.id,
                    "place",
                    f"placed {perf.place.value} in {_fmt(perf.time)}, but {faster} finisher(s) "
                    "were faster",
                )


@check(
    "birth-dates-agree",
    severity=Severity.ERROR,
    suspect=False,
    title="An athlete's birth date is the same everywhere",
    explanation=(
        "Documents that print an athlete's birth date must agree on it. If they do not, "
        "either a document is wrong or two athletes have been taken for one."
    ),
)
def birth_dates_agree(records: Records) -> Iterator[Finding]:
    printed: dict[AthleteId, list[tuple[PerformanceId, str]]] = defaultdict(list)
    for perf in records.assembled.performances:
        if perf.birth_date is not None:
            printed[perf.athlete].append((perf.id, str(perf.birth_date.value)))
    agreed = {athlete.id: athlete.birth_date for athlete in records.assembled.athletes}
    for athlete, dates in printed.items():
        if agreed[athlete] is None and len({date for _, date in dates}) > 1:
            listing = ", ".join(sorted({date for _, date in dates}))
            for perf_id, date in dates:
                yield Finding(perf_id, "birth_date", f"birth date {date}; others print {listing}")


@check(
    "documents-agree",
    severity=Severity.WARNING,
    suspect=False,
    title="Documents of a race agree",
    explanation=(
        "When a race's results and race analysis both give a fact (a place, a time, a lane), "
        "they should agree. Where they do not, the results document stands, as the official "
        "record, and the difference is reported here."
    ),
)
def documents_agree(records: Records) -> Iterator[Finding]:
    for conflict in records.assembled.conflicts:
        kept, other = conflict.kept, conflict.other
        yield Finding(
            conflict.subject,
            conflict.field,
            f"{conflict.field.replace('_', ' ')}: {_show(kept.value)} in "
            f"{kept.span.document.rsplit('/', 1)[1]}, but {_show(other.value)} in "
            f"{other.span.document.rsplit('/', 1)[1]}",
        )


@check(
    "athlete-in-race",
    severity=Severity.ERROR,
    suspect=True,
    title="Athletes timed in a race ran in it",
    explanation=(
        "A report that times an athlete in a race, when the race's official results do not "
        "name them, has put them in the wrong race (a misprinted heat number). Their row is "
        "left out of the race, and reported here."
    ),
)
def athlete_in_race(records: Records) -> Iterator[Finding]:
    for unplaced in records.assembled.unplaced:
        entry = unplaced.entry
        name, country = entry.name.value, entry.country.value if entry.country else "?"
        yield Finding(
            unplaced.document,
            None,
            f"times {name.given} {name.family} ({country}, {_show(entry.result.value)}; page "
            f"{entry.row.page}: {entry.row.text!r}), whom the race's results do not name; "
            "the row is left out",
        )


def _show(value: object) -> str:
    return str(getattr(value, "time", None) or getattr(value, "status", None) or value)
