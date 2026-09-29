"""Discovery: turning a publisher's listing into catalog entries, and auditing the catalog
against it. The listings here are copies of parts of real ones, so no network is needed."""

from typing import Any

from splits.discover import ListedDocument, Listing, compare
from splits.discover.oris_index import copy_names, races
from splits.discover.world_athletics import _round, document_format
from splits.formats.oris import race_key
from splits.model import Catalog, RaceKey, Sex
from splits.model.ids import competition_id, format_id

FILES = "https://media.aws.iaaf.org/competitiondocuments/pdf/7180312"


def _document(kind: str, name: str, unit: int) -> dict[str, Any]:
    return {"typeName": kind, "fileName": name, "filePath": "\\pdf\\7180312\\", "unitId": unit}


def test_a_round_page_lists_each_timed_race_with_the_rounds_results() -> None:
    """A round's page (Glasgow 2024, men's 400 m round 1) lists its races ("units") and their
    documents: the round's, such as its results, under unit 0. Here the results are labelled
    "Phase Results" ("Official Results" elsewhere); their file is what identifies them."""
    data = {
        "phaseName": "Round 1",
        "units": [{"unitId": 51601, "unitCode": "1"}, {"unitId": 51602, "unitCode": "2"}],
        "documents": [
            _document("Official Startlist", "AT-400sh-M-h----.SL2.pdf", 0),
            _document("Phase Results", "AT-400sh-M-h----.RS6.pdf", 0),
            _document("Race Analysis", "AT-400sh-M-h--1--.RS5.pdf", 51601),
            _document("Photofinish", "M_400sh_h_1.jpg", 51601),
            _document("Photofinish", "M_400sh_h_2.jpg", 51602),
        ],
    }
    listed = _round(data, "400m", Sex.MEN, 2024)
    assert [(str(doc.race), doc.format, doc.url) for doc in listed] == [
        ("400m-men/heat-1", "wa-rs5", f"{FILES}/AT-400sh-M-h--1--.RS5.pdf"),
        ("400m-men/heat-1", "wa-results", f"{FILES}/AT-400sh-M-h----.RS6.pdf"),
    ]  # heat 2 has no race analysis, so no splits: it is not listed


def test_a_race_analysis_is_read_by_the_layout_of_its_year() -> None:
    assert document_format("AT-800-M-f--1--.RS5.pdf", 2019) == "wa-rs5"
    assert document_format("AT-800-M-f--1--.RS5.pdf", 2017) == "wa-rs5-2015"
    assert document_format("AT-800-M-f--1--.RS7.pdf", 2013) is None  # no reader
    assert document_format("AT-800-M-f----.RS6.pdf", 2013) == "wa-results"
    assert document_format("M_800_f_1.jpg", 2023) is None


def test_the_tokyo_index_names_its_races_and_world_athletics_copies() -> None:
    base = "https://olympics.com/tokyo-2020/olympic-games/resOG2020-/pdf/OG2020-/ATH/OG2020-_ATH_"
    files = [
        f"{base}C77A_ATHM800M--------------RND1000200--.pdf",
        f"{base}C73H_ATHM800M--------------RND1--------.pdf",
        f"{base}C73A_ATHM800M--------------RND1000200--.pdf",  # the start list
        f"{base}C77A_ATHW10000M------------FNL-000100--.pdf",
        f"{base}C77A_ATHM4X100M------------FNL-000100--.pdf",  # a relay: not ours
    ]
    found = [(file, results, str(race)) for file, results, race in races(files)]
    assert found == [
        (files[0], files[1], "800m-men/heat-2"),
        (files[3], None, "10000m-women/final"),  # its results are not in the index
    ]
    assert copy_names(files[0]) == ("AT-800-M-h--2--.RS7.pdf", "AT-800-M-h----.RS6.pdf")
    assert copy_names(files[3]) == ("AT-10K-W-f--1--.RS7.pdf", "AT-10K-W-f----.RS6.pdf")


def test_a_results_book_page_names_its_race_in_either_dialect() -> None:
    """The first lines of real pages: Tokyo 2020, Rio 2016 (a whole round's results, whose
    sections name the races) and Rome 2024 (a final run in two races)."""
    tokyo = ["Men's 800m", "男子800m / 800 m - hommes", "SAT 31 JUL 2021 Round 1 - Heat 2/6"]
    rio = ["Men's 800m", "800m rasos masculino / 800 m - hommes", "SAT 13 AUG 2016 Semifinals"]
    rome = ["10000m Men", "WED 12 JUN 2024", "Start Time20:12 B-race", "Race Analysis"]
    assert str(race_key(tokyo)) == "800m-men/heat-2"
    assert str(race_key(rio)) == "800m-men/semi-final"
    assert str(race_key(rome)) == "10000m-men/final-2"
    assert race_key(["Men's 4 x 100m Relay", "FRI 6 AUG 2021 Final"]) is None


def test_the_audit_sorts_a_listing_against_the_catalog(catalog: Catalog) -> None:
    competition = catalog.competitions[competition_id("wch-2019-doha")]
    declared = {doc.id: doc for doc in catalog.documents if doc.competition == competition.id}
    analysis = declared["wch-2019-doha/800m-men/final/wa-rs5"]  # type: ignore[index]
    listing = Listing(
        source="part of World Athletics' results pages",
        formats=(format_id("wa-rs5"), format_id("wa-results")),
        documents=(
            ListedDocument(race=analysis.race, format=analysis.format, url=analysis.url),
            ListedDocument(
                race=RaceKey.parse("1500m-men/final"),
                format=format_id("wa-rs5"),
                url="https://media.aws.iaaf.org/competitiondocuments/pdf/6033/moved.RS5.pdf",
            ),
            ListedDocument(
                race=RaceKey.parse("100m-men/heat-5"),
                format=format_id("wa-rs5"),
                url="https://media.aws.iaaf.org/competitiondocuments/pdf/6033/AT-100-M-h--5--.RS5.pdf",
            ),
            ListedDocument(
                race=RaceKey.parse("100m-women/final"),
                format=format_id("wa-rs5"),
                url="https://media.aws.iaaf.org/competitiondocuments/pdf/6033/AT-100-W-f--1--.RS5.pdf",
            ),
        ),
    )
    comparison = compare(listing, catalog, competition)
    assert [str(doc.race) for doc in comparison.missing] == ["100m-women/final"]
    assert [str(doc.race) for doc, _ in comparison.moved] == ["1500m-men/final"]
    assert [str(doc.race) for doc in comparison.excluded] == ["100m-men/heat-5"]
    # declared in a listed format for a listed race, but not listed
    assert comparison.unlisted == (
        "wch-2019-doha/800m-men/final/wa-results",
        "wch-2019-doha/1500m-men/final/wa-results",
    )
    # races the listing does not mention are the catalog's own business
    assert RaceKey.parse("5000m-men/final") in comparison.by_hand
    assert RaceKey.parse("800m-men/final") not in comparison.by_hand
