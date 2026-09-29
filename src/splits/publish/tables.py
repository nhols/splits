"""The dataset as relational tables: the one schema behind the DuckDB database and the CSV and
Parquet downloads.

Every value that was read from a document or declared in the catalog has a sibling
``<name>_source`` column holding the ID of a row in the ``provenance`` table, which says
exactly where it came from: document, page, box and text, and the extraction rule used, or
the catalog file and line. Columns, like tables, carry descriptions, which the database
stores as comments and ``docs/schema.md`` lists.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from splits.checks import CHECKS
from splits.formats import FORMATS
from splits.model import CatalogRef, Dataset, Sourced, Span

SOURCE = "VARCHAR"


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    description: str


@dataclass
class Table:
    name: str
    description: str
    columns: list[Column]
    rows: list[tuple[Any, ...]] = field(default_factory=list)


class Provenance:
    """Collects the sources of sourced values into the ``provenance`` table."""

    def __init__(self) -> None:
        self.rows: dict[str, tuple[Any, ...]] = {}

    def id(self, value: Sourced[Any] | None) -> str | None:
        if value is None:
            return None
        payload = json.dumps(
            [value.source.model_dump(mode="json"), value.method], sort_keys=True
        ).encode()
        key = hashlib.sha256(payload).hexdigest()[:16]
        if key not in self.rows:
            source = value.source
            if isinstance(source, Span):
                box = source.bbox
                self.rows[key] = (
                    key,
                    "document",
                    source.document,
                    source.page,
                    box.x0,
                    box.top,
                    box.x1,
                    box.bottom,
                    source.text,
                    value.method,
                    None,
                    None,
                    None,
                )
            else:
                self.rows[key] = (
                    key,
                    "catalog",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    value.method,
                    source.file,
                    source.line,
                    source.pointer,
                )
        return key


def _v(value: Sourced[Any] | None, convert: Callable[[Any], Any] = lambda x: x) -> Any:
    return None if value is None else convert(value.value)


def _declared(ref: CatalogRef | None) -> tuple[str | None, int | None]:
    return (ref.file, ref.line) if ref else (None, None)


def _cols(spec: str) -> list[Column]:
    """Parse ``name TYPE: description`` lines into columns."""
    columns = []
    for line in spec.strip().splitlines():
        head, _, description = line.strip().partition(": ")
        name, _, sql_type = head.partition(" ")
        columns.append(Column(name, sql_type, description))
    return columns


def build_tables(dataset: Dataset) -> list[Table]:
    prov = Provenance()
    tables = [
        _competitions(dataset),
        _series(dataset),
        _disciplines(dataset),
        _barriers(dataset),
        _formats(),
        _documents(dataset, prov),
        _races(dataset, prov),
        _athletes(dataset),
        _performances(dataset, prov),
        _annotations(dataset, prov),
        _splits(dataset, prov),
        _segments(dataset, prov),
        _checks(),
        _flags(dataset),
    ]
    tables.append(_provenance(prov))
    tables.append(
        Table(
            "build",
            "When and from which code this dataset was built.",
            _cols("""
                built_at TIMESTAMPTZ: When the build ran.
                code_version VARCHAR: Git commit of the code, suffixed -dirty if uncommitted.
            """),
            [(dataset.build.built_at, dataset.build.code_version)],
        )
    )
    return tables


def _competitions(dataset: Dataset) -> Table:
    return Table(
        "competitions",
        "Competitions, as declared in catalog/competitions/<id>/competition.yaml.",
        _cols("""
            id VARCHAR: Competition ID, e.g. wch-2023-budapest.
            name VARCHAR: Official name.
            series VARCHAR: Series ID (series.id).
            start_date DATE: First day.
            end_date DATE: Last day.
            venue VARCHAR: Stadium or arena.
            city VARCHAR: City.
            country VARCHAR: Country code.
            setting VARCHAR: outdoor, indoor (200 m short track) or road.
            timezone VARCHAR: IANA time zone of the venue; document times are local to it.
            results_url VARCHAR: The organiser's official results page.
            declared_file VARCHAR: Catalog file that declares the competition.
            declared_line INTEGER: Line in that file.
        """),
        [
            (
                c.id,
                c.name,
                c.series,
                c.start_date,
                c.end_date,
                c.venue.name,
                c.venue.city,
                c.venue.country,
                c.setting.value,
                c.timezone,
                c.results_url,
                *_declared(c.declared),
            )
            for c in dataset.competitions
        ],
    )


def _series(dataset: Dataset) -> Table:
    return Table(
        "series",
        "Families of competitions (catalog/series.yaml).",
        _cols("""
            id VARCHAR: Series ID, e.g. diamond-league.
            name VARCHAR: Full name.
            short_name VARCHAR: Compact name.
            kind VARCHAR: games, championships or meeting.
        """),
        [(s.id, s.name, s.short_name, s.kind.value) for s in dataset.series],
    )


def _disciplines(dataset: Dataset) -> Table:
    return Table(
        "disciplines",
        "What is raced (catalog/disciplines.yaml).",
        _cols("""
            id VARCHAR: Discipline ID, e.g. 400mh.
            name VARCHAR: Full name, e.g. 400 metres hurdles.
            short_name VARCHAR: Compact name, e.g. 400mH.
            kind VARCHAR: flat, hurdles, steeplechase, relay, road or race-walk.
            distance_m DECIMAL(9,3): Race distance in metres.
        """),
        [(d.id, d.name, d.short_name, d.kind.value, d.distance) for d in dataset.disciplines],
    )


def _barriers(dataset: Dataset) -> Table:
    return Table(
        "barriers",
        "Barrier layouts of hurdles disciplines, per sex, from the World Athletics rules.",
        _cols("""
            discipline VARCHAR: Discipline ID.
            sex VARCHAR: men or women.
            count INTEGER: Number of barriers.
            first_m DECIMAL(9,3): Distance from the start to the first barrier.
            spacing_m DECIMAL(9,3): Distance between barriers.
            height_m DECIMAL(9,3): Barrier height.
        """),
        [
            (d.id, sex.value, b.count, b.first, b.spacing, b.height)
            for d in dataset.disciplines
            for sex, b in d.barriers.items()
        ],
    )


def _formats() -> Table:
    return Table(
        "formats",
        "The kinds of document the dataset is read from, and their readers.",
        _cols("""
            id VARCHAR: Format ID, e.g. wa-rs5.
            version VARCHAR: Version of the reader that read the documents.
            name VARCHAR: Name of the document type.
            publisher VARCHAR: Who publishes documents of this type.
            description VARCHAR: What the documents contain.
        """),
        [(f.id, f.version, f.name, f.publisher, f.description) for f in FORMATS.values()],
    )


def _documents(dataset: Dataset, prov: Provenance) -> Table:
    return Table(
        "documents",
        "Every document the dataset was read from: where it was published, the exact bytes "
        "that were read (SHA-256), and what the document says about itself.",
        _cols(f"""
            id VARCHAR: Document ID: <race>/<format>.
            race VARCHAR: The race the document reports (races.id).
            format VARCHAR: Document format (formats.id).
            format_version VARCHAR: Version of the reader that read it.
            url VARCHAR: Where the publisher published it.
            archive_url VARCHAR: An immutable archived copy, if any.
            sha256 VARCHAR: SHA-256 of the bytes that were read, pinned in the lock file.
            size_bytes BIGINT: Size of those bytes.
            retrieved_at TIMESTAMPTZ: When they were downloaded.
            retrieved_from VARCHAR: The URL that served them.
            pages INTEGER: Number of pages.
            issued TIMESTAMP: When the publisher issued this version (local time, as printed).
            issued_source {SOURCE}: Provenance of issued.
            revision VARCHAR: The document's own version marker, e.g. v2.0.
            revision_source {SOURCE}: Provenance of revision.
            timing_by VARCHAR: Timing provider credited by the document.
            timing_by_source {SOURCE}: Provenance of timing_by.
        """),
        [
            (
                d.id,
                d.race,
                d.format,
                d.format_version,
                d.url,
                d.archive_url,
                d.retrieval.sha256,
                d.retrieval.size,
                d.retrieval.retrieved_at,
                d.retrieval.retrieved_from,
                d.pages,
                _v(d.issued),
                prov.id(d.issued),
                _v(d.revision),
                prov.id(d.revision),
                _v(d.timing_by),
                prov.id(d.timing_by),
            )
            for d in dataset.documents
        ],
    )


def _races(dataset: Dataset, prov: Provenance) -> Table:
    return Table(
        "races",
        "Races: one start, one finish. Declared in the catalog, confirmed by the document.",
        _cols(f"""
            id VARCHAR: Race ID: <competition>/<discipline>-<sex>/<round>[-<heat>].
            competition VARCHAR: competitions.id.
            discipline VARCHAR: disciplines.id.
            sex VARCHAR: men, women or mixed.
            round VARCHAR: heat, repechage, quarter-final, semi-final or final.
            heat INTEGER: Heat number within the round; null for a single race.
            setting VARCHAR: outdoor, indoor or road.
            title VARCHAR: The race heading as printed.
            title_source {SOURCE}: Provenance of title.
            date DATE: Date of the race.
            date_source {SOURCE}: Provenance of date.
            start_time TIME: Local start time.
            start_time_source {SOURCE}: Provenance of start_time.
            wind_mps DECIMAL(5,2): Wind in m/s, positive is a tailwind.
            wind_mps_source {SOURCE}: Provenance of wind_mps.
            temperature_c DECIMAL(5,1): Temperature in °C.
            temperature_c_source {SOURCE}: Provenance of temperature_c.
            humidity_pct DECIMAL(5,1): Relative humidity in percent.
            humidity_pct_source {SOURCE}: Provenance of humidity_pct.
            weather VARCHAR: Conditions as described.
            weather_source {SOURCE}: Provenance of weather.
            declared_file VARCHAR: Catalog file that declares the race's document.
            declared_line INTEGER: Line in that file.
        """),
        [
            (
                r.id,
                r.competition,
                r.key.discipline,
                r.key.sex.value,
                r.key.round.value,
                r.key.heat,
                r.setting.value,
                _v(r.title),
                prov.id(r.title),
                _v(r.date),
                prov.id(r.date),
                _v(r.start_time),
                prov.id(r.start_time),
                _v(r.wind),
                prov.id(r.wind),
                _v(r.temperature),
                prov.id(r.temperature),
                _v(r.humidity),
                prov.id(r.humidity),
                _v(r.weather),
                prov.id(r.weather),
                *_declared(r.declared),
            )
            for r in dataset.races
        ],
    )


def _athletes(dataset: Dataset) -> Table:
    return Table(
        "athletes",
        "Athletes, identified across documents. Names and birth dates summarise the printed "
        "values stored, with provenance, on each performance.",
        _cols("""
            id VARCHAR: Athlete ID, e.g. karsten-warholm.
            given_name VARCHAR: Given name.
            family_name VARCHAR: Family name, in display case.
            name VARCHAR: Given and family name.
            sex VARCHAR: men or women.
            country VARCHAR: Country of the most recent performance.
            birth_date VARCHAR: YYYY-MM-DD, or YYYY when only the year is printed.
            rule_file VARCHAR: The identity rule applied (catalog/athletes.yaml), if any.
            rule_line INTEGER: Line of that rule.
        """),
        [
            (
                a.id,
                a.given_name,
                a.family_name,
                a.name,
                a.sex.value,
                a.country,
                str(a.birth_date) if a.birth_date else None,
                *_declared(a.rule),
            )
            for a in dataset.athletes
        ],
    )


def _performances(dataset: Dataset, prov: Provenance) -> Table:
    return Table(
        "performances",
        "One athlete's run in one race.",
        _cols(f"""
            id VARCHAR: Performance ID: <race>/<athlete>.
            race VARCHAR: races.id.
            athlete VARCHAR: athletes.id.
            given_name VARCHAR: Given name as printed.
            family_name VARCHAR: Family name as printed.
            name_source {SOURCE}: Provenance of the printed name.
            country VARCHAR: Country code as printed.
            country_source {SOURCE}: Provenance of country.
            birth_date VARCHAR: Birth date as printed: YYYY-MM-DD, or YYYY.
            birth_date_source {SOURCE}: Provenance of birth_date.
            bib VARCHAR: Bib number.
            bib_source {SOURCE}: Provenance of bib.
            lane INTEGER: Lane.
            lane_source {SOURCE}: Provenance of lane.
            place INTEGER: Finishing place.
            place_source {SOURCE}: Provenance of place.
            status VARCHAR: finished, dnf, dns or dq.
            time_s DECIMAL(9,3): Official finishing time in seconds; null unless finished.
            result_source {SOURCE}: Provenance of status and time_s (the printed result).
            reaction_time_s DECIMAL(6,3): Reaction time in seconds; negative for a false start.
            reaction_time_s_source {SOURCE}: Provenance of reaction_time_s.
            precise_time_s DECIMAL(9,3): The finishing time to the thousandth, where printed.
            precise_time_s_source {SOURCE}: Provenance of precise_time_s.
            qualification VARCHAR: Q (by place) or q (by time).
            qualification_source {SOURCE}: Provenance of qualification.
        """),
        [
            (
                p.id,
                p.race,
                p.athlete,
                p.name.value.given,
                p.name.value.family,
                prov.id(p.name),
                _v(p.country),
                prov.id(p.country),
                _v(p.birth_date, str),
                prov.id(p.birth_date),
                _v(p.bib),
                prov.id(p.bib),
                _v(p.lane),
                prov.id(p.lane),
                _v(p.place),
                prov.id(p.place),
                p.status.value,
                p.time,
                prov.id(p.result),
                _v(p.reaction_time),
                prov.id(p.reaction_time),
                _v(p.precise_time),
                prov.id(p.precise_time),
                _v(p.qualification, lambda q: q.value),
                prov.id(p.qualification),
            )
            for p in dataset.performances
        ],
    )


def _annotations(dataset: Dataset, prov: Provenance) -> Table:
    rows: list[tuple[Any, ...]] = []
    for perf in dataset.performances:
        rows.extend((perf.id, "record", tag.value, prov.id(tag)) for tag in perf.records)
        rows.extend((perf.id, "remark", remark.value, prov.id(remark)) for remark in perf.remarks)
    return Table(
        "annotations",
        "Annotations printed next to results: record tags (PB, SB, NR...) and remarks such "
        "as disqualification rules (TR17.3.1) or cards (YC).",
        _cols(f"""
            performance VARCHAR: performances.id.
            kind VARCHAR: record or remark.
            value VARCHAR: The annotation as printed.
            source {SOURCE}: Provenance of value.
        """),
        rows,
    )


def _splits(dataset: Dataset, prov: Provenance) -> Table:
    return Table(
        "splits",
        "Cumulative times from the gun at timing points, each from the document that "
        "measured it. Derive segment times and speeds from these, not from segments.",
        _cols(f"""
            id VARCHAR: Split ID: <performance>/<point>@<format>.
            performance VARCHAR: performances.id.
            document VARCHAR: documents.id of the document that measured it.
            point VARCHAR: Timing point label: 100m, H3 (hurdle 3), TD3 (touchdown), Finish.
            point_kind VARCHAR: distance, hurdle, touchdown (after a hurdle) or finish.
            distance_m DECIMAL(9,3): Distance of the point from the start.
            hurdle INTEGER: Barrier number, for hurdle and touchdown points.
            time_s DECIMAL(9,3): Time from the gun, in seconds.
            time_source {SOURCE}: Provenance of time_s.
            rank INTEGER: Position at the point, as printed.
            rank_source {SOURCE}: Provenance of rank.
        """),
        [
            (
                s.id,
                s.performance,
                s.document,
                s.point.label,
                s.point.kind.value,
                s.point.distance,
                s.point.hurdle,
                s.time.value,
                prov.id(s.time),
                _v(s.rank),
                prov.id(s.rank),
            )
            for s in dataset.splits
        ],
    )


def _segments(dataset: Dataset, prov: Provenance) -> Table:
    return Table(
        "segments",
        "Segment times as printed by documents. Kept to verify the splits: each must equal "
        "the difference of the cumulative times at its ends (check segment-matches-splits).",
        _cols(f"""
            id VARCHAR: Segment ID.
            performance VARCHAR: performances.id.
            document VARCHAR: documents.id.
            start_point VARCHAR: Label of the point the segment starts at (Start for the gun).
            start_m DECIMAL(9,3): Its distance.
            end_point VARCHAR: Label of the point it ends at.
            end_m DECIMAL(9,3): Its distance.
            time_s DECIMAL(9,3): Segment time in seconds.
            time_source {SOURCE}: Provenance of time_s.
        """),
        [
            (
                s.id,
                s.performance,
                s.document,
                s.start.label,
                s.start.distance,
                s.end.label,
                s.end.distance,
                s.time.value,
                prov.id(s.time),
            )
            for s in dataset.segments
        ],
    )


def _checks() -> Table:
    return Table(
        "checks",
        "The data-quality checks run on every build.",
        _cols("""
            id VARCHAR: Check ID.
            severity VARCHAR: error (values contradict each other) or warning (implausible).
            suspect BOOLEAN: Whether flagged values are left out of analyses.
            title VARCHAR: What the check verifies, briefly.
            explanation VARCHAR: What the check verifies and why.
        """),
        [(c.id, c.severity.value, c.suspect, c.title, c.explanation) for c in CHECKS],
    )


def _flags(dataset: Dataset) -> Table:
    return Table(
        "flags",
        "Findings of the checks, attached to the value they are about. Flagged values are "
        "kept as published; suspect ones are left out of analyses.",
        _cols("""
            check_id VARCHAR: checks.id.
            severity VARCHAR: error or warning.
            subject VARCHAR: ID of the record the finding is about.
            field VARCHAR: The field of that record, e.g. time.
            message VARCHAR: What was found.
            suspect BOOLEAN: Whether analyses leave the value out.
        """),
        [
            (f.check, f.severity.value, f.subject, f.field, f.message, f.suspect)
            for f in dataset.flags
        ],
    )


def _provenance(prov: Provenance) -> Table:
    return Table(
        "provenance",
        "Where each value came from. A document source gives the page, the box (in PDF "
        "points from the top-left corner) and the exact text read; a catalog source gives "
        "the file and line. method names the extraction rule.",
        _cols("""
            id VARCHAR: Provenance ID, referenced by the *_source columns.
            kind VARCHAR: document or catalog.
            document VARCHAR: documents.id, for document sources.
            page INTEGER: Page number, from 1.
            x0 DOUBLE: Left edge of the box.
            top DOUBLE: Top edge of the box.
            x1 DOUBLE: Right edge of the box.
            bottom DOUBLE: Bottom edge of the box.
            text VARCHAR: The exact text read from the box.
            method VARCHAR: The rule that interpreted the text, e.g. cumulative.time.
            file VARCHAR: Catalog file, for catalog sources.
            line INTEGER: Line in that file.
            pointer VARCHAR: JSON pointer to the value in that file.
        """),
        list(prov.rows.values()),
    )
