"""The survey's coverage report: how much of the search space Splits holds, and how much more
was published.

Reads ``survey/editions.csv``, ``survey/races.csv``, ``survey/categories.yaml`` and
``survey/availability.yaml`` and writes the generated part of ``survey/README.md`` (between the
``<!-- report -->`` markers).

A race counts once in the inventory. Its splits are *published* when the availability research
found per-runner splits, publicly or on the Wayback Machine, for its category, year, discipline
and round, or when Splits holds it (it was read from a published document); *held* when Splits
holds it.

    uv run python survey/tools/report.py
"""

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import yaml

SURVEY = Path(__file__).resolve().parents[1]
README = SURVEY / "README.md"
START, END = "<!-- report -->", "<!-- /report -->"
SCOPES = ["elite-core", "elite-secondary", "sub-elite"]
PUBLISHED = {"official-splits-public", "official-splits-archived", "unofficial-splits"}
EVENT_ORDER = [
    "60m",
    "100m",
    "200m",
    "300m",
    "400m",
    "600m",
    "800m",
    "1000m",
    "1500m",
    "mile",
    "2000m",
    "3000m",
    "2-miles",
    "5000m",
    "10000m",
    "60mh",
    "80mh",
    "100mh",
    "110mh",
    "300mh",
    "400mh",
    "3000msc",
]


@dataclass
class Tally:
    editions: set[str] = field(default_factory=set)
    editions_with_races: set[str] = field(default_factory=set)
    editions_held: set[str] = field(default_factory=set)
    events: set[tuple[str, str, str]] = field(default_factory=set)
    events_held: set[tuple[str, str, str]] = field(default_factory=set)
    races: int = 0
    held: int = 0
    published: int = 0
    published_held: int = 0
    first: int = 9999
    last: int = 0

    COLUMNS: ClassVar[list[str]] = [
        "Editions", "Events", "Events held", "With race counts", "Races", "Held", "Share",
        "Published", "Published, not held",
    ]  # fmt: skip

    def columns(self) -> list[str]:
        return [
            _n(len(self.editions)), _n(len(self.events)), _n(len(self.events_held)),
            _n(len(self.editions_with_races)), _n(self.races), _n(self.held),
            _pct(self.held, self.races), _n(self.published),
            _n(self.published - self.published_held),
        ]  # fmt: skip

    @classmethod
    def merge(cls, tallies: list["Tally"]) -> "Tally":
        merged = cls()
        for t in tallies:
            for name in (
                "editions",
                "editions_with_races",
                "editions_held",
                "events",
                "events_held",
            ):
                getattr(merged, name).update(getattr(t, name))
            for name in ("races", "held", "published", "published_held"):
                setattr(merged, name, getattr(merged, name) + getattr(t, name))
        return merged

    def add_edition(self, edition: dict[str, str]) -> None:
        self.editions.add(edition["id"])
        year = int(edition["year"])
        self.first, self.last = min(self.first, year), max(self.last, year)

    def add_race(self, row: dict[str, str], published: bool) -> None:
        races = int(row["races"]) if row["races"] else 0
        held = int(row["held"] or 0)
        races = max(races, held)
        event = (row["edition"], row["discipline"], row["sex"])
        self.events.add(event)
        if races:
            self.editions_with_races.add(row["edition"])
        if held:
            self.editions_held.add(row["edition"])
            self.events_held.add(event)
        self.races += races
        self.held += held
        # a race Splits holds was evidently published, whatever the availability research found
        self.published += races if published else held
        self.published_held += held


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _pct(part: int, whole: int) -> str:
    if not whole:
        return "–"
    share = 100 * part / whole
    return f"{share:.1f}%" if share >= 0.1 or part == 0 else "<0.1%"


def _n(value: int) -> str:
    return f"{value:,}"


class Availability:
    """Which (category, year, discipline, round) had per-runner splits published."""

    def __init__(self) -> None:
        path = SURVEY / "availability.yaml"
        self.eras: dict[str, list[dict[str, Any]]] = defaultdict(list)
        if path.exists():
            for category in yaml.safe_load(path.read_text()) or []:
                self.eras[category["category"]] += category["eras"]

    def published(self, category: str, year: int, discipline: str, round_: str) -> bool:
        return self.era(category, year, discipline, round_) is not None

    def era(self, category: str, year: int, discipline: str, round_: str) -> dict[str, Any] | None:
        """The availability era that published this race's per-runner splits, if any."""
        for era in self.eras.get(category, []):
            if era["status"] not in PUBLISHED or not era["from_year"] <= year <= era["to_year"]:
                continue
            disciplines = {d.lower().replace(" ", "") for d in era.get("disciplines") or []}
            if "all" not in disciplines and discipline not in disciplines:
                continue
            if era.get("all_rounds", True) or round_ in ("final", ""):
                return era
        return None


def report() -> str:
    categories = {c["id"]: c for c in yaml.safe_load((SURVEY / "categories.yaml").read_text())}
    editions = {e["id"]: e for e in _read(SURVEY / "editions.csv")}
    rows = _read(SURVEY / "races.csv")
    availability = Availability()

    by_scope: dict[str, Tally] = defaultdict(Tally)
    by_category: dict[str, Tally] = defaultdict(Tally)
    by_decade: dict[tuple[str, int], Tally] = defaultdict(Tally)
    by_event: dict[tuple[str, str], Tally] = defaultdict(Tally)
    by_event_modern: dict[tuple[str, str], Tally] = defaultdict(Tally)
    origins: Counter[str] = Counter()
    races_from: Counter[tuple[str, str]] = Counter()

    for e in editions.values():
        scope = e["scope"]
        by_scope[scope].add_edition(e)
        by_category[e["category"]].add_edition(e)
        by_decade[(scope, int(e["year"]) // 10 * 10)].add_edition(e)
        for origin in e["origins"].split():
            origins[origin.split(":")[0]] += 1
        races_from[(scope, e["races_from"])] += 1

    gaps: Counter[tuple[str, int, int, str, str, str]] = Counter()
    for row in rows:
        e = editions[row["edition"]]
        scope, year = e["scope"], int(e["year"])
        era = availability.era(e["category"], year, row["discipline"], row["round"])
        published = era is not None
        missing = max(int(row["races"] or 0), int(row["held"] or 0)) - int(row["held"] or 0)
        if era and missing and scope in ("elite-core", "elite-secondary"):
            url = (era.get("urls") or [""])[0]
            gaps[(e["category"], era["from_year"], era["to_year"], era["status"],
                  era["publisher"], url)] += missing  # fmt: skip
        for tally in (
            by_scope[scope],
            by_category[e["category"]],
            by_decade[(scope, year // 10 * 10)],
        ):
            tally.add_race(row, published)
        if scope in ("elite-core", "elite-secondary"):
            by_event[(row["discipline"], row["sex"])].add_race(row, published)
            if year >= 2010:
                by_event_modern[(row["discipline"], row["sex"])].add_race(row, published)

    out = []
    elite = [by_scope[s] for s in ("elite-core", "elite-secondary")]
    races, held = sum(t.races for t in elite), sum(t.held for t in elite)
    published = sum(t.published for t in elite)
    published_held = sum(t.published_held for t in elite)
    out.append("## Headline\n")
    out.append(
        f"Across the elite categories (core and secondary) the survey counts **{_n(races)} "
        f"individual track races** whose number is known, at "
        f"{_n(sum(len(t.editions) for t in elite))} editions. Splits holds **{_n(held)} "
        f"({_pct(held, races)})**. Of the {_n(published)} races whose per-runner splits are known "
        f"to have been published, it holds {_n(published_held)} "
        f"({_pct(published_held, published)}).\n"
    )

    out.append("## By scope\n")
    rows_out = []
    for scope in SCOPES:
        t = by_scope[scope]
        n_cats = len({e["category"] for e in editions.values() if e["scope"] == scope})
        rows_out.append([scope, n_cats, *t.columns()])
    out += _table(["Scope", "Categories", *Tally.COLUMNS], rows_out)

    for scope in ("elite-core", "elite-secondary"):
        out.append(f"## {scope.capitalize()} categories\n")
        ids = [
            c
            for c in by_category
            if (categories.get(c, {}).get("scope") or editions_scope(editions, c)) == scope
        ]
        rows_out = []
        for cid in sorted(ids, key=lambda c: (-by_category[c].races, c)):
            t = by_category[cid]
            name = categories.get(cid, {}).get("name", cid)
            rows_out.append([name, f"{t.first}–{t.last}", *t.columns()])
        out += _table(["Category", "Years", *Tally.COLUMNS], rows_out)

    out.append("## By decade (elite core and secondary)\n")
    rows_out = []
    for decade in sorted({d for (_, d) in by_decade}):
        t = Tally.merge([by_decade[(s, decade)] for s in ("elite-core", "elite-secondary")])
        rows_out.append([f"{decade}s", *t.columns()])
    out += _table(["Decade", *Tally.COLUMNS], rows_out)

    out.append("## By event (elite core and secondary)\n")
    rows_out = []
    for key in sorted(by_event, key=_event_order):
        t, m = by_event[key], by_event_modern[key]
        if t.races >= 20:
            rows_out.append(
                [f"{key[0]} {key[1]}", _n(t.races), _n(t.held), _pct(t.held, t.races),
                 _n(m.races), _n(m.held), _pct(m.held, m.races), _n(m.published),
                 _n(m.published - m.published_held)]
            )  # fmt: skip
    out += _table(
        ["Event", "Races", "Held", "Share", "Races since 2010", "Held", "Share",
         "Published since 2010", "Published, not held"],
        rows_out,
    )  # fmt: skip

    out.append("## Published but not held, largest first\n")
    rows_out = []
    for (cid, first, last, status, publisher, url), n in gaps.most_common(25):
        name = categories.get(cid, {}).get("name", cid)
        where = f"[link]({url})" if url.startswith("http") else ""
        rows_out.append([name, f"{first}–{last}", _n(n), status.replace("official-splits-", ""),
                         publisher.replace("|", "/")[:80], where])  # fmt: skip
    out += _table(["Category", "Era", "Races", "Status", "Publisher", "Where"], rows_out)

    out.append("## Where the counts come from\n")
    rows_out = [[s, src, _n(n)] for (s, src), n in sorted(races_from.items()) if s in SCOPES]
    out += _table(["Scope", "Races counted from", "Editions"], rows_out)
    sources = ", ".join(f"{k} {_n(v)}" for k, v in origins.most_common())
    out.append(f"Edition sources: {sources}.\n")
    return "\n".join(out)


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    """A markdown table: the first column left-aligned, the rest right-aligned."""
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|---|" + "|".join("--:" for _ in headers[1:]) + "|")
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return [*lines, ""]


def _event_order(key: tuple[str, str]) -> tuple[int, str, str]:
    return (EVENT_ORDER.index(key[0]) if key[0] in EVENT_ORDER else 99, key[0], key[1])


def editions_scope(editions: dict[str, dict[str, str]], category: str) -> str | None:
    return next((e["scope"] for e in editions.values() if e["category"] == category), None)


def main() -> None:
    text = README.read_text() if README.exists() else f"# Survey\n\n{START}\n{END}\n"
    generated = report()
    text = re.sub(
        f"{re.escape(START)}.*{re.escape(END)}", f"{START}\n{generated}\n{END}", text, flags=re.S
    )
    README.write_text(text)
    print(generated[:3000])


if __name__ == "__main__":
    main()
