"""Identifiers.

Every entity has a readable identifier built deterministically from its natural key, so IDs
are stable across rebuilds and meaningful in URLs, SQL and diffs:

    competition   wch-2023-budapest
    race          wch-2023-budapest/400m-men/semi-final-2
    document      wch-2023-budapest/400m-men/semi-final-2/wa-rs5
    athlete       karsten-warholm
    performance   wch-2023-budapest/400m-men/final/antonio-watson

Each kind of ID is its own type, so mypy rejects a document ID where a race ID is expected.
Build IDs with the functions in this module rather than by formatting strings by hand.
"""

import re
import unicodedata
from typing import Annotated, NewType, Self

from pydantic import Field

from splits.model.base import Record
from splits.model.values import PositiveInt, Round, Sex

SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_SLUG_RE = re.compile(f"^{SLUG}$")


def _path_pattern(parts: int) -> str:
    return "^" + "/".join([SLUG] * parts) + "$"


_CompetitionId = NewType("_CompetitionId", str)
_SeriesId = NewType("_SeriesId", str)
_DisciplineId = NewType("_DisciplineId", str)
_FormatId = NewType("_FormatId", str)
_AthleteId = NewType("_AthleteId", str)
_CheckId = NewType("_CheckId", str)
_RaceId = NewType("_RaceId", str)
_DocumentId = NewType("_DocumentId", str)
_PerformanceId = NewType("_PerformanceId", str)

CompetitionId = Annotated[_CompetitionId, Field(pattern=_path_pattern(1))]
SeriesId = Annotated[_SeriesId, Field(pattern=_path_pattern(1))]
DisciplineId = Annotated[_DisciplineId, Field(pattern=_path_pattern(1))]
FormatId = Annotated[_FormatId, Field(pattern=_path_pattern(1))]
AthleteId = Annotated[_AthleteId, Field(pattern=_path_pattern(1))]
CheckId = Annotated[_CheckId, Field(pattern=_path_pattern(1))]
RaceId = Annotated[_RaceId, Field(pattern=_path_pattern(3))]
DocumentId = Annotated[_DocumentId, Field(pattern=_path_pattern(4))]
PerformanceId = Annotated[_PerformanceId, Field(pattern=_path_pattern(4))]


_UNDECOMPOSABLE = str.maketrans(
    {
        "Ł": "L",
        "ł": "l",
        "Ø": "O",
        "ø": "o",
        "Đ": "D",
        "đ": "d",
        "Ð": "D",
        "ð": "d",
        "Þ": "Th",
        "þ": "th",
        "Æ": "Ae",
        "æ": "ae",
        "Œ": "Oe",
        "œ": "oe",
        "ß": "ss",
        "ı": "i",
        "Ħ": "H",
        "ħ": "h",
    }
)


def ascii_fold(text: str) -> str:
    """Latin text without diacritics: ``"KOTWIŁA"`` -> ``"KOTWILA"``, ``"MÄGI"`` -> ``"MAGI"``.
    Other scripts are dropped."""
    decomposed = unicodedata.normalize("NFKD", text.translate(_UNDECOMPOSABLE))
    return decomposed.encode("ascii", "ignore").decode("ascii")


def slugify(text: str) -> str:
    """Lower-case ASCII slug: ``"Håvard Bentdal INGVALDSEN"`` -> ``"havard-bentdal-ingvaldsen"``."""
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_fold(text).lower()).strip("-")
    if not slug:
        raise ValueError(f"cannot build a slug from {text!r}")
    return slug


def _require_slug(value: str, kind: str) -> str:
    if not _SLUG_RE.fullmatch(value):
        raise ValueError(f"invalid {kind} {value!r}: expected a lower-case slug like 'abc-123'")
    return value


def competition_id(value: str) -> CompetitionId:
    return _CompetitionId(_require_slug(value, "competition id"))


def series_id(value: str) -> SeriesId:
    return _SeriesId(_require_slug(value, "series id"))


def discipline_id(value: str) -> DisciplineId:
    return _DisciplineId(_require_slug(value, "discipline id"))


def format_id(value: str) -> FormatId:
    return _FormatId(_require_slug(value, "format id"))


def athlete_id(value: str) -> AthleteId:
    return _AthleteId(_require_slug(value, "athlete id"))


def check_id(value: str) -> CheckId:
    return _CheckId(_require_slug(value, "check id"))


_STAGE_RE = re.compile(
    r"^(?P<round>" + "|".join(re.escape(r.value) for r in Round) + r")(?:-(?P<heat>[1-9]\d*))?$"
)


class RaceKey(Record):
    """Identifies a race within a competition: the event, the round, and the heat.

    ``heat`` is ``None`` when the round is a single race (a final, a one-day-meeting race).
    The string form is ``{discipline}-{sex}/{round}[-{heat}]``, e.g. ``400mh-women/semi-final-2``.
    """

    discipline: DisciplineId
    sex: Sex
    round: Round
    heat: PositiveInt | None = None

    @property
    def event(self) -> str:
        """``400mh-women``: the discipline contested by one sex."""
        return f"{self.discipline}-{self.sex.value}"

    @property
    def stage(self) -> str:
        """``semi-final-2``, or ``final`` for a single-race round."""
        if self.heat is None:
            return self.round.value
        return f"{self.round.value}-{self.heat}"

    def __str__(self) -> str:
        return f"{self.event}/{self.stage}"

    @classmethod
    def parse(cls, text: str) -> Self:
        """Parse the string form, e.g. ``"400m-men/heat-3"``."""
        event, sep, stage = text.partition("/")
        discipline, dash, sex = event.rpartition("-")
        match = _STAGE_RE.fullmatch(stage)
        if not (sep and dash and match) or sex not in Sex:
            raise ValueError(
                f"invalid race key {text!r}: expected '<discipline>-<sex>/<round>[-<heat>]', "
                "e.g. '400m-men/semi-final-2' or '200m-women/final'"
            )
        heat = match["heat"]
        return cls(
            discipline=discipline_id(discipline),
            sex=Sex(sex),
            round=Round(match["round"]),
            heat=int(heat) if heat else None,
        )


def race_id(competition: CompetitionId, key: RaceKey) -> RaceId:
    return _RaceId(f"{competition}/{key}")


def document_id(race: RaceId, fmt: FormatId) -> DocumentId:
    return _DocumentId(f"{race}/{fmt}")


def performance_id(race: RaceId, athlete: AthleteId) -> PerformanceId:
    return _PerformanceId(f"{race}/{athlete}")


def competition_of(race: RaceId) -> CompetitionId:
    return _CompetitionId(race.split("/", 1)[0])


def race_of(record: DocumentId | PerformanceId) -> RaceId:
    """The race a document or performance belongs to (both are ``{race}/{leaf}``)."""
    return _RaceId(record.rsplit("/", 1)[0])
