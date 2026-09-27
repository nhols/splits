"""Write the dataset as a DuckDB database (for local exploration) and as CSV and Parquet files
(for download). Both come from the same table definitions in :mod:`splits.publish.tables`."""

import csv
import tempfile
from pathlib import Path

import duckdb

from splits.publish.tables import Table

ANALYSIS_VIEWS = {
    "results": (
        "Results with names, races and competitions joined in: a convenient starting point.",
        """
        SELECT p.id AS performance, r.id AS race, c.name AS competition, r.date, r.discipline,
               r.sex, r.round, r.heat, r.setting, a.name AS athlete, p.country, p.place,
               p.status, p.time_s
        FROM performances p
        JOIN races r ON r.id = p.race
        JOIN competitions c ON c.id = r.competition
        JOIN athletes a ON a.id = p.athlete
        """,
    ),
    "split_analysis": (
        "Each split series with the finish added from the official result, and the derived "
        "segment time, speed and share of the race. Derived columns are computed here, from "
        "the stored splits, never stored. suspect marks values analyses leave out: those a "
        "check flagged, and the whole run when a check flagged its result.",
        """
        WITH points AS (
            SELECT s.performance, s.document, s.point, s.point_kind, s.distance_m, s.time_s,
                   s.rank, s.id AS split
            FROM splits s
            WHERE s.point_kind <> 'finish'
            UNION ALL
            SELECT DISTINCT s.performance, s.document, 'Finish', 'finish', d.distance_m,
                   p.time_s, p.place, NULL
            FROM splits s
            JOIN performances p ON p.id = s.performance
            JOIN races r ON r.id = p.race
            JOIN disciplines d ON d.id = r.discipline
            WHERE p.status = 'finished'
        )
        SELECT pt.performance, pt.document, pt.point, pt.point_kind, pt.distance_m,
               pt.time_s, pt.rank,
               pt.distance_m - lag(pt.distance_m, 1, 0) OVER w AS segment_m,
               pt.time_s - lag(pt.time_s, 1, 0) OVER w AS segment_s,
               round((pt.distance_m - lag(pt.distance_m, 1, 0) OVER w)
                     / (pt.time_s - lag(pt.time_s, 1, 0) OVER w), 3) AS speed_mps,
               round(pt.time_s / p.time_s, 4) AS share_of_race,
               pt.split,
               EXISTS (SELECT 1 FROM flags f
                       WHERE f.suspect AND (f.subject = pt.split
                           OR (f.subject = pt.performance AND f.field = 'result')))
                   AS suspect
        FROM points pt
        JOIN performances p ON p.id = pt.performance
        WINDOW w AS (PARTITION BY pt.performance, pt.document ORDER BY pt.distance_m)
        """,
    ),
}


def _literal(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


NULL = "\\N"


def _load_rows(con: duckdb.DuckDBPyConnection, table: Table, scratch: Path) -> None:
    """Bulk-load rows by staging them as CSV (row-by-row inserts are slow in DuckDB)."""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".csv", dir=scratch, delete=False, newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle)
        writer.writerows([NULL if value is None else value for value in row] for row in table.rows)
        staged = Path(handle.name)
    try:
        con.execute(
            f"COPY {table.name} FROM {_literal(str(staged))} "
            f"(HEADER false, NULLSTR {_literal(NULL)}, QUOTE '\"')"
        )
    finally:
        staged.unlink()


def write_database(tables: list[Table], path: Path) -> None:
    """Write a fresh database at ``path`` (replacing any existing one atomically)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.duckdb")
    temporary.unlink(missing_ok=True)
    with duckdb.connect(str(temporary)) as con:
        for table in tables:
            columns = ", ".join(f'"{c.name}" {c.type}' for c in table.columns)
            con.execute(f"CREATE TABLE {table.name} ({columns})")
            if table.rows:
                _load_rows(con, table, temporary.parent)
            con.execute(f"COMMENT ON TABLE {table.name} IS {_literal(table.description)}")
            for column in table.columns:
                con.execute(
                    f'COMMENT ON COLUMN {table.name}."{column.name}" IS '
                    f"{_literal(column.description)}"
                )
        for name, (description, query) in ANALYSIS_VIEWS.items():
            con.execute(f"CREATE VIEW {name} AS {query}")
            con.execute(f"COMMENT ON VIEW {name} IS {_literal(description)}")
    temporary.replace(path)


def export_tables(database: Path, directory: Path, tables: list[Table]) -> None:
    """Export every table to CSV and Parquet in ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(database), read_only=True) as con:
        for table in tables:
            for suffix, options in (
                ("csv", "(HEADER, DELIMITER ',')"),
                ("parquet", "(FORMAT parquet)"),
            ):
                target = directory / f"{table.name}.{suffix}"
                con.execute(f"COPY {table.name} TO {_literal(str(target))} {options}")


def schema_markdown(tables: list[Table]) -> str:
    """The schema as Markdown, for ``docs/schema.md``."""
    lines = [
        "# Database schema",
        "",
        "Generated from `src/splits/publish/tables.py` by `splits schema`; do not edit by hand.",
        "",
        "Every value read from a document or declared in the catalog has a sibling `*_source`",
        "column referencing `provenance.id`.",
        "",
    ]
    for table in tables:
        lines += [
            f"## `{table.name}`",
            "",
            table.description,
            "",
            "| Column | Type | Meaning |",
            "| --- | --- | --- |",
        ]
        lines += [f"| `{c.name}` | {c.type} | {c.description} |" for c in table.columns]
        lines.append("")
    lines += ["## Views", ""]
    for name, (description, _) in ANALYSIS_VIEWS.items():
        lines += [f"- `{name}`: {description}"]
    return "\n".join(lines) + "\n"
