import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from splits.acquire.store import sha256_of
from splits.assemble.identity import IdentityError, IdentityResolver
from splits.assemble.world_athletics import WorldAthleticsResults, split_name
from splits.formats.base import EntryReading
from splits.model import (
    AthleteRule,
    BBox,
    BirthDate,
    CatalogRef,
    PersonName,
    Result,
    Retrieval,
    Sex,
    Sourced,
    Span,
    Status,
)
from splits.model.ids import (
    RaceKey,
    athlete_id,
    competition_id,
    document_id,
    format_id,
    race_id,
)

REF = CatalogRef(file="catalog/athletes.yaml", line=1, pointer="/0")
DOCUMENT = document_id(
    race_id(competition_id("og-2024-paris"), RaceKey.parse("800m-women/final")),
    format_id("wa-results"),
)
SPAN = Span(document=DOCUMENT, page=1, bbox=BBox(x0=0, top=0, x1=1, bottom=1), text="row")


def _sourced[T](value: T) -> Sourced[T]:
    return Sourced(value=value, source=SPAN, method="test")


def _entry(
    given: str, family: str, country: str, time: str | None, born: BirthDate | None = None
) -> EntryReading:
    result = (
        Result(status=Status.FINISHED, time=Decimal(time))
        if time
        else Result(status=Status.DID_NOT_FINISH)
    )
    return EntryReading(
        row=SPAN,
        name=_sourced(PersonName(given=given, family=family)),
        country=_sourced(country),
        result=_sourced(result),
        birth_date=None if born is None else _sourced(born),
    )


def _results(*rows: tuple[str, str, str, str, str | None]) -> WorldAthleticsResults:
    """Rows of (gender, name, nationality, mark, url slug)."""
    answer = {
        "days": [
            {
                "eventTitles": [
                    {
                        "events": [
                            {
                                "gender": gender,
                                "races": [
                                    {
                                        "results": [
                                            {
                                                "place": "1.",
                                                "mark": mark,
                                                "nationality": nationality,
                                                "competitor": {
                                                    "name": name,
                                                    "urlSlug": slug,
                                                    "birthDate": "17 OCT 1993",
                                                },
                                            }
                                        ]
                                    }
                                ],
                            }
                            for gender, name, nationality, mark, slug in rows
                        ]
                    }
                ]
            }
        ]
    }
    content = json.dumps(answer).encode()
    retrieval = Retrieval(
        sha256=sha256_of(content),
        size=len(content),
        media_type="application/json",
        retrieved_at=datetime(2026, 10, 2, tzinfo=UTC),
        retrieved_from="https://graphql-prod-4896.edge.aws.worldathletics.org/graphql",
    )
    return WorldAthleticsResults(competition_id("og-2024-paris"), retrieval, content)


PARIS = _results(
    ("W", "Georgia HUNTER BELL", "GBR", "1:57.22", "great-britain-ni/georgia-hunter-bell-14329797"),
    ("W", "Keely HODGKINSON", "GBR", "1:56.72", "great-britain-ni/keely-hodgkinson-14627708"),
    ("M", "Max BURGIN", "GBR", "1:57.22", "great-britain-ni/max-burgin-14720522"),
    ("W", "GBR team", "GBR", "3:20.00", None),
)


def test_world_athletics_writes_family_names_in_capitals() -> None:
    assert split_name("Georgia HUNTER BELL") == PersonName(given="Georgia", family="HUNTER BELL")
    assert split_name("Faith Chepngetich KIPYEGON") == PersonName(
        given="Faith Chepngetich", family="KIPYEGON"
    )
    assert split_name("Marie-Josée TA LOU-SMITH") == PersonName(
        given="Marie-Josée", family="TA LOU-SMITH"
    )


def test_a_row_is_linked_by_time_country_and_a_word_of_its_name() -> None:
    """The documents of Paris 2024 print her earlier name, Georgia BELL."""
    link = PARIS.link(_entry("Georgia", "BELL", "GBR", "117.22"), Sex.WOMEN)
    assert link is not None
    assert link.value.id == 14329797
    assert link.value.name == PersonName(given="Georgia", family="HUNTER BELL")
    assert link.method == "wa-results.time-country-name"
    assert link.source.text == "1. Georgia HUNTER BELL GBR 1:57.22"  # type: ignore[union-attr]


def test_a_row_without_a_time_is_linked_by_its_whole_name() -> None:
    link = PARIS.link(_entry("Keely", "HODGKINSON", "GBR", None), Sex.WOMEN)
    assert link is not None and link.value.id == 14627708
    link = PARIS.link(_entry("Georgia", "BELL", "GBR", None), Sex.WOMEN)
    assert link is not None and link.method == "wa-results.country-name"
    assert PARIS.link(_entry("Georgia", "SMITH", "GBR", None), Sex.WOMEN) is None


def test_a_link_needs_the_same_sex_and_country() -> None:
    assert PARIS.link(_entry("Georgia", "BELL", "IRL", "117.22"), Sex.WOMEN) is None
    link = PARIS.link(_entry("Max", "BURGIN", "GBR", "117.22"), Sex.MEN)
    assert link is not None and link.value.id == 14720522


def test_birth_dates_rule_out_only_a_match_by_name_and_only_by_year() -> None:
    """Publishers misprint days and months; a result matched by time stands."""
    misprinted = BirthDate(year=1993, month=10, day=18)
    assert PARIS.link(_entry("Georgia", "BELL", "GBR", "117.22", misprinted), Sex.WOMEN)
    assert PARIS.link(_entry("Georgia", "BELL", "GBR", None, misprinted), Sex.WOMEN)
    other_year = BirthDate(year=1990)
    assert PARIS.link(_entry("Georgia", "BELL", "GBR", None, other_year), Sex.WOMEN) is None


def test_words_may_be_spelled_another_way() -> None:
    link = PARIS.link(_entry("Keeley", "HODGKINSEN", "GBR", "116.72"), Sex.WOMEN)
    assert link is not None and link.value.id == 14627708
    assert PARIS.link(_entry("Kay", "HO", "GBR", "116.72"), Sex.WOMEN) is None


def test_a_race_not_finished_is_matched_by_its_status() -> None:
    results = _results(
        ("W", "Halimah NAKAAYI", "UGA", "DNF", "uganda/halimah-nakaayi-14431159"),
        ("W", "Winnie NANYONDO", "UGA", "1:58.00", "uganda/winnie-nanyondo-14431160"),
    )
    link = results.link(_entry("Halima", "NAKAYI", "UGA", None), Sex.WOMEN)
    assert link is not None and link.value.id == 14431159
    assert link.method == "wa-results.status-country-name"


def test_rows_of_one_world_athletics_athlete_are_one_athlete() -> None:
    resolver = IdentityResolver(())
    old, new = (
        PersonName(given="Georgia", family="BELL"),
        PersonName(given="Georgia", family="HUNTER-BELL"),
    )
    current = PersonName(given="Georgia", family="HUNTER BELL")
    resolver.learn([(old, "GBR"), (new, "GBR")])
    resolver.learn_profiles([(old, "GBR", 14329797, current), (new, "GBR", 14329797, current)])
    assert resolver.resolve(old, "GBR", 14329797).athlete == "georgia-hunter-bell"
    assert resolver.resolve(new, "GBR", 14329797).athlete == "georgia-hunter-bell"
    # A row World Athletics does not list, printing a name it links elsewhere.
    assert resolver.resolve(old, "GBR").athlete == "georgia-hunter-bell"
    resolver.check()


def test_a_rule_names_a_world_athletics_athlete() -> None:
    rule = AthleteRule(
        id=athlete_id("carl-lewis"),
        given="Carl",
        family="Lewis",
        country="USA",
        world_athletics=14244008,
        declared=REF,
    )
    resolver = IdentityResolver((rule,))
    assert resolver.resolve(PersonName(given="Carl", family="LEWIS"), "USA").athlete == "carl-lewis"
    assert resolver.profile_of(athlete_id("carl-lewis")) == 14244008


def test_a_rule_contradicting_world_athletics_stops_the_build() -> None:
    rule = AthleteRule(
        id=athlete_id("georgia-bell"),
        given="Georgia",
        family="Bell",
        country="GBR",
        world_athletics=1,
        declared=REF,
    )
    resolver = IdentityResolver((rule,))
    name = PersonName(given="Georgia", family="BELL")
    with pytest.raises(IdentityError, match="georgia-bell"):
        resolver.learn_profiles([(name, "GBR", 14329797, name)])


def test_a_name_linked_to_two_athletes_cannot_identify_an_unlisted_row() -> None:
    resolver = IdentityResolver(())
    name = PersonName(given="Chris", family="TAYLOR")
    resolver.learn_profiles([(name, "JAM", 1, name), (name, "JAM", 2, name)])
    with pytest.raises(IdentityError, match="Chris TAYLOR"):
        resolver.resolve(name, "JAM")
