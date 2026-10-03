"""Which World Athletics athlete each printed row names, from World Athletics' own results.

World Athletics lists every result of a competition with the athlete it belongs to (see
:mod:`splits.acquire.world_athletics`). A row of a document is that athlete's when, among the
competition's results of the same sex, exactly one World Athletics athlete fits it:

1. by result: a result with the row's finishing time (to the hundredth, or within the tenth
   for a time printed to the tenth) and a word of the row's name, or the same DNF, DNS or DQ
   and two words of the row's name (or its only word), and the row's country;
2. failing that (a result World Athletics gives differently), by name: a result with the row's
   country and two words of the row's name (or its only word), and no other birth year.

Words are compared case- and accent-insensitively and allow a letter or two of another
spelling (``NAKAYI``, ``NAKAAYI``; not ``FERRARIO``, ``FERRARA``). Birth dates rule out only a
match by name, and only by the year: publishers misprint days and months (Halimah Nakaayi is
born on the 14th in some documents, the 16th in others). Several athletes fitting, or none,
leaves the row unlinked: it is identified by its name, as before.
"""

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any

from splits.assemble.identity import fold
from splits.formats.base import EntryReading
from splits.model import (
    BirthDate,
    CompetitionId,
    PersonName,
    RegistryRef,
    Retrieval,
    Sex,
    Sourced,
    Status,
    WorldAthleticsAthlete,
)

REGISTRY = "world-athletics"
_PROFILE_ID = re.compile(r"-0*(\d+)$")
_MARK = re.compile(r"^(?:(\d+):)?(?:(\d+):)?(\d+(?:\.\d+)?)$")
_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

HOME_NATIONS = dict.fromkeys(("ENG", "SCO", "WAL", "NIR", "JEY", "GGY"), "GBR")
"""Commonwealth Games teams that World Athletics counts as Great Britain."""
COUNTRY_SPELLINGS = {"TRI": "TTO"}
"""Codes printed for a country that World Athletics now writes another way."""


_STATUSES = {"DNF": Status.DID_NOT_FINISH, "DNS": Status.DID_NOT_START, "DQ": Status.DISQUALIFIED}


@dataclass(frozen=True)
class _Result:
    sex: Sex
    seconds: Decimal | None
    status: Status | None
    country: str
    athlete: WorldAthleticsAthlete
    words: frozenset[str]
    birth_date: BirthDate | None
    pointer: str
    text: str


class WorldAthleticsResults:
    """The results of one competition, as pinned in its lock file."""

    def __init__(self, competition: CompetitionId, retrieval: Retrieval, content: bytes) -> None:
        self.competition = competition
        self.retrieval = retrieval
        self.results = tuple(_results(json.loads(content)))

    def link(self, entry: EntryReading, sex: Sex) -> Sourced[WorldAthleticsAthlete] | None:
        """The World Athletics athlete the row names, if exactly one fits."""
        if entry.country is None:
            return None
        country = _country(entry.country.value)
        words = _words(entry.name.value)
        if not words:
            return None
        candidates = [r for r in self.results if r.sex is sex and r.country == country]
        result = entry.result.value
        needed = min(2, len(words))
        if result.status is Status.FINISHED:
            assert result.time is not None
            same = [r for r in candidates if _same_time(result.time, r.seconds)]
            method, words_needed = "wa-results.time-country-name", 1
        else:
            same = [r for r in candidates if r.status is result.status]
            method, words_needed = "wa-results.status-country-name", needed
        if found := _one([r for r in same if _shared(words, r.words) >= words_needed]):
            return self._sourced(found, method)
        born = entry.birth_date.value if entry.birth_date is not None else None
        named = [
            r for r in candidates if _shared(words, r.words) >= needed and _born_alike(born, r)
        ]
        if found := _one(named):
            return self._sourced(found, "wa-results.country-name")
        return None

    def _sourced(self, result: _Result, method: str) -> Sourced[WorldAthleticsAthlete]:
        return Sourced(
            value=result.athlete,
            source=RegistryRef(
                registry=REGISTRY,
                sha256=self.retrieval.sha256,
                pointer=result.pointer,
                text=result.text,
            ),
            method=method,
        )


def _one(results: list[_Result]) -> _Result | None:
    athletes = {result.athlete.id for result in results}
    return results[0] if len(athletes) == 1 else None


def _same_time(time: Decimal, listed: Decimal | None) -> bool:
    if listed is None:
        return False
    if abs(listed - time) <= Decimal("0.005"):
        return True
    # A time printed to the tenth (OMEGA's 2023 analyses cut 4:07.64 to 4:07.6).
    return time.as_tuple().exponent == -1 and abs(listed - time) < Decimal("0.1")


def _shared(words: frozenset[str], listed: frozenset[str]) -> int:
    """How many of a row's words World Athletics' name has, allowing another spelling."""
    return sum(1 for word in words if any(_alike(word, other) for other in listed))


def _alike(word: str, other: str) -> bool:
    if word == other:
        return True
    return min(len(word), len(other)) >= 4 and SequenceMatcher(None, word, other).ratio() >= 0.85


def _born_alike(born: BirthDate | None, result: _Result) -> bool:
    return born is None or result.birth_date is None or born.year == result.birth_date.year


def _country(code: str) -> str:
    return HOME_NATIONS.get(code, COUNTRY_SPELLINGS.get(code, code))


def _words(name: PersonName) -> frozenset[str]:
    """A name's words of two letters or more: initials match nothing."""
    return frozenset(word for word in fold(f"{name.given} {name.family}").split() if len(word) > 1)


def split_name(listed: str) -> PersonName:
    """World Athletics writes the family name in capitals: ``Georgia HUNTER BELL``."""
    words = listed.split()
    family_from = len(words)
    while family_from > 0 and _capitals(words[family_from - 1]):
        family_from -= 1
    if family_from == len(words):  # no capitals: the last word
        family_from = len(words) - 1
    if family_from == 0 and len(words) > 1:  # all capitals: the given names first
        family_from = len(words) - 1
    return PersonName(given=" ".join(words[:family_from]), family=" ".join(words[family_from:]))


def _capitals(word: str) -> bool:
    letters = [char for char in word if char.isalpha()]
    return bool(letters) and all(char.isupper() for char in letters)


def _results(answer: dict[str, Any]) -> list[_Result]:
    found: list[_Result] = []
    for d, day in enumerate(answer["days"]):
        for t, title in enumerate(day.get("eventTitles") or []):
            for e, event in enumerate(title.get("events") or []):
                sex = {"M": Sex.MEN, "W": Sex.WOMEN}.get(event.get("gender") or "")
                if sex is None:
                    continue
                for r, race in enumerate(event.get("races") or []):
                    for i, result in enumerate(race.get("results") or []):
                        pointer = f"/days/{d}/eventTitles/{t}/events/{e}/races/{r}/results/{i}"
                        listed = _result(result, sex, pointer)
                        if listed is not None:
                            found.append(listed)
    return found


def _result(result: dict[str, Any], sex: Sex, pointer: str) -> _Result | None:
    competitor = result.get("competitor") or {}
    slug, listed_name = competitor.get("urlSlug"), competitor.get("name")
    match = _PROFILE_ID.search(slug) if isinstance(slug, str) else None
    if match is None or not listed_name or not result.get("nationality"):
        return None  # a relay team, or an athlete without a profile
    name = split_name(listed_name)
    athlete = WorldAthleticsAthlete(id=int(match.group(1)), name=name, url_slug=match.string)
    mark = (result.get("mark") or "").strip()
    text = " ".join(
        part for part in (result.get("place"), listed_name, result["nationality"], mark) if part
    )
    return _Result(
        sex=sex,
        seconds=_seconds(mark),
        status=_STATUSES.get(mark.upper()),
        country=result["nationality"],
        athlete=athlete,
        words=_words(name),
        birth_date=_birth_date(competitor.get("birthDate")),
        pointer=pointer,
        text=text,
    )


def _seconds(mark: str) -> Decimal | None:
    match = _MARK.match(mark)
    if match is None:
        return None
    total = Decimal(0)
    for part in match.groups():
        if part is not None:
            total = total * 60 + Decimal(part)
    return total


def _birth_date(text: str | None) -> BirthDate | None:
    """``21 AUG 1986``, or a year alone."""
    parts = (text or "").split()
    try:
        if len(parts) == 3:
            return BirthDate(
                year=int(parts[2]), month=_MONTHS.index(parts[1]) + 1, day=int(parts[0])
            )
        if len(parts) == 1:
            return BirthDate(year=int(parts[0]))
    except ValueError:
        return None
    return None
