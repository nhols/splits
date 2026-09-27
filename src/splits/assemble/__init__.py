"""Assembly: from document readings and catalog declarations to canonical records."""

from splits.assemble.assemble import Assembled, AssemblyError, Conflict, DocumentRead, assemble
from splits.assemble.identity import IdentityError

__all__ = ["Assembled", "AssemblyError", "Conflict", "DocumentRead", "IdentityError", "assemble"]
