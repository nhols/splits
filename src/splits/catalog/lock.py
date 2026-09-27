"""Lock files: the pinned fingerprint of every document a competition's data is read from.

``catalog/competitions/<id>/lock.json`` is written by ``splits fetch`` and committed. A build
reads only bytes whose SHA-256 matches the lock, so the dataset can be rebuilt from exactly the
documents that were reviewed, and a publisher silently replacing a PDF is detected rather than
absorbed.
"""

from pathlib import Path

from pydantic import Field

from splits.model import DocumentId, Retrieval
from splits.model.base import Record

LOCK_FILE = "lock.json"


class Lock(Record):
    documents: dict[DocumentId, Retrieval] = Field(default_factory=dict)


def read_lock(competition_dir: Path) -> Lock:
    path = competition_dir / LOCK_FILE
    if not path.exists():
        return Lock()
    return Lock.model_validate_json(path.read_text(encoding="utf-8"))


def write_lock(competition_dir: Path, lock: Lock) -> None:
    ordered = Lock(documents=dict(sorted(lock.documents.items())))
    text = ordered.model_dump_json(indent=2) + "\n"
    (competition_dir / LOCK_FILE).write_text(text, encoding="utf-8")
