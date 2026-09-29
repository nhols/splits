"""Results books of the Olympic results system (ORIS): which pages report which race.

After the Games the organising committee compiles every report of a sport into one results
book. Each page's footer names its report by event unit and report code: ``ATM008901_77A`` is
the race analysis (C77A) of the men's 800 m, round 1, heat 1; ``_73G`` the results of a final,
``_73H`` those of a whole round, one section per race. A report may run to several pages. The
page's heading names the event and the round the way the readers read it, so a book is listed
by reading every page's footer and heading: each race analysis becomes a race, read from its
pages together with its round's results.

A book that survives only in the Wayback Machine is listed from its snapshot; its entries
declare the book's original address, and the snapshot as its archived copy.
"""

import re
from dataclasses import dataclass

import httpx

from splits.acquire.store import sha256_of
from splits.discover import ListedDocument, Listing
from splits.formats.oris import FOOTER, race_key
from splits.model import Catalog, Competition, FormatId, RaceKey
from splits.model.ids import format_id
from splits.pdf.layout import group_lines
from splits.pdf.textlayer import extract_text_layer

ANALYSIS = "77A"
SNAPSHOT = re.compile(
    r"^https://web\.archive\.org/web/(?P<time>\d{14})id_/(?P<original>https?://.+)$"
)
FORMATS = (format_id("oris-c77a"), format_id("oris-c73b1"))


def handles(url: str) -> bool:
    return url.lower().endswith(".pdf")


@dataclass
class _Report:
    """One report in the book: its pages, and the race or round its heading names."""

    report: str
    pages: list[int]
    race: RaceKey


def listing(competition: Competition, catalog: Catalog, client: httpx.Client) -> Listing:
    url = competition.listing_url
    if url is None:
        raise ValueError(f"{competition.id}: no results book declared as its listing")
    response = client.get(url)
    response.raise_for_status()
    content = response.content

    reports: dict[tuple[str, str], _Report] = {}
    for page in extract_text_layer(content, sha256_of(content)).pages:
        lines = [line.text for line in group_lines(page.words, page.number)]
        footer = next((found for text in lines if (found := FOOTER.search(text))), None)
        if footer is None or footer["report"][:2] not in ("73", "77"):
            continue  # a cover, a timetable, a start list: nothing we read
        key = (footer["unit"], footer["report"])
        if key in reports:
            reports[key].pages.append(page.number)
            continue
        race = race_key(lines)
        if race is None or race.discipline not in catalog.disciplines:
            continue  # a field event, a relay, a walk
        reports[key] = _Report(report=footer["report"], pages=[page.number], race=race)

    snapshot = SNAPSHOT.match(url)
    original, archived = (snapshot["original"], url) if snapshot else (url, None)
    results = {
        (r.race.discipline, r.race.sex, r.race.round, r.race.heat): r
        for r in reports.values()
        if r.report != ANALYSIS
    }
    documents: list[ListedDocument] = []
    for analysis in (r for r in reports.values() if r.report == ANALYSIS):
        race = analysis.race
        own = (race.discipline, race.sex, race.round, race.heat)
        of_round = (race.discipline, race.sex, race.round, None)
        documents.append(_entry(race, FORMATS[0], original, archived, analysis.pages))
        results_report = results.get(own) or results.get(of_round)
        if results_report is not None:
            documents.append(_entry(race, FORMATS[1], original, archived, results_report.pages))
    return Listing(
        source=f"the pages of the results book {original}",
        formats=FORMATS,
        documents=tuple(documents),
    )


def _entry(
    race: RaceKey, fmt: FormatId, url: str, archived: str | None, pages: list[int]
) -> ListedDocument:
    return ListedDocument(race=race, format=fmt, url=url, archive_url=archived, pages=tuple(pages))
