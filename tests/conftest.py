"""Shared test fixtures.

Tests run on text layers of real documents saved in ``tests/fixtures/text/`` (written by
``splits fixture``), so they need neither the network nor the PDF store.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from splits.assemble import DocumentRead
from splits.catalog import load_catalog
from splits.formats import DocumentReading, ReadContext, get_format
from splits.model import Catalog, Dataset
from splits.pdf.layout import DocumentView
from splits.pdf.textlayer import TextLayer
from splits.pipeline import make_dataset

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
TEXT = FIXTURES / "text"


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
    return load_catalog(ROOT / "catalog")


@pytest.fixture(scope="session")
def reads(catalog: Catalog) -> list[DocumentRead]:
    return [read_fixture(catalog, document) for document in fixture_documents()]


@pytest.fixture(scope="session")
def dataset(catalog: Catalog, reads: list[DocumentRead]) -> Dataset:
    return make_dataset(
        catalog, reads, code_version="test", built_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
