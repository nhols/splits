"""Acquiring documents: downloading, content-addressed storage, pinning."""

from splits.acquire.fetch import FetchResult, Outcome, fetch_documents
from splits.acquire.store import Store

__all__ = ["FetchResult", "Outcome", "Store", "fetch_documents"]
