from decimal import Decimal

import pytest

from splits.formats import ReadContext
from splits.formats.flash_results import _day, _point
from splits.model import Catalog, DocumentSpec, PointKind, RaceKey
from splits.model.ids import DocumentId, competition_id, format_id
from splits.model.provenance import CatalogRef


def _context(catalog: Catalog, race: str) -> ReadContext:
    competition = catalog.competitions[competition_id("dl-2018-eugene")]
    key = RaceKey.parse(race)
    spec = DocumentSpec(
        id=DocumentId(f"{competition.id}/{key}/flash-splits"),
        competition=competition.id,
        race=key,
        format=format_id("flash-splits"),
        url="https://example.org/006-1-01.htm",
        declared=CatalogRef(file="catalog/x.yaml", line=1, pointer="/documents/0"),
    )
    return ReadContext(
        spec=spec, discipline=catalog.disciplines[key.discipline], competition=competition
    )


@pytest.mark.parametrize(
    ("race", "label", "distance"),
    [
        ("mile-men/final", "409m", Decimal("409.344")),  # three laps to go
        ("mile-men/final", "1209m", Decimal("1209.344")),
        ("mile-men/final", "1500m", Decimal("1500")),  # a distance, not a lap
        ("2-miles-men/final", "418m", Decimal("418.688")),
        ("2-miles-men/final", "3000m", Decimal("3000")),
        ("1500m-women/final", "300m", Decimal("300")),
        ("5000m-women/final", "200m", Decimal("200")),
    ],
)
def test_laps_of_a_mile_are_printed_rounded_down_to_the_metre(
    catalog: Catalog, race: str, label: str, distance: Decimal
) -> None:
    point = _point(label, _context(catalog, race))
    assert (point.kind, point.distance) == (PointKind.DISTANCE, distance)


@pytest.mark.parametrize(
    ("race", "label"),
    [("mile-men/final", "Mile"), ("mile-men/final", "1 Mile"), ("2-miles-men/final", "2 Mile")],
)
def test_the_finish_is_labelled_by_the_race(catalog: Catalog, race: str, label: str) -> None:
    context = _context(catalog, race)
    assert _point(label, context) == context.discipline.finish()


def test_a_label_at_the_race_distance_is_the_finish(catalog: Catalog) -> None:
    context = _context(catalog, "800m-men/final")
    assert _point("800m", context) == context.discipline.finish()


def test_a_label_naming_another_race_is_refused(catalog: Catalog) -> None:
    with pytest.raises(ValueError, match="not the finish of a Mile"):
        _point("2 Mile", _context(catalog, "mile-men/final"))


def test_a_steeplechase_is_not_placed(catalog: Catalog) -> None:
    """Flash Results labels a steeplechase's laps as the flat track's (200m, 600m ...); a
    steeplechase lap is shorter, so the labels do not say where the times were taken."""
    with pytest.raises(ValueError, match="flat track's"):
        _point("200m", _context(catalog, "3000msc-men/final"))


def test_the_day_is_the_meeting_day_with_the_weekday_printed() -> None:
    assert str(_day("Friday May 25-26, 2018")) == "2018-05-25"
    assert str(_day("Saturday May 25-26, 2018")) == "2018-05-26"
    assert str(_day("Sunday June 30, 2019")) == "2019-06-30"
    with pytest.raises(ValueError, match="no Monday"):
        _day("Monday May 25-26, 2018")
