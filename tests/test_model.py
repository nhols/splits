"""The data model's invariants: what it refuses to represent."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from splits.model import (
    BirthDate,
    Dataset,
    RaceKey,
    Result,
    Round,
    Sex,
    Sourced,
    Status,
    TimingPoint,
)


def test_race_key_round_trips() -> None:
    for text in ("400mh-women/semi-final-2", "200m-men/final", "half-marathon-men/final"):
        assert str(RaceKey.parse(text)) == text
    key = RaceKey.parse("400m-men/heat-3")
    assert (key.discipline, key.sex, key.round, key.heat) == ("400m", Sex.MEN, Round.HEAT, 3)


@pytest.mark.parametrize("text", ["400m-man/final", "400m-men", "400m-men/heat-0", "400m/final"])
def test_race_key_rejects(text: str) -> None:
    with pytest.raises(ValueError, match="invalid race key"):
        RaceKey.parse(text)


def test_timing_points() -> None:
    assert TimingPoint.at(Decimal("100")).label == "100m"
    assert TimingPoint.at(Decimal("13.72")).slug == "13-72m"
    hurdle = TimingPoint.at_hurdle(3, Decimal("115"))
    assert (hurdle.label, hurdle.slug) == ("H3", "h3")
    assert TimingPoint.start().order < hurdle.order < TimingPoint.finish(Decimal(400)).order
    with pytest.raises(ValidationError):
        TimingPoint(kind=TimingPoint.at(Decimal(1)).kind, distance=Decimal(0))


def test_a_time_only_for_finishers() -> None:
    assert Result(status=Status.FINISHED, time=Decimal("44.22")).time == Decimal("44.22")
    with pytest.raises(ValidationError):
        Result(status=Status.FINISHED)
    with pytest.raises(ValidationError):
        Result(status=Status.DISQUALIFIED, time=Decimal("44.22"))


def test_birth_dates_may_be_partial_but_not_impossible() -> None:
    assert str(BirthDate(year=2001)) == "2001"
    assert str(BirthDate(year=2001, month=9, day=11)) == "2001-09-11"
    assert BirthDate(year=2001, month=9, day=11).refines(BirthDate(year=2001))
    assert not BirthDate(year=2001).refines(BirthDate(year=2001, month=9, day=11))
    with pytest.raises(ValidationError):
        BirthDate(year=2001, month=2, day=30)


def test_records_are_strict_and_frozen(dataset: Dataset) -> None:
    race = dataset.races[0]
    with pytest.raises(ValidationError):
        race.model_validate({**race.model_dump(), "unexpected": 1})
    with pytest.raises(ValidationError):
        race.title = race.title  # type: ignore[misc]


def test_every_value_keeps_its_source_through_json(dataset: Dataset) -> None:
    split = dataset.splits[0]
    restored = Sourced[Decimal].model_validate_json(split.time.model_dump_json())
    assert restored == split.time
    assert restored.span.document == split.document


def test_dataset_refuses_dangling_references(dataset: Dataset) -> None:
    orphan = dataset.performances[0].model_copy(update={"athlete": "nobody-at-all"})
    with pytest.raises(ValidationError, match="unknown athlete"):
        Dataset.model_validate(
            {**dict(dataset), "performances": (orphan, *dataset.performances[1:])}
        )


def test_dataset_refuses_values_read_from_another_races_document(dataset: Dataset) -> None:
    first, second = (
        dataset.splits[0],
        next(s for s in dataset.splits if s.document != dataset.splits[0].document),
    )
    stolen = first.model_copy(update={"time": second.time})
    with pytest.raises(ValidationError, match="was read from"):
        Dataset.model_validate({**dict(dataset), "splits": (stolen, *dataset.splits[1:])})
