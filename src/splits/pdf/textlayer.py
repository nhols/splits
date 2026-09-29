"""The text layer of a PDF: every word with its position, font and size.

This is the only module that touches PDF internals. Everything downstream (format readers,
provenance spans, the website's source viewer) works on this representation, which is cached
per document hash. If extraction settings change, bump ``EXTRACTOR`` and caches rebuild.
"""

import io
from collections.abc import Sequence
from pathlib import Path

import pdfplumber

from splits.acquire.store import Store
from splits.model.base import Record
from splits.model.provenance import BBox
from splits.model.values import PositiveInt, Sha256

EXTRACTOR = "pdfplumber-words/4"


class Word(Record):
    """A run of characters with no gap and one font, as it appears on the page."""

    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    font: str
    """Font name without the subset prefix, e.g. ``DIN-Bold``."""
    size: float

    @property
    def xc(self) -> float:
        """Horizontal centre."""
        return (self.x0 + self.x1) / 2

    @property
    def yc(self) -> float:
        """Vertical centre."""
        return (self.top + self.bottom) / 2

    @property
    def bbox(self) -> BBox:
        return BBox(x0=self.x0, top=self.top, x1=self.x1, bottom=self.bottom)

    @property
    def bold(self) -> bool:
        return "bold" in self.font.lower()


class Page(Record):
    number: PositiveInt
    width: float
    height: float
    words: tuple[Word, ...]


class TextLayer(Record):
    sha256: Sha256
    extractor: str
    pages: tuple[Page, ...]

    def page(self, number: int) -> Page:
        for page in self.pages:
            if page.number == number:
                return page
        raise KeyError(f"page {number} is not in this text layer")


FRAGMENT_GAP = 0.5
"""Points. Letters set flush against each other in different fonts (a fallback font for one
accented capital, as in ``KOMA`` ``Ń`` ``SKI``) are one word."""


def _join_fragments(words: list[Word]) -> list[Word]:
    joined: list[Word] = []
    for word in words:
        previous = joined[-1] if joined else None
        if (
            previous is not None
            and abs(previous.top - word.top) < 3
            and abs(word.x0 - previous.x1) < FRAGMENT_GAP
            and any(char.isalpha() for char in previous.text)
            and any(char.isalpha() for char in word.text)
        ):
            joined[-1] = Word(
                text=previous.text + word.text,
                x0=previous.x0,
                top=min(previous.top, word.top),
                x1=word.x1,
                bottom=max(previous.bottom, word.bottom),
                font=previous.font,
                size=max(previous.size, word.size),
            )
        else:
            joined.append(word)
    return joined


def extract_text_layer(content: bytes, sha256: str, only: Sequence[int] | None = None) -> TextLayer:
    """Every page's words, or just those of the pages numbered in ``only``."""
    pages: list[Page] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        numbers = list(only) if only is not None else range(1, len(pdf.pages) + 1)
        for number in numbers:
            # Some documents draw bold text twice, a hair apart ("fake bold"): keep one copy of
            # each character, or 1:42.15 reads as 11::4422..1155.
            page = pdf.pages[number - 1].dedupe_chars(tolerance=1)
            words = page.extract_words(
                # Letters of a word sit within about half a point of each other; results
                # documents print adjacent columns (place, bib) as little as 2.3 points apart.
                x_tolerance=1.5,
                keep_blank_chars=False,
                use_text_flow=False,
                extra_attrs=["fontname", "size"],
            )
            pages.append(
                Page(
                    number=number,
                    width=round(float(page.width), 2),
                    height=round(float(page.height), 2),
                    words=tuple(
                        _join_fragments(
                            [
                                Word(
                                    text=word["text"],
                                    x0=round(float(word["x0"]), 2),
                                    top=round(float(word["top"]), 2),
                                    x1=round(float(word["x1"]), 2),
                                    bottom=round(float(word["bottom"]), 2),
                                    font=str(word["fontname"]).split("+", 1)[-1],
                                    size=round(float(word["size"]), 2),
                                )
                                for word in words
                            ]
                        )
                    ),
                )
            )
    return TextLayer(sha256=sha256, extractor=EXTRACTOR, pages=tuple(pages))


def load_text_layer(
    store: Store, cache_dir: Path, sha256: str, only: Sequence[int] | None = None
) -> TextLayer:
    """The text layer of a stored document (or of some of its pages), extracted once and then
    read from the cache."""
    suffix = "" if only is None else "-p" + "-".join(str(n) for n in only)
    cached = cache_dir / "text" / f"{sha256}{suffix}.json"
    if cached.is_file():
        layer = TextLayer.model_validate_json(cached.read_bytes())
        if layer.extractor == EXTRACTOR and layer.sha256 == sha256:
            return layer
    layer = extract_text_layer(store.read(sha256), sha256, only)
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(layer.model_dump_json(), encoding="utf-8")
    return layer
