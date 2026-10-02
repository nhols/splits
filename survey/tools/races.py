"""Individual track races from the harvested World Athletics results.

A competition's results name each event ("Women's 400 Metres Short Track", "Men's 110 Metres
Hurdles (91.4cm)") and each race in it ("Round 1 - Heat", number 3). Only senior individual
track races are kept: relays, walks, road and field events, combined-event races ("Combined -
Group") and the age-group, masters and para sections of a programme are left out. Each race
keeps its section title, which at one-day meetings separates the meeting's own races ("Diamond
Discipline", "Promotional Events") from its undercard ("Pre-Programme", "National Events").
"""

import gzip
import json
import re
from dataclasses import dataclass
from typing import Any

from world_athletics import RESULTS

NOT_TRACK = re.compile(
    r"Relay|Walk|athlon|Marathon|Road|Cross|Kilometres|Jump|Vault|Put|Throw|Medley|Hour|"
    r"Wheelchair| x |\u00d7",
    re.I,
)
NOT_SENIOR = re.compile(r"U1\d|U2\d|Masters|Disabled|Para|Combined|Decathlon|Heptathlon", re.I)
EN_ROUTE = "Split times"
"""A section of times taken inside a longer race (the 1500 m of a mile), not races of its own."""
NOT_ELITE = re.compile(
    r"Young|Youth|Junior|School|Kids|Development|Warm Up|Demo|Veteran|Exhibition", re.I
)
"""Section titles of races that are never the meeting's own elite races."""
UNDERCARD = re.compile(
    r"Pre-Programme|Pre Programme|Pre Meet|(?<!Inter)National|Regional|Extra|Open", re.I
)
"""Section titles that hold a meeting's undercard but also, at some meetings, its non-circuit
international races ("National Events" at Diamond League meetings): such a race is undercard
only when its field is a national one."""
NATIONAL_FIELD = 0.8
"""The share of host-country athletes that makes a field national, as in the catalog."""

ROUNDS = {
    "Preliminary Round - Heat": "preliminary",
    "Round 1 - Heat": "heat",
    "Round 2 - Heat": "round-2",
    "Repechage Round - Heat": "repechage",
    "Quarterfinal - Heat": "quarter-final",
    "Semifinal - Heat": "semi-final",
    "Final": "final",
}
NOT_RACES = {"Combined - Group", "Qualification - Group", "Extra Race - Heat"}


@dataclass(frozen=True)
class Race:
    competition: int
    discipline: str
    sex: str
    indoor: bool
    nonstandard: bool
    """The event's name carries a barrier height or weight: an age-group implement."""
    round: str
    number: int | None
    date: str | None
    starters: int
    section: str | None
    undercard: bool


def discipline(event: str) -> tuple[str, str, bool, bool] | None:
    """Our discipline id, the sex, whether indoor, whether non-standard, or ``None``."""
    if NOT_TRACK.search(event):
        return None
    found = re.match(r"(Men|Women)'s (.+)$", event)
    if found is None:
        return None
    sex = found[1].lower()
    name = found[2]
    indoor = "Short Track" in name
    name = name.replace(" Short Track", "").strip()
    nonstandard = "(" in name
    name = re.sub(r"\s*\(.*?\)", "", name)
    if name in ("Mile", "One Mile"):
        return "mile", sex, indoor, nonstandard
    if name == "2 Miles":
        return "2-miles", sex, indoor, nonstandard
    parts = re.match(r"([\d,]+) (Metres|Yards)( Hurdles| Steeplechase)?$", name)
    if parts is None:
        return None
    unit = "m" if parts[2] == "Metres" else "y"
    suffix = {" Hurdles": "h", " Steeplechase": "sc", None: ""}[parts[3]]
    return f"{parts[1].replace(',', '')}{unit}{suffix}", sex, indoor, nonstandard


def _undercard(title: str | None, results: list[dict[str, Any]], host: str | None) -> bool:
    if not title:
        return False
    if NOT_ELITE.search(title):
        return True
    if not UNDERCARD.search(title):
        return False
    countries = [r.get("nationality") for r in results if r.get("nationality")]
    if not countries or host is None:
        return True
    return countries.count(host) / len(countries) >= NATIONAL_FIELD


def _same_field(a: frozenset[str | None], b: frozenset[str | None]) -> bool:
    """Whether two listings are of one race: most of the smaller field ran in the other. A
    listing without results cannot be told apart from any other."""
    if not a or not b:
        return True
    return len(a & b) > min(len(a), len(b)) / 2


unknown_rounds: set[str] = set()
incomplete: set[int] = set()
"""Competitions with a day whose results the API would not return."""


def races(competition: int) -> list[Race] | None:
    """Every individual track race of a harvested competition, or ``None`` if not harvested."""
    path = RESULTS / f"{competition}.json.gz"
    if not path.exists():
        return None
    data: dict[str, Any] = json.loads(gzip.decompress(path.read_bytes()))
    if "error" in data:
        return None
    host = re.search(r"\(([A-Z]{3})\)\s*$", (data.get("competition") or {}).get("venue") or "")
    found: list[Race] = []
    seen: dict[tuple[Any, ...], list[frozenset[str | None]]] = {}
    for sections in (data.get("days") or {}).values():
        if not isinstance(sections, list):
            if sections is not None:
                incomplete.add(competition)
            continue
        for section in sections:
            title = section.get("eventTitle")
            if title and (NOT_SENIOR.search(title) or title == EN_ROUTE):
                continue
            for event in section["events"]:
                kind = None if event.get("isRelay") else discipline(event["event"])
                if kind is None:
                    continue
                for race in event["races"]:
                    round_ = ROUNDS.get(race["race"])
                    if round_ is None:
                        if race["race"] not in NOT_RACES:
                            unknown_rounds.add(race["race"])
                        continue
                    # The API can list a race twice: under two days, or again in a section
                    # ranking part of its field (a national championship inside an open
                    # race). Its ids do not tell races apart (a meeting's two miles, heats
                    # without numbers); their fields do.
                    key = (
                        event["eventId"],
                        race.get("raceId"),
                        race["race"],
                        race.get("raceNumber"),
                    )
                    field = frozenset(
                        (r.get("competitor") or {}).get("name") for r in race.get("results") or []
                    )
                    if any(_same_field(field, other) for other in seen.get(key, [])):
                        continue
                    seen.setdefault(key, []).append(field)
                    found.append(
                        Race(
                            competition=competition,
                            discipline=kind[0],
                            sex=kind[1],
                            indoor=kind[2],
                            nonstandard=kind[3],
                            round=round_,
                            number=race.get("raceNumber"),
                            date=race.get("date"),
                            starters=len(race.get("results") or []),
                            section=title,
                            undercard=_undercard(
                                title, race.get("results") or [], host[1] if host else None
                            ),
                        )
                    )
    return found
