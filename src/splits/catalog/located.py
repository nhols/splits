"""YAML loading that remembers where every value was declared.

Catalog values carry a :class:`~splits.model.CatalogRef` (file, line, JSON pointer), so a value
shown on the website can link to the exact line of the catalog that declared it, and a
validation error can say exactly which line is wrong.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from splits.model import CatalogRef


class CatalogError(ValueError):
    """The catalog is invalid. The message starts with ``file:line``."""


def _escape(key: object) -> str:
    return str(key).replace("~", "~0").replace("/", "~1")


@dataclass(frozen=True)
class LocatedYaml:
    """A parsed YAML file plus the line on which every value starts."""

    file: str
    """Repository-relative path, used in references and messages."""
    data: Any
    lines: dict[str, int]
    """JSON pointer -> 1-based line number."""

    @classmethod
    def load(cls, path: Path, root: Path) -> "LocatedYaml":
        relative = path.relative_to(root.parent).as_posix()
        loader = yaml.SafeLoader(path.read_text(encoding="utf-8"))
        try:
            node = loader.get_single_node()
            if node is None:
                raise CatalogError(f"{relative}:1: the file is empty")
            data = loader.construct_document(node)
        except yaml.YAMLError as error:
            raise CatalogError(f"{relative}: invalid YAML: {error}") from error
        finally:
            loader.dispose()

        lines: dict[str, int] = {}

        def walk(current: yaml.Node, pointer: str) -> None:
            lines[pointer] = current.start_mark.line + 1
            if isinstance(current, yaml.MappingNode):
                for key_node, value_node in current.value:
                    walk(value_node, f"{pointer}/{_escape(key_node.value)}")
            elif isinstance(current, yaml.SequenceNode):
                for index, item in enumerate(current.value):
                    walk(item, f"{pointer}/{index}")

        walk(node, "")
        return cls(file=relative, data=data, lines=lines)

    def line(self, pointer: str) -> int:
        """The line of ``pointer``, or of its nearest ancestor that has one."""
        while pointer not in self.lines and pointer:
            pointer = pointer.rsplit("/", 1)[0]
        return self.lines.get(pointer, 1)

    def ref(self, pointer: str) -> CatalogRef:
        return CatalogRef(file=self.file, line=self.line(pointer), pointer=pointer)

    def error(self, pointer: str, message: str) -> CatalogError:
        return CatalogError(f"{self.file}:{self.line(pointer)}: {message}")

    def invalid(self, pointer: str, error: ValidationError) -> CatalogError:
        """Turn a validation error into one that points at the offending line."""
        first = error.errors()[0]
        field_pointer = pointer + "".join(f"/{_escape(part)}" for part in first["loc"])
        where = ".".join(str(part) for part in first["loc"]) or "value"
        return self.error(field_pointer, f"{where}: {first['msg']}")
