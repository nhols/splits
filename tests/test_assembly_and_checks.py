from datetime import UTC, datetime
from decimal import Decimal

import pytest

from splits.assemble import Assembled, AssemblyError, DocumentRead
from splits.assemble.assemble import confirm_heading
from splits.assemble.world_athletics import WorldAthleticsResults
from splits.checks import run_checks
from splits.formats import EntryReading
from splits.model import Catalog, Dataset, RaceKey, Result, Status
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


def test_a_b_race_printed_as_a_final_confirms_its_event(reads: list[DocumentRead]) -> None:
    """The Prefontaine Classic of 2017 prints its International Mile, a B race, as
    ``Men 1 Mile Run Int'l (Final)``: it confirms the event, and contradicts a heat."""
    read = next(r for r in reads if r.spec.id == "dl-2017-eugene/mile-men/b-race/flash-splits")
    confirm_heading(read)
    heat = read.spec.model_copy(update={"race": RaceKey.parse("mile-men/heat-1")})
    with pytest.raises(AssemblyError, match="declares round heat"):
        confirm_heading(DocumentRead(heat, read.reading))
    women = read.spec.model_copy(update={"race": RaceKey.parse("mile-women/b-race")})
    with pytest.raises(AssemblyError, match="declares sex women"):
        confirm_heading(DocumentRead(women, read.reading))


def test_a_b_race_is_confirmed_by_its_heading_or_its_heat(reads: list[DocumentRead]) -> None:
    """Lausanne 2021 prints its B race's first heat as ``100m Women - B Race - Heat 1``; Zürich
    2023 prints its B race's heats as the event's, ``100m Women - Heat A``. Both confirm the
    heat they are declared, and neither confirms another."""
    for document in (
        "dl-2021-lausanne/100m-women/b-race-1/omega-race-analysis",
        "dl-2023-zurich/100m-women/b-race-1/omega-race-analysis",
    ):
        read = next(r for r in reads if r.spec.id == document)
        confirm_heading(read)
        wrong = read.spec.model_copy(update={"race": RaceKey.parse("100m-women/b-race-2")})
        with pytest.raises(AssemblyError, match="declares heat 2"):
            confirm_heading(DocumentRead(wrong, read.reading))
        final = read.spec.model_copy(update={"race": RaceKey.parse("100m-women/heat-1")})
        if "B Race" in read.reading.title.value:
            with pytest.raises(AssemblyError, match="declares round heat"):
                confirm_heading(DocumentRead(final, read.reading))


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
    # The Berlin 2009 biomechanics report puts three runners of heat 6 in heat 5.
    "wch-2009-berlin/400m-men/heat-5/iaaf-biomechanics",
    # The handbook's halves of the 1932 800m add up to the statisticians' estimates of the
    # times (Edwards 52.4/58.2, 1:50.6e), not to the official times beside them (1:51.5).
    "og-1932-los-angeles/800m-men/final/",
    # His halves (54.4/59.8) add up to his adjusted time, 1:54.2, not his result, 1:53.0.
    "og-1948-london/800m-men/final/robert-chef-dhotel/",
    # His last 300m, 40.79, does not fit his 1200m split, 2:56.5, and his 3:36.40.
    "og-1996-atlanta/1500m-men/final/fermin-cacho/",
    # The handbook times Ralph Doubell at 400m in 51.3 in its table and 51.8 in his halves.
    "og-1968-mexico-city/800m-men/final/ralph-doubell/",
    # Linden Hall's birth date: 29 JUN 1991 in the Lausanne results of 2017, 20 JUN in Brussels'
    # of 2025.
    "dl-2017-lausanne/mile-women/final/linden-hall",
    "dl-2025-brussels/1500m-women/final/linden-hall",
}


def test_the_published_dataset_is_clean_except_known_problems(dataset: Dataset) -> None:
    serious = {flag.subject for flag in dataset.flags if flag.severity.value == "error"}
    unexplained = {s for s in serious if not any(s.startswith(known) for known in KNOWN_ERRORS)}
    assert unexplained == set()
    # Every known problem is still found, so the list stays honest.
    assert all(any(s.startswith(known) for s in serious) for known in KNOWN_ERRORS)


def test_a_runner_the_results_do_not_name_is_left_out_and_reported(dataset: Dataset) -> None:
    """Berlin 2009: the biomechanics report prints Jeremy Wariner's heat as 5; the results
    have him winning heat 6. His row is not attached to heat 5, and the report is flagged."""
    heat = "wch-2009-berlin/400m-men/heat-5"
    assert not any(perf.id == f"{heat}/jeremy-wariner" for perf in dataset.performances)
    messages = [
        flag.message
        for flag in dataset.flags
        if flag.check == "athlete-in-race" and flag.subject == f"{heat}/iaaf-biomechanics"
    ]
    assert any("Jeremy Wariner" in message for message in messages)


def test_a_table_of_splits_misprinting_a_name_is_read_and_reported(dataset: Dataset) -> None:
    """Sydney 2000: the handbook's table of splits prints ``Mokganyetsi`` for Hendrik
    Moganyetsi, sixth in the results and sixth in the table. His splits are his, and the
    different spelling is reported on the document. (World Athletics now spells him
    Hendrick Mokganyetsi, which names the athlete.)"""
    perf = "og-2000-sydney/400m-men/final/hendrick-mokganyetsi"
    assert any(split.id == f"{perf}/300m@wa-handbook" for split in dataset.splits)
    note = _flags(dataset, "reader-notes")["og-2000-sydney/400m-men/final/wa-handbook"]
    assert "'Mokganyetsi' for Hendrik Moganyetsi" in note


def test_a_time_printed_twice_keeps_both_printings(dataset: Dataset) -> None:
    """Mexico City 1968: the handbook times Ralph Doubell at 400m in 51.3 in its table of
    splits and 51.8 in his halves. The table's stands as the split; the other is kept as his
    time from the start to 400m, and the disagreement is flagged."""
    perf = "og-1968-mexico-city/800m-men/final/ralph-doubell"
    split = next(s for s in dataset.splits if s.id == f"{perf}/400m@wa-handbook")
    assert split.time.value == Decimal("51.3")
    flagged = _flags(dataset, "segment-matches-splits")[f"{perf}/start-400m@wa-handbook"]
    assert "51.80" in flagged and "51.30" in flagged


def test_names_printed_without_a_split_match_the_results(dataset: Dataset) -> None:
    """Berlin 2009's report prints ``Sakari Joy Nakhumicha``, with nothing to say where the
    given name starts, and ``Polyakova Yevgeniya`` where the results print Evgeniya: each is
    the athlete the race's results name, not a new one. (World Athletics now names them
    Joyce Sakari and Yevgeniya Polyakova.)"""
    timed = {split.performance for split in dataset.splits if "iaaf-biomechanics" in split.id}
    assert "wch-2009-berlin/400m-women/semi-final-2/joyce-sakari" in timed
    assert "wch-2009-berlin/100m-women/heat-5/yevgeniya-polyakova" in timed


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
    catalog: Catalog,
    reads: list[DocumentRead],
    world_athletics: dict[str, WorldAthleticsResults],
    seconds: str,
    check: str,
) -> None:
    doctored = [
        _doctored(read, "HUDSON-SMITH", "200m", seconds)
        if read.spec.id == "wch-2023-budapest/400m-men/final/wa-rs5"
        else read
        for read in reads
    ]
    dataset = make_dataset(
        catalog,
        doctored,
        code_version="test",
        built_at=datetime(2026, 1, 1, tzinfo=UTC),
        world_athletics=world_athletics,
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


def _with_status(dataset: Dataset, perf_id: str, status: Status) -> Assembled:
    """The dataset's records, but with one performance ending in ``status``: no time and no
    place, its splits as printed."""
    result = Result(status=status)
    performances = tuple(
        perf.model_copy(
            update={"result": perf.result.model_copy(update={"value": result}), "place": None}
        )
        if perf.id == perf_id
        else perf
        for perf in dataset.performances
    )
    return Assembled(
        documents=dataset.documents,
        races=dataset.races,
        athletes=dataset.athletes,
        performances=performances,
        splits=dataset.splits,
        segments=dataset.segments,
    )


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (Status.DISQUALIFIED, None),
        (Status.DID_NOT_FINISH, "a time at the line for an athlete who did not finish"),
        (Status.DID_NOT_START, "a time at the line for an athlete who did not start"),
    ],
)
def test_a_time_at_the_line_needs_a_result_unless_disqualified(
    catalog: Catalog, dataset: Dataset, status: Status, message: str | None
) -> None:
    """Paris 2024: the analysis times Makanakaishe Charamba at the line in 20.53, his result.
    Disqualified instead (for running out of his lane, say), he would still have crossed it:
    the time there contradicts nothing, as there is no result to compare it with. Not
    finishing, or not starting, he could have no time at the line at all."""
    perf = "og-2024-paris/200m-men/final/makanakaishe-charamba"
    at_line = {
        flag.check: flag.message
        for flag in run_checks(catalog, _with_status(dataset, perf, status))
        if flag.subject == f"{perf}/finish@oris-c77a"
    }
    assert at_line == ({"finish-matches-result": message} if message else {})


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
