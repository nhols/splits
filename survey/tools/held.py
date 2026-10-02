"""The races Splits holds, read from the built database, and their World Athletics competitions.

A competition in the catalog is matched to the World Athletics calendar entry held in the same
country whose dates overlap its own (championships list the dates of the whole Games, World
Athletics those of the athletics), preferring the higher ranking category: a Diamond League
meeting shares its city and day with nothing better, but a Games shares them with local meets.
"""

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

DATABASE = Path(__file__).resolve().parents[2] / "build" / "splits.duckdb"
RANK = {"OW": 0, "DF": 1, "GW": 2, "GL": 3, "A": 4, "Pre 2018": 4, "B": 5, "C": 6, "D": 7}


@dataclass(frozen=True)
class HeldRace:
    competition: str
    discipline: str
    sex: str
    round: str
    heat: int | None


def held_races() -> list[HeldRace]:
    with duckdb.connect(str(DATABASE), read_only=True) as db:
        rows = db.sql("select competition, discipline, sex, round, heat from races").fetchall()
    return [HeldRace(*row) for row in rows]


def competitions() -> list[dict[str, Any]]:
    with duckdb.connect(str(DATABASE), read_only=True) as db:
        cursor = db.sql(
            "select id, name, series, start_date, end_date, city, country, setting "
            "from competitions"
        )
        names = [c[0] for c in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def _country(venue: str | None) -> str | None:
    found = re.search(r"\(([A-Z]{3})\)\s*$", venue or "")
    return found[1] if found else None


def match_world_athletics(
    competition: dict[str, Any], calendar: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """The calendar entry for a catalog competition, or ``None``."""
    start: dt.date = competition["start_date"]
    end: dt.date = competition["end_date"] or start
    candidates = []
    for entry in calendar:
        if not entry.get("startDate") or "Track and Field" not in (entry.get("disciplines") or ""):
            continue
        if _country(entry["venue"]) != competition["country"]:
            continue
        entry_start = dt.date.fromisoformat(entry["startDate"])
        entry_end = dt.date.fromisoformat(entry.get("endDate") or entry["startDate"])
        if entry_start > end + dt.timedelta(days=1) or entry_end < start - dt.timedelta(days=1):
            continue
        candidates.append(
            (RANK.get(entry["rankingCategory"], 9), abs((entry_start - start).days), entry)
        )
    candidates.sort(key=lambda c: (c[0], c[1]))
    return candidates[0][2] if candidates else None
