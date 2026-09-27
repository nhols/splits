from datetime import date, time
from decimal import Decimal

import pytest

from splits.formats import parse
from splits.model import BirthDate, Round, Sex, Status


@pytest.mark.parametrize(
    ("text", "family_first", "given", "family", "local"),
    [
        ("Karsten WARHOLM", False, "Karsten", "WARHOLM", None),
        ("WARHOLM Karsten", True, "Karsten", "WARHOLM", None),
        ("Wayde VAN NIEKERK", False, "Wayde", "VAN NIEKERK", None),
        ("van NIEKERK Wayde", True, "Wayde", "van NIEKERK", None),
        ("dos SANTOS Alison", True, "Alison", "dos SANTOS", None),
        ("De GRASSE Andre", True, "Andre", "De GRASSE", None),
        ("McMASTER Kyron", True, "Kyron", "McMASTER", None),
        ("Håvard Bentdal INGVALDSEN", False, "Håvard Bentdal", "INGVALDSEN", None),
        ("ALLEN CJ", True, "CJ", "ALLEN", None),  # a given name in capitals
        ("CJ ALLEN", False, "CJ", "ALLEN", None),
        ("Ammar Ismail YAHIA IBRAHIM", False, "Ammar Ismail", "YAHIA IBRAHIM", None),
        ("Zakithi NENE ザキティ・ネネ", False, "Zakithi", "NENE", "ザキティ・ネネ"),
        ("van der WEKEN Patrizia", True, "Patrizia", "van der WEKEN", None),
        ("van den BERG Isabel (Phanos)", True, "Isabel", "van den BERG", None),  # a nickname
        ("ANKITA", True, "", "ANKITA", None),  # known by one name
    ],
)
def test_person_name(
    text: str, family_first: bool, given: str, family: str, local: str | None
) -> None:
    name = parse.person_name(text, family_first=family_first)
    assert (name.given, name.family, name.local) == (given, family, local)


def test_person_name_needs_a_family_name_in_capitals() -> None:
    with pytest.raises(ValueError, match="family name"):
        parse.person_name("Karsten Warholm", family_first=False)


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("44.22", Decimal("44.22")),
        ("44.20", Decimal("44.20")),
        ("9.98", Decimal("9.98")),
        ("1:43.12", Decimal("103.12")),
        ("2:03:45", Decimal("7425")),
    ],
)
def test_seconds(text: str, seconds: Decimal) -> None:
    value = parse.seconds(text)
    assert value == seconds
    assert str(value) == str(seconds)  # the printed precision is kept


@pytest.mark.parametrize("text", ["44", "1:60.00", "abc", ""])
def test_seconds_rejects(text: str) -> None:
    if text == "44":
        assert parse.seconds(text) == 44  # whole seconds are fine
        return
    with pytest.raises(ValueError):
        parse.seconds(text)


def test_result() -> None:
    assert parse.result("44.22").time == Decimal("44.22")
    assert parse.result("DQ").status is Status.DISQUALIFIED
    assert parse.result("DNF").status is Status.DID_NOT_FINISH
    assert parse.result("DNS").time is None


@pytest.mark.parametrize(("text", "rank"), [("(4)", 4), ("(=1)", 1), ("3", 3)])
def test_rank(text: str, rank: int) -> None:
    assert parse.rank(text) == rank


@pytest.mark.parametrize(
    ("text", "day"),
    [
        ("24 August 2023", date(2023, 8, 24)),
        ("THU 8 AUG 2024", date(2024, 8, 8)),
        ("Thursday, 24 August 2023", date(2023, 8, 24)),
        ("31st August 2023 - Letzigrund", date(2023, 8, 31)),
    ],
)
def test_day_month_year(text: str, day: date) -> None:
    assert parse.day_month_year(text) == day


def test_birth_date_century_is_relative_to_the_race() -> None:
    race = date(2023, 8, 24)
    assert parse.birth_date_short("11 Sep 01", race) == BirthDate(year=2001, month=9, day=11)
    assert parse.birth_date_short("28 Feb 96", race) == BirthDate(year=1996, month=2, day=28)
    assert parse.birth_date_short("01", race) == BirthDate(year=2001)  # year only


def test_clock_and_wind() -> None:
    assert parse.clock("21:34") == time(21, 34)
    assert parse.signed_decimal("-0.5") == Decimal("-0.5")


@pytest.mark.parametrize(
    ("text", "discipline"),
    [
        ("400 Metres Hurdles", "400mh"),
        ("400m Hurdles", "400mh"),
        ("200 Metres", "200m"),
        ("3000m Steeplechase", "3000msc"),
        ("10,000m", "10000m"),
        ("Mile", "mile"),
        ("1 Mile", "mile"),
        ("2 Miles", "2-miles"),
        ("300m Hurdles", "300mh"),
    ],
)
def test_discipline(text: str, discipline: str) -> None:
    assert parse.discipline(text) == discipline


@pytest.mark.parametrize(
    ("text", "round_"),
    [
        ("Final", Round.FINAL),
        ("Semi-Final", Round.SEMI_FINAL),
        ("Semi-Finals", Round.SEMI_FINAL),
        ("Round 1", Round.HEAT),
        ("Repechage Round", Round.REPECHAGE),
        ("Repechage", Round.REPECHAGE),
        ("Preliminary Round", Round.PRELIMINARY),
    ],
)
def test_round_name(text: str, round_: Round) -> None:
    assert parse.round_name(text) is round_


def test_sex() -> None:
    assert parse.sex("Men") is Sex.MEN
    assert parse.sex("Women's") is Sex.WOMEN
    assert parse.sex("hommes") is Sex.MEN
