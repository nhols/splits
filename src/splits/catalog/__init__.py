"""The curated catalog: loading, validation and lock files."""

from splits.catalog.load import load_catalog
from splits.catalog.located import CatalogError

__all__ = ["CatalogError", "load_catalog"]
