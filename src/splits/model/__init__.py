"""The data model: pure types with their invariants, and no I/O.

Read in this order: ``values`` (vocabularies), ``ids`` (identifiers), ``provenance`` (where
values come from), ``reference`` (disciplines, timing points, series), ``catalog`` (what people
declare), ``records`` (what the dataset says happened), ``dataset`` (all of it, consistent).
"""

from splits.model.catalog import (
    AthleteRule,
    Catalog,
    Competition,
    DocumentSpec,
    Exclusion,
    NameVariant,
    Retrieval,
    Venue,
)
from splits.model.dataset import BuildInfo, Dataset, sourced_values
from splits.model.ids import (
    AthleteId,
    CheckId,
    CompetitionId,
    DisciplineId,
    DocumentId,
    FormatId,
    PerformanceId,
    RaceId,
    RaceKey,
    SeriesId,
)
from splits.model.provenance import BBox, CatalogRef, Source, Sourced, Span
from splits.model.records import (
    Athlete,
    BirthDate,
    Document,
    Flag,
    Performance,
    PersonName,
    Race,
    Result,
    Segment,
    Split,
)
from splits.model.reference import BarrierLayout, Discipline, Series, TimingPoint
from splits.model.values import (
    DisciplineKind,
    PointKind,
    Qualification,
    Round,
    SeriesKind,
    Setting,
    Severity,
    Sex,
    Status,
)

__all__ = [
    "Athlete",
    "AthleteId",
    "AthleteRule",
    "BBox",
    "BarrierLayout",
    "BirthDate",
    "BuildInfo",
    "Catalog",
    "CatalogRef",
    "CheckId",
    "Competition",
    "CompetitionId",
    "Dataset",
    "Discipline",
    "DisciplineId",
    "DisciplineKind",
    "Document",
    "DocumentId",
    "DocumentSpec",
    "Exclusion",
    "Flag",
    "FormatId",
    "NameVariant",
    "Performance",
    "PerformanceId",
    "PersonName",
    "PointKind",
    "Qualification",
    "Race",
    "RaceId",
    "RaceKey",
    "Result",
    "Retrieval",
    "Round",
    "Segment",
    "Series",
    "SeriesId",
    "SeriesKind",
    "Setting",
    "Severity",
    "Sex",
    "Source",
    "Sourced",
    "Span",
    "Split",
    "Status",
    "TimingPoint",
    "Venue",
    "sourced_values",
]
