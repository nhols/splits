"""Reference data: what is raced (disciplines), where along a race times are taken (timing
points), and the competition series races belong to.

Disciplines and series are declared in ``catalog/disciplines.yaml`` and ``catalog/series.yaml``.
"""

from decimal import Decimal
from typing import Self

from pydantic import Field, model_validator

from splits.model.base import Record
from splits.model.ids import DisciplineId, SeriesId
from splits.model.provenance import CatalogRef
from splits.model.values import (
    DisciplineKind,
    Metres,
    NonEmptyStr,
    PointKind,
    PositiveInt,
    SeriesKind,
    Sex,
)


def format_metres(distance: Decimal) -> str:
    """``Decimal("100.000")`` -> ``"100"``, ``Decimal("13.720")`` -> ``"13.72"``."""
    text = format(distance.normalize(), "f")
    return text


class TimingPoint(Record):
    """A place along the race where times are taken.

    Points are compared by ``(distance, kind)``: a hurdle at 45 m and a 45 m line are different
    points even though they are the same distance from the start.
    """

    kind: PointKind
    distance: Metres
    hurdle: PositiveInt | None = None
    """For ``hurdle`` points: which barrier, counting from 1."""

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if (self.kind is PointKind.HURDLE) != (self.hurdle is not None):
            raise ValueError("a hurdle number is required for, and only for, hurdle points")
        if self.kind is PointKind.START and self.distance != 0:
            raise ValueError("the start is at 0 m")
        if self.kind is not PointKind.START and self.distance == 0:
            raise ValueError("only the start is at 0 m")
        return self

    @classmethod
    def start(cls) -> Self:
        return cls(kind=PointKind.START, distance=Decimal(0))

    @classmethod
    def at(cls, distance: Decimal) -> Self:
        return cls(kind=PointKind.DISTANCE, distance=distance)

    @classmethod
    def at_hurdle(cls, number: int, distance: Decimal) -> Self:
        return cls(kind=PointKind.HURDLE, distance=distance, hurdle=number)

    @classmethod
    def finish(cls, distance: Decimal) -> Self:
        return cls(kind=PointKind.FINISH, distance=distance)

    @property
    def label(self) -> str:
        """Human label: ``Start``, ``100m``, ``H3``, ``Finish``."""
        match self.kind:
            case PointKind.START:
                return "Start"
            case PointKind.FINISH:
                return "Finish"
            case PointKind.HURDLE:
                return f"H{self.hurdle}"
            case PointKind.DISTANCE:
                return f"{format_metres(self.distance)}m"

    @property
    def slug(self) -> str:
        """Identifier-safe label: ``start``, ``100m``, ``h3``, ``finish``, ``13-72m``."""
        return self.label.lower().replace(".", "-")

    @property
    def order(self) -> tuple[Decimal, int]:
        """Sort key: by distance; at equal distance a line comes before a barrier."""
        return (self.distance, list(PointKind).index(self.kind))


class BarrierLayout(Record):
    """Where the barriers of a hurdles race stand, under the rules for one sex."""

    count: PositiveInt
    first: Metres
    """Distance from the start line to the first barrier."""
    spacing: Metres
    """Distance between consecutive barriers."""
    height: Metres

    def position(self, number: int) -> Decimal:
        if not 1 <= number <= self.count:
            raise ValueError(f"there is no hurdle {number}; this race has {self.count}")
        return self.first + self.spacing * (number - 1)


class Discipline(Record):
    """Something that is raced, independent of where or by whom: ``400m``, ``400mh``."""

    id: DisciplineId
    name: NonEmptyStr
    """Full name, e.g. ``400 metres hurdles``."""
    short_name: NonEmptyStr
    """Compact name for tables and charts, e.g. ``400mH``."""
    kind: DisciplineKind
    distance: Metres
    barriers: dict[Sex, BarrierLayout] = Field(default_factory=dict)
    """Barrier layouts by sex, for hurdles races."""
    declared: CatalogRef

    @model_validator(mode="after")
    def _barriers_match_kind(self) -> Self:
        if (self.kind is DisciplineKind.HURDLES) != bool(self.barriers):
            raise ValueError(f"{self.id}: hurdles races, and only they, need barrier layouts")
        for sex, layout in self.barriers.items():
            if layout.position(layout.count) >= self.distance:
                raise ValueError(f"{self.id} ({sex}): the last barrier is beyond the finish")
        return self

    def hurdle(self, sex: Sex, number: int) -> TimingPoint:
        """The timing point at barrier ``number`` for races of ``sex``."""
        layout = self.barriers.get(sex)
        if layout is None:
            raise ValueError(f"{self.id} has no barriers for {sex.value}")
        return TimingPoint.at_hurdle(number, layout.position(number))

    def finish(self) -> TimingPoint:
        return TimingPoint.finish(self.distance)


class Series(Record):
    """A family of competitions: the Olympic Games, the Diamond League, ..."""

    id: SeriesId
    name: NonEmptyStr
    short_name: NonEmptyStr
    kind: SeriesKind
    declared: CatalogRef
