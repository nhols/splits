"""Data-quality checks over the assembled records."""

from splits.checks import rules as _rules  # noqa: F401  (registers the checks)
from splits.checks.framework import CHECKS, Check, Finding, run_checks

__all__ = ["CHECKS", "Check", "Finding", "run_checks"]
