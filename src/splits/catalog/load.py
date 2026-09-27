"""Load the catalog directory into a validated :class:`~splits.model.Catalog`.

Every error names the file and line to fix. Every record gets a ``declared`` reference to the
place that declared it.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from splits.catalog.located import CatalogError, LocatedYaml
from splits.catalog.lock import read_lock
from splits.model import (
    AthleteRule,
    Catalog,
    Competition,
    Discipline,
    DocumentSpec,
    RaceKey,
    Series,
)
from splits.model.ids import competition_id, document_id, format_id, race_id

COMPETITIONS_DIR = "competitions"
COMPETITION_FILE = "competition.yaml"


def load_catalog(root: Path) -> Catalog:
    """Load ``root`` (the ``catalog/`` directory) and validate it as a whole."""
    disciplines = _load_list(root / "disciplines.yaml", root, Discipline)
    series = _load_list(root / "series.yaml", root, Series)
    athletes = _load_list(root / "athletes.yaml", root, AthleteRule)

    competitions: dict[str, Competition] = {}
    documents: list[DocumentSpec] = []
    for directory in sorted((root / COMPETITIONS_DIR).iterdir()):
        if directory.is_dir():
            competition, specs = _load_competition(directory, root)
            competitions[competition.id] = competition
            documents.extend(specs)

    try:
        return Catalog.model_validate(
            {
                "disciplines": {d.id: d for d in disciplines},
                "series": {s.id: s for s in series},
                "competitions": competitions,
                "documents": tuple(documents),
                "athletes": tuple(athletes),
            }
        )
    except ValidationError as error:
        raise CatalogError(error.errors()[0]["msg"].removeprefix("Value error, ")) from error


def _load_list[M: BaseModel](path: Path, root: Path, model: type[M]) -> list[M]:
    located = LocatedYaml.load(path, root)
    if not isinstance(located.data, list):
        raise located.error("", "expected a list")
    return [_validate(located, f"/{index}", model, item) for index, item in enumerate(located.data)]


def _validate[M: BaseModel](located: LocatedYaml, pointer: str, model: type[M], data: Any) -> M:
    """Validate one declared entity, attaching where it was declared."""
    if not isinstance(data, dict):
        raise located.error(pointer, "expected a mapping")
    try:
        return model.model_validate({**data, "declared": located.ref(pointer)}, strict=False)
    except ValidationError as error:
        raise located.invalid(pointer, error) from error


def _load_competition(directory: Path, root: Path) -> tuple[Competition, list[DocumentSpec]]:
    located = LocatedYaml.load(directory / COMPETITION_FILE, root)
    if not isinstance(located.data, dict):
        raise located.error("", "expected a mapping")
    fields = dict(located.data)
    entries = fields.pop("documents", [])
    competition = _validate(located, "", Competition, fields)
    if competition.id != directory.name:
        raise located.error("/id", f"id {competition.id!r} must match the directory name")

    lock = read_lock(directory)
    specs = [
        _document(located, f"/documents/{index}", competition, entry, lock.documents)
        for index, entry in enumerate(_as_list(located, "/documents", entries))
    ]
    stale = set(lock.documents) - {spec.id for spec in specs}
    if stale:
        raise CatalogError(
            f"{directory.relative_to(root.parent)}/lock.json pins documents that are no longer "
            f"declared: {sorted(stale)}. Run `splits fetch` to refresh the lock."
        )
    return competition, specs


def _document(
    located: LocatedYaml,
    pointer: str,
    competition: Competition,
    entry: Any,
    pinned: dict[Any, Any],
) -> DocumentSpec:
    if not isinstance(entry, dict):
        raise located.error(pointer, "expected a mapping")
    parse: Callable[[str], Any]
    for key, parse in (("race", RaceKey.parse), ("format", format_id)):
        if key not in entry:
            raise located.error(pointer, f"missing '{key}'")
        try:
            entry = {**entry, key: parse(str(entry[key]))}
        except ValueError as error:
            raise located.error(f"{pointer}/{key}", str(error)) from error
    doc_id = document_id(race_id(competition_id(competition.id), entry["race"]), entry["format"])
    return _validate(
        located,
        pointer,
        DocumentSpec,
        {**entry, "id": doc_id, "competition": competition.id, "retrieval": pinned.get(doc_id)},
    )


def _as_list(located: LocatedYaml, pointer: str, value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise located.error(pointer, "expected a list")
    return value
