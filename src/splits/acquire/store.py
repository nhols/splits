"""Content-addressed storage for document bytes.

A document is stored under the SHA-256 of its bytes (``data/store/ab/ab12….pdf``, or ``.html``
for a web page), so a stored file can never silently change: reading re-verifies the hash.
"""

import hashlib
import tempfile
from pathlib import Path

SUFFIXES = {"application/pdf": ".pdf", "text/html": ".html"}


def sha256_of(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def media_type_of(content: bytes) -> str:
    """What a document is, from its bytes: a PDF or a web page. Anything else is refused."""
    if content.startswith(b"%PDF"):
        return "application/pdf"
    head = content[:1024].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if head.startswith((b"<!doctype html", b"<html")):
        return "text/html"
    raise ValueError("neither a PDF nor a web page")


class Store:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, sha256: str) -> Path:
        """Where the document is stored, or would be if it were a PDF."""
        for suffix in SUFFIXES.values():
            candidate = self.root / sha256[:2] / f"{sha256}{suffix}"
            if candidate.is_file():
                return candidate
        return self.root / sha256[:2] / f"{sha256}.pdf"

    def has(self, sha256: str) -> bool:
        return self.path(sha256).is_file()

    def put(self, content: bytes) -> str:
        """Store ``content`` and return its SHA-256. Writing is atomic."""
        digest = sha256_of(content)
        target = self.root / digest[:2] / f"{digest}{SUFFIXES[media_type_of(content)]}"
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
