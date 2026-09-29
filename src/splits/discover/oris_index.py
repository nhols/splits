"""The document index of an Olympic results site (Tokyo 2020).

The Tokyo 2020 results site listed every PDF it published in one index (``zzjp000b.json``,
kept by the Wayback Machine after the Games). A file's name gives its report and its event
unit: ``OG2020-_ATH_C77A_ATHM800M--------------RND1000200--.pdf`` is the race analysis (report
C77A) of the men's 800 m, round 1 ("RND1"), race 2 ("0002"); ``C73G`` reports the results of
a final, ``C73H`` and ``C73B`` those of a whole round.

The files are gone from olympics.com, but World Athletics keeps the Games' documents on its
own server, byte for byte, under its own names: a race analysis as ``AT-800-M-h--2--.RS7.pdf``,
a round's results as ``AT-800-M-h----.RS6.pdf``. Entries declare that copy, and the Wayback
Machine's copy of the original where it kept one.
"""

import gzip
import json
import re
from urllib.parse import urljoin

import httpx

from splits.discover import ListedDocument, Listing
from splits.model import Catalog, Competition, RaceKey, Round, Sex
from splits.model.ids import discipline_id, format_id

EVENTS = {
    "100M": ("100m", "100"),
    "200M": ("200m", "200"),
    "400M": ("400m", "400"),
    "800M": ("800m", "800"),
    "1500M": ("1500m", "1500"),
    "5000M": ("5000m", "5000"),
    "10000M": ("10000m", "10K"),
    "100MHURD": ("100mh", "100H"),
    "110MHURD": ("110mh", "110H"),
    "400MHURD": ("400mh", "400H"),
    "3000MST": ("3000msc", "3KSC"),
}
"""ORIS event codes: our discipline, and World Athletics' code for it in file names."""
PHASES = {
    "PREL": (Round.PRELIMINARY, "pr"),
    "RND1": (Round.HEAT, "h"),
    "SFNL": (Round.SEMI_FINAL, "sf"),
    "FNL-": (Round.FINAL, "f"),
}
FILE = re.compile(
    r"_ATH_(?P<report>C7[37][A-Z]\d?)_ATH(?P<sex>[MW])(?P<event>[0-9A-Z]+?)-+"
    r"(?P<phase>[A-Z0-9-]{4})(?P<unit>\d{4}00|-{6})--\.pdf$"
)
ARCHIVE_INDEX = "https://web.archive.org/cdx/search/cdx"
WORLD_ATHLETICS = "https://media.aws.iaaf.org/competitiondocuments/pdf/{id}/"
WORLD_ATHLETICS_ID = {"og-2020-tokyo": 7132391}
"""World Athletics' numbers for the Games whose documents it keeps."""
FORMATS = (format_id("oris-c77a"), format_id("oris-c73b1"))
ROUND_RESULTS = ("C73G", "C73H", "C73B")


def handles(url: str) -> bool:
    return url.endswith("/zzjp000b.json")


def listing(competition: Competition, catalog: Catalog, client: httpx.Client) -> Listing:
    url = competition.listing_url
    if url is None or competition.id not in WORLD_ATHLETICS_ID:
        raise ValueError(f"{competition.id}: no results-site index to read")
    response = client.get(url)
    response.raise_for_status()
    content = response.content
    data = json.loads(gzip.decompress(content) if content[:2] == b"\x1f\x8b" else content)
    base = url.split("id_/", 1)[-1]  # the original address, if the index is a snapshot
    files = [urljoin(base, entry["pdfLink"]) for entry in data["pdfsJSON"]]
    snapshots = _snapshots(client, files)
    copies = WORLD_ATHLETICS.format(id=WORLD_ATHLETICS_ID[competition.id])

    documents: list[ListedDocument] = []
    for analysis, results, race in races(files):
        if race.discipline not in catalog.disciplines:
            continue
        analysis_copy, results_copy = copy_names(analysis)
        documents.append(
            ListedDocument(
                race=race,
                format=FORMATS[0],
                url=copies + analysis_copy,
                archive_url=snapshots.get(analysis),
            )
        )
        if results is not None:
            documents.append(
                ListedDocument(
                    race=race,
                    format=FORMATS[1],
                    url=copies + results_copy,
                    archive_url=snapshots.get(results),
                )
            )
    return Listing(
        source=f"the results site's document index {base}",
        formats=FORMATS,
        documents=tuple(documents),
    )


def races(files: list[str]) -> list[tuple[str, str | None, RaceKey]]:
    """Each race analysis in the index of ``files``: the file, its round's results (if the
    index has them) and the race."""
    parsed = [(file, found) for file in files if (found := FILE.search(file))]
    found_races: list[tuple[str, str | None, RaceKey]] = []
    for file, found in parsed:
        wanted = found["event"] in EVENTS and found["phase"] in PHASES
        if found["report"] != "C77A" or not wanted:
            continue
        round_ = PHASES[found["phase"]][0]
        race = RaceKey(
            discipline=discipline_id(EVENTS[found["event"]][0]),
            sex=Sex.MEN if found["sex"] == "M" else Sex.WOMEN,
            round=round_,
            heat=int(found["unit"][:4]) if round_ is not Round.FINAL else None,
        )
        results = next(
            (
                other
                for other, match in parsed
                if match["report"] in ROUND_RESULTS
                and (match["sex"], match["event"], match["phase"])
                == (found["sex"], found["event"], found["phase"])
            ),
            None,
        )
        found_races.append((file, results, race))
    return found_races


def copy_names(analysis: str) -> tuple[str, str]:
    """World Athletics' names for its copies of a race analysis and of its round's results:
    ``…_C77A_ATHM800M--------------RND1000200--.pdf`` is ``AT-800-M-h--2--.RS7.pdf``, with the
    round's results in ``AT-800-M-h----.RS6.pdf``."""
    found = FILE.search(analysis)
    if found is None:
        raise ValueError(f"not a report of the results system: {analysis}")
    code = EVENTS[found["event"]][1]
    phase = PHASES[found["phase"]][1]
    name = f"AT-{code}-{found['sex']}-{phase}"
    return f"{name}--{found['unit'][:4].lstrip('0')}--.RS7.pdf", f"{name}----.RS6.pdf"


def _snapshots(client: httpx.Client, files: list[str]) -> dict[str, str]:
    """The Wayback Machine's copy of each file it kept (the latest), by original address."""
    prefix = files[0].rsplit("/", 1)[0] + "/" if files else ""
    response = client.get(
        ARCHIVE_INDEX,
        params={
            "url": prefix,
            "matchType": "prefix",
            "filter": "statuscode:200",
            "fl": "original,timestamp",
            "output": "json",
        },
    )
    response.raise_for_status()
    rows = response.json()[1:] if response.text.strip() else []
    latest: dict[str, str] = {}
    for original, timestamp in rows:
        address = original.replace("http://", "https://", 1)
        if address in files and timestamp > latest.get(address, ""):
            latest[address] = timestamp
    return {
        address: f"https://web.archive.org/web/{timestamp}id_/{address}"
        for address, timestamp in latest.items()
    }
