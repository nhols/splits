"""World Athletics' competition calendar and results, as the spine of the survey.

The site's public GraphQL API lists every competition in its calendar (complete from 2018;
before that the global championships, the European outdoor and indoor championships from 1934,
the World Cup from 1998, the World Athletics Final, the Diamond League from 2010 and a sparse
selection of others) and, for each competition with results, every race of every event, day by
day. Both are harvested once into ``data/cache/survey/wa/`` and read from there.

    uv run python survey/tools/world_athletics.py calendar  # ~40,000 competitions, minutes
    uv run python survey/tools/world_athletics.py results   # ~5,600 competitions' races, hours
    uv run python survey/tools/world_athletics.py cited     # and those the research cites
"""

import csv
import gzip
import json
import re
import sys
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx

ENDPOINT = "https://graphql-prod-4896.edge.aws.worldathletics.org/graphql"
API_KEY = "da2-kw72k7ccfrcl7m2bzvkejgd44a"
"""The public key the worldathletics.org pages send with every request."""

CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "survey" / "wa"
CALENDAR = CACHE / "calendar.json"
RESULTS = CACHE / "results"

CALENDAR_QUERY = """query($s:String,$e:String,$o:Int,$l:Int){getCalendarEvents(startDate:$s,
endDate:$e,limit:$l,offset:$o){hits results{id name venue area rankingCategory disciplines
competitionGroup competitionSubgroup startDate endDate dateRange hasResults
hasCompetitionInformation}}}"""

RESULTS_QUERY = """query($c:Int,$d:Int){getCalendarCompetitionResults(competitionId:$c,day:$d){
competition{dateRange endDate name rankingCategory startDate venue} eventTitles{rankingCategory
eventTitle events{event eventId gender isRelay withWind races{date day race raceId raceNumber
wind results{competitor{name iaafId} mark place nationality}}}} options{days{date day}
events{gender id name combined}}}}"""

HARVESTED_CATEGORIES = {"OW", "DF", "GW", "GL", "A", "B", "C", "D"}
"""World Athletics ranking categories whose competitions' races are harvested (from 2018); every
competition before 2018 with results is harvested too, and every championship."""


def query(client: httpx.Client, text: str, variables: dict[str, Any]) -> Any:
    """One GraphQL call, retried; the API answers transient failures with ``null`` data."""
    for attempt in range(6):
        try:
            response = client.post(
                ENDPOINT,
                json={"query": text, "variables": variables},
                headers={"x-api-key": API_KEY},
            )
            response.raise_for_status()
            data = response.json().get("data") or {}
            value = next(iter(data.values()), None)
            if value is not None:
                return value
        except httpx.HTTPError:
            pass
        time.sleep(2 * (attempt + 1))
    return None


def _months(first_year: int, last_year: int) -> Iterator[tuple[str, str]]:
    for year in range(first_year, last_year + 1):
        for month in range(1, 13):
            yield f"{year}-{month:02d}-01", f"{year}-{month:02d}-31"


def harvest_calendar(client: httpx.Client) -> list[dict[str, Any]]:
    """Every competition in the calendar. The API rejects start dates before 1900; before 2018
    a year at a time is small enough, after it a month at a time."""
    ranges = [("1900-01-01", "1979-12-31")]
    ranges += [(f"{y}-01-01", f"{y}-12-31") for y in range(1980, 2018)]
    ranges += list(_months(2018, 2026))
    found: dict[int, dict[str, Any]] = {}
    for start, end in ranges:
        offset = 0
        while True:
            page = query(client, CALENDAR_QUERY, {"s": start, "e": end, "o": offset, "l": 200})
            rows = (page or {}).get("results") or []
            for row in rows:
                found[row["id"]] = row
            offset += len(rows)
            if not rows or offset >= page["hits"]:
                break
    return sorted(found.values(), key=lambda r: (r["startDate"] or "", r["id"]))


def harvested(competition: dict[str, Any]) -> bool:
    """Whether a calendar entry's races are worth harvesting: track and field with results,
    before 2018 or in an elite ranking category, or any senior championship."""
    if not competition.get("hasResults"):
        return False
    disciplines = competition.get("disciplines") or ""
    if disciplines and "Track and Field" not in disciplines:
        return False
    category = competition["rankingCategory"]
    if category == "Pre 2018" or category in HARVESTED_CATEGORIES:
        return True
    group = competition.get("competitionGroup") or ""
    return "Championships" in group and not re.search(r"U1\d|U2\d|Masters", group)


def harvest_results(client: httpx.Client, competition_id: int) -> None:
    """Every day's results of one competition, stored gzipped; the API returns one day at a
    time (the first, when no day is given)."""
    path = RESULTS / f"{competition_id}.json.gz"
    if path.exists():
        return
    first = query(client, RESULTS_QUERY, {"c": competition_id})
    if first is None:
        record: dict[str, Any] = {"id": competition_id, "error": "no data"}
    else:
        days = [d["day"] for d in (first.get("options") or {}).get("days") or []]
        record = {
            "id": competition_id,
            "competition": first.get("competition"),
            "options": first.get("options"),
            "days": {} if days else {"_": first.get("eventTitles")},
        }
        for day in days:
            result = query(client, RESULTS_QUERY, {"c": competition_id, "d": day})
            record["days"][str(day)] = (result or {}).get("eventTitles")
    path.write_bytes(gzip.compress(json.dumps(record).encode()))


def cited() -> set[int]:
    """World Athletics competitions the edition research ties editions to."""
    research = Path(__file__).resolve().parents[1] / "research"
    ids = set()
    for name in ("editions.csv", "lineages.csv"):
        path = research / name
        if path.exists():
            with path.open(newline="") as f:
                ids |= {
                    int(float(r["wa_competition"]))
                    for r in csv.DictReader(f)
                    if r["wa_competition"]
                }
    return ids


def calendar() -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads(CALENDAR.read_text())
    return data


def main() -> None:
    command = sys.argv[1]
    CACHE.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60, headers={"User-Agent": "splits-survey"}) as client:
        if command == "calendar":
            rows = harvest_calendar(client)
            CALENDAR.write_text(json.dumps(rows, indent=0))
            print(f"{len(rows)} competitions")
        elif command in ("results", "cited"):
            RESULTS.mkdir(exist_ok=True)
            known = {row["id"] for row in calendar()}
            ids = (
                [row["id"] for row in calendar() if harvested(row)]
                if command == "results"
                else sorted(cited() & known)
            )
            print(f"{len(ids)} competitions")
            with ThreadPoolExecutor(8) as pool:
                list(pool.map(lambda cid: harvest_results(client, cid), ids))


if __name__ == "__main__":
    main()
