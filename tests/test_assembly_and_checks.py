from datetime import UTC, datetime
from decimal import Decimal

import pytest

from splits.assemble import AssemblyError, DocumentRead
from splits.assemble.assemble import confirm_heading
from splits.formats import EntryReading
from splits.model import Catalog, Dataset, RaceKey
from splits.pipeline import make_dataset


def _flags(dataset: Dataset, check: str) -> dict[str, str]:
    return {flag.subject: flag.message for flag in dataset.flags if flag.check == check}


def test_a_document_must_confirm_the_declared_race(reads: list[DocumentRead]) -> None:
    read = next(r for r in reads if r.spec.id.startswith("wch-2023-budapest/400m-men/final"))
    confirm_heading(read)
    wrong = read.spec.model_copy(update={"race": RaceKey.parse("400m-men/semi-final-1")})
    with pytest.raises(
        AssemblyError, match="declares round semi-final, but the document says final"
    ):
        confirm_heading(DocumentRead(wrong, read.reading))


KNOWN_ERRORS = {
    # OMEGA's analysis times her 40–50m in 0.67 s (14.9 m/s): a timing glitch in the document.
    "dl-2025-zurich/100m-women/final/patrizia-van-der-weken/50m",
    # The analysis prints each runner's 2400m and 2500m times under 2800m and 2900m.
    "dl-2021-doha/3000msc-women/final/",
    # Her 3200m to 4000m times are garbled (3600m after 4000m).
    "dl-2024-eugene/5000m-women/final/birke-haylom/",
    # The timing caught several runners late at 3600m (Ingebrigtsen 28.68 for that 100 m, then
    # 3.01 for the next), and one at 3800m and one at 4000m.
    "wch-2023-budapest/5000m-men/heat-1/",
}


def test_the_published_dataset_is_clean_except_known_problems(dataset: Dataset) -> None:
    serious = {flag.subject for flag in dataset.flags if flag.severity.value == "error"}
    unexplained = {s for s in serious if not any(s.startswith(known) for known in KNOWN_ERRORS)}
    assert unexplained == set()
    # Every known problem is still found, so the list stays honest.
    assert all(any(s.startswith(known) for s in serious) for known in KNOWN_ERRORS)


def test_a_misattributed_split_is_flagged_not_dropped(dataset: Dataset) -> None:
    """Budapest 2023: the winner's 200 m split is printed as 23.76 (8th), impossible for a
    44.22 finish. It stays in the data, flagged, with a diagnosis."""
    split_id = "wch-2023-budapest/400m-men/final/antonio-watson/200m@wa-rs5"
    assert any(split.id == split_id for split in dataset.splits)
    message = _flags(dataset, "split-outlier")[split_id]
    assert "23.76" in message and "probably a timing error" in message


def test_time_lost_late_flags_the_result_and_keeps_the_splits(dataset: Dataset) -> None:
    """Zürich 2026: every one of Chris Robinson's splits is fast for his 51.41, and more so
    towards the finish: he lost the time late in the race. His splits are true, so they stay
    clean (the replay shows the race as he ran it); his result is flagged instead."""
    perf = "dl-2026-zurich/400mh-men/final/chris-robinson"
    assert "lost late in the race" in _flags(dataset, "time-lost-late")[perf]
    suspect = [flag.subject for flag in dataset.flags if flag.suspect]
    assert not any(subject.startswith(f"{perf}/") for subject in suspect)


def _doctored(read: DocumentRead, family: str, label: str, seconds: str) -> DocumentRead:
    entries = []
    for entry in read.reading.entries:
        if entry.name.value.family == family:
            splits = tuple(
                split.model_copy(
                    update={"time": split.time.model_copy(update={"value": Decimal(seconds)})}
                )
                if split.point.label == label
                else split
                for split in entry.splits
            )
            entry = EntryReading.model_validate({**dict(entry), "splits": splits})
        entries.append(entry)
    return DocumentRead(read.spec, read.reading.model_copy(update={"entries": tuple(entries)}))


@pytest.mark.parametrize(
    ("seconds", "check"),
    [
        ("20.50", "segment-matches-splits"),  # disagrees with the printed 9.98 segment
        ("32.50", "split-order"),  # later than the 300 m split
        ("45.00", "split-before-finish"),  # later than the finish
    ],
)
def test_inconsistent_values_are_flagged(
    catalog: Catalog, reads: list[DocumentRead], seconds: str, check: str
) -> None:
    doctored = [
        _doctored(read, "HUDSON-SMITH", "200m", seconds)
        if read.spec.id == "wch-2023-budapest/400m-men/final/wa-rs5"
        else read
        for read in reads
    ]
    dataset = make_dataset(
        catalog, doctored, code_version="test", built_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    flagged = _flags(dataset, check)
    assert any("matthew-hudson-smith" in subject for subject in flagged), flagged


def test_times_cut_to_the_tenth_agree_with_the_result(dataset: Dataset) -> None:
    """Monaco 2023: the analysis cuts every time to the tenth. Kipyegon's world record, 4:07.64,
    is 4:07.6 at the line, and Hiltz's 4:16.35 is 4:16.3 (not rounded up to 4:16.4); the
    printed segments are cut too, so they may fall short of the splits by up to 0.2 s."""
    race = "dl-2023-monaco/mile-women/final/"
    for check in ("finish-matches-result", "segment-matches-splits"):
        assert not any(subject.startswith(race) for subject in _flags(dataset, check))
    at_line = {
        str(split.performance): split.time.value
        for split in dataset.splits
        if split.id.startswith(race) and split.point.kind.value == "finish"
    }
    assert at_line[f"{race}faith-kipyegon"] == Decimal("247.6")
    assert at_line[f"{race}nikki-hiltz"] == Decimal("256.3")


def test_a_finish_printed_alone_is_the_finish(dataset: Dataset) -> None:
    """Monaco 2024: the timing caught Maël Gouyette only at the line. His lone time is printed
    in the finish's column, which shares a row with 1100 m to 1400 m: it is his finish, not a
    split at the column above it in the first row (500 m)."""
    perf = "dl-2024-monaco/1500m-men/final/mael-gouyette"
    times = {
        split.point.kind.value: split.time.value
        for split in dataset.splits
        if str(split.performance) == perf
    }
    assert times == {"finish": Decimal("213.29")}


def test_rank_check_accepts_any_tie_convention(dataset: Dataset) -> None:
    """ORIS numbers ties densely ("=2", "=2", then "3"); that is not an inconsistency."""
    flagged = _flags(dataset, "rank-order")
    assert not any(subject.startswith("og-2024-paris/400mh-men") for subject in flagged)


def test_ranks_out_of_step_with_the_times_are_flagged_on_the_runner_they_belong_to(
    dataset: Dataset,
) -> None:
    """Budapest 2023, 5000 m heat 1: the analysis ranks Abdihamid Nur last at almost every
    point while his times put him among the leaders. The other twenty runners' ranks agree
    with their times once his are set aside, so his alone are flagged."""
    race = "wch-2023-budapest/5000m-men/heat-1/"
    flagged = {
        subject.removeprefix(race).split("/")[0]
        for subject in _flags(dataset, "rank-order")
        if subject.startswith(race)
    }
    assert flagged == {"abdihamid-nur"}
