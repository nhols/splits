import shutil
from pathlib import Path

import pytest

from splits.catalog import CatalogError, load_catalog
from splits.formats import FORMATS
from splits.model import Catalog
from splits.model.values import annotation_meaning
from tests.conftest import ROOT

RESULTS_ALONE = {"og-2020-tokyo/400mh-men/final"}
"""A world-record race read from its official results alone: no splits were published."""


def test_the_catalog_is_valid(catalog: Catalog) -> None:
    assert len(catalog.competitions) == 115
    assert all(doc.retrieval is not None for doc in catalog.documents), "run `splits fetch`"


def test_every_race_has_its_results_and_its_analysis(catalog: Catalog) -> None:
    """Races of the past are read from what survives of them: a statistics handbook's result
    with its halves and splits, or the official results alone."""
    kinds: dict[str, set[str]] = {}
    for doc in catalog.documents:
        kinds.setdefault(doc.race_id, set()).add(FORMATS[doc.format].kind.value)
    assert len(kinds) == 2078
    assert all("results" in found for found in kinds.values())
    past = {doc.race_id for doc in catalog.documents if doc.format == "wa-handbook"}
    current = {race: found for race, found in kinds.items() if race not in past | RESULTS_ALONE}
    assert all(found == {"results", "analysis"} for found in current.values())


def test_a_race_cannot_be_both_declared_and_excluded(tmp_path: Path) -> None:
    root = _catalog_copy(tmp_path)
    competition = root / "competitions" / "wch-2019-doha" / "competition.yaml"
    _break(competition, "race: 100m-men/heat-5", "race: 800m-men/final")
    with pytest.raises(CatalogError, match="800m-men/final is both declared and excluded"):
        load_catalog(root)


def test_exclusions_give_a_reason(catalog: Catalog) -> None:
    excluded = {f"{e.competition}/{e.race}": e.reason for e in catalog.exclusions}
    assert "wch-2019-doha/100m-men/heat-5" in excluded
    assert all(reason.strip() for reason in excluded.values())


def test_values_know_where_they_were_declared(catalog: Catalog) -> None:
    doc = next(d for d in catalog.documents if d.id == "og-2024-paris/400m-men/final/oris-c77a")
    declared = doc.declared
    assert declared.file == "catalog/competitions/og-2024-paris/competition.yaml"
    lines = (ROOT / declared.file).read_text().splitlines()
    assert lines[declared.line - 1].strip() == "- race: 400m-men/final"


@pytest.mark.parametrize(
    ("printed", "meaning"),
    [
        ("PB", "Personal best"),
        ("=SB", "Season best, equalled"),
        ("TR 16.8", "False start"),
        ("TR № 17.3.1", "Lane infringement"),
        ("TR17.1.2(J)", "Jostling"),
        ("R 163.2", "Jostling or obstruction"),
        ("Rule 10.1", "Disqualified under the anti-doping rules (provisionally suspended)"),
        ("Q", None),
    ],
)
def test_a_mark_means_the_same_however_it_is_printed(
    catalog: Catalog, printed: str, meaning: str | None
) -> None:
    meanings = {annotation.code: annotation.meaning for annotation in catalog.annotations}
    assert annotation_meaning(printed, meanings) == meaning


def test_a_mark_is_explained_once(tmp_path: Path) -> None:
    root = _catalog_copy(tmp_path)
    _break(root / "annotations.yaml", "- code: YC\n", '- code: "Y"\n')
    with pytest.raises(CatalogError, match=r"annotations explained twice: \['Y'\]"):
        load_catalog(root)


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
