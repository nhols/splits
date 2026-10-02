"""The Olympic Games' individual track events from Olympedia, 1896 to 2000: rounds and heats.

World Athletics holds Olympic results only from 1996. Olympedia has every edition: its sport
page links each event, and each event's page has one section (``<h2>``) per round. A round's
heats are counted from its ``<h3>Heat #n`` headings where the page splits the round by heat, and
otherwise from the summary table, which marks each athlete eliminated in a round with the heat
they ran (``h6 r1/4``: heat 6 of round 1 of 4). 1996 and 2000 are read too, to check the method
against World Athletics' own counts.

    uv run python survey/tools/olympedia.py
"""

import json
import re
import time
from pathlib import Path
from typing import Any

import httpx

CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "survey" / "olympedia"
SITE = "https://www.olympedia.org"
EDITIONS = {
    1: 1896,
    2: 1900,
    3: 1904,
    4: 1906,
    5: 1908,
    6: 1912,
    7: 1920,
    8: 1924,
    9: 1928,
    10: 1932,
    11: 1936,
    12: 1948,
    13: 1952,
    14: 1956,
    15: 1960,
    16: 1964,
    17: 1968,
    18: 1972,
    19: 1976,
    20: 1980,
    21: 1984,
    22: 1988,
    23: 1992,
    24: 1996,
    25: 2000,
}
"""Olympedia's edition ids and their years (4 is the 1906 Intercalated Games)."""

NOT_TRACK = re.compile(
    r"Relay|Walk|Marathon|Cross-Country|Team|Wheelchair|Standing|Jump|Vault|Put|Throw|athlon|"
    r"Both Hands|Military|All-Around|Handicap|Tug",
    re.I,
)
EVENT_LINK = re.compile(r'<a href="(/results/\d+)">([^<]+), (Men|Women)</a>')
SIDE_MEET = re.compile(r"\((?![\d,]+ (?:metres|m|miles|yards)\))[^)]*\)")
"""A parenthesis that is not a distance names a side meet (1904's AAU and YMCA championships)."""
STATUS = re.compile(r"<th>Status</th><td>([^<]+)</td>")
HEAT_HEADING = re.compile(r"<h3>\s*(?:Heat|Race|Semi-Final|Group)\s*#?\s*\w+\s*</h3>")
HEAT_CODE = re.compile(r"\bh(\d+) r(\d+)/\d+")


def page(client: httpx.Client, url: str, path: Path) -> str:
    if path.exists():
        return path.read_text()
    for attempt in range(8):
        try:
            response = client.get(url)
            if response.status_code == 200 and len(response.text) > 2000:
                path.write_text(response.text)
                time.sleep(1.0)
                return response.text
        except httpx.HTTPError:
            pass
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"{url}: no page")


def discipline(name: str) -> str | None:
    """Our discipline id for an Olympedia event name, e.g. '100 / 80 metres Hurdles (80 m)'
    -> '80mh', 'Steeplechase (3,000 metres)' -> '3000msc', '5 miles' -> '5-miles'."""
    name = name.replace(",", "")
    steeple = re.search(r"Steeplechase \((\d+) metres\)|(\d+) metres Steeplechase", name)
    if steeple:
        return f"{steeple[1] or steeple[2]}msc"
    distance = re.search(r"(\d+(?:\.\d+)?) (metres|miles|mile|yards)", name)
    if distance is None:
        return None
    actual = re.search(r"\((\d+) m\)", name)
    unit = {"metres": "m", "miles": "-miles", "mile": "-mile", "yards": "y"}[distance[2]]
    base = f"{actual[1] if actual else distance[1]}{unit}"
    if base == "1-mile":
        base = "mile"
    return base + ("h" if "Hurdles" in name else "")


def events(sport: str) -> dict[str, tuple[str, str]]:
    """Each individual track event on an edition's sport page: its result page and its name and
    sex. The page links an event more than once, sometimes by a shorter name ("Steeplechase"
    beside "Steeplechase (3,000 metres)"); the longest name is kept."""
    found: dict[str, tuple[str, str]] = {}
    for url, name, sex in EVENT_LINK.findall(sport):
        if NOT_TRACK.search(name) or SIDE_MEET.search(name):
            continue
        if url not in found or len(name) > len(found[url][0]):
            found[url] = (name, sex)
    return found


def event(html: str) -> tuple[str | None, list[dict[str, Any]]]:
    """An event page's dates and its rounds, each with its number of races."""
    date = re.search(r"<th>Date</th><td>([^<]+)</td>", html)
    summary, *sections = re.split(r"<h2>(.*?)</h2>", html)
    eliminated: dict[int, int] = {}
    for heat, round_ in HEAT_CODE.findall(summary):
        eliminated[int(round_)] = max(eliminated.get(int(round_), 0), int(heat))
    rounds = []
    for number, (name, body) in enumerate(zip(sections[::2], sections[1::2], strict=True), 1):
        headings = len(HEAT_HEADING.findall(body))
        races = max(headings, eliminated.get(number, 0)) or 1
        rounds.append({"round": name.strip(), "races": races})
    return (date[1] if date else None), rounds


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    read, unread = [], []
    with httpx.Client(timeout=60, headers={"User-Agent": "splits-survey"}) as client:
        for edition, year in EDITIONS.items():
            sport = page(
                client, f"{SITE}/editions/{edition}/sports/ATH", CACHE / f"edition-{edition}.html"
            )
            for url, (name, sex) in events(sport).items():
                result_id = url.rsplit("/", 1)[1]
                html = page(client, SITE + url, CACHE / f"result-{result_id}.html")
                status = STATUS.search(html)
                if status is None or status[1] not in ("Olympic", "Intercalated"):
                    continue
                date, rounds = event(html)
                record = {
                    "year": year,
                    "edition": edition,
                    "event": name,
                    "sex": sex.lower(),
                    "discipline": discipline(name),
                    "result_id": result_id,
                    "date": date,
                    "rounds": rounds,
                }
                (read if record["discipline"] else unread).append(record)
    (CACHE / "olympics.json").write_text(json.dumps({"events": read, "unread": unread}, indent=1))
    print(f"{len(read)} events; unread: {[(u['year'], u['event']) for u in unread]}")


if __name__ == "__main__":
    main()
