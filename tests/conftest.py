"""Shared test fixtures.

Tests run on text layers of real documents saved in ``tests/fixtures/text/`` (written by
``splits fixture``), with World Athletics' results of their competitions saved in
``tests/fixtures/world-athletics/``, so they need neither the network nor the PDF store.
"""

import gzip
from datetime import UTC, datetime
from pathlib import Path

import pytest

from splits.acquire.store import sha256_of
from splits.assemble import DocumentRead
from splits.assemble.world_athletics import WorldAthleticsResults
from splits.catalog import load_catalog
from splits.formats import DocumentReading, ReadContext, get_format
from splits.model import Catalog, Dataset
from splits.pdf.layout import DocumentView
from splits.pdf.textlayer import TextLayer
from splits.pipeline import make_dataset

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
TEXT = FIXTURES / "text"
WORLD_ATHLETICS = FIXTURES / "world-athletics"


def fixture_documents() -> list[str]:
    return sorted(
        path.relative_to(TEXT).with_suffix("").as_posix() for path in TEXT.rglob("*.json")
    )


def load_layer(document: str) -> TextLayer:
    return TextLayer.model_validate_json((TEXT / f"{document}.json").read_text(encoding="utf-8"))


def read_fixture(catalog: Catalog, document: str, layer: TextLayer | None = None) -> DocumentRead:
    spec = next(doc for doc in catalog.documents if doc.id == document)
    context = ReadContext(
        spec=spec,
        discipline=catalog.discipline_of(spec),
        competition=catalog.competition_of(spec),
    )
    reading: DocumentReading = get_format(spec.format).read(
        DocumentView(spec.id, layer or load_layer(document)), context
    )
    return DocumentRead(spec, reading)


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    # The fixtures hold a few races, not every athlete that has a number.
    return load_catalog(ROOT / "catalog").model_copy(update={"athlete_numbers": {}})


@pytest.fixture(scope="session")
def reads(catalog: Catalog) -> list[DocumentRead]:
    return [read_fixture(catalog, document) for document in fixture_documents()]


@pytest.fixture(scope="session")
def world_athletics(
    catalog: Catalog, reads: list[DocumentRead]
) -> dict[str, WorldAthleticsResults]:
    """World Athletics' results of the fixtures' competitions, as pinned."""
    found = {}
    for competition in {read.spec.competition for read in reads}:
        pinned = catalog.competitions[competition].world_athletics_results
        if pinned is None:
            continue
        content = gzip.decompress((WORLD_ATHLETICS / f"{pinned.sha256}.gz").read_bytes())
        assert sha256_of(content) == pinned.sha256, f"{competition}: stale fixture"
        found[str(competition)] = WorldAthleticsResults(competition, pinned, content)
    return found


@pytest.fixture(scope="session")
def dataset(
    catalog: Catalog, reads: list[DocumentRead], world_athletics: dict[str, WorldAthleticsResults]
) -> Dataset:
    return make_dataset(
        catalog,
        reads,
        code_version="test",
        built_at=datetime(2026, 1, 1, tzinfo=UTC),
        world_athletics=world_athletics,
    )
