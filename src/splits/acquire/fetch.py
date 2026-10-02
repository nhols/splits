"""Download catalog documents into the store and pin them in lock files.

For each document: if its pinned bytes are already stored, nothing happens. Otherwise the
publisher's URL is tried, then the archive snapshot. What was downloaded must be a PDF or a web
page and, if the document is already pinned, must have exactly the pinned hash: a publisher
replacing a document is reported, never absorbed. Pass ``accept_changes`` to re-pin changed
documents after reviewing them.
"""

import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from itertools import groupby
from pathlib import Path

import httpx

from splits.acquire.store import Store, media_type_of, sha256_of
from splits.catalog.load import COMPETITIONS_DIR
from splits.catalog.lock import Lock, read_lock, write_lock
from splits.model import DocumentId, DocumentSpec, Retrieval

USER_AGENT = "splits/0.1 (a research dataset of split times; polite, cached fetches)"
PAUSE_SECONDS = 0.5
ARCHIVE_PAUSE_SECONDS = 6.0
"""The Web Archive refuses connections, for minutes at a time, from a client that asks it for
more than about ten documents a minute."""
ARCHIVE_HOSTS = frozenset({"web.archive.org"})


class Outcome(StrEnum):
    STORED = "stored"  # already pinned and present in the store
    FETCHED = "fetched"  # downloaded for the first time and pinned
    RESTORED = "restored"  # pinned bytes re-downloaded into an empty store
    CHANGED = "changed"  # the publisher now serves different bytes
    FAILED = "failed"


@dataclass(frozen=True)
class FetchResult:
    document: DocumentId
    outcome: Outcome
    detail: str = ""


def fetch_documents(
    catalog_root: Path,
    store: Store,
    documents: Iterable[DocumentSpec],
    *,
    accept_changes: bool = False,
) -> list[FetchResult]:
    results: list[FetchResult] = []
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=60) as client:
        downloader = _Downloader(client)
        by_competition = groupby(
            sorted(documents, key=lambda d: d.competition), key=lambda d: d.competition
        )
        for competition, specs in by_competition:
            directory = catalog_root / COMPETITIONS_DIR / competition
            lock = read_lock(directory)
            pinned = dict(lock.documents)
            for spec in specs:
                result, retrieval = _fetch_one(downloader, store, spec, pinned.get(spec.id))
                results.append(result)
                if retrieval is not None and (
                    result.outcome is not Outcome.CHANGED or accept_changes
                ):
                    pinned[spec.id] = retrieval
            write_lock(directory, Lock(documents=pinned))
    return results


def _fetch_one(
    downloader: "_Downloader", store: Store, spec: DocumentSpec, pinned: Retrieval | None
) -> tuple[FetchResult, Retrieval | None]:
    if pinned is not None and store.has(pinned.sha256):
        return FetchResult(spec.id, Outcome.STORED), None

    errors: list[str] = []
    changed: Retrieval | None = None
    for url in (spec.url, spec.archive_url):
        if url is None:
            continue
        try:
            retrieval, content = downloader.get(url)
        except (httpx.HTTPError, ValueError) as error:
            errors.append(f"{url}: {error}")
            continue
        if pinned is None:
            store.put(content)
            return FetchResult(spec.id, Outcome.FETCHED, url), retrieval
        if retrieval.sha256 == pinned.sha256:
            store.put(content)
            return FetchResult(spec.id, Outcome.RESTORED, url), pinned
        changed = changed or retrieval
        store.put(content)
        errors.append(f"{url}: serves {retrieval.sha256[:12]}…, pinned {pinned.sha256[:12]}…")

    if changed is not None:
        return FetchResult(spec.id, Outcome.CHANGED, "; ".join(errors)), changed
    return FetchResult(spec.id, Outcome.FAILED, "; ".join(errors)), None


class _Downloader:
    """Downloads each URL at most once per run: several races can share one document, such
    as a round's results covering all its heats. A host that does not answer at all (a
    timeout, a refused connection) is not asked again in the same run, so documents with an
    archived copy go straight to it rather than waiting out every timeout."""

    def __init__(self, client: httpx.Client) -> None:
        self.client = client
        self.seen: dict[str, tuple[Retrieval, bytes] | Exception] = {}
        self.unreachable: dict[str, Exception] = {}

    def get(self, url: str) -> tuple[Retrieval, bytes]:
        host = httpx.URL(url).host
        if url not in self.seen and host in self.unreachable:
            self.seen[url] = self.unreachable[host]
        if url not in self.seen:
            try:
                self.seen[url] = _download(self.client, url)
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                self.unreachable[host] = error
                self.seen[url] = error
            except (httpx.HTTPError, ValueError) as error:
                self.seen[url] = error
        outcome = self.seen[url]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _download(client: httpx.Client, url: str) -> tuple[Retrieval, bytes]:
    time.sleep(ARCHIVE_PAUSE_SECONDS if httpx.URL(url).host in ARCHIVE_HOSTS else PAUSE_SECONDS)
    response = client.get(url)
    response.raise_for_status()
    content = response.content
    try:
        media_type = media_type_of(content)
    except ValueError as error:
        kind = response.headers.get("content-type", "unknown type")
        raise ValueError(f"neither a PDF nor a web page ({kind})") from error
    retrieval = Retrieval(
        sha256=sha256_of(content),
        size=len(content),
        media_type=media_type,
        retrieved_at=datetime.now(UTC).replace(microsecond=0),
        retrieved_from=str(response.url),
    )
    return retrieval, content
