"""Closed vocabularies and constrained scalar types shared by the whole model."""

import re
from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import Field

Seconds = Annotated[Decimal, Field(ge=0, max_digits=9, decimal_places=3)]
"""A duration in seconds. ``Decimal`` keeps the printed precision: ``Decimal("44.20")``."""

Metres = Annotated[Decimal, Field(ge=0, max_digits=8, decimal_places=3)]
"""A distance along the race in metres, e.g. ``Decimal("13.72")`` for the first 110mH hurdle."""

CountryCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
"""A three-letter country code as printed in results (World Athletics / IOC codes)."""

Url = Annotated[str, Field(pattern=r"^https?://\S+$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonEmptyStr = Annotated[str, Field(min_length=1)]
PositiveInt = Annotated[int, Field(ge=1)]


class Sex(StrEnum):
    MEN = "men"
    WOMEN = "women"
    MIXED = "mixed"


class Setting(StrEnum):
    """Where a race is run. ``indoor`` means a 200 m short track."""

    OUTDOOR = "outdoor"
    INDOOR = "indoor"
    ROAD = "road"


class Round(StrEnum):
    """The stage of a competition that a race belongs to.

    First-round races are ``heat`` whatever the programme calls them ("Heats", "Round 1").
    One-day meetings such as the Diamond League run each event as a single ``final``.
    """

    PRELIMINARY = "preliminary"
    HEAT = "heat"
    REPECHAGE = "repechage"
    QUARTER_FINAL = "quarter-final"
    SEMI_FINAL = "semi-final"
    FINAL = "final"


class Status(StrEnum):
    """How a performance ended."""

    FINISHED = "finished"
    DID_NOT_FINISH = "dnf"
    DID_NOT_START = "dns"
    DISQUALIFIED = "dq"


class Qualification(StrEnum):
    """Advancement to the next round: ``Q`` by place, ``q`` as a fastest loser."""

    BY_PLACE = "Q"
    BY_TIME = "q"


class PointKind(StrEnum):
    """What a timing point along the race is anchored to."""

    START = "start"
    DISTANCE = "distance"  # a line at a fixed distance, e.g. 100 m
    HURDLE = "hurdle"  # a barrier, e.g. hurdle 3 of the 400 m hurdles (115 m)
    TOUCHDOWN = "touchdown"  # the first foot down after a barrier, as video analyses time it
    FINISH = "finish"


class DisciplineKind(StrEnum):
    FLAT = "flat"
    HURDLES = "hurdles"
    STEEPLECHASE = "steeplechase"
    RELAY = "relay"
    ROAD = "road"
    RACE_WALK = "race-walk"


class SeriesKind(StrEnum):
    GAMES = "games"  # multi-sport games, e.g. the Olympic Games
    CHAMPIONSHIPS = "championships"  # global, area or national championships
    MEETING = "meeting"  # one-day meetings, e.g. the Diamond League


class Severity(StrEnum):
    """How bad a data-quality finding is."""

    ERROR = "error"  # values contradict each other: at least one of them is wrong
    WARNING = "warning"  # a value is implausible and probably wrong
    INFO = "info"  # notable, not a problem


RECORD_TAGS: dict[str, str] = {
    "PB": "Personal best",
    "SB": "Season best",
    "NR": "National record",
    "AR": "Area record",
    "WR": "World record",
    "OR": "Olympic record",
    "CR": "Championship record",
    "WL": "World lead",
    "MR": "Meeting record",
    "DLR": "Diamond League record",
    "WBP": "World best performance",
    "NU20R": "National U20 record",
    "WU20R": "World U20 record",
    "AU20R": "Area U20 record",
}
"""Record annotations printed next to results. A leading ``=`` means the record was equalled."""

RecordTag = Annotated[str, Field(pattern=rf"^=?(?:{'|'.join(RECORD_TAGS)})$")]


def annotation_key(printed: str) -> str:
    """The form a mark printed beside a result is explained under: a rule however printed
    (``TR 16.8``, ``TR № 17.3.1``, ``TR17.1.2(J)``, ``R 163.2``) as ``TR16.8``, ``TR17.3.1``,
    ``TR17.1.2[J]``, ``163.2``; anything else as printed."""
    key = printed.replace("№", "").replace(" ", "")
    key = re.sub(r"\(([A-Z])\)$", r"[\1]", key)  # TR17.1.2(J): the decision of the Jury
    return re.sub(r"^R(?=\d{3})", "", key)  # R 163.2: an IAAF rule, numbered before 2020


def annotation_meaning(printed: str, meanings: Mapping[str, str]) -> str | None:
    """What a printed mark means: a record tag's (``=PB``: personal best, equalled), or the one
    ``meanings`` gives under its :func:`annotation_key`."""
    tag = printed.removeprefix("=")
    if tag in RECORD_TAGS:
        return f"{RECORD_TAGS[tag]}, equalled" if printed.startswith("=") else RECORD_TAGS[tag]
    return meanings.get(annotation_key(printed))
