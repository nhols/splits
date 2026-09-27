"""Parsers for values as results documents print them.

Each parser takes the exact printed text and returns a typed value, or raises ``ValueError``.
They are shared by every format reader, so a convention (say, how a two-digit birth year is
read) is decided once.
"""

import re
import unicodedata
from datetime import date, time
from decimal import Decimal

from splits.model import BirthDate, DisciplineId, PersonName, Result, Round, Sex, Status
from splits.model.ids import discipline_id

MONTHS = {
    name: number
    for number, names in enumerate(
        (
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ),
        start=1,
    )
    for name in names
}

_SECONDS = re.compile(r"(?:(?P<h>\d+):(?=\d{1,2}:))?(?:(?P<m>\d+):)?(?P<s>\d+(?:\.\d{1,3})?)")


def seconds(text: str) -> Decimal:
    """A time: ``"44.22"`` -> 44.22, ``"1:43.12"`` -> 103.12, ``"2:03:45"`` -> 7425.

    The result keeps the printed precision: ``"44.20"`` -> ``Decimal("44.20")``.
    """
    match = _SECONDS.fullmatch(text.strip())
    if not match:
        raise ValueError(f"not a time: {text!r}")
    total = Decimal(match["s"])
    if match["m"] is not None:
        if total >= 60:
            raise ValueError(f"seconds out of range in {text!r}")
        total += 60 * int(match["m"])
    if match["h"] is not None:
        if int(match["m"]) >= 60:
            raise ValueError(f"minutes out of range in {text!r}")
        total += 3600 * int(match["h"])
    return total


def precise_time(text: str) -> Decimal:
    """A result with its thousandths in brackets: ``"20.90 (.893)"`` -> 20.893.

    The hundredths are rounded up from the thousandths, so ``"21.00 (.995)"`` is 20.995."""
    match = re.fullmatch(r"(?P<result>\S+) \((?P<fraction>\.\d{3})\)", text.strip())
    if not match:
        raise ValueError(f"not a time with thousandths: {text!r}")
    shown = seconds(match["result"])
    whole = int(shown)
    for candidate in (whole + Decimal(match["fraction"]), whole - 1 + Decimal(match["fraction"])):
        if (candidate * 100).to_integral_value(rounding="ROUND_CEILING") == shown * 100:
            return candidate
    raise ValueError(f"thousandths {match['fraction']} do not round up to {match['result']}")


def rank(text: str) -> int:
    """A position, possibly tied and bracketed: ``"(4)"``, ``"(=1)"``, ``"3"``."""
    match = re.fullmatch(r"\(?=?(\d+)\)?", text.strip())
    if not match or int(match[1]) < 1:
        raise ValueError(f"not a rank: {text!r}")
    return int(match[1])


_STATUSES = {
    "DNF": Status.DID_NOT_FINISH,
    "DNS": Status.DID_NOT_START,
    "DQ": Status.DISQUALIFIED,
    "DSQ": Status.DISQUALIFIED,
}


def result(text: str) -> Result:
    """A result: a finishing time, or ``DNF`` / ``DNS`` / ``DQ``."""
    status = _STATUSES.get(text.strip().upper())
    if status is not None:
        return Result(status=status)
    return Result(status=Status.FINISHED, time=seconds(text))


def signed_decimal(text: str) -> Decimal:
    """A signed reading such as a wind speed: ``"+0.3"``, ``"-1.2"``, ``"0.0"``."""
    match = re.fullmatch(r"([+-]?)(\d+(?:\.\d+)?)", text.strip())
    if not match:
        raise ValueError(f"not a number: {text!r}")
    return Decimal(match[1] + match[2])


def day_month_year(text: str) -> date:
    """A date with the month in words, e.g. ``"24 August 2023"``, ``"THU 8 AUG 2024"``."""
    match = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})", text)
    if not match or match[2].lower() not in MONTHS:
        raise ValueError(f"not a date: {text!r}")
    return date(int(match[3]), MONTHS[match[2].lower()], int(match[1]))


def clock(text: str) -> time:
    """A time of day: ``"21:34"``."""
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", text.strip())
    if not match:
        raise ValueError(f"not a time of day: {text!r}")
    return time(int(match[1]), int(match[2]))


def birth_date_short(text: str, on: date) -> BirthDate:
    """A birth date with a two-digit year, e.g. ``"11 Sep 01"``, or the year alone (``"01"``),
    read relative to the race date ``on``: the century is the one that makes the athlete
    between 10 and 110 years old."""
    match = re.fullmatch(r"(?:(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+)?(\d{2})", text.strip())
    if not match or (match[2] is not None and match[2].lower() not in MONTHS):
        raise ValueError(f"not a birth date: {text!r}")
    for century in (on.year // 100 * 100, on.year // 100 * 100 - 100):
        year = century + int(match[3])
        if 10 <= on.year - year <= 110:
            if match[1] is None:
                return BirthDate(year=year)
            return BirthDate(year=year, month=MONTHS[match[2].lower()], day=int(match[1]))
    raise ValueError(f"implausible birth year in {text!r} for a race on {on}")


def country(text: str) -> str:
    if not re.fullmatch(r"[A-Z]{3}", text):
        raise ValueError(f"not a country code: {text!r}")
    return text


def sex(text: str) -> Sex:
    """``Men``, ``Women``, ``Men's``, ``hommes`` ... -> :class:`Sex`."""
    word = re.sub(r"['’]s$", "", text.strip().lower())
    for sex_value, words in (
        (Sex.MEN, ("men", "man", "male", "hommes")),
        (Sex.WOMEN, ("women", "woman", "female", "femmes")),
        (Sex.MIXED, ("mixed",)),
    ):
        if word in words:
            return sex_value
    raise ValueError(f"not a sex: {text!r}")


def discipline(text: str) -> DisciplineId:
    """An event name: ``"400 Metres Hurdles"``, ``"400m Hurdles"``, ``"200m"`` -> ``400mh``...;
    ``"3000m Steeplechase"`` -> ``3000msc``; ``"Mile"`` -> ``mile``; ``"2 Miles"`` ->
    ``2-miles``."""
    words = " ".join(text.strip().lower().replace(",", "").split())
    if words in ("mile", "one mile", "1 mile"):
        return discipline_id("mile")
    if words in ("2 miles", "two miles"):
        return discipline_id("2-miles")
    match = re.fullmatch(
        r"(\d+)\s*(?:m|metres|meters)\s*(hurdles|h|steeplechase|sc)?", words, flags=re.IGNORECASE
    )
    if not match:
        raise ValueError(f"not a recognised event: {text!r}")
    suffix = {None: "", "hurdles": "h", "h": "h", "steeplechase": "sc", "sc": "sc"}[match[2]]
    return discipline_id(f"{match[1]}m{suffix}")


def round_name(text: str) -> Round:
    """A round as programmes name it: ``Final``, ``Semi-Final``, ``Round 1``, ``Heats`` ..."""
    words = re.sub(r"[\s-]+", " ", text.strip().lower())
    names = {
        "final": Round.FINAL,
        "finals": Round.FINAL,
        "semi final": Round.SEMI_FINAL,
        "semi finals": Round.SEMI_FINAL,
        "quarter final": Round.QUARTER_FINAL,
        "quarter finals": Round.QUARTER_FINAL,
        "round 1": Round.HEAT,
        "heat": Round.HEAT,
        "heats": Round.HEAT,
        "round 2": Round.QUARTER_FINAL,
        "repechage": Round.REPECHAGE,
        "repechage round": Round.REPECHAGE,
        "preliminary round": Round.PRELIMINARY,
    }
    if words not in names:
        raise ValueError(f"not a recognised round: {text!r}")
    return names[words]


# ---- Names ------------------------------------------------------------------------------------

PARTICLES = frozenset(
    {
        "al",
        "bin",
        "da",
        "das",
        "de",
        "del",
        "della",
        "den",
        "der",
        "des",
        "di",
        "do",
        "dos",
        "du",
        "el",
        "la",
        "le",
        "ten",
        "ter",
        "van",
        "von",
        "zu",
    }
)
"""Lower-case words that belong to the family name that follows them: ``van NIEKERK``."""


def _is_latin(token: str) -> bool:
    return any("LATIN" in unicodedata.name(char, "") for char in token)


def _is_capitalised(token: str) -> bool:
    """Whether ``token`` is written the way documents mark family names: in capitals,
    allowing a Mc/Mac/O' prefix (``WARHOLM``, ``McMASTER``, ``HUDSON-SMITH``, ``KOŠIR``)."""
    letters = [char for char in re.sub(r"^(?:Mc|Mac|O')", "", token) if char.isalpha()]
    return bool(letters) and all(char.isupper() for char in letters)


def _is_particle(token: str) -> bool:
    return token.lower() in PARTICLES and not token.isupper()


def _in_family_name(ordered: list[str], index: int, family_first: bool, taken: int) -> bool:
    token = ordered[index]
    if _is_capitalised(token):
        return True
    if not _is_particle(token):
        return False
    if family_first:  # the particles precede the capitalised word they belong to
        rest = index + 1
        while rest < len(ordered) and _is_particle(ordered[rest]):
            rest += 1
        return rest < len(ordered) and _is_capitalised(ordered[rest])
    return taken > 0  # walking backwards: it follows a word already taken


def person_name(text: str, *, family_first: bool) -> PersonName:
    """Split a printed name into given and family names.

    Documents mark the family name by writing it in capitals; they differ in order:
    ``Karsten WARHOLM`` (``family_first=False``) or ``WARHOLM Karsten`` (``True``).
    Words in a non-Latin script (e.g. katakana printed alongside) become ``local``. An athlete
    known by one name (``ANKITA``) has no given name.
    """
    # A nickname in brackets is not part of the name: ``van den BERG Isabel (Phanos)``.
    tokens = re.sub(r"\s*\([^)]*\)", "", text).split()
    latin = [token for token in tokens if _is_latin(token)]
    local = " ".join(token for token in tokens if not _is_latin(token)) or None
    if len(latin) == 1 and _is_capitalised(latin[0]):
        return PersonName(given="", family=latin[0], local=local)  # known by one name
    if len(latin) < 2:
        raise ValueError(f"expected a given and a family name in {text!r}")

    # Walk from the family-name end of the name, taking capitalised words and the particles
    # attached to them ("dos SANTOS"), and stop at the first given name.
    ordered = latin if family_first else latin[::-1]
    family_count = 0
    for index in range(len(ordered)):
        if not _in_family_name(ordered, index, family_first, family_count):
            break
        family_count = index + 1
    if family_count == 0:
        raise ValueError(f"no family name (in capitals) in {text!r}")
    family_count = min(family_count, len(ordered) - 1)  # always leave a given name

    family_tokens = ordered[:family_count]
    given_tokens = ordered[family_count:]
    if not family_first:
        family_tokens, given_tokens = family_tokens[::-1], given_tokens[::-1]
    return PersonName(given=" ".join(given_tokens), family=" ".join(family_tokens), local=local)
