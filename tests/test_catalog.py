import shutil
from pathlib import Path

import pytest

from splits.catalog import CatalogError, load_catalog
from splits.formats import FORMATS
from splits.model import Catalog
from tests.conftest import ROOT

RECORD_MEETS = {
    "og-1988-seoul",
    "og-2016-rio",
    "og-2020-tokyo",
    "wch-2009-berlin",
    "wcup-1985-canberra",
}
"""Competitions catalogued for a world record alone, read from what survives of them."""


def test_the_catalog_is_valid(catalog: Catalog) -> None:
    assert len(catalog.competitions) == 89
    assert all(doc.retrieval is not None for doc in catalog.documents), "run `splits fetch`"


def test_every_race_has_its_results_and_its_analysis(catalog: Catalog) -> None:
    kinds: dict[str, set[str]] = {}
    for doc in catalog.documents:
        kinds.setdefault(doc.race_id, set()).add(FORMATS[doc.format].kind.value)
    assert len(kinds) == 1145
    assert all("results" in found for found in kinds.values())
    current = {
        race: found for race, found in kinds.items() if race.split("/")[0] not in RECORD_MEETS
    }
    assert all(found == {"results", "analysis"} for found in current.values())


def test_values_know_where_they_were_declared(catalog: Catalog) -> None:
    doc = next(d for d in catalog.documents if d.id == "og-2024-paris/400m-men/final/oris-c77a")
    declared = doc.declared
    assert declared.file == "catalog/competitions/og-2024-paris/competition.yaml"
    lines = (ROOT / declared.file).read_text().splitlines()
    assert lines[declared.line - 1].strip() == "- race: 400m-men/final"


def _catalog_copy(tmp_path: Path) -> Path:
    root = tmp_path / "catalog"
    shutil.copytree(ROOT / "catalog", root)
    return root


def _break(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new, 1))


def test_errors_name_the_file_and_line(tmp_path: Path) -> None:
    root = _catalog_copy(tmp_path)
    competition = root / "competitions" / "dl-2023-zurich" / "competition.yaml"
    _break(competition, "race: 400m-women/final", "race: 400m-woman/final")
    with pytest.raises(CatalogError, match=r"dl-2023-zurich/competition\.yaml:\d+: invalid race"):
        load_catalog(root)


def test_unknown_fields_are_rejected(tmp_path: Path) -> None:
    root = _catalog_copy(tmp_path)
    competition = root / "competitions" / "dl-2023-zurich" / "competition.yaml"
    _break(competition, "setting: outdoor", "setting: outdoor\nsettting: indoor")
    with pytest.raises(CatalogError, match="settting"):
        load_catalog(root)


def test_a_lock_must_not_pin_undeclared_documents(tmp_path: Path) -> None:
    root = _catalog_copy(tmp_path)
    competition = root / "competitions" / "dl-2023-zurich" / "competition.yaml"
    _break(competition, "race: 400mh-men/final", "race: 400mh-men/semi-final-1")
    with pytest.raises(CatalogError, match="pins documents that are no longer declared"):
        load_catalog(root)


def test_hurdles_races_need_barriers_for_that_sex(tmp_path: Path) -> None:
    root = _catalog_copy(tmp_path)
    (root / "competitions" / "dl-2023-zurich" / "lock.json").unlink()
    competition = root / "competitions" / "dl-2023-zurich" / "competition.yaml"
    _break(competition, "race: 400mh-men/final", "race: 110mh-women/final")
    with pytest.raises(CatalogError, match="no barriers for"):
        load_catalog(root)
