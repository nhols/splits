"""The text layer of a web page: what its tables' cells print, laid out on a grid.

A web page has no geometry of its own, so its text layer lays out its text the way its tables
would print it: each table row is a line, ``ROW`` points below the one before, and each of its
cells a column ``COLUMN`` points wide, its words left to right (narrowed to fit, in a cell too
long for its column); text outside tables (a title, the meeting's dates) is a line of its own,
in the first column. A word's box therefore says which row and which cell it was read from
(the column is ``x0 // COLUMN``), and readers read a web page's tables with the same toolkit as
a PDF's. Header cells are in the font ``th``, other cells in ``td``, and text outside tables
in ``text``.

Pages from timing companies are often malformed (rows without their opening ``<tr>``, a cell
opened inside another): a cell ends where the next begins, and a cell outside a row starts one.
"""

from html.parser import HTMLParser

from splits.pdf.textlayer import Page, TextLayer, Word

EXTRACTOR = "html-cells/1"
ROW = 20.0
COLUMN = 200.0
CHARACTER = 4.0
HEIGHT = 10.0
CELLS = frozenset({"td", "th"})
BLOCKS = frozenset({"br", "p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "center"})
HIDDEN = frozenset({"script", "style", "title", "head"})


class _Lines(HTMLParser):
    """The page's lines in reading order, each a list of cells: (column, tag, text)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[list[tuple[int, str, str]]] = []
        self.tables = 0
        self.row: list[tuple[int, str, str]] | None = None
        self.cell: tuple[str, list[str]] | None = None
        self.text: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in HIDDEN:
            self.hidden += 1
        elif tag == "table":
            self._end_text()
            self._end_row()
            self.tables += 1
        elif tag == "tr" and self.tables:
            self._end_row()
            self.row = []
        elif tag in CELLS and self.tables:
            self._end_cell()
            if self.row is None:
                self.row = []
            self.cell = (tag, [])
        elif tag in BLOCKS and not self.tables:
            self._end_text()

    def handle_endtag(self, tag: str) -> None:
        if tag in HIDDEN:
            self.hidden = max(self.hidden - 1, 0)
        elif tag in CELLS:
            self._end_cell()
        elif tag == "tr":
            self._end_row()
        elif tag == "table" and self.tables:
            self._end_row()
            self.tables -= 1
        elif tag in BLOCKS and not self.tables:
            self._end_text()

    def handle_data(self, data: str) -> None:
        if self.hidden:
            return
        if self.cell is not None:
            self.cell[1].append(data)
        elif not self.tables:
            self.text.append(data)

    def close(self) -> None:
        super().close()
        self._end_row()
        self._end_text()

    def _end_cell(self) -> None:
        if self.cell is None:
            return
        tag, parts = self.cell
        if self.row is None:
            self.row = []
        self.row.append((len(self.row), tag, " ".join("".join(parts).split())))
        self.cell = None

    def _end_row(self) -> None:
        self._end_cell()
        if self.row and any(text for _, _, text in self.row):
            self.lines.append(self.row)
        self.row = None

    def _end_text(self) -> None:
        text = " ".join("".join(self.text).split())
        if text:
            self.lines.append([(0, "text", text)])
        self.text = []


def extract_page_layer(content: bytes, sha256: str) -> TextLayer:
    """The text layer of a web page, as one page."""
    parser = _Lines()
    parser.feed(content.decode("utf-8", errors="replace"))
    parser.close()
    words: list[Word] = []
    columns = 1
    for index, line in enumerate(parser.lines):
        top = ROW * (index + 1)
        for column, tag, text in line:
            columns = max(columns, column + 1)
            x = column * COLUMN + CHARACTER
            character = min(CHARACTER, (COLUMN - 2 * CHARACTER) / max(len(text), 1))
            for token in text.split():
                width = len(token) * character
                words.append(
                    Word(
                        text=token,
                        x0=x,
                        top=top,
                        x1=x + width,
                        bottom=top + HEIGHT,
                        font=tag,
                        size=HEIGHT,
                    )
                )
                x += width + character
    page = Page(
        number=1,
        width=columns * COLUMN,
        height=ROW * (len(parser.lines) + 2),
        words=tuple(words),
    )
    return TextLayer(sha256=sha256, extractor=EXTRACTOR, pages=(page,))
