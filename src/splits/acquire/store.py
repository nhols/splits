"""Content-addressed storage for document bytes.

A document is stored under the SHA-256 of its bytes (``data/store/ab/ab12….pdf``), so a stored
file can never silently change: reading re-verifies the hash.
"""

import hashlib
import tempfile
from pathlib import Path


def sha256_of(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class Store:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, sha256: str) -> Path:
        return self.root / sha256[:2] / f"{sha256}.pdf"

    def has(self, sha256: str) -> bool:
        return self.path(sha256).is_file()

    def put(self, content: bytes) -> str:
        """Store ``content`` and return its SHA-256. Writing is atomic."""
        digest = sha256_of(content)
        target = self.path(digest)
        if target.is_file():
            return digest
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        temporary.replace(target)
        return digest

    def read(self, sha256: str) -> bytes:
        content = self.path(sha256).read_bytes()
        if sha256_of(content) != sha256:
            raise ValueError(f"stored file {self.path(sha256)} does not match its hash")
        return content
