"""Where the pipeline reads and writes, relative to the repository root."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def catalog(self) -> Path:
        return self.root / "catalog"

    @property
    def store(self) -> Path:
        """Downloaded documents, by content hash. Reproducible from the lock files."""
        return self.root / "data" / "store"

    @property
    def cache(self) -> Path:
        """Derived working files, e.g. extracted text layers. Safe to delete."""
        return self.root / "data" / "cache"

    @property
    def build(self) -> Path:
        """Build outputs: the DuckDB database and table exports."""
        return self.root / "build"

    @property
    def site_data(self) -> Path:
        """Data files for the website."""
        return self.root / "site" / "public" / "data"

    @classmethod
    def discover(cls, start: Path | None = None) -> "Paths":
        """Find the repository root: the nearest directory with a ``catalog/`` folder."""
        here = (start or Path.cwd()).resolve()
        for directory in (here, *here.parents):
            if (directory / "catalog").is_dir() and (directory / "pyproject.toml").is_file():
                return cls(directory)
        raise FileNotFoundError(f"no repository root (with catalog/) above {here}")
