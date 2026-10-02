"""Assemble the survey: every edition of every series, the races run at it, and which of those
races Splits holds.

Editions come from four places, merged in this order:

1. World Athletics' calendar, for every competition whose results were harvested: the races
   are counted from its results, and its series follows from its group, name and host
   (``classify.py``).
2. Olympedia, for the Olympic Games before 1996 (World Athletics holds them from 1996).
3. The edition research (``survey/research/editions.csv``): an edition the research ties to a
   World Athletics competition, or that shares its country and dates with one, is that
   competition; its series replaces a generic one ("an ordinary meeting"). Otherwise it is
   new, and its races come from the research's round counts, its event list, or its series'
   programme for that year.
4. The meeting-lineage research (``survey/research/lineages.csv``): a meeting held in a year
   that no edition above covers adds an edition whose programme is unknown.

Splits' own races (``build/splits.duckdb``) are matched to editions through their competition's
World Athletics entry, and counted against the race inventory.

    uv run python survey/tools/build.py
"""

import csv
import datetime as dt
import difflib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml
from classify import MEETING_TIERS, country, series_of
from held import competitions, held_races, match_world_athletics
from olympedia import CACHE as OLYMPEDIA
from races import races
from world_athletics import calendar

SURVEY = Path(__file__).resolve().parents[1]
RESEARCH = SURVEY / "research"

SYNTHETIC = {
    "wa-meeting-ow": ("Other World Athletics OW-category meetings", "elite-core"),
    "wa-meeting-df": ("Other World Athletics DF-category meetings", "elite-core"),
    "wa-meeting-gw": ("Other World Athletics GW-category meetings", "elite-core"),
    "wa-meeting-gl": ("Other World Athletics GL-category meetings", "elite-secondary"),
    "wa-meeting-a": ("Other World Athletics A-category meetings", "elite-secondary"),
    "wa-meeting-b": ("Other World Athletics B-category meetings", "sub-elite"),
    "wa-meeting-c": ("Other World Athletics C-category meetings", "sub-elite"),
    "wa-meeting-d": ("Other World Athletics D-category meetings", "sub-elite"),
    "wa-meeting-e": ("Other World Athletics E-category meetings", "sub-elite"),
    "wa-meeting-f": ("Other World Athletics F-category meetings", "sub-elite"),
    "wa-meeting-pre-2018": ("Other meetings in World Athletics' calendar before 2018", "sub-elite"),
    "area-championships-other": ("Other area championships", "elite-secondary"),
    "area-games-other": ("Other area games", "sub-elite"),
    "regional-championships-other": ("Other regional championships", "sub-elite"),
    "unassigned-meetings": ("Meetings researched without a series", "sub-elite"),
}
"""Buckets for World Athletics competitions that fit no researched series."""

GENERIC = set(SYNTHETIC) | {
    "other-national-championships",
    "other-national-indoor-championships",
    "area-permit-meetings",
}
"""Series that research may replace with a more specific one."""

TIERS = [
    "iaaf-grand-prix-final",
    "iaaf-world-athletics-final",
    "iaaf-golden-events",
    "diamond-league",
    "iaaf-golden-league",
    "iaaf-super-grand-prix",
    "iaaf-grand-prix",
    "iaaf-grand-prix-ii",
    "iaaf-world-challenge",
    "continental-tour",
    "iaaf-permit-meetings",
    "world-indoor-tour",
    "iaaf-indoor-permit-meetings",
    "golden-spike-tour",
]
"""Circuits from the most to the least specific: a meeting that counted for several (a Golden
League meeting was also a Grand Prix meeting; a final was also a meeting) takes the first."""
SCOPE_RANK = {"elite-core": 0, "elite-secondary": 1, "sub-elite": 2, "out-of-scope": 3}

OLYMPIC_CITIES = {
    1896: ("Athens", "GRE"),
    1900: ("Paris", "FRA"),
    1904: ("St. Louis", "USA"),
    1906: ("Athens", "GRE"),
    1908: ("London", "GBR"),
    1912: ("Stockholm", "SWE"),
    1920: ("Antwerp", "BEL"),
    1924: ("Paris", "FRA"),
    1928: ("Amsterdam", "NED"),
    1932: ("Los Angeles", "USA"),
    1936: ("Berlin", "GER"),
    1948: ("London", "GBR"),
    1952: ("Helsinki", "FIN"),
    1956: ("Melbourne", "AUS"),
    1960: ("Rome", "ITA"),
    1964: ("Tokyo", "JPN"),
    1968: ("Mexico City", "MEX"),
    1972: ("Munich", "FRG"),
    1976: ("Montreal", "CAN"),
    1980: ("Moscow", "URS"),
    1984: ("Los Angeles", "USA"),
    1988: ("Seoul", "KOR"),
    1992: ("Barcelona", "ESP"),
}
OLYMPEDIA_ROUNDS = {
    "Round One": "heat",
    "Round Two": "quarter-final",
    "Quarter-Finals": "quarter-final",
    "Semi-Finals": "semi-final",
    "Final Round": "final",
    "Final": "final",
    "Repêchage": "repechage",
    "Repechage": "repechage",
    "Round One Repêchage": "repechage",
    "Preliminary Round": "preliminary",
}
MEETING_KINDS = {"one-day-circuit", "pro-league", "invitational-meeting", "circuit-final"}
CIRCUITS = [
    (r"Diamond League", "diamond-league"),
    (r"Golden League", "iaaf-golden-league"),
    (r"Golden Four", "iaaf-golden-league"),
    (r"Super Grand Prix", "iaaf-super-grand-prix"),
    (r"Grand Prix II|GP ?II", "iaaf-grand-prix-ii"),
    (r"Grand Prix Final", "iaaf-grand-prix-final"),
    (r"World Athletics Final", "iaaf-world-athletics-final"),
    (r"IAAF Grand Prix|Mobil Grand Prix|Grand Prix I\b|GP ?I\b", "iaaf-grand-prix"),
    (r"World Challenge", "iaaf-world-challenge"),
    (r"Continental Tour.*Gold", "continental-tour"),
    (r"Continental Tour.*Silver", "continental-tour-silver"),
    (r"Continental Tour.*Bronze", "continental-tour-bronze"),
    (r"Indoor Tour", "world-indoor-tour"),
    (r"Indoor Permit|IAAF Indoor", "iaaf-indoor-permit-meetings"),
    (r"Golden Events", "iaaf-golden-events"),
    (r"Golden Spike Tour|Visa Championship|USATF.*Tour", "golden-spike-tour"),
    (r"Permit", "iaaf-permit-meetings"),
    (r"EAA|European Athletics", "european-athletics-permit-meetings"),
]
"""The circuit a meeting edition belonged to, from the lineage research's free text."""


@dataclass
class Edition:
    id: str
    series: str
    name: str
    year: int
    start_date: str | None
    end_date: str | None
    city: str | None
    country: str | None
    setting: str
    meeting: str | None = None
    venue: str | None = None
    wa_competition: int | None = None
    wa_ranking: str | None = None
    origins: list[str] = field(default_factory=list)
    races_from: str = "unknown"
    url: str | None = None
    repo_competition: str | None = None


@dataclass
class Count:
    races: int | None
    undercard: int = 0
    held: int = 0
    basis: str = ""


EXONYMS = {
    "roma": "rome",
    "bruxelles": "brussels",
    "brussel": "brussels",
    "moskva": "moscow",
    "athina": "athens",
    "athinai": "athens",
    "praha": "prague",
    "wien": "vienna",
    "munchen": "munich",
    "koln": "cologne",
    "goteborg": "gothenburg",
    "lisboa": "lisbon",
    "sevilla": "seville",
    "torino": "turin",
    "milano": "milan",
    "firenze": "florence",
    "napoli": "naples",
    "kobenhavn": "copenhagen",
    "warszawa": "warsaw",
    "beograd": "belgrade",
    "bucuresti": "bucharest",
    "kyiv": "kiev",
    "ciudad-de-mexico": "mexico-city",
    "den-haag": "the-hague",
    "genova": "genoa",
    "saint-denis": "paris",
    "paris-st-denis": "paris",
    "st-denis": "paris",
    "bern": "berne",
    "zurich": "zurich",
    "geneve": "geneva",
    "lausanne": "lausanne",
    "sankt-peterburg": "st-petersburg",
    "saint-petersburg": "st-petersburg",
    "leningrad": "st-petersburg",
    "chorzow": "katowice",
    "keqiao": "shaoxing",
    "shaoxing-keqiao": "shaoxing",
    "miramar": "miami",
}
"""Local and English names of cities, so research and World Athletics agree on where."""


def same_city(a: str | None, b: str | None) -> bool:
    x, y = slug(a), slug(b)
    if not x or not y:
        return False
    x, y = EXONYMS.get(x, x), EXONYMS.get(y, y)
    return (
        x == y
        or x.startswith(y)
        or y.startswith(x)
        or difflib.SequenceMatcher(None, x, y).ratio() >= 0.8
    )


def slug(text: str | None) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _city(venue: str | None) -> str | None:
    """The city in a World Athletics venue: 'Hayward Field, Eugene, OR (USA)' -> 'Eugene'."""
    parts = [p.strip() for p in re.sub(r"\s*\([A-Z]{3}\)\s*$", "", venue or "").split(",")]
    parts = [p for p in parts if p]
    if len(parts) >= 2 and re.fullmatch(r"[A-Z]{2}", parts[-1]):
        parts = parts[:-1]
    return parts[-1] if parts else None


def _date(text: Any) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(text)[:10])
    except ValueError:
        return None


class Survey:
    def __init__(self) -> None:
        self.series = {c["id"]: c for c in yaml.safe_load((SURVEY / "series.yaml").read_text())}
        for cid, (name, scope) in SYNTHETIC.items():
            self.series.setdefault(cid, {"id": cid, "name": name, "scope": scope, "kind": "other"})
        self.editions: dict[str, Edition] = {}
        self.counts: dict[tuple[str, str, str, str], Count] = {}
        self.by_wa: dict[int, str] = {}
        self.by_day: dict[tuple[str | None, dt.date], list[str]] = defaultdict(list)
        self.unknown_series: Counter[str] = Counter()

    # --- editions --------------------------------------------------------------------------

    def add(self, edition: Edition) -> Edition:
        base = edition.id
        n = 1
        while edition.id in self.editions:
            n += 1
            edition.id = f"{base}-{n}"
        self.editions[edition.id] = edition
        if edition.wa_competition:
            self.by_wa[edition.wa_competition] = edition.id
        start = _date(edition.start_date)
        if start:
            end = _date(edition.end_date) or start
            day = start
            while day <= end and (day - start).days < 20:
                self.by_day[(edition.country, day)].append(edition.id)
                day += dt.timedelta(days=1)
        return edition

    def find(
        self, country_code: str | None, start: Any, end: Any = None, city: str | None = None
    ) -> Edition | None:
        """An edition already known in the same country on an overlapping day (± one day)."""
        first = _date(start)
        if first is None:
            return None
        last = _date(end) or first
        seen = []
        day = first - dt.timedelta(days=1)
        while day <= last + dt.timedelta(days=1):
            seen += self.by_day.get((country_code, day), [])
            day += dt.timedelta(days=1)
        candidates = [self.editions[e] for e in dict.fromkeys(seen)]
        if city:
            candidates = [
                e for e in candidates if same_city(e.city, city) or same_city(e.venue, city)
            ]
        return candidates[0] if len(candidates) == 1 else None

    def edition_id(self, series_id: str, year: int, label: str | None) -> str:
        return f"{series_id}/{year}-{slug(label) or 'x'}"

    def set_count(
        self,
        edition: str,
        discipline: str,
        sex: str,
        round_: str,
        races: int | None,
        basis: str,
        undercard: int = 0,
    ) -> None:
        key = (edition, discipline, sex, round_)
        if key in self.counts and self.counts[key].races is not None:
            return
        self.counts[key] = Count(races=races, undercard=undercard, basis=basis)

    # --- sources ---------------------------------------------------------------------------

    def world_athletics(self) -> None:
        for entry in calendar():
            found = races(entry["id"])  # harvested in bulk, or because the research cites it
            if not found:
                continue  # no results, or no individual track races (cross country, walks)
            cid = series_of(entry)
            city = _city(entry["venue"])
            year = int(entry["startDate"][:4])
            edition = self.add(
                Edition(
                    id=self.edition_id(cid, year, f"{entry['startDate'][5:]}-{city}"),
                    series=cid,
                    name=entry["name"],
                    year=year,
                    start_date=entry["startDate"],
                    end_date=entry.get("endDate"),
                    city=city,
                    country=country(entry["venue"]),
                    venue=entry["venue"],
                    setting="indoor" if found and all(r.indoor for r in found) else "outdoor",
                    wa_competition=entry["id"],
                    wa_ranking=entry["rankingCategory"],
                    origins=["wa"],
                    races_from="wa",
                )
            )
            totals: Counter[tuple[str, str, str]] = Counter()
            under: Counter[tuple[str, str, str]] = Counter()
            for race in found:
                if race.nonstandard:
                    continue
                key = (race.discipline, race.sex, race.round)
                if race.undercard:
                    under[key] += 1
                else:
                    totals[key] += 1
            for key in totals.keys() | under.keys():
                self.set_count(
                    edition.id, *key, races=totals[key], basis="wa", undercard=under[key]
                )

    def olympedia(self) -> None:
        data = json.loads((OLYMPEDIA / "olympics.json").read_text())
        for event in data["events"]:
            year = event["year"]
            if year >= 1996:
                continue  # World Athletics has them, race by race
            cid = "intercalated-games-1906" if year == 1906 else "olympic-games"
            city, host = OLYMPIC_CITIES[year]
            eid = self.edition_id(cid, year, city)
            if eid not in self.editions:
                self.add(
                    Edition(
                        id=eid,
                        series=cid,
                        name=f"Olympic Games {year}" if year != 1906 else "1906 Intercalated Games",
                        year=year,
                        start_date=None,
                        end_date=None,
                        city=city,
                        country=host,
                        setting="outdoor",
                        origins=["olympedia"],
                        races_from="olympedia",
                        url=f"https://www.olympedia.org/editions/{event['edition']}/sports/ATH",
                    )
                )
            sex = {"men": "men", "women": "women"}[event["sex"]]
            per_round: Counter[str] = Counter()
            for r in event["rounds"]:
                per_round[OLYMPEDIA_ROUNDS.get(r["round"], slug(r["round"]))] += r["races"]
            for round_, n in per_round.items():
                self.set_count(eid, event["discipline"], sex, round_, n, "olympedia")

    def research(self) -> None:
        path = RESEARCH / "editions.csv"
        if not path.exists():
            return
        programmes = defaultdict(list)
        for p in _read(RESEARCH / "programmes.csv"):
            programmes[p["series"]].append(p)
        rounds = defaultdict(list)
        for r in _read(RESEARCH / "rounds.csv"):
            rounds[
                (r["series"], int(r["year"]), slug(r["meeting"] or r["city"] or r["name"]))
            ].append(r)
        for row in _read(path):
            if row["check"].startswith("spurious"):
                continue
            cid = row["series"]
            if cid not in self.series:
                self.unknown_series[cid] += 1
                continue
            year = int(row["year"])
            wa = int(float(row["wa_competition"])) if row["wa_competition"] else None
            known = self.editions.get(self.by_wa.get(wa, "")) if wa else None
            known = known or self.find(
                row["country"], row["start_date"], row["end_date"], row["city"]
            )
            label = row["meeting"] or row["city"] or row["name"]
            if known:
                known.origins.append(f"research:{row['task']}")
                known.meeting = known.meeting or row["meeting"] or None
                if row["setting"] == "indoor":
                    known.setting = "indoor"
                if self._precedes(cid, known.series):
                    self._reassign(known, cid)
                if known.races_from != "unknown":
                    continue
                edition = known
            else:
                edition = self.add(
                    Edition(
                        id=self.edition_id(cid, year, label),
                        series=cid,
                        name=row["name"],
                        year=year,
                        start_date=row["start_date"] or None,
                        end_date=row["end_date"] or None,
                        city=row["city"] or None,
                        country=row["country"] or None,
                        venue=row["venue"] or None,
                        setting=row["setting"] or "outdoor",
                        meeting=row["meeting"] or None,
                        wa_competition=wa,
                        origins=[f"research:{row['task']}"],
                        url=row["source"] or None,
                    )
                )
            meeting_like = self.series[cid].get("kind") in MEETING_KINDS or bool(row["meeting"])
            own = rounds.get((cid, year, slug(label)), [])
            if own:
                for r in own:
                    event, _, sex = r["event"].rpartition("-")
                    self.set_count(
                        edition.id, event, sex, r["round"], int(r["races"]), "research-rounds"
                    )
                edition.races_from = "research-rounds"
                continue
            events = row["events"].split()
            if not events and row["events_scope"] == "programme-era":
                era = [
                    p for p in programmes[cid] if int(p["from_year"]) <= year <= int(p["to_year"])
                ]
                events = era[0]["events"].split() if era else []
                edition.races_from = "programme-era" if events else "unknown"
            elif events:
                edition.races_from = "research-events"
            for e in events:
                event, _, sex = e.rpartition("-")
                if meeting_like:
                    self.set_count(
                        edition.id, event, sex, "final", 1, "assumed: one race per meeting event"
                    )
                else:
                    self.set_count(edition.id, event, sex, "", None, "event held; rounds unknown")

    def lineages(self) -> None:
        path = RESEARCH / "lineages.csv"
        if not path.exists():
            return
        for row in _read(path):
            year = int(row["year"])
            wa = int(float(row["wa_competition"])) if row["wa_competition"] else None
            known = self.editions.get(self.by_wa.get(wa, "")) if wa else None
            if known is None:
                same_year = [
                    e
                    for e in self.editions.values()
                    if e.year == year
                    and (
                        slug(e.meeting) == slug(row["meeting"])
                        or (
                            row["date"]
                            and e.start_date == row["date"]
                            and same_city(e.city, row["city"])
                        )
                    )
                ]
                known = same_year[0] if same_year else None
            if known:
                known.meeting = known.meeting or row["meeting"]
                known.origins.append("lineage")
                continue
            circuit = row["circuit"] or ""
            cid = circuit if circuit in self.series else None
            cid = cid or next((c for p, c in CIRCUITS if re.search(p, circuit, re.I)), None)
            cid = cid or self._unaffiliated(row, year)
            self.add(
                Edition(
                    id=self.edition_id(cid, year, row["meeting"]),
                    series=cid,
                    name=row["name"] or row["meeting"],
                    year=year,
                    start_date=row["date"] or None,
                    end_date=None,
                    city=row["city"] or None,
                    country=None,
                    venue=row["venue"] or None,
                    setting=row["setting"] or "outdoor",
                    meeting=row["meeting"],
                    wa_competition=wa,
                    origins=["lineage"],
                    url=row["source"] or None,
                )
            )

    def _precedes(self, new: str, old: str) -> bool:
        """Whether a researched series should replace the one an edition already has."""
        if old in GENERIC:
            return new not in GENERIC
        if new in TIERS and old in TIERS:
            return TIERS.index(new) < TIERS.index(old)
        rank = {"olympic-games": 0, "global-championships": 0, "global-cup": 0, "circuit-final": 0}
        new_kind = rank.get(self.series.get(new, {}).get("kind", ""), 1)
        old_kind = rank.get(self.series.get(old, {}).get("kind", ""), 1)
        if new_kind != old_kind:
            return new_kind < old_kind
        new_scope = SCOPE_RANK.get(self.series.get(new, {}).get("scope", ""), 3)
        old_scope = SCOPE_RANK.get(self.series.get(old, {}).get("scope", ""), 3)
        return new_scope < old_scope

    def _unaffiliated(self, row: dict[str, str], year: int) -> str:
        """The grab-bag series of a meeting edition outside any circuit."""
        indoor = row["setting"] == "indoor"
        if year < 1985:
            return "european-indoor-invitationals" if indoor else "pre-grand-prix-invitationals"
        return "indoor-invitational-meetings" if indoor else "other-invitational-meetings"

    def _reassign(self, edition: Edition, cid: str) -> None:
        old = edition.id
        new = self.edition_id(
            cid,
            edition.year,
            old.split("/", 1)[1].split("-", 1)[-1] if "/" in old else edition.city,
        )
        edition.series = cid
        if new != old and new not in self.editions:
            self.editions[new] = self.editions.pop(old)
            edition.id = new
            if edition.wa_competition:
                self.by_wa[edition.wa_competition] = new
            for key in [k for k in self.counts if k[0] == old]:
                self.counts[(new, *key[1:])] = self.counts.pop(key)
            for day_key, ids in self.by_day.items():
                if old in ids:
                    self.by_day[day_key] = [new if i == old else i for i in ids]

    # --- what Splits holds -------------------------------------------------------------------

    def held(self) -> None:
        cal = calendar()
        edition_of: dict[str, str] = {}
        for comp in competitions():
            wa = match_world_athletics(comp, cal)
            found = self.editions.get(self.by_wa.get(wa["id"], "")) if wa else None
            if found is None:
                year = comp["start_date"].year
                same = [
                    e
                    for e in self.editions.values()
                    if e.year == year
                    and e.series == comp["series"]
                    and (slug(e.city) == slug(comp["city"]) or e.country == comp["country"])
                ]
                found = same[0] if same else None
            if found:
                edition_of[comp["id"]] = found.id
                found.repo_competition = comp["id"]
        for race in held_races():
            edition = edition_of.get(race.competition)
            if edition is None:
                continue
            # World Athletics lists a meeting's B race, and its heats, as finals
            round_ = "final" if race.round == "b-race" else race.round
            key = (edition, race.discipline, race.sex, round_)
            if key not in self.counts:
                fallback = (edition, race.discipline, race.sex, "")
                if fallback in self.counts:
                    key = fallback
                else:
                    self.counts[key] = Count(
                        races=None, basis="held by Splits; not in the inventory"
                    )
            self.counts[key].held += 1
        self.unmatched_competitions = sorted({c["id"] for c in competitions()} - set(edition_of))

    # --- output ------------------------------------------------------------------------------

    def write(self) -> None:
        editions = sorted(
            self.editions.values(), key=lambda e: (e.series, e.year, e.start_date or "", e.id)
        )
        with (SURVEY / "editions.csv").open("w", newline="") as f:
            fields = [
                "id",
                "series",
                "scope",
                "name",
                "year",
                "start_date",
                "end_date",
                "meeting",
                "city",
                "country",
                "venue",
                "setting",
                "wa_competition",
                "wa_ranking",
                "races_from",
                "origins",
                "repo_competition",
                "url",
            ]
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for e in editions:
                row = asdict(e)
                row["scope"] = self.scope(e)
                row["origins"] = " ".join(dict.fromkeys(e.origins))
                writer.writerow({k: row.get(k) for k in fields})
        with (SURVEY / "races.csv").open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["edition", "discipline", "sex", "round", "races", "undercard", "held", "basis"]
            )
            for key in sorted(self.counts):
                c = self.counts[key]
                writer.writerow([*key, c.races, c.undercard or "", c.held or "", c.basis])

    def scope(self, edition: Edition) -> str:
        if edition.series.startswith("wa-meeting-"):
            return MEETING_TIERS.get(edition.series.removeprefix("wa-meeting-"), "sub-elite")
        return str(self.series.get(edition.series, {}).get("scope", "unclassified"))


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def main() -> Survey:
    survey = Survey()
    survey.world_athletics()
    survey.olympedia()
    survey.research()
    survey.lineages()
    survey.held()
    survey.write()
    print(f"{len(survey.editions)} editions, {len(survey.counts)} race counts")
    if survey.unknown_series:
        print("research rows with unknown series:", dict(survey.unknown_series))
    if survey.unmatched_competitions:
        print("Splits competitions with no edition:", survey.unmatched_competitions)
    return survey


if __name__ == "__main__":
    main()
