from decimal import Decimal

import pytest

from splits.formats import ReadContext
from splits.formats.omega_grid import TieredGrid
from splits.model import Catalog, DocumentSpec, RaceKey
from splits.model.ids import DocumentId, competition_id, format_id
from splits.model.provenance import CatalogRef
from splits.pdf.layout import DocumentView, Line, ReadError
from splits.pdf.textlayer import TextLayer, Word


def _line(*tokens: tuple[str, float], top: float = 236.0) -> Line:
    words = tuple(
        Word(text=text, x0=x, top=top, x1=x + 4 * len(text), bottom=top + 8, font="DIN", size=8)
        for text, x in tokens
    )
    return Line(page=1, words=words)


def _labels(text: str, start: float = 80.0, pitch: float = 50.0) -> Line:
    """A line of labels such as ``3 laps to go``, each label starting ``pitch`` points after
    the one before."""
    tokens, x = [], start
    for label in text.split(" | "):
        for offset, word in enumerate(label.split()):
            tokens.append((word, x + 12 * offset))
        x += pitch
    return _line(*tokens)


def _context(catalog: Catalog, race: str) -> ReadContext:
    competition = catalog.competitions[competition_id("dl-2021-zurich")]
    key = RaceKey.parse(race)
    spec = DocumentSpec(
        id=DocumentId(f"{competition.id}/{key}/omega-race-analysis"),
        competition=competition.id,
        race=key,
        format=format_id("omega-race-analysis"),
        url="https://example.org/analysis.pdf",
        declared=CatalogRef(file="catalog/x.yaml", line=1, pointer="/documents/0"),
    )
    return ReadContext(
        spec=spec, discipline=catalog.disciplines[key.discipline], competition=competition
    )


VIEW = DocumentView(
    DocumentId("x/mile-women/final/omega-race-analysis"),
    TextLayer(sha256="0" * 64, extractor="test", pages=()),
)


def test_laps_to_go_are_laps_of_the_track_before_the_finish(catalog: Catalog) -> None:
    labels = _labels("3.75 laps to go | 3 laps to go | 1 lap to go | 1/4 lap to go")
    grid = TieredGrid.find(
        VIEW, [labels], _context(catalog, "mile-women/final"), unlabelled_finish_after=10
    )
    assert grid is not None
    distances = [point.distance for point in grid.order]
    assert distances == [
        Decimal("109.344"),
        Decimal("409.344"),
        Decimal("1209.344"),
        Decimal("1509.344"),
        Decimal("1609.344"),  # the unlabelled finish
    ]


def test_a_steeplechase_timed_at_laps_to_go_is_not_placed(catalog: Catalog) -> None:
    labels = _labels("7 laps to go | 6 laps to go | 5 laps to go")
    with pytest.raises(ReadError, match="steeplechase lap"):
        TieredGrid.find(
            VIEW, [labels], _context(catalog, "3000msc-men/final"), unlabelled_finish_after=10
        )


def test_a_grid_of_one_label_takes_the_values_beneath_it(catalog: Catalog) -> None:
    grid = TieredGrid.find(
        VIEW, [_line(("400m", 166.0))], _context(catalog, "800m-women/final"),
        unlabelled_finish_after=10,
    )  # fmt: skip
    assert grid is not None
    assert [point.label for point in grid.order] == ["400m"]
    band = [_line(("56.4", 179.0), ("(2)", 223.0), top=252.0)]
    splits, segments = grid.read(VIEW, band)
    assert [(split.point.label, split.time.value) for split in splits] == [
        ("400m", Decimal("56.4"))
    ]
    assert segments == ()
