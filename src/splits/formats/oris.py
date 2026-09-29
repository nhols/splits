"""What a report of an Olympic-style results system (ORIS) says about its race, shared by the
race analysis and results readers and by the discovery of results books.

Results systems built on the Olympic model print the same reports under the same codes, and
name the race in one of two ways::

    Men's 800m                          the Olympic and Commonwealth Games
    WED 4 AUG 2021 Final                the date, then the round: "Round 1 - Heat 2/5"
    Start Time: 21:05

    800m Men                            European Athletics
    SUN 9 JUN 2024
    Start Time22:27 Final               the start time, then the round: "Round 1 Heat 2/4", or
                                        "A-race" for a final run in several races

Each report's footer names it by its event unit and report code, with its version:
``ATHM800M--------------FNL-000100--_77A v2.0`` (``_C77A 1.0`` at European Athletics).
"""

import re
from dataclasses import dataclass

from splits.formats import parse
from splits.formats.base import HeadingReading
from splits.model import RaceKey, Round, Sourced
from splits.pdf.layout import DocumentView, Line, LineMatch

EVENT = r"(?:\d{1,2},\d{3}|\d+)m(?: Hurdles| Steeplechase)?|(?:One |1 )?Mile"
STAGE = (
    r"(?:(?P<round>Final|Semi-?[Ff]inals?|Round 1|Repechage Round|Repechage|Preliminary Round)"
    r"(?:(?: -)? Heat (?P<heat>\d+)(?:/\d+)?| (?P<of>\d+)/\d+)?|(?P<race>[A-Z])-race)"
)
"""The round and, for a round run in several races, which: ``Round 1 - Heat 2/5``,
``Semi-Final 1/3``, ``B-race`` (the second race of a final)."""

OLYMPIC_EVENT = re.compile(rf"^(?P<sex>Men's|Women's) (?P<discipline>{EVENT})$")
OLYMPIC_STAGE = re.compile(rf"^[A-Z]{{3}} (?P<date>\d{{1,2}} [A-Z]{{3}} \d{{4}}) {STAGE}$")
OLYMPIC_START = re.compile(r"^Start Time:? (?P<time>\d{1,2}:\d{2})\b")
EUROPEAN_EVENT = re.compile(rf"^(?P<discipline>{EVENT}) (?P<sex>Men|Women)$")
EUROPEAN_DATE = re.compile(r"^[A-Z]{3} (?P<date>\d{1,2} [A-Z]{3} \d{4})$")
EUROPEAN_STAGE = re.compile(rf"^Start Time ?(?P<time>\d{{1,2}}:\d{{2}}) {STAGE}$")

FOOTER = re.compile(
    r"(?P<unit>[A-Z0-9-]{6,})_C?(?P<report>7\d[A-Z]\d?) (?P<version>v?\d+(?:\.\d+)?) "
    r"Report Created (?P<created>[A-Z]{3} \d{1,2} [A-Z]{3} \d{4} \d{1,2}:\d{2})"
)


@dataclass(frozen=True)
class OrisRace:
    """The lines of a report that name its race."""

    event: LineMatch
    """The discipline and sex."""
    stage: LineMatch
    """The round, and the race within it."""
    date: LineMatch
    start: LineMatch | None


def find_race(view: DocumentView, lines: list[Line]) -> OrisRace | None:
    """The race a report's first page names, in either dialect; ``None`` for anything else."""
    event = view.find(lines, OLYMPIC_EVENT, "heading")
    if event is not None:
        stage = view.find(lines, OLYMPIC_STAGE, "date-round")
        start = view.find(lines, OLYMPIC_START, "start")
        return OrisRace(event, stage, stage, start) if stage else None
    event = view.find(lines, EUROPEAN_EVENT, "heading")
    if event is not None:
        date = view.find(lines, EUROPEAN_DATE, "date")
        stage = view.find(lines, EUROPEAN_STAGE, "start-round")
        return OrisRace(event, stage, date, stage) if date and stage else None
    return None


def heading(race: OrisRace, heat: Sourced[int] | None = None) -> HeadingReading:
    """How the report names its race. ``heat``: a race number read elsewhere (the section of a
    report on a whole round), which takes precedence."""
    stage = race.stage
    if stage["race"]:  # a final run in lettered races: "B-race" is race 2
        return HeadingReading(
            discipline=race.event.read("discipline", parse.discipline),
            sex=race.event.read("sex", parse.sex),
            round=stage.read("race", lambda _: Round.FINAL),
            heat=heat or stage.read("race", lambda letter: ord(letter) - ord("A") + 1),
        )
    return HeadingReading(
        discipline=race.event.read("discipline", parse.discipline),
        sex=race.event.read("sex", parse.sex),
        round=stage.read("round", parse.round_name),
        heat=heat or stage.read_opt("heat", int) or stage.read_opt("of", int),
    )


def race_key(texts: list[str]) -> RaceKey | None:
    """The race the lines of a report's first page name, from their text alone (for listing a
    results book); ``None`` for anything else."""
    event = next((found for text in texts if (found := OLYMPIC_EVENT.match(text))), None)
    stage = next((found for text in texts if (found := OLYMPIC_STAGE.match(text))), None)
    if event is None:
        event = next((found for text in texts if (found := EUROPEAN_EVENT.match(text))), None)
        stage = next((found for text in texts if (found := EUROPEAN_STAGE.match(text))), None)
    if event is None or stage is None:
        return None
    number: int | None
    if stage["race"]:
        round_, number = Round.FINAL, ord(stage["race"]) - ord("A") + 1
    else:
        round_ = parse.round_name(stage["round"])
        printed = stage["heat"] or stage["of"]
        number = int(printed) if printed else None
    return RaceKey(
        discipline=parse.discipline(event["discipline"]),
        sex=parse.sex(event["sex"]),
        round=round_,
        heat=number,
    )
