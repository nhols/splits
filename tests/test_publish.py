import json
from pathlib import Path

import duckdb

from splits.model import Dataset
from splits.publish import build_tables, schema_markdown, write_database, write_site_data
from splits.publish.site_schema import EventData, Index, RaceData
from tests.conftest import ROOT


def test_database_links_every_value_to_its_source(dataset: Dataset, tmp_path: Path) -> None:
    database = tmp_path / "splits.duckdb"
    write_database(build_tables(dataset), database)
    with duckdb.connect(str(database), read_only=True) as con:
        orphans = con.execute(
            "SELECT count(*) FROM splits s LEFT JOIN provenance p ON p.id = s.time_source "
            "WHERE p.id IS NULL"
        ).fetchone()
        assert orphans == (0,)
        text, method = con.execute(
            "SELECT p.text, p.method FROM splits s JOIN provenance p ON p.id = s.time_source "
            "WHERE s.id = 'wch-2023-budapest/400m-men/final/antonio-watson/200m@wa-rs5'"
        ).fetchone() or (None, None)
        assert (text, method) == ("23.76", "cumulative.time")
        suspect = con.execute(
            "SELECT suspect FROM split_analysis WHERE split LIKE '%antonio-watson/200m%'"
        ).fetchone()
        assert suspect == (True,)


def test_site_data_is_valid_and_self_consistent(dataset: Dataset, tmp_path: Path) -> None:
    write_site_data(dataset, tmp_path)

    index = Index.model_validate_json((tmp_path / "index.json").read_text())
    assert index.build.races == len(dataset.races)

    for event in index.events:
        data = EventData.model_validate_json((tmp_path / "events" / f"{event.id}.json").read_text())
        assert all(len(p.splits) == len(data.points) for p in data.performances)

    for summary in index.races:
        race = RaceData.model_validate_json((tmp_path / "races" / f"{summary.id}.json").read_text())
        values = json.loads(race.model_dump_json(by_alias=True))
        sources = _source_indexes(values)
        assert sources and max(sources) < len(race.sources)
        for performance in race.performances:
            assert all(split.point < len(race.points) for split in performance.splits)


def test_races_list_athletes_in_finishing_order(dataset: Dataset, tmp_path: Path) -> None:
    """Paris 2024: Lyles and Thompson both ran 9.79; the thousandths (9.784, 9.789) and the
    places put Lyles first."""
    write_site_data(dataset, tmp_path)
    race = RaceData.model_validate_json(
        (tmp_path / "races" / "og-2024-paris" / "100m-men" / "final.json").read_text()
    )
    assert [p.athlete for p in race.performances[:2]] == ["noah-lyles", "kishane-thompson"]


def test_analyses_leave_out_a_run_that_lost_time_late(dataset: Dataset, tmp_path: Path) -> None:
    write_site_data(dataset, tmp_path)
    event = EventData.model_validate_json((tmp_path / "events" / "400mh-men.json").read_text())
    robinson = next(p for p in event.performances if p.athlete == "chris-robinson")
    timed = [i for i, value in enumerate(robinson.splits) if value is not None]
    assert timed and robinson.suspect == timed


def _source_indexes(value: object) -> list[int]:
    if isinstance(value, dict):
        found = [value["s"]] if set(value) == {"v", "s"} else []
        return found + [i for item in value.values() for i in _source_indexes(item)]
    if isinstance(value, list):
        return [i for item in value for i in _source_indexes(item)]
    return []


def test_schema_docs_are_current(dataset: Dataset) -> None:
    expected = schema_markdown(build_tables(dataset))
    assert (ROOT / "docs" / "schema.md").read_text() == expected, "run `make docs`"
