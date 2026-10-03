"""Athlete numbers: the permanent number in each athlete's address on the website.

An athlete's address is ``/athletes/<number>-<name>`` (``/athletes/1234-georgia-hunter-bell``).
The website finds the athlete by the number alone, so the address keeps working when the
athlete's name changes. ``catalog/athlete-numbers.json`` records whom each number was given to:
their World Athletics ID, which does not change, and their athlete ID.

Each build finds every recorded number's athlete, by World Athletics ID or else by athlete ID
(their own or one of their aliases, the IDs of other names their documents print). A number
whose athlete cannot be found stops the build, as its address would stop working. Two numbers
finding one athlete (two athletes found to be one person) both stay theirs: the lower is the
athlete's, the other redirects to it. Athletes without a number are numbered after the highest
one, in the order of their first race. ``splits build`` writes the file back, so it only grows.
It is machine-written and committed, like the lock files.
"""

from pathlib import Path

from pydantic import Field

from splits.model import NumberHolder
from splits.model.base import Record
from splits.model.values import PositiveInt

NUMBERS_FILE = "athlete-numbers.json"


class Numbers(Record):
    numbers: dict[PositiveInt, NumberHolder] = Field(default_factory=dict)


def read_numbers(catalog_root: Path) -> dict[int, NumberHolder]:
    path = catalog_root / NUMBERS_FILE
    if not path.exists():
        return {}
    return dict(Numbers.model_validate_json(path.read_text(encoding="utf-8")).numbers)


def write_numbers(catalog_root: Path, numbers: dict[int, NumberHolder]) -> None:
    ordered = Numbers(numbers=dict(sorted(numbers.items())))
    text = ordered.model_dump_json(indent=1, exclude_none=True) + "\n"
    (catalog_root / NUMBERS_FILE).write_text(text, encoding="utf-8")
