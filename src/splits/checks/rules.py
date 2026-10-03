"""The data-quality checks.

Each check says in plain words what it verifies. The thresholds are deliberately loose: a
flag should mean "look at this", not "this is unusual".
"""

from collections import defaultdict
from collections.abc import Iterator
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from itertools import pairwise
from statistics import median

from splits.checks.framework import CheckGroup, Finding, Records, Series, check
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
    group=CheckGroup.LOGIC,
    severity=Severity.ERROR,
    suspect=True,
    title="Each split is later than the one before",
    explanation=(
        "A runner's time at each point must be later than at the point before. If it "
        "isn't, one of the two times is wrong, or belongs to a different point."
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
    group=CheckGroup.LOGIC,
    severity=Severity.ERROR,
    suspect=True,
    title="Splits come before the finish",
    explanation="Every split must be earlier than the runner's official finishing time.",
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
    group=CheckGroup.CONSISTENCY,
    severity=Severity.ERROR,
    suspect=True,
    title="The time at the line matches the result",
    explanation=(
        "Some documents time runners at the finish line as well as giving their "
        "official result. The two must match, allowing for one being printed with fewer "
        "decimals (4:07.6 for a result of 4:07.64). A runner who didn't start or didn't "
        "finish can't have a time at the line. A disqualified runner usually crossed it "
        "all the same, but has no result to compare it with, so isn't checked."
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
    group=CheckGroup.CONSISTENCY,
    severity=Severity.ERROR,
    suspect=True,
    title="Printed stretch times add up",
    explanation=(
        "Documents give each runner's time at every point, and often the time for each "
        "stretch between points too. A stretch's time must equal the difference between "
        "the times at its two ends, allowing for rounding: a hundredth, or up to a "
        "tenth for times printed to the tenth."
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
    group=CheckGroup.LOGIC,
    severity=Severity.ERROR,
    suspect=True,
    title="No impossible speeds",
    explanation=(
        f"Nobody can average more than {MAX_SPEED} m/s between two points: the fastest "
        "10 m ever timed in a race is about 12.4 m/s. A faster stretch means one of its "
        "times is wrong."
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
    group=CheckGroup.ANOMALY,
    severity=Severity.WARNING,
    suspect=True,
    title="Splits in line with other runners'",
    explanation=(
        "At any point in a race, runners have used up much the same share of their "
        "finishing time, whatever that time: just under half of it at halfway in a 400 "
        f"m. A split far out of line with that (more than {OUTLIER_Z:g} times the usual "
        "spread away) is almost always a timing mistake: a checkpoint missed, or a time "
        "given to the wrong runner. The message says whether the runner's other splits "
        "suggest a mistake or a race that went wrong. A run whose every split is fast "
        "for its finish is a different case: see the next check."
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
    group=CheckGroup.ANOMALY,
    severity=Severity.INFO,
    suspect=True,
    title="Slowed badly near the end",
    explanation=(
        "When a runner falls, gets injured or eases off near the end, every split looks "
        "fast for their finishing time, because the time was lost after them. The "
        "splits and result are kept, and the replay shows the race as it happened, but "
        "the run is left out of the typical race, because it isn't how the event is "
        "normally run."
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
    group=CheckGroup.LOGIC,
    severity=Severity.WARNING,
    suspect=False,
    title="Positions at each point match the times",
    explanation=(
        "Documents often give each runner's position at every point. Nobody should be "
        "placed ahead of someone with a faster time there; equal times can go either "
        "way. When positions and times disagree, only the fewest positions that explain "
        "it are flagged: one runner wrongly placed last at every point is one flag, not "
        "one for everyone behind them."
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
    group=CheckGroup.LOGIC,
    severity=Severity.WARNING,
    suspect=False,
    title="Places match finishing times",
    explanation="A runner's finishing place must agree with the finishing times of the others.",
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
    group=CheckGroup.CONSISTENCY,
    severity=Severity.ERROR,
    suspect=False,
    title="Birth dates agree",
    explanation=(
        "Every document that prints a runner's birth date must give the same one. If "
        "not, a document is wrong, or two runners have been taken for one."
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
    group=CheckGroup.CONSISTENCY,
    severity=Severity.WARNING,
    suspect=False,
    title="A race's documents agree",
    explanation=(
        "When a race's results and its split analysis both give the same fact, such as "
        "a place, a time or a lane, they should match. If they don't, the official "
        "results are used, and the difference is listed."
    ),
)
def documents_agree(records: Records) -> Iterator[Finding]:
    for conflict in records.assembled.conflicts:
        kept, other = conflict.kept, conflict.other
        yield Finding(
            conflict.subject,
            conflict.field,
            f"{conflict.field.replace('_', ' ').capitalize()} {_show(kept.value)} in the "
            f"{records.document_title(kept).lower()}, but {_show(other.value)} in the "
            f"{records.document_title(other).lower()}",
            sources=(kept, other),
        )


@check(
    "athlete-in-race",
    group=CheckGroup.CONSISTENCY,
    severity=Severity.ERROR,
    suspect=True,
    title="Runners timed in a race ran in it",
    explanation=(
        "If a split document times someone the race's official results don't list, it "
        "has put them in the wrong race, usually through a misprinted heat number. "
        "Their row is left out of the race."
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


@check(
    "reader-notes",
    group=CheckGroup.READING,
    severity=Severity.WARNING,
    suspect=False,
    title="Notes from reading a document",
    explanation=(
        "Reading a document sometimes needs a judgement, such as matching a misspelt "
        "name in the splits to the right runner in the results, and now and then a row "
        "can't be placed at all. Each case is noted here, against its document, for a "
        "person to check."
    ),
)
def reader_notes(records: Records) -> Iterator[Finding]:
    for note in records.assembled.notes:
        yield Finding(note.document, None, note.text)


def _show(value: object) -> str:
    return str(getattr(value, "time", None) or getattr(value, "status", None) or value)
