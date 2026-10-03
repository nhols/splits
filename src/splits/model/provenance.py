"""Provenance: where every value in the dataset came from.

The dataset obeys one rule: **every stored value is either read from a document or declared in
the catalog** (or, for which World Athletics athlete ran, taken from World Athletics' results,
pinned like a document). Values computed from other values (segment times, speeds,
differentials) are never stored; they are derived from the stored ones when needed, so they
cannot drift.

A value read from a document is wrapped in :class:`Sourced` with a :class:`Span` source: the
page and rectangle the text was read from, the exact text found there, and the name of the
extraction rule that interpreted it. A value a person declared in the catalog carries a
:class:`CatalogRef`: the file, line and path of the declaration. A value taken from a
registry's answer (World Athletics' results, which say which of its athletes ran) carries a
:class:`RegistryRef`: the pinned copy of the answer and the place in it.
"""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from splits.model.base import Record
from splits.model.ids import DocumentId
from splits.model.values import NonEmptyStr, PositiveInt, Sha256


class BBox(Record):
    """A rectangle on a PDF page, in points (1/72 inch) from the page's top-left corner."""

    x0: float
    top: float
    x1: float
    bottom: float

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.x0 > self.x1 or self.top > self.bottom:
            raise ValueError(f"degenerate box {self}")
        return self

    def union(self, other: "BBox") -> "BBox":
        return BBox(
            x0=min(self.x0, other.x0),
            top=min(self.top, other.top),
            x1=max(self.x1, other.x1),
            bottom=max(self.bottom, other.bottom),
        )


class Span(Record):
    """A region of a document that a value was read from."""

    kind: Literal["document"] = "document"
    document: DocumentId
    page: PositiveInt
    bbox: BBox
    text: NonEmptyStr
    """The exact text found in the region, as extracted from the PDF."""


class CatalogRef(Record):
    """A place in the curated catalog where a person declared a value."""

    kind: Literal["catalog"] = "catalog"
    file: NonEmptyStr
    """Repository-relative path, e.g. ``catalog/competitions/og-2024-paris/competition.yaml``."""
    line: PositiveInt
    pointer: str
    """JSON pointer to the declaration inside the file, e.g. ``/documents/3/race``."""


class RegistryRef(Record):
    """A place in a registry's answer: a result in World Athletics' results of a competition."""

    kind: Literal["registry"] = "registry"
    registry: NonEmptyStr
    """``world-athletics``."""
    sha256: Sha256
    """The pinned copy of the answer (in the competition's lock file)."""
    pointer: str
    """JSON pointer to the entry inside it, e.g. ``/days/0/eventTitles/0/events/2/races/0``."""
    text: NonEmptyStr
    """The entry as the registry gives it, e.g. ``1. Georgia HUNTER BELL GBR 1:56.74``."""


Source = Annotated[Span | CatalogRef | RegistryRef, Field(discriminator="kind")]


class Sourced[T](Record):
    """A value together with where it came from and the rule that produced it."""

    value: T
    source: Source
    method: NonEmptyStr
    """The extraction rule that interpreted the source, e.g. ``athlete-row.result``;
    ``declared`` for catalog values."""

    @property
    def span(self) -> Span:
        """The document span, for values that must have been read from a document."""
        if not isinstance(self.source, Span):
            raise TypeError(f"value {self.value!r} was declared in the catalog, not read")
        return self.source
