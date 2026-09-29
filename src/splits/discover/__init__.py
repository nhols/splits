"""Discovery: the documents a publisher lists for a competition, as catalog entries.

The catalog declares, race by race, which documents the dataset is read from. Discovery reads
the publisher's own listing of a competition's documents (World Athletics' results pages, for
example) and turns it into the same entries, so a competition's catalog file can be written
from the listing and later checked against it: every race the publisher gives splits for is
then either declared or excluded with a reason, and nothing is missed silently.

A listing only proposes; the catalog decides. Entries are written for review, and the build
still makes every document confirm the race it is declared for.
"""

from dataclasses import dataclass

import httpx

from splits.model import Catalog, Competition, DocumentId, FormatId, RaceKey
from splits.model.base import Record
from splits.model.ids import document_id, race_id
from splits.model.values import NonEmptyStr, PositiveInt, Url

USER_AGENT = "splits/0.1 (a research dataset of split times; polite, cached fetches)"


class ListedDocument(Record):
    """One document a publisher lists for one race, as a catalog entry would declare it."""

    race: RaceKey
    format: FormatId
    url: Url
    archive_url: Url | None = None
    pages: tuple[PositiveInt, ...] | None = None


class Listing(Record):
    """Everything a publisher lists for a competition, and where the list was read."""

    source: NonEmptyStr
    """Where the listing comes from, e.g. World Athletics' results pages for one competition."""
    formats: tuple[FormatId, ...]
    """The formats this kind of listing proposes: catalog documents of other formats (a
    statistics handbook, say) are not the listing's business."""
    documents: tuple[ListedDocument, ...]


@dataclass(frozen=True)
class Comparison:
    """A listing set against the catalog's declarations for the same competition."""

    listing: Listing
    missing: tuple[ListedDocument, ...]
    """Listed, for a race neither declared nor excluded."""
    moved: tuple[tuple[ListedDocument, Url], ...]
    """Declared, but the listing gives another URL (the listed document, the declared URL)."""
    unlisted: tuple[DocumentId, ...]
    """Declared in one of the listing's formats for a race the listing lists, but not listed."""
    by_hand: tuple[RaceKey, ...]
    """Races the catalog declares that the listing does not list at all: declared by hand (a
    world record's results, a biomechanics report), and kept when the listing is written."""
    excluded: tuple[ListedDocument, ...]
    """Listed for a race the catalog excludes."""


def compare(listing: Listing, catalog: Catalog, competition: Competition) -> Comparison:
    declared = {doc.id: doc for doc in catalog.documents if doc.competition == competition.id}
    excluded_races = {
        race_id(competition.id, exclusion.race)
        for exclusion in catalog.exclusions
        if exclusion.competition == competition.id
    }
    missing: list[ListedDocument] = []
    moved: list[tuple[ListedDocument, Url]] = []
    excluded: list[ListedDocument] = []
    listed_ids: set[DocumentId] = set()
    for listed in listing.documents:
        doc_id = listed_id(competition, listed)
        listed_ids.add(doc_id)
        if race_id(competition.id, listed.race) in excluded_races:
            excluded.append(listed)
        elif doc_id not in declared:
            missing.append(listed)
        elif declared[doc_id].url != listed.url:
            moved.append((listed, declared[doc_id].url))
    listed_races = {doc.race for doc in listing.documents}
    unlisted = tuple(
        doc_id
        for doc_id, doc in declared.items()
        if doc.format in listing.formats and doc_id not in listed_ids and doc.race in listed_races
    )
    by_hand = tuple(sorted({doc.race for doc in declared.values()} - listed_races, key=str))
    return Comparison(listing, tuple(missing), tuple(moved), unlisted, by_hand, tuple(excluded))


def listed_id(competition: Competition, listed: ListedDocument) -> DocumentId:
    return document_id(race_id(competition.id, listed.race), listed.format)


def discover(competition: Competition, catalog: Catalog) -> Listing:
    """The publisher's listing for ``competition``: where its catalog file says the documents
    are listed, or else its results page."""
    from splits.discover import oris_index, results_book, world_athletics

    url = competition.listing_url or competition.results_url or ""
    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=120
    ) as client:
        if world_athletics.handles(url):
            return world_athletics.listing(competition, catalog, client)
        if results_book.handles(url):
            return results_book.listing(competition, catalog, client)
        if oris_index.handles(url):
            return oris_index.listing(competition, catalog, client)
    raise ValueError(f"{competition.id}: no discovery for its listing ({url or 'none declared'})")
