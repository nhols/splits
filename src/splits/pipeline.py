"""The build, end to end: catalog and documents in, a consistent dataset out.

    catalog/ ──load──▶ Catalog
    lock + store ──▶ document bytes ──extract──▶ text layers (cached)
    text layer ──format reader──▶ DocumentReading     (one per document)
    lock + store ──▶ World Athletics' results          (who each result's athlete is)
    readings ──assemble──▶ records                     (identities, races, performances…)
    records ──checks──▶ flags
    records + flags ──▶ Dataset                        (integrity enforced)

Every step is deterministic, so the same catalog, lock files and code give the same dataset.
"""

import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from splits.acquire import Store
from splits.assemble import DocumentRead, assemble
from splits.assemble.world_athletics import WorldAthleticsResults
from splits.catalog import load_catalog
from splits.checks import run_checks
from splits.formats import ReadContext, get_format
from splits.model import BuildInfo, Catalog, Dataset, DocumentId
from splits.paths import Paths
from splits.pdf.layout import DocumentView, ReadError
from splits.pdf.textlayer import TextLayer, load_text_layer


class BuildError(Exception):
    def __init__(self, failures: list[str]) -> None:
        super().__init__(f"{len(failures)} document(s) could not be read:\n" + "\n".join(failures))
        self.failures = failures


@dataclass(frozen=True)
class Build:
    catalog: Catalog
    dataset: Dataset
    layers: dict[DocumentId, TextLayer]
    """The text layer of every document, for showing sources."""


def read_documents(
    catalog: Catalog, paths: Paths, only: Iterable[DocumentId] | None = None
) -> tuple[list[DocumentRead], dict[DocumentId, TextLayer]]:
    """Read catalog documents with their formats' readers. Raises :class:`BuildError` listing
    every document that is not fetched or does not read, rather than stopping at the first."""
    wanted = set(only) if only is not None else None
    store = Store(paths.store)
    reads: list[DocumentRead] = []
    layers: dict[DocumentId, TextLayer] = {}
    failures: list[str] = []
    for spec in catalog.documents:
        if wanted is not None and spec.id not in wanted:
            continue
        if spec.retrieval is None or not store.has(spec.retrieval.sha256):
            failures.append(f"{spec.id}: not fetched (run `splits fetch`)")
            continue
        reader = get_format(spec.format)
        if spec.retrieval.media_type != reader.media_type:
            failures.append(
                f"{spec.id}: is {spec.retrieval.media_type}, but {spec.format} reads"
                f" {reader.media_type}"
            )
            continue
        layer = load_text_layer(store, paths.cache, spec.retrieval.sha256, spec.pages)
        context = ReadContext(
            spec=spec,
            discipline=catalog.discipline_of(spec),
            competition=catalog.competition_of(spec),
        )
        try:
            reading = reader.read(DocumentView(spec.id, layer), context)
        except (ReadError, ValueError) as error:
            failures.append(f"{spec.id}: {error}")
            continue
        reads.append(DocumentRead(spec, reading))
        layers[spec.id] = layer
    if failures:
        raise BuildError(failures)
    return reads, layers


def read_world_athletics(catalog: Catalog, paths: Paths) -> dict[str, WorldAthleticsResults]:
    """World Athletics' results of every competition that has them pinned. Raises
    :class:`BuildError` if a competition's results are not fetched."""
    store = Store(paths.store)
    found: dict[str, WorldAthleticsResults] = {}
    failures: list[str] = []
    for competition in catalog.competitions.values():
        if competition.world_athletics is None:
            continue
        pinned = competition.world_athletics_results
        if pinned is None or not store.has(pinned.sha256):
            failures.append(f"{competition.id}: World Athletics results not fetched")
            continue
        found[competition.id] = WorldAthleticsResults(
            competition.id, pinned, store.read(pinned.sha256)
        )
    if failures:
        raise BuildError(failures)
    return found


def build(paths: Paths) -> Build:
    catalog = load_catalog(paths.catalog)
    reads, layers = read_documents(catalog, paths)
    dataset = make_dataset(
        catalog,
        reads,
        code_version=code_version(paths),
        world_athletics=read_world_athletics(catalog, paths),
    )
    return Build(catalog=catalog, dataset=dataset, layers=layers)


def make_dataset(
    catalog: Catalog,
    reads: list[DocumentRead],
    *,
    code_version: str,
    built_at: datetime | None = None,
    world_athletics: Mapping[str, WorldAthleticsResults] | None = None,
) -> Dataset:
    """Assemble readings, run the checks, and return the consistent dataset."""
    records = assemble(catalog, reads, world_athletics)
    flags = run_checks(catalog, records)
    return Dataset(
        build=BuildInfo(
            built_at=built_at or datetime.now(UTC).replace(microsecond=0),
            code_version=code_version,
        ),
        disciplines=tuple(catalog.disciplines.values()),
        series=tuple(catalog.series.values()),
        competitions=tuple(catalog.competitions.values()),
        documents=records.documents,
        races=records.races,
        athletes=records.athletes,
        performances=records.performances,
        splits=records.splits,
        segments=records.segments,
        flags=flags,
        annotation_meanings=catalog.annotations,
    )


def code_version(paths: Paths) -> str:
    """The git commit the build ran from, marked ``-dirty`` if there are uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "describe", "--always", "--dirty", "--abbrev=12"],
            cwd=paths.root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "uncommitted"
    return result.stdout.strip() or "uncommitted"
