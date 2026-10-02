from pathlib import Path

import pytest

from splits.acquire.store import Store, media_type_of
from splits.pdf.layout import group_lines
from splits.pdf.textlayer import extract_text_layer
from splits.pdf.webpage import COLUMN

# As timing companies write them: a row without its <tr>, a cell opened inside another, and a
# script whose text looks like cells.
PAGE = b"""<!DOCTYPE html>
<html><head><title>Results</title><script>var row = "<td>not a cell</td>";</script></head>
<body><h1>Prefontaine Classic</h1><p>Historic Hayward Field | May 25-26, 2018</p>
<table>
<tr><th>Pl</th><th>Athlete</th><th>Time</th></tr>
<td>1</td><td>Natoya GOULE</td><td>2:00.84</td></tr>
<tr><td>2<td>Stephanie BROWN</td><td>2:01.84</td></tr>
<tr><td></td><td>A name far too long for its column, as a cell may be on a page like this</td>
<td>DNF</td></tr>
</table></body></html>"""


def _rows(content: bytes) -> list[list[tuple[int, str, str]]]:
    """Each line's cells: (column, font, text)."""
    page = extract_text_layer(content, "0" * 64).pages[0]
    rows = []
    for line in group_lines(page.words, 1):
        cells: dict[int, list[str]] = {}
        fonts: dict[int, str] = {}
        for word in line.words:
            column = int(word.x0 // COLUMN)
            assert word.x1 <= (column + 1) * COLUMN, f"{word.text} runs out of its column"
            cells.setdefault(column, []).append(word.text)
            fonts[column] = word.font
        rows.append([(column, fonts[column], " ".join(words)) for column, words in cells.items()])
    return rows


def test_a_web_page_is_read_as_a_grid_of_its_table_cells() -> None:
    assert _rows(PAGE) == [
        [(0, "text", "Prefontaine Classic")],
        [(0, "text", "Historic Hayward Field | May 25-26, 2018")],
        [(0, "th", "Pl"), (1, "th", "Athlete"), (2, "th", "Time")],
        [(0, "td", "1"), (1, "td", "Natoya GOULE"), (2, "td", "2:00.84")],
        [(0, "td", "2"), (1, "td", "Stephanie BROWN"), (2, "td", "2:01.84")],
        [
            (1, "td", "A name far too long for its column, as a cell may be on a page like this"),
            (2, "td", "DNF"),
        ],
    ]


def test_a_web_page_has_one_page() -> None:
    with pytest.raises(ValueError, match="one page"):
        extract_text_layer(PAGE, "0" * 64, only=[2])


def test_documents_are_pdfs_or_web_pages(tmp_path: Path) -> None:
    assert media_type_of(b"%PDF-1.7\n") == "application/pdf"
    assert media_type_of(b"\xef\xbb\xbf\r\n<!doctype HTML>") == "text/html"
    assert media_type_of(b"<html><body></body></html>") == "text/html"
    with pytest.raises(ValueError, match="neither a PDF nor a web page"):
        media_type_of(b"GIF89a")
    store = Store(tmp_path)
    digest = store.put(PAGE)
    assert store.path(digest).suffix == ".html"
    assert store.read(digest) == PAGE
