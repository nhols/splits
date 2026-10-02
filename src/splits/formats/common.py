"""Building blocks shared by format readers."""

import re
from collections.abc import Callable, Iterable
from decimal import Decimal

from splits.formats import parse
from splits.model import Qualification, Round, Sourced
from splits.model.values import RECORD_TAGS
from splits.pdf.layout import DocumentView, Line, LineMatch
from splits.pdf.textlayer import Word

TIME_WORD = re.compile(r"\d{1,2}(?::\d{2})?\.\d{1,3}")
"""A time as timing reports print it: to the hundredth, the thousandth, or (older Diamond
League race analyses, laser-timed) the tenth."""
RANK_WORD = re.compile(r"\(=?\d+\)")
RECORD_TAG = re.compile(rf"=?(?:{'|'.join(RECORD_TAGS)})")
RULE_PREFIX = ("TR", "R", "Rule")
"""Words a rule's number may be printed after, as a word of its own: ``TR 16.8``, ``R 163.2``."""
RULE_NUMBER = re.compile(r"\d+(?:\.\d+)*[a-z]?(?:\([a-z]\))?")
CARD = r"YC|YRC|RC|L"
"""A card or mark shown to an athlete, printed beside the name or before the result: a yellow,
yellow-red or red card, or ``L`` for a lane infringement."""


def time_tokens(line: Line) -> list[tuple[Word, Word | None]]:
    """If ``line`` holds only times, each optionally followed by a bracketed rank such as
    ``(3)``, the ``(time, rank)`` pairs; otherwise an empty list. What some documents print in
    the column of a point the timing recorded nothing at is passed over: ``NO VALUE``, a status
    (``DNF (12)``, at the finish of an athlete who did not reach it), or a rank alone."""
    pairs: list[tuple[Word, Word | None]] = []
    words = line.words
    index = 0
    while index < len(words):
        if (
            words[index].text == "NO"
            and index + 1 < len(words)
            and words[index + 1].text == "VALUE"
        ):
            index += 2  # a time the timing did not record: the others keep their columns
            continue
        if words[index].text in ("DNF", "DNS", "DQ"):
            index += 1
            if index < len(words) and RANK_WORD.fullmatch(words[index].text):
                index += 1
            continue
        if RANK_WORD.fullmatch(words[index].text):
            index += 1  # a rank printed without its time
            continue
        if not TIME_WORD.fullmatch(words[index].text):
            return []
        following = words[index + 1] if index + 1 < len(words) else None
        if following is not None and RANK_WORD.fullmatch(following.text):
            pairs.append((words[index], following))
            index += 2
        else:
            pairs.append((words[index], None))
            index += 1
    return pairs


def mentions_time(line: Line) -> bool:
    return any(TIME_WORD.fullmatch(word.text) for word in line.words)


def split_band(
    view: DocumentView, lines: list[Line], start: int, is_row: Callable[[Line], bool]
) -> list[Line]:
    """The split lines following the athlete row at ``lines[start]``: every following line
    made only of times and ranks, up to the next athlete row or any other line. A line that
    holds times but is neither a split line nor an athlete row is an error, not a silent loss
    of data."""
    band: list[Line] = []
    for line in lines[start + 1 :]:
        if time_tokens(line):
            band.append(line)
            continue
        if mentions_time(line) and not is_row(line):
            raise view.error(f"unrecognised line after an athlete row: {line.text!r}", line.page)
        break
    return band


def read_tail(
    view: DocumentView, row: LineMatch, group: str = "tail"
) -> tuple[tuple[Sourced[str], ...], Sourced[Qualification] | None, tuple[Sourced[str], ...]]:
    """Classify the annotations after a result: record tags (``PB``, ``=SB``, ``WR,OR``),
    a qualification mark (``Q``/``q``), and anything else as remarks (``TR17.3.1``, ``YC``).
    A rule printed in two words (``TR 16.8``) is one remark."""
    records: list[Sourced[str]] = []
    remarks: list[Sourced[str]] = []
    qualification: Sourced[Qualification] | None = None
    words = list(row.words(group)) if row[group] else []
    index = 0
    while index < len(words):
        word = words[index]
        index += 1
        following = words[index] if index < len(words) else None
        if word.text in RULE_PREFIX and following and RULE_NUMBER.fullmatch(following.text):
            text = f"{word.text} {following.text}"
            pair = [word, following]
            remarks.append(view.read(row.line.page, pair, str, f"{row.rule}.remark", text))
            index += 1
            continue
        for token in word.text.split(","):
            if not token:
                continue
            if RECORD_TAG.fullmatch(token):
                records.append(view.read(row.line.page, [word], str, f"{row.rule}.record", token))
            elif token in ("Q", "q") and qualification is None:
                qualification = view.read(
                    row.line.page, [word], Qualification, f"{row.rule}.qualification", token
                )
            else:
                remarks.append(view.read(row.line.page, [word], str, f"{row.rule}.remark", token))
    return tuple(records), qualification, tuple(remarks)


def read_first[T](
    view: DocumentView,
    lines: Iterable[Line],
    pattern: re.Pattern[str],
    rule: str,
    group: str,
    parser: Callable[[str], T],
) -> Sourced[T] | None:
    """Read ``group`` from the first line ``pattern`` matches, if any does."""
    found = view.find(lines, pattern, rule)
    return found.read(group, parser) if found else None


def wind_before_unit(
    view: DocumentView,
    page: int,
    unit: str = "m/s",
    within: tuple[float, float] | None = None,
) -> Sourced[Decimal] | None:
    """A wind reading: the signed number printed immediately left of ``m/s``, optionally only
    between two heights on the page (for documents with several races on a page)."""
    words = view.layer.page(page).words
    if within is not None:
        words = tuple(word for word in words if within[0] <= word.yc <= within[1])
    for unit_word in (word for word in words if word.text == unit):
        for word in words:
            if abs(word.yc - unit_word.yc) < 4 and 0 <= unit_word.x0 - word.x1 < 4:
                return view.read(page, [word], parse.signed_decimal, "weather.wind")
    return None


_OMEGA_RACE = (
    r"(?P<race>(?:Dream )?(?P<discipline>(?:\d{1,2},\d{3}|\d+)m(?: Hurdles| Steeplechase)?"
    r"|(?:1 |One )?Mile|2 Miles)(?: (?P<b_before>B))? (?P<sex>Men|Women)"
    r"(?: - (?:(?P<final>Final)|(?:Round 1 )?Heat (?P<heat>\d|[A-Z])"
    r"|(?P<b>B(?: Race)?)(?: - Heat (?P<b_heat>\d))?"
    r"|(?:[A-Z][a-z]+ )+(?:Mile|\d+m)|[A-Z][a-z]+ [A-Z][a-z]+|International|promotional))?)"
)
_OMEGA_TIME = r"(?P<time>\d{1,2}:\d{2}) (?P<date>\d{1,2} [A-Z]{3} \d{4})"
_OMEGA_REVISED = r"(?: \d{1,2} [A-Z]{3} \d{1,2}:\d{2})"

OMEGA_HEADING = re.compile(rf"^{_OMEGA_RACE}(?: {_OMEGA_TIME}{_OMEGA_REVISED}?)?$")
"""An OMEGA race heading: ``100m Women``, ``10,000m Men``, and for an event run in heats and a
final ``110m Hurdles Men - Round 1 Heat 1`` (or ``Heat A``) and ``110m Hurdles Men - Final``.
Races named for someone keep the name: ``1 Mile Men - Bowerman Mile``, ``Dream Mile Men``,
``800m Women - Mutola 800m``, or by the name alone: ``1 Mile Men - Emsley Carr``. A meeting's
race outside its Diamond League programme may be ``- promotional`` (or, at the Prefontaine
Classic, ``- International``). A B race is
``800m Men - B Race`` (``- B`` in 2017, ``800m B Men`` in 2025), and its heats
``100m Women - B Race - Heat 1``. Some meetings print the start time on the same line."""

OMEGA_START = re.compile(rf"^(?:{_OMEGA_RACE} )?{_OMEGA_TIME}{_OMEGA_REVISED}?$")
"""The start time and date, on a line of its own or after the heading; a revised document adds
when it was revised (``20:02 28 AUG 2025 28 AUG 20:17``)."""


def omega_round(heading: LineMatch) -> tuple[Sourced[Round] | None, Sourced[int] | None]:
    """The round and heat an OMEGA heading names, if any: Diamond League events are usually
    single races, and then it names none."""
    if heading["b"] or heading["b_before"]:
        b_race = heading.read("b" if heading["b"] else "b_before", lambda _: Round.B_RACE)
        return b_race, heading.read_opt("b_heat", int)
    if heading["final"]:
        return heading.read("final", parse.round_name), None
    if heading["heat"]:
        return (
            heading.read("heat", lambda _: Round.HEAT),
            heading.read(
                "heat", lambda text: int(text) if text.isdigit() else ord(text) - ord("A") + 1
            ),
        )
    return None, None
