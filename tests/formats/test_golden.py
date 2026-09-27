"""Golden tests: every fixture document must read exactly as recorded in
``tests/fixtures/readings/``, value by value, including where each value was read from.

After an intended change to a reader, regenerate the snapshots and review the diff:

    UPDATE_GOLDEN=1 uv run pytest tests/formats
"""

import os
from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import BaseModel

from splits.formats import EntryReading, SegmentReading, SplitReading
from splits.model import Catalog, Sourced, Span, TimingPoint
from tests.conftest import FIXTURES, fixture_documents, read_fixture

READINGS = FIXTURES / "readings"


def transcript(value: Any, path: str = "") -> Iterator[str]:
    """One line per value: its path, value and source (page, box, text, rule)."""
    if isinstance(value, Sourced):
        span = value.span
        box = span.bbox
        yield (
            f"{path} = {value.value!r} ← p{span.page} "
            f"({box.x0:.1f},{box.top:.1f},{box.x1:.1f},{box.bottom:.1f}) "
            f"{span.text!r} [{value.method}]"
        )
    elif isinstance(value, TimingPoint):
        yield f"{path} = {value.label} ({value.kind.value} at {value.distance} m)"
    elif isinstance(value, Span):
        box = value.bbox
        yield (
            f"{path} = p{value.page} ({box.x0:.1f},{box.top:.1f},{box.x1:.1f},{box.bottom:.1f}) "
            f"{value.text!r}"
        )
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from transcript(getattr(value, name), f"{path}.{name}" if path else name)
    elif isinstance(value, tuple):
        for index, item in enumerate(value):
            yield from transcript(item, f"{path}[{_label(item, index)}]")
    else:
        yield f"{path} = {value!r}"


def _label(item: Any, index: int) -> str:
    if isinstance(item, EntryReading):
        return f"{index}:{item.name.value.family}"
    if isinstance(item, SplitReading):
        return item.point.label
    if isinstance(item, SegmentReading):
        return f"{item.start.label}-{item.end.label}"
    return str(index)


@pytest.mark.parametrize("document", fixture_documents())
def test_reading_matches_golden(catalog: Catalog, document: str) -> None:
    reading = read_fixture(catalog, document).reading
    actual = "\n".join(transcript(reading)) + "\n"
    expected = READINGS / f"{document}.txt"
    if os.environ.get("UPDATE_GOLDEN"):
        expected.parent.mkdir(parents=True, exist_ok=True)
        expected.write_text(actual, encoding="utf-8")
    assert expected.exists(), f"no golden reading for {document}; run with UPDATE_GOLDEN=1"
    assert actual == expected.read_text(encoding="utf-8")
