import re

import pytest

from splits.formats.common import read_tail, time_tokens
from splits.model import Span
from splits.model.ids import DocumentId
from splits.pdf.layout import DocumentView, Line
from splits.pdf.textlayer import TextLayer, Word


def _line(text: str) -> Line:
    words, x = [], 40.0
    for token in text.split():
        words.append(
            Word(text=token, x0=x, top=100, x1=x + 5 * len(token), bottom=108, font="Arial", size=8)
        )
        x += 5 * len(token) + 20
    return Line(page=1, words=tuple(words))


@pytest.mark.parametrize(
    ("text", "pairs"),
    [
        ("1:01.80 (2) 1:57.82 (2)", [("1:01.80", "(2)"), ("1:57.82", "(2)")]),
        ("56.02 56.05 39.74", [("56.02", None), ("56.05", None), ("39.74", None)]),
        # a time the timing did not record, and a status where the finish would be
        ("13:48.53 (5) NO VALUE 14:15.12 (6)", [("13:48.53", "(5)"), ("14:15.12", "(6)")]),
        ("24:15.40 (21) DNF (22)", [("24:15.40", "(21)")]),
        ("(12) 2:45.10 (11)", [("2:45.10", "(11)")]),  # a rank printed without its time
        ("Heat 1 7 0.0", []),
        ("1:01.80 (2) PB", []),
    ],
)
def test_split_lines_hold_times_and_ranks_only(
    text: str, pairs: list[tuple[str, str | None]]
) -> None:
    found = time_tokens(_line(text))
    assert [(time.text, rank.text if rank else None) for time, rank in found] == pairs


@pytest.mark.parametrize(
    ("tail", "remarks"),
    [
        ("TR 16.8", ["TR 16.8"]),
        ("TR17.3.1 YC", ["TR17.3.1", "YC"]),
        ("R 163.3a", ["R 163.3a"]),
        ("Rule 10.1", ["Rule 10.1"]),
        ("TR* L", ["TR*", "L"]),
    ],
)
def test_a_rule_printed_in_two_words_is_one_remark(tail: str, remarks: list[str]) -> None:
    view = DocumentView(
        DocumentId("x/400m-men/final/oris"), TextLayer(sha256="0" * 64, extractor="test", pages=())
    )
    row = view.match(
        _line(f"8 SINGHAPURAGE 45.75 {tail}"), re.compile(r"\d+\.\d+ (?P<tail>.+)"), "row"
    )
    assert row is not None
    records, qualification, read = read_tail(view, row)
    assert (records, qualification) == ((), None)
    assert [remark.value for remark in read] == remarks
    for remark, printed in zip(read, remarks, strict=True):
        assert isinstance(remark.source, Span) and remark.source.text == printed
