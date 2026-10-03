"""The catalog: what the dataset is built from, curated by people.

    catalog/
      disciplines.yaml          what is raced
      series.yaml               families of competitions
      athletes.yaml             identity rules: merges, name variants, display spellings
      athlete-numbers.json      the permanent number of each athlete's address (machine-written)
      annotations.yaml          what the marks printed beside results mean
      competitions/<id>/
        competition.yaml        one competition and the documents published for it
        lock.json               pinned fingerprints of those documents (machine-written)

The catalog *declares* and documents *attest*. A document entry says "this PDF, in this format,
reports this race"; before any value is taken from the PDF, its reader confirms the document
itself names the same event, round and heat.
"""

from datetime import date
from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, Field, model_validator

from splits.model.base import Record
from splits.model.ids import (
    AthleteId,
    CompetitionId,
    DisciplineId,
    DocumentId,
    FormatId,
    RaceId,
    RaceKey,
    SeriesId,
    race_id,
)
from splits.model.provenance import CatalogRef
from splits.model.reference import Discipline, Series
from splits.model.values import (
    CountryCode,
    DisciplineKind,
    NonEmptyStr,
    PositiveInt,
    Setting,
    Sha256,
    Url,
)


class Venue(Record):
    name: NonEmptyStr
    city: NonEmptyStr
    country: CountryCode


class Retrieval(Record):
    """How and when a document's bytes were obtained. Pinned in the competition's lock file,
    so every build reads exactly the bytes that were reviewed."""

    sha256: Sha256
    size: PositiveInt
    media_type: NonEmptyStr
    retrieved_at: AwareDatetime
    retrieved_from: Url
    """The URL that actually served the bytes: the publisher's, or the archive snapshot."""


class Competition(Record):
    id: CompetitionId
    name: NonEmptyStr
    series: SeriesId
    start_date: date
    end_date: date
    venue: Venue
    setting: Setting
    """Where the competition's races are run; a document entry may override it."""
    timezone: NonEmptyStr
    """IANA time zone of the venue. Times printed in documents are local to it."""
    results_url: Url | None = None
    """The organiser's official results page."""
    listing_url: Url | None = None
    """Where the competition's documents are listed, when not on its results page: the index
    of a results system, or a results book. Read by ``splits discover``."""
    world_athletics: PositiveInt | None = None
    """World Athletics' ID of the competition (the number ending its results URL). Its results
    there name the World Athletics athlete of every result, which identifies athletes."""
    world_athletics_results: Retrieval | None = None
    """From the lock file: the pinned copy of those results; ``None`` until fetched."""
    declared: CatalogRef

    @model_validator(mode="after")
    def _valid(self) -> Self:
        if self.start_date > self.end_date:
            raise ValueError(f"{self.id}: starts after it ends")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"{self.id}: unknown time zone {self.timezone!r}") from error
        return self


class DocumentSpec(Record):
    """A published document and the race it reports, as declared in the catalog."""

    id: DocumentId
    competition: CompetitionId
    race: RaceKey
    format: FormatId
    """The reader that understands this document's layout, e.g. ``wa-rs5``."""
    url: Url
    """Where the publisher published the document."""
    archive_url: Url | None = None
    """An immutable snapshot of the document, e.g. on the Wayback Machine."""
    pages: tuple[PositiveInt, ...] | None = None
    """For a compilation (a statistics handbook, a results book): the pages that report this
    race, in reading order. Only these are read."""
    setting: Setting | None = None
    """Overrides the competition's setting for this race."""
    retrieval: Retrieval | None = None
    """From the lock file; ``None`` until the document has been fetched."""
    declared: CatalogRef

    @property
    def race_id(self) -> RaceId:
        return race_id(self.competition, self.race)


class Exclusion(Record):
    """A race its publisher gives splits for that the catalog leaves out on purpose, and why:
    a race analysis that prints no times, a national race on a meeting's programme. Discovery
    reports every listed race that is neither declared nor excluded."""

    competition: CompetitionId
    race: RaceKey
    reason: NonEmptyStr
    declared: CatalogRef


class NameVariant(Record):
    """A spelling under which an athlete appears in documents."""

    given: NonEmptyStr
    family: NonEmptyStr
    country: CountryCode | None = None
    """The country printed with this spelling, when it differs from the athlete's."""


class AthleteRule(Record):
    """A curated identity decision, for cases where printed names alone would go wrong:
    a name that changed, two athletes sharing a name, or a spelling to display."""

    id: AthleteId
    given: NonEmptyStr
    family: NonEmptyStr
    """Display spelling of the family name, e.g. ``McLaughlin-Levrone``."""
    country: CountryCode
    also_known_as: tuple[NameVariant, ...] = ()
    world_athletics: PositiveInt | None = None
    """The athlete's World Athletics ID (the number ending their profile URL), for athletes
    no World Athletics results identify, or to overrule them."""
    declared: CatalogRef


class NumberHolder(Record):
    """Whom an athlete number was given to, as last built (see :mod:`splits.catalog.numbers`)."""

    athlete: AthleteId
    world_athletics: PositiveInt | None = None


class AnnotationMeaning(Record):
    """What a mark printed beside results means (a rule broken, a card, a lead), for readers.
    Record tags are explained by the model's own list (``RECORD_TAGS``)."""

    code: NonEmptyStr
    """The mark as ``annotation_key`` writes it: ``TR16.8``, ``163.3b``, ``ADR10.8``, ``L``."""
    meaning: NonEmptyStr
    source: NonEmptyStr
    """Where the meaning comes from: the documents' own notes or legends, or a rulebook."""
    declared: CatalogRef


class Catalog(Record):
    disciplines: dict[DisciplineId, Discipline]
    series: dict[SeriesId, Series]
    competitions: dict[CompetitionId, Competition]
    documents: tuple[DocumentSpec, ...]
    exclusions: tuple[Exclusion, ...] = ()
    athletes: tuple[AthleteRule, ...] = ()
    annotations: tuple[AnnotationMeaning, ...] = ()
    athlete_numbers: dict[PositiveInt, NumberHolder] = Field(default_factory=dict)
    """Whom each athlete number was given to; see :mod:`splits.catalog.numbers`."""

    @model_validator(mode="after")
    def _references_resolve(self) -> Self:
        for discipline_key, discipline in self.disciplines.items():
            if discipline_key != discipline.id:
                raise ValueError(f"discipline {discipline.id} is filed under {discipline_key}")
        for series_key, series in self.series.items():
            if series_key != series.id:
                raise ValueError(f"series {series.id} is filed under {series_key}")
        for competition_key, competition in self.competitions.items():
            if competition_key != competition.id:
                raise ValueError(f"competition {competition.id} is filed under {competition_key}")
            if competition.series not in self.series:
                raise ValueError(f"{competition.id}: unknown series {competition.series!r}")

        seen: set[DocumentId] = set()
        for doc in self.documents:
            where = f"{doc.declared.file}:{doc.declared.line}"
            if doc.id in seen:
                raise ValueError(f"{where}: document {doc.id} is declared twice")
            seen.add(doc.id)
            if doc.competition not in self.competitions:
                raise ValueError(f"{where}: unknown competition {doc.competition!r}")
            raced = self.disciplines.get(doc.race.discipline)
            if raced is None:
                raise ValueError(f"{where}: unknown discipline {doc.race.discipline!r}")
            if raced.kind is DisciplineKind.HURDLES and doc.race.sex not in raced.barriers:
                raise ValueError(f"{where}: {raced.id} has no barriers for {doc.race.sex}")

        declared_races = {doc.race_id for doc in self.documents}
        for exclusion in self.exclusions:
            where = f"{exclusion.declared.file}:{exclusion.declared.line}"
            if race_id(exclusion.competition, exclusion.race) in declared_races:
                raise ValueError(f"{where}: {exclusion.race} is both declared and excluded")

        rule_ids = [rule.id for rule in self.athletes]
        duplicates = {rule_id for rule_id in rule_ids if rule_ids.count(rule_id) > 1}
        if duplicates:
            raise ValueError(f"athlete rules declared twice: {sorted(duplicates)}")
        codes = [annotation.code for annotation in self.annotations]
        explained_twice = {code for code in codes if codes.count(code) > 1}
        if explained_twice:
            raise ValueError(f"annotations explained twice: {sorted(explained_twice)}")
        return self

    def competition_of(self, doc: DocumentSpec) -> Competition:
        return self.competitions[doc.competition]

    def discipline_of(self, doc: DocumentSpec) -> Discipline:
        return self.disciplines[doc.race.discipline]
