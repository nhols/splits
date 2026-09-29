"""Writing a competition's document entries to its catalog file.

Discovery proposes entries; this module writes them in the catalog's order (by event as in
``disciplines.yaml``, then sex, round and heat, a race analysis before its results), keeping
everything above the ``documents:`` key exactly as it was: the comments, the competition's
fields and its exclusions.
"""

import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path

from splits.formats import FORMATS, DocumentKind
from splits.model import Catalog, DocumentSpec, FormatId, RaceKey, Round, Sex
from splits.model.base import Record
from splits.model.values import PositiveInt, Setting

DOCUMENTS_KEY = re.compile(r"^documents:\s*$", re.MULTILINE)
PLAIN = re.compile(r"^[A-Za-z0-9][^\s#]*$")
"""Values that need no quotes in YAML: no spaces, no comment marks."""


class Entry(Record):
    """One document entry as the catalog file declares it."""

    race: RaceKey
    format: FormatId
    url: str
    archive_url: str | None = None
    pages: tuple[PositiveInt, ...] | None = None
    setting: Setting | None = None

    @classmethod
    def of(cls, doc: DocumentSpec) -> "Entry":
        return cls(
            race=doc.race,
            format=doc.format,
            url=doc.url,
            archive_url=doc.archive_url,
            pages=doc.pages,
            setting=doc.setting,
        )


def write_documents(path: Path, catalog: Catalog, entries: Iterable[Entry]) -> None:
    """Replace the ``documents:`` list at the end of the catalog file at ``path``."""
    text = path.read_text(encoding="utf-8")
    found = DOCUMENTS_KEY.search(text)
    head = text[: found.start()] if found else text.rstrip("\n") + "\n\n"
    path.write_text(head + render(sorted(entries, key=_order(catalog))), encoding="utf-8")


def render(entries: Iterable[Entry]) -> str:
    lines = ["documents:"]
    for entry in entries:
        lines.append(f"  - race: {entry.race}")
        lines.append(f"    format: {entry.format}")
        lines.append(f"    url: {_scalar(entry.url)}")
        if entry.archive_url:
            lines.append(f"    archive_url: {_scalar(entry.archive_url)}")
        if entry.pages:
            lines.append(f"    pages: [{', '.join(str(page) for page in entry.pages)}]")
        if entry.setting:
            lines.append(f"    setting: {entry.setting.value}")
    return "\n".join(lines) + "\n"


def _scalar(value: str) -> str:
    return value if PLAIN.fullmatch(value) and ": " not in value else json.dumps(value)


def _order(catalog: Catalog) -> Callable[[Entry], tuple[int, int, int, int, int, str]]:
    disciplines = list(catalog.disciplines)
    sexes, rounds = list(Sex), list(Round)

    def key(entry: Entry) -> tuple[int, int, int, int, int, str]:
        race = entry.race
        reader = FORMATS.get(entry.format)
        analysis = reader is not None and reader.kind is DocumentKind.ANALYSIS
        return (
            disciplines.index(race.discipline),
            sexes.index(race.sex),
            rounds.index(race.round),
            race.heat or 0,
            0 if analysis else 1,
            entry.format,
        )

    return key
