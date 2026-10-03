from datetime import UTC, datetime

import pytest

from splits.assemble import AssemblyError, DocumentRead
from splits.assemble.assemble import number_holders
from splits.assemble.identity import IdentityError, IdentityResolver, display_family, fold
from splits.assemble.world_athletics import WorldAthleticsResults
from splits.model import (
    AthleteRule,
    Catalog,
    CatalogRef,
    Dataset,
    NameVariant,
    NumberHolder,
    PersonName,
)
from splits.model.ids import athlete_id
from splits.pipeline import make_dataset

REF = CatalogRef(file="catalog/athletes.yaml", line=1, pointer="/0")


def test_fold_ignores_case_accents_and_punctuation() -> None:
    assert fold("HUDSON-SMITH") == fold("Hudson Smith") == "hudson smith"
    assert fold("MÄGI") == fold("Magi")
    assert fold("KOTWIŁA") == "kotwila"


def test_same_name_and_country_in_any_order_is_one_athlete() -> None:
    resolver = IdentityResolver(())
    a = resolver.resolve(PersonName(given="Karsten", family="WARHOLM"), "NOR")
    b = resolver.resolve(PersonName(given="Karsten", family="Warholm"), "NOR")
    assert a.athlete == b.athlete == "karsten-warholm"
    resolver.check()


def test_a_clash_asks_for_a_rule() -> None:
    resolver = IdentityResolver(())
    resolver.resolve(PersonName(given="Chris", family="TAYLOR"), "JAM")
    resolver.resolve(PersonName(given="Chris", family="TAYLOR"), "USA")
    with pytest.raises(IdentityError, match="chris-taylor"):
        resolver.check()


def test_rules_merge_name_variants() -> None:
    rule = AthleteRule(
        id=athlete_id("sydney-mclaughlin-levrone"),
        given="Sydney",
        family="McLaughlin-Levrone",
        country="USA",
        also_known_as=(NameVariant(given="Sydney", family="McLaughlin"),),
        declared=REF,
    )
    resolver = IdentityResolver((rule,))
    old = resolver.resolve(PersonName(given="Sydney", family="McLAUGHLIN"), "USA")
    new = resolver.resolve(PersonName(given="Sydney", family="McLAUGHLIN-LEVRONE"), "USA")
    assert old.athlete == new.athlete == "sydney-mclaughlin-levrone"
    assert old.rule == REF
    resolver.check()


def test_display_family_prefers_spellings_with_lower_case() -> None:
    assert display_family(["MCMASTER", "McMASTER"]) == "McMaster"
    assert display_family(["DOS SANTOS", "dos SANTOS"]) == "dos Santos"
    assert display_family(["HUDSON-SMITH"]) == "Hudson-Smith"
    assert display_family(["MCPHERSON"]) == "McPherson"
    assert display_family(["ST. PIERRE"]) == "St. Pierre"


def test_athletes_are_linked_across_publishers(dataset: Dataset) -> None:
    races = {p.race for p in dataset.performances if p.athlete == "karsten-warholm"}
    assert "wic-2024-glasgow/400m-men/heat-1" in races  # World Athletics, "Karsten WARHOLM"
    assert "dl-2023-zurich/400mh-men/final" in races  # OMEGA, "WARHOLM Karsten"
    assert "og-2024-paris/400mh-men/final" in races  # Olympic ORIS
    athlete = next(a for a in dataset.athletes if a.id == "karsten-warholm")
    assert str(athlete.birth_date) == "1996-02-28"  # only World Athletics prints it


def test_initials_are_the_one_athlete_they_fit() -> None:
    """Results sometimes shorten given names to fit the column: ``THOMPSON-HERAH E``."""
    resolver = IdentityResolver(())
    printed = [
        (PersonName(given="Elaine", family="THOMPSON-HERAH"), "JAM"),
        (PersonName(given="E", family="THOMPSON-HERAH"), "JAM"),
        (PersonName(given="Yupun Abeykoon", family="MUDIYANSELAGE"), "SRI"),
        (PersonName(given="YA", family="MUDIYANSELAGE"), "SRI"),
        (PersonName(given="Devon", family="ALLEN"), "USA"),
        (PersonName(given="CJ", family="ALLEN"), "USA"),
    ]
    resolver.learn(printed)
    athletes = [resolver.resolve(name, country).athlete for name, country in printed]
    assert athletes[0] == athletes[1] == "elaine-thompson-herah"
    assert athletes[2] == athletes[3] == "yupun-abeykoon-mudiyanselage"
    # CJ Allen is not Devon Allen: the initials don't fit.
    assert athletes[4:] == ["devon-allen", "cj-allen"]
    resolver.check()


def test_initials_fitting_two_athletes_stand_as_printed() -> None:
    resolver = IdentityResolver(())
    resolver.learn(
        [
            (PersonName(given="Jasmine", family="SMITH"), "USA"),
            (PersonName(given="Jordan", family="SMITH"), "USA"),
        ]
    )
    assert resolver.resolve(PersonName(given="J", family="SMITH"), "USA").athlete == "j-smith"


def test_a_family_name_alone_is_the_finalist_of_that_name(dataset: Dataset) -> None:
    """Birmingham 2018: the biomechanics report names the 60 m hurdles finalists by family
    name alone, and wraps the longest round its row ("MARTINOT-" above, "LAGARDE" below).
    Each is the one runner of that name in the race's results."""
    race = "wic-2018-birmingham/60mh-men/final"
    assert len([p for p in dataset.performances if p.race == race]) == 8
    splits = [
        split.id.rsplit("/", 1)[-1]
        for split in dataset.splits
        if str(split.performance) == f"{race}/pascal-martinot-lagarde"
    ]
    assert splits == [
        *(f"h{hurdle}@wa-biomechanics" for hurdle in range(1, 6)),
        "finish@wa-biomechanics",
    ]


@pytest.mark.parametrize(
    ("performance", "card"),
    [
        ("dl-2024-stockholm/100m-men/final/kyree-king", "YC"),  # "KING Kyree YC"
        ("og-2024-paris/200m-men/heat-2/cesar-almiron", "L"),  # "ALMIRON Cesar L 20.87"
    ],
)
def test_a_card_beside_a_name_is_not_part_of_it(
    dataset: Dataset, performance: str, card: str
) -> None:
    found = next(p for p in dataset.performances if p.id == performance)
    assert [remark.value for remark in found.remarks][:1] == [card]


def _with_numbers(
    catalog: Catalog,
    reads: list[DocumentRead],
    world_athletics: dict[str, WorldAthleticsResults],
    numbers: dict[int, NumberHolder],
) -> Dataset:
    return make_dataset(
        catalog.model_copy(update={"athlete_numbers": numbers}),
        reads,
        code_version="test",
        built_at=datetime(2026, 1, 1, tzinfo=UTC),
        world_athletics=world_athletics,
    )


def test_an_athlete_keeps_their_number_whatever_their_name(
    catalog: Catalog,
    reads: list[DocumentRead],
    world_athletics: dict[str, WorldAthleticsResults],
    dataset: Dataset,
) -> None:
    """A number is found again by World Athletics ID, whatever the athlete is now called;
    new athletes are numbered after the highest number."""
    warholm = next(a for a in dataset.athletes if a.id == "karsten-warholm")
    assert warholm.world_athletics is not None
    renamed = NumberHolder(
        athlete=athlete_id("karsten-old-name"), world_athletics=warholm.world_athletics.id
    )
    built = _with_numbers(catalog, reads, world_athletics, {5000: renamed})
    athletes = {a.id: a for a in built.athletes}
    assert athletes[athlete_id("karsten-warholm")].number == 5000
    assert sorted(a.number for a in built.athletes)[:2] == [5000, 5001]
    assert number_holders(built.athletes)[5000].athlete == "karsten-warholm"


def test_two_numbers_of_one_athlete_both_stay_theirs(
    catalog: Catalog,
    reads: list[DocumentRead],
    world_athletics: dict[str, WorldAthleticsResults],
) -> None:
    holders = {
        7: NumberHolder(athlete=athlete_id("karsten-warholm")),
        3: NumberHolder(athlete=athlete_id("karsten-warholm")),
    }
    built = _with_numbers(catalog, reads, world_athletics, holders)
    warholm = next(a for a in built.athletes if a.id == "karsten-warholm")
    assert (warholm.number, warholm.former_numbers) == (3, (7,))


def test_a_number_whose_athlete_is_gone_stops_the_build(
    catalog: Catalog, reads: list[DocumentRead], world_athletics: dict[str, WorldAthleticsResults]
) -> None:
    with pytest.raises(AssemblyError, match="12 \\(nobody-now\\)"):
        _with_numbers(
            catalog, reads, world_athletics, {12: NumberHolder(athlete=athlete_id("nobody-now"))}
        )
