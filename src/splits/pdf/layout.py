"""A toolkit for reading tabular PDF layouts, with provenance built in.

Format readers work with *lines* of words. Reading a value, whether from a regular-expression
group or from particular words, produces a ``Sourced`` value whose span covers exactly the
words it was read from. Readers never construct provenance by hand, so it cannot be wrong.
"""

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import cached_property, reduce

from splits.model import BBox, DocumentId, Sourced, Span
from splits.pdf.textlayer import Page, TextLayer, Word


class ReadError(ValueError):
    """A document does not look like its declared format expects."""

    def __init__(self, document: DocumentId, message: str, page: int | None = None) -> None:
        where = f"{document}" + (f" (page {page})" if page else "")
        super().__init__(f"{where}: {message}")
        self.document = document
        self.page = page


@dataclass(frozen=True)
class Line:
    """Words that share a baseline, left to right."""

    page: int
    words: tuple[Word, ...]

    @cached_property
    def text(self) -> str:
        return " ".join(word.text for word in self.words)

    @cached_property
    def _starts(self) -> tuple[int, ...]:
        starts, offset = [], 0
        for word in self.words:
            starts.append(offset)
            offset += len(word.text) + 1
        return tuple(starts)

    @property
    def top(self) -> float:
        return min(word.top for word in self.words)

    @property
    def bottom(self) -> float:
        return max(word.bottom for word in self.words)

    @property
    def bbox(self) -> BBox:
        return bbox_of(self.words)

    def words_in(self, start: int, end: int) -> tuple[Word, ...]:
        """The words overlapping characters ``start:end`` of :attr:`text`."""
        return tuple(
            word
            for word, word_start in zip(self.words, self._starts, strict=True)
            if word_start < end and word_start + len(word.text) > start
        )

    def where(self, keep: Callable[[Word], bool]) -> "Line":
        return Line(self.page, tuple(word for word in self.words if keep(word)))


def bbox_of(words: Iterable[Word]) -> BBox:
    boxes = [word.bbox for word in words]
    if not boxes:
        raise ValueError("no words")
    return reduce(BBox.union, boxes)


def group_lines(words: Iterable[Word], page: int, tolerance: float = 2.5) -> list[Line]:
    """Group words into lines: words whose vertical centres are within ``tolerance`` points of
    the line's running centre belong to the same line."""
    lines: list[list[Word]] = []
    centre = 0.0
    for word in sorted(words, key=lambda w: (w.yc, w.x0)):
        if lines and abs(word.yc - centre) <= tolerance:
            lines[-1].append(word)
            centre = sum(w.yc for w in lines[-1]) / len(lines[-1])
        else:
            lines.append([word])
            centre = word.yc
    return [Line(page, tuple(sorted(line, key=lambda w: w.x0))) for line in lines]


@dataclass(frozen=True)
class DocumentView:
    """A document's text layer as a format reader sees it."""

    document: DocumentId
    layer: TextLayer

    @property
    def pages(self) -> tuple[Page, ...]:
        return self.layer.pages

    def lines(
        self, page: int, keep: Callable[[Word], bool] | None = None, tolerance: float = 2.5
    ) -> list[Line]:
        words = [w for w in self.layer.page(page).words if keep is None or keep(w)]
        return group_lines(words, page, tolerance)

    def error(self, message: str, page: int | None = None) -> ReadError:
        return ReadError(self.document, message, page)

    def span(self, page: int, words: Sequence[Word], text: str | None = None) -> Span:
        return Span(
            document=self.document,
            page=page,
            bbox=bbox_of(words),
            text=text if text is not None else " ".join(word.text for word in words),
        )

    def read[T](
        self,
        page: int,
        words: Sequence[Word],
        parse: Callable[[str], T],
        method: str,
        text: str | None = None,
    ) -> Sourced[T]:
        """Parse the text of ``words`` into a sourced value."""
        raw = text if text is not None else " ".join(word.text for word in words)
        try:
            value = parse(raw)
        except ValueError as error:
            raise self.error(f"{method}: cannot read {raw!r}: {error}", page) from error
        return Sourced[T](value=value, source=self.span(page, words, raw), method=method)

    def match(
        self, line: Line, pattern: re.Pattern[str], rule: str, *, full: bool = False
    ) -> "LineMatch | None":
        found = pattern.fullmatch(line.text) if full else pattern.search(line.text)
        return LineMatch(self, line, found, rule) if found else None

    def find(
        self, lines: Iterable[Line], pattern: re.Pattern[str], rule: str
    ) -> "LineMatch | None":
        """The first of ``lines`` that ``pattern`` matches."""
        for line in lines:
            found = self.match(line, pattern, rule)
            if found:
                return found
        return None


@dataclass(frozen=True)
class LineMatch:
    """A regular-expression match on a line; its groups read out as sourced values."""

    view: DocumentView
    line: Line
    found: re.Match[str]
    rule: str

    def __getitem__(self, group: str) -> str | None:
        return self.found[group]

    def words(self, group: str | int = 0) -> tuple[Word, ...]:
        start, end = self.found.span(group)
        return self.line.words_in(start, end)

    def span(self, group: str | int = 0) -> Span:
        return self.view.span(self.line.page, self.words(group), self.found[group])

    def read[T](self, group: str, parse: Callable[[str], T]) -> Sourced[T]:
        text = self.found[group]
        if text is None:
            raise self.view.error(
                f"{self.rule}: no {group!r} in {self.line.text!r}", self.line.page
            )
        return self.view.read(
            self.line.page, self.words(group), parse, f"{self.rule}.{group}", text
        )

    def read_opt[T](self, group: str, parse: Callable[[str], T]) -> Sourced[T] | None:
        return None if self.found[group] is None else self.read(group, parse)


@dataclass(frozen=True)
class Columns[K]:
    """Column anchors: horizontal positions that values are assigned to by proximity."""

    anchors: tuple[tuple[K, float], ...]
    tolerance: float
    """How far (in points) a value's centre may be from its column's anchor."""

    def assign(self, word: Word) -> K | None:
        """The column nearest ``word``, or ``None`` if no anchor is within tolerance."""
        key, x = min(self.anchors, key=lambda anchor: abs(anchor[1] - word.xc))
        return key if abs(x - word.xc) <= self.tolerance else None
