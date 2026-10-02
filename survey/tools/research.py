"""Turn the edition research (agents' structured answers) into the survey's research tables.

The research ran as one task per category or year range: a researcher listed the editions, the
series' programme over time and the years it was not held; for elite categories a second
researcher checked the list and returned missing editions, corrections and spurious entries.
Corrections are applied here, missing editions added and spurious ones dropped, each marked in
``check`` so nothing is changed silently. Meeting lineages and split availability were separate
tasks. The raw answers stay in ``data/cache/survey/research/``; the tables written here are the
committed record.

    uv run python survey/tools/research.py data/cache/survey/research/*.json
"""

import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SURVEY = Path(__file__).resolve().parents[1]
RESEARCH = SURVEY / "research"

EDITION_FIELDS = [
    "category",
    "year",
    "name",
    "start_date",
    "end_date",
    "city",
    "country",
    "venue",
    "setting",
    "meeting",
    "wa_competition",
    "events",
    "events_scope",
    "confidence",
    "check",
    "source",
    "notes",
    "task",
]
CORRECTABLE = {
    "date": "start_date",
    "start": "start_date",
    "start_date": "start_date",
    "end_date": "end_date",
    "city": "city",
    "country": "country",
    "venue": "venue",
    "name": "name",
    "wa_competition_id": "wa_competition",
    "wa id": "wa_competition",
    "wa_id": "wa_competition",
    "meeting": "meeting",
    "setting": "setting",
}


def _key(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _edition_row(category: str, task: str, edition: dict[str, Any], check: str) -> dict[str, Any]:
    return {
        "category": category,
        "year": edition["year"],
        "name": edition.get("name"),
        "start_date": edition.get("start_date"),
        "end_date": edition.get("end_date"),
        "city": edition.get("city"),
        "country": edition.get("country"),
        "venue": edition.get("venue"),
        "setting": edition.get("setting"),
        "meeting": edition.get("meeting"),
        "wa_competition": edition.get("wa_competition_id"),
        "events": " ".join(edition.get("events") or []),
        "events_scope": edition.get("events_scope"),
        "confidence": edition.get("confidence"),
        "check": check,
        "source": edition.get("source"),
        "notes": edition.get("notes"),
        "task": task,
    }


def _matches(row: dict[str, Any], year: int, name: str) -> bool:
    """Whether a verifier's correction or spurious entry names this row."""
    if row["year"] != year:
        return False
    wanted = _key(name)
    return any(
        wanted and (wanted in _key(row[f]) or _key(row[f]) in wanted)
        for f in ("name", "meeting", "city")
        if row[f]
    )


def editions(results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], ...]:
    rows, rounds, programmes, not_held = [], [], [], []
    for result in results:
        task, answer, verdict = result["task"], result.get("res"), result.get("verdict")
        if task["type"] != "editions" or not answer:
            continue
        label = f"{task['cat']}:{task['from']}-{task['to']}"
        check = "verified" if verdict else "unverified"
        chunk = [_edition_row(task["cat"], label, e, check) for e in answer["editions"]]
        for e in answer["editions"]:
            for r in e.get("rounds") or []:
                rounds.append(
                    {
                        "category": task["cat"],
                        "year": e["year"],
                        "name": e.get("name"),
                        "meeting": e.get("meeting"),
                        "city": e.get("city"),
                        "event": r["event"],
                        "round": r["round"],
                        "races": r["races"],
                    }
                )
        if verdict:
            for spurious in verdict.get("spurious") or []:
                for row in chunk:
                    if _matches(row, spurious["year"], spurious["name"]):
                        row["check"] = f"spurious: {spurious['reason']}"[:300]
            for fix in verdict.get("corrections") or []:
                field = CORRECTABLE.get(fix["field"].strip().lower())
                for row in chunk:
                    if field and _matches(row, fix["year"], fix["name"]):
                        row[field] = fix["should_be"]
                        row["check"] = f"corrected {field}: was {fix['was']}"[:300]
            for e in verdict.get("missing") or []:
                chunk.append(_edition_row(task["cat"], label, e, "added by verifier"))
                for r in e.get("rounds") or []:
                    rounds.append(
                        {
                            "category": task["cat"],
                            "year": e["year"],
                            "name": e.get("name"),
                            "meeting": e.get("meeting"),
                            "city": e.get("city"),
                            "event": r["event"],
                            "round": r["round"],
                            "races": r["races"],
                        }
                    )
        rows += chunk
        for p in answer.get("programme_eras") or []:
            programmes.append(
                {
                    "category": task["cat"],
                    "from_year": p["from_year"],
                    "to_year": p["to_year"],
                    "events": " ".join(p["events"]),
                    "usual_rounds": p.get("usual_rounds"),
                    "source": p.get("source"),
                }
            )
        for n in answer.get("not_held") or []:
            not_held.append({"category": task["cat"], "year": n["year"], "reason": n["reason"]})
    return rows, rounds, programmes, not_held


def lineages(results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows, meetings = [], []
    for result in results:
        if result["task"]["type"] != "lineages" or not result.get("res"):
            continue
        for meeting in result["res"]["meetings"]:
            meetings.append(
                {
                    k: meeting.get(k)
                    for k in (
                        "name",
                        "held_from",
                        "held_to",
                        "years_not_held",
                        "confidence",
                        "notes",
                        "sources",
                    )
                }
            )
            for e in meeting["editions"]:
                rows.append(
                    {
                        "meeting": meeting["name"],
                        "year": e["year"],
                        "date": e.get("date"),
                        "city": e.get("city"),
                        "venue": e.get("venue"),
                        "name": e.get("name"),
                        "setting": e.get("setting"),
                        "circuit": e.get("circuit"),
                        "wa_competition": e.get("wa_competition_id"),
                        "source": e.get("source"),
                    }
                )
    return rows, meetings


def availability(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found = []
    for result in results:
        if result["task"]["type"] != "availability" or not result.get("res"):
            continue
        found += result["res"]["categories"]
    return sorted(found, key=lambda c: c["category"])


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    results: list[dict[str, Any]] = []
    for name in sys.argv[1:]:
        data = json.loads(Path(name).read_text())
        data = data.get("result", data)  # the workflow's output file wraps its return value
        if "results" in data:
            results += data["results"]
    RESEARCH.mkdir(exist_ok=True)
    rows, rounds, programmes, not_held = editions(results)
    rows.sort(
        key=lambda r: (
            r["category"],
            r["year"],
            r["start_date"] or "",
            r["meeting"] or "",
            r["name"] or "",
        )
    )
    _write_csv(RESEARCH / "editions.csv", rows, EDITION_FIELDS)
    _write_csv(RESEARCH / "rounds.csv", rounds)
    _write_csv(RESEARCH / "programmes.csv", programmes)
    _write_csv(RESEARCH / "not-held.csv", not_held)
    lineage_rows, meetings = lineages(results)
    lineage_rows.sort(key=lambda r: (r["meeting"], r["year"]))
    _write_csv(RESEARCH / "lineages.csv", lineage_rows)
    (RESEARCH / "meetings.yaml").write_text(
        yaml.safe_dump(
            sorted(meetings, key=lambda m: m["name"]),
            sort_keys=False,
            allow_unicode=True,
            width=100,
        )
    )
    (SURVEY / "availability.yaml").write_text(
        "# For each elite category, era by era: were split times published, for which events and\n"
        "# rounds, at what granularity, and where they can be found. Researched 2026-10-01.\n\n"
        + yaml.safe_dump(availability(results), sort_keys=False, allow_unicode=True, width=100)
    )
    print(
        f"{len(rows)} editions, {len(rounds)} round counts, {len(programmes)} programme eras, "
        f"{len(lineage_rows)} meeting editions in {len(meetings)} lineages"
    )


if __name__ == "__main__":
    main()
