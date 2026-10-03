"""The ``splits`` command line: fetch documents, build the dataset, and inspect it."""

import shutil
from collections import Counter
from pathlib import Path
from typing import Annotated

import typer

from splits.acquire import Outcome, Store, fetch_documents, fetch_world_athletics
from splits.catalog import load_catalog
from splits.model import Catalog, DocumentSpec
from splits.paths import Paths
from splits.pdf.textlayer import TextLayer

app = typer.Typer(no_args_is_help=True, add_completion=False, help=__doc__)


@app.callback()
def _group() -> None:
    """Build and inspect the splits dataset."""


@app.command()
def fetch(
    competition: Annotated[
        list[str] | None, typer.Argument(help="Only these competitions (default: all).")
    ] = None,
    accept_changes: Annotated[
        bool, typer.Option(help="Re-pin documents whose publisher now serves different bytes.")
    ] = False,
    locked: Annotated[
        bool,
        typer.Option(help="Fail if any document is not pinned yet; lock files stay as they are."),
    ] = False,
    refresh_world_athletics: Annotated[
        bool,
        typer.Option(
            help="Ask World Athletics for its results again and re-pin them, to take up "
            "athletes' new names."
        ),
    ] = False,
) -> None:
    """Download catalog documents, and World Athletics' results of each competition, into the
    store and pin them in lock files."""
    paths = Paths.discover()
    catalog = load_catalog(paths.catalog)
    wanted = set(competition or catalog.competitions)
    unknown = wanted - set(catalog.competitions)
    if unknown:
        raise typer.BadParameter(f"unknown competitions: {sorted(unknown)}")
    specs = [doc for doc in catalog.documents if doc.competition in wanted]
    if locked:
        if accept_changes:
            raise typer.BadParameter("--locked and --accept-changes contradict each other")
        unpinned = [str(doc.id) for doc in specs if doc.retrieval is None] + [
            f"{c.id} (World Athletics results)"
            for c in catalog.competitions.values()
            if c.id in wanted
            and c.world_athletics is not None
            and c.world_athletics_results is None
        ]
        if unpinned:
            typer.secho(
                f"{len(unpinned)} document(s) not pinned (run `splits fetch` and commit the "
                "lock files):\n  " + "\n  ".join(unpinned),
                fg="red",
            )
            raise typer.Exit(1)
    store = Store(paths.store)
    results = fetch_documents(paths.catalog, store, specs, accept_changes=accept_changes)
    results += fetch_world_athletics(
        paths.catalog,
        store,
        [c for c in catalog.competitions.values() if c.id in wanted],
        refresh=refresh_world_athletics,
        accept_changes=accept_changes,
    )
    for result in results:
        if result.outcome in (Outcome.CHANGED, Outcome.FAILED):
            typer.secho(f"{result.outcome}: {result.document}\n  {result.detail}", fg="red")
    counts = Counter(result.outcome.value for result in results)
    typer.echo(", ".join(f"{count} {outcome}" for outcome, count in sorted(counts.items())))
    if counts[Outcome.CHANGED] or counts[Outcome.FAILED]:
        raise typer.Exit(1)


@app.command()
def discover(
    competition: Annotated[str, typer.Argument(help="Competition ID, e.g. wch-2023-budapest.")],
    write: Annotated[
        bool,
        typer.Option(help="Write the listed documents into the competition's catalog file."),
    ] = False,
) -> None:
    """Compare the documents a competition's publisher lists with the catalog, or write them
    into the catalog (then run `splits fetch` to pin them)."""
    from splits.catalog.load import COMPETITION_FILE, COMPETITIONS_DIR
    from splits.catalog.write import Entry, write_documents
    from splits.discover import compare
    from splits.discover import discover as list_documents

    paths = Paths.discover()
    catalog = load_catalog(paths.catalog)
    found = next((c for c in catalog.competitions.values() if c.id == competition), None)
    if found is None:
        raise typer.BadParameter(f"unknown competition {competition!r}")
    comparison = compare(list_documents(found, catalog), catalog, found)
    listing = comparison.listing
    races = {doc.race for doc in listing.documents}
    typer.echo(f"{listing.source}: {len(listing.documents)} documents for {len(races)} races")
    for doc in comparison.missing:
        typer.secho(f"  + {doc.race} {doc.format}  {doc.url}", fg="green")
    for doc, declared in comparison.moved:
        typer.secho(f"  ~ {doc.race} {doc.format}  {declared} -> {doc.url}", fg="yellow")
    for doc_id in comparison.unlisted:
        typer.secho(f"  - {doc_id} (declared, not listed)", fg="red")
    if comparison.by_hand:
        by_hand = ", ".join(str(race) for race in comparison.by_hand)
        typer.echo(f"  {len(comparison.by_hand)} race(s) declared by hand, kept: {by_hand}")
    excluded = {doc.race for doc in comparison.excluded}
    if excluded:
        typer.echo(f"  {len(excluded)} excluded race(s) left out")
    if not write:
        return
    # The listing replaces what the catalog declares for the races it lists, in its formats;
    # anything else (a race declared by hand, a document of another kind) is kept.
    kept = [
        Entry.of(doc)
        for doc in catalog.documents
        if doc.competition == competition
        and (doc.format not in listing.formats or doc.race not in races)
    ]
    listed = [
        Entry(
            race=doc.race,
            format=doc.format,
            url=doc.url,
            archive_url=doc.archive_url,
            pages=doc.pages,
        )
        for doc in listing.documents
        if doc.race not in excluded
    ]
    target = paths.catalog / COMPETITIONS_DIR / competition / COMPETITION_FILE
    write_documents(target, catalog, [*kept, *listed])
    typer.echo(f"wrote {target.relative_to(paths.root)}; run `splits fetch {competition}`")


@app.command()
def build(
    site: Annotated[bool, typer.Option(help="Also write the website's data files.")] = True,
) -> None:
    """Read every document, assemble and check the dataset, and publish it."""
    from splits.assemble.assemble import number_holders
    from splits.catalog.numbers import write_numbers
    from splits.pipeline import BuildError
    from splits.pipeline import build as run_build
    from splits.publish import build_tables, export_tables, write_database, write_site_data
    from splits.publish.site import annotation_meanings

    paths = Paths.discover()
    try:
        result = run_build(paths)
    except BuildError as error:
        typer.secho(str(error), fg="red")
        raise typer.Exit(1) from error
    dataset = result.dataset
    # Record every athlete's number, so their address keeps working whatever names change.
    write_numbers(paths.catalog, number_holders(dataset.athletes))
    tables = build_tables(dataset)
    database = paths.build / "splits.duckdb"
    write_database(tables, database)
    export_tables(database, paths.build / "tables", tables)
    if site:
        write_site_data(dataset, paths.site_data)
        downloads = paths.site_data / "downloads"
        shutil.copytree(paths.build / "tables", downloads)
        shutil.copy2(database, downloads / database.name)

    flags = Counter(f"{flag.severity.value}s" for flag in dataset.flags)
    typer.echo(
        f"{len(dataset.races)} races, {len(dataset.performances)} performances, "
        f"{len(dataset.athletes)} athletes, {len(dataset.splits)} splits "
        f"from {len(dataset.documents)} documents; "
        + (", ".join(f"{n} {kind}" for kind, n in sorted(flags.items())) or "no flags")
    )
    typer.echo(f"database: {database.relative_to(paths.root)}")
    if site:
        typer.echo(f"site data: {paths.site_data.relative_to(paths.root)}")
    unexplained = [value for value, meaning in annotation_meanings(dataset).items() if not meaning]
    if unexplained:
        typer.secho(
            f"marks printed beside results with no meaning in catalog/annotations.yaml: "
            f"{', '.join(unexplained)}",
            fg="yellow",
        )


@app.command()
def schema(
    output: Annotated[Path | None, typer.Option(help="Write to this file.")] = None,
) -> None:
    """Print the database schema as Markdown (docs/schema.md is generated by this)."""
    from splits.pipeline import build as run_build
    from splits.publish import build_tables, schema_markdown

    text = schema_markdown(build_tables(run_build(Paths.discover()).dataset))
    if output:
        output.write_text(text, encoding="utf-8")
    else:
        typer.echo(text, nl=False)


def _document(paths: Paths, document: str) -> tuple[Catalog, DocumentSpec, TextLayer]:
    """A catalog document and its text layer."""
    from splits.pdf.textlayer import load_text_layer

    catalog = load_catalog(paths.catalog)
    spec = next((doc for doc in catalog.documents if doc.id == document), None)
    if spec is None:
        raise typer.BadParameter(f"no document {document!r} in the catalog")
    if spec.retrieval is None:
        raise typer.BadParameter(f"{document} has not been fetched; run `splits fetch`")
    return (
        catalog,
        spec,
        load_text_layer(Store(paths.store), paths.cache, spec.retrieval.sha256, spec.pages),
    )


@app.command()
def inspect(
    document: Annotated[
        str, typer.Argument(help="Document ID, e.g. og-2024-paris/400m-men/final/oris-c77a")
    ],
    page: Annotated[int | None, typer.Option(help="Only this page.")] = None,
    words: Annotated[bool, typer.Option(help="List words with coordinates and fonts.")] = False,
) -> None:
    """Show a document's text layer as its reader sees it: lines, or words with positions.
    The starting point for writing a format reader."""
    from splits.pdf.layout import DocumentView

    paths = Paths.discover()
    _, spec, layer = _document(paths, document)
    view = DocumentView(spec.id, layer)
    for number in [page] if page else [each.number for each in layer.pages]:
        typer.secho(f"── page {number} ──", bold=True)
        if words:
            for word in layer.page(number).words:
                typer.echo(
                    f"{word.top:7.1f} {word.x0:7.1f}-{word.x1:<7.1f} "
                    f"{word.font[:18]:18} {word.size:4.1f}  {word.text}"
                )
        else:
            for line in view.lines(number):
                typer.echo(f"{line.top:7.1f} │ {line.text}")


@app.command()
def read(
    document: Annotated[str, typer.Argument(help="Document ID.")],
    json_output: Annotated[bool, typer.Option("--json", help="Print the full reading.")] = False,
) -> None:
    """Read one document with its format's reader and print what was transcribed."""
    from splits.formats import ReadContext, get_format
    from splits.pdf.layout import DocumentView

    paths = Paths.discover()
    catalog, spec, layer = _document(paths, document)
    context = ReadContext(
        spec=spec, discipline=catalog.discipline_of(spec), competition=catalog.competition_of(spec)
    )
    reading = get_format(spec.format).read(DocumentView(spec.id, layer), context)
    if json_output:
        typer.echo(reading.model_dump_json(indent=2))
        return
    dated = f"  ({reading.date.value})" if reading.date else ""
    typer.secho(f"{reading.title.value}{dated}", bold=True)
    for entry in reading.entries:
        name = entry.name.value
        result = entry.result.value
        typer.echo(
            f"{entry.place.value if entry.place else '-':>3} {name.given} {name.family} "
            f"{entry.country.value if entry.country else ''} "
            f"{result.time if result.time is not None else result.status.value}"
        )
        if entry.splits:
            typer.echo(
                "      "
                + "  ".join(f"{split.point.label} {split.time.value}" for split in entry.splits)
            )
    for note in reading.notes:
        typer.secho(f"note: {note}", fg="yellow")


@app.command()
def trace(
    record: Annotated[str, typer.Argument(help="A race, performance or split ID (or prefix).")],
) -> None:
    """Show where every value of a record came from."""
    import duckdb

    paths = Paths.discover()
    database = paths.build / "splits.duckdb"
    if not database.exists():
        raise typer.BadParameter("no database; run `splits build`")
    with duckdb.connect(str(database), read_only=True) as con:
        rows = con.execute(
            """
            SELECT 'split ' || s.point, s.time_s::VARCHAR, p.document, p.page, p.text, p.method
            FROM splits s JOIN provenance p ON p.id = s.time_source
            WHERE s.performance LIKE ? || '%'
            UNION ALL
            SELECT 'result', coalesce(pf.time_s::VARCHAR, pf.status), p.document, p.page,
                   p.text, p.method
            FROM performances pf JOIN provenance p ON p.id = pf.result_source
            WHERE pf.id LIKE ? || '%'
            ORDER BY 3, 1
            """,
            [record, record],
        ).fetchall()
    if not rows:
        typer.echo("nothing found")
    for what, value, doc, page, text, method in rows:
        typer.echo(f"{what:>14} {value:>8}  ← {doc} p{page} {text!r} ({method})")


@app.command()
def fixture(
    document: Annotated[list[str], typer.Argument(help="Document IDs.")],
) -> None:
    """Save documents' text layers as test fixtures (tests/fixtures/text/), with World
    Athletics' results of their competitions (tests/fixtures/world-athletics/)."""
    import gzip

    paths = Paths.discover()
    store = Store(paths.store)
    for doc in document:
        catalog, spec, layer = _document(paths, doc)
        target = paths.root / "tests" / "fixtures" / "text" / f"{spec.id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(layer.model_dump_json(indent=1) + "\n", encoding="utf-8")
        typer.echo(f"wrote {target.relative_to(paths.root)}")
        pinned = catalog.competitions[spec.competition].world_athletics_results
        if pinned is not None:
            results = paths.root / "tests" / "fixtures" / "world-athletics" / f"{pinned.sha256}.gz"
            if not results.exists():
                results.parent.mkdir(parents=True, exist_ok=True)
                results.write_bytes(gzip.compress(store.read(pinned.sha256), mtime=0))
                typer.echo(f"wrote {results.relative_to(paths.root)}")


def main() -> None:
    app()
