"""World Athletics' results pages: the documents of every race at its championships.

Each round's results page (``/competitions/<group>/<slug>-<id>/results/<sex>/<event>/<round>/
result``) embeds, in its page data, the round's races ("units") and the documents published for
them: the official results (one ``.RS6`` for the whole round) and, for each race timed at
checkpoints, its race analysis (``.RS5``). The page also names the event's other rounds. Races
without a race analysis give no splits and are not listed; World Athletics publishes none for
the 100 m, 60 m and sprint hurdles. In 2013 it published "official split times" (``.RS7``)
instead, which no reader reads: their names, in title case and in no fixed order, cannot be
split into given and family names.
"""

import json
import re
import time
from typing import Any

import httpx

from splits.discover import ListedDocument, Listing
from splits.formats import parse
from splits.model import Catalog, Competition, FormatId, RaceKey, Sex
from splits.model.ids import discipline_id, format_id

EVENTS = {
    "60m": "60-metres",
    "100m": "100-metres",
    "200m": "200-metres",
    "400m": "400-metres",
    "800m": "800-metres",
    "1500m": "1500-metres",
    "mile": "one-mile",
    "3000m": "3000-metres",
    "5000m": "5000-metres",
    "10000m": "10000-metres",
    "60mh": "60-metres-hurdles",
    "100mh": "100-metres-hurdles",
    "110mh": "110-metres-hurdles",
    "400mh": "400-metres-hurdles",
    "3000msc": "3000-metres-steeplechase",
}
"""Our disciplines and World Athletics' names for them in its URLs."""

SPLIT_DOCUMENTS = ("Race Analysis",)
FILES = "https://media.aws.iaaf.org/competitiondocuments"
PAGE_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
COMPETITION = re.compile(
    r"^https://worldathletics\.org/competitions/(?P<group>[a-z0-9-]+)/"
    r"(?:[a-z0-9-]+-)?(?P<id>\d{7})(?:/|$)"
)
"""A competition's pages: the group (``world-athletics-championships``) and the numeric id; the
words before the id are decoration."""
PAUSE_SECONDS = 0.5

FORMATS = (format_id("wa-rs5"), format_id("wa-rs5-2015"), format_id("wa-results"))


def handles(url: str) -> bool:
    return COMPETITION.match(url) is not None


def document_format(file_name: str, year: int) -> FormatId | None:
    """The reader for a document, by its kind (the file's extension) and the year: race
    analyses were laid out differently until 2017."""
    if file_name.endswith(".RS5.pdf"):
        return format_id("wa-rs5" if year >= 2019 else "wa-rs5-2015")
    if file_name.endswith(".RS6.pdf"):
        return format_id("wa-results")
    return None


def listing(competition: Competition, catalog: Catalog, client: httpx.Client) -> Listing:
    found = COMPETITION.match(competition.results_url or "")
    if found is None:
        raise ValueError(f"{competition.id}: not a World Athletics results page")
    base = f"https://worldathletics.org/competitions/{found['group']}/x-{found['id']}/results"
    documents: list[ListedDocument] = []
    for discipline, slug in EVENTS.items():
        if discipline not in catalog.disciplines:
            continue
        for sex in (Sex.MEN, Sex.WOMEN):
            final = _page(client, f"{base}/{sex.value}/{slug}/final/result")
            if final is None:
                continue
            for phase in final.get("allEventPhasesByDiscipline") or []:
                if phase["sexNameUrlSlug"] != sex.value:
                    continue
                name = phase["phaseNameUrlSlug"]
                data = (
                    final
                    if name == "final"
                    else _page(client, f"{base}/{sex.value}/{slug}/{name}/result")
                )
                round_data = (data or {}).get("eventPhasesByDiscipline")
                if round_data:
                    documents.extend(
                        _round(round_data, discipline, sex, competition.start_date.year)
                    )
    return Listing(
        source=f"World Athletics results pages of competition {found['id']}",
        formats=FORMATS,
        documents=tuple(documents),
    )


def _round(data: dict[str, Any], discipline: str, sex: Sex, year: int) -> list[ListedDocument]:
    """The documents of each race in one round that has a race analysis."""
    round_ = parse.round_name(data["phaseName"])
    units = data.get("units") or []
    documents = data.get("documents") or []
    # the round's results, whether labelled "Official Results" or "Phase Results"
    results = [doc for doc in documents if str(doc["fileName"]).endswith(".RS6.pdf")]
    listed: list[ListedDocument] = []
    for unit in units:
        splits = [
            doc
            for doc in documents
            if doc["typeName"] in SPLIT_DOCUMENTS and doc["unitId"] == unit["unitId"]
        ]
        if not splits:
            continue
        heat = int(unit["unitCode"]) if len(units) > 1 else None
        race = RaceKey(discipline=discipline_id(discipline), sex=sex, round=round_, heat=heat)
        own_results = [doc for doc in results if doc["unitId"] in (unit["unitId"], 0)]
        for doc in [*splits, *own_results[:1]]:
            fmt = document_format(doc["fileName"], year)
            if fmt is not None:
                listed.append(ListedDocument(race=race, format=fmt, url=_url(doc)))
    return listed


def _url(doc: dict[str, Any]) -> str:
    path = str(doc["filePath"]).replace("\\", "/")
    return f"{FILES}{path}{doc['fileName']}"


def _page(client: httpx.Client, url: str) -> dict[str, Any] | None:
    """A results page's data, or ``None`` for an event the competition did not hold."""
    time.sleep(PAUSE_SECONDS)
    response = client.get(url)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    found = PAGE_DATA.search(response.text)
    if found is None:
        raise ValueError(f"{url}: no page data")
    props: dict[str, Any] = json.loads(found[1])["props"]["pageProps"]
    return props if props.get("eventPhasesByDiscipline") else None
