"""Format readers: one module per kind of published document.

To add a format, write a :class:`~splits.formats.base.Format` subclass in its own module and
list it in ``FORMATS`` below. See ``docs/adding-a-format.md``.
"""

from splits.formats.base import (
    DocumentKind,
    DocumentReading,
    EntryReading,
    Format,
    HeadingReading,
    ReadContext,
    SegmentReading,
    SplitReading,
)
from splits.formats.flash_results import FlashResults, FlashSplits
from splits.formats.iaaf_biomechanics import IaafBiomechanics
from splits.formats.omega_race_analysis import OmegaRaceAnalysis
from splits.formats.omega_result_lists import OmegaResultLists
from splits.formats.omega_results import OmegaResults
from splits.formats.oris_c73b1 import OrisC73b1
from splits.formats.oris_c77a import OrisC77a
from splits.formats.wa_biomechanics import WaBiomechanics
from splits.formats.wa_handbook import WaHandbook
from splits.formats.wa_results import WaResults
from splits.formats.wa_results_2009 import WaResultsOf2009
from splits.formats.wa_rs5 import WaRs5
from splits.formats.wa_rs5_2015 import WaRs5Of2015
from splits.model import FormatId

FORMATS: dict[FormatId, Format] = {
    reader.id: reader
    for reader in (
        WaRs5(),
        WaRs5Of2015(),
        WaResults(),
        WaResultsOf2009(),
        OmegaRaceAnalysis(),
        OmegaResults(),
        OmegaResultLists(),
        OrisC77a(),
        OrisC73b1(),
        WaHandbook(),
        IaafBiomechanics(),
        WaBiomechanics(),
        FlashSplits(),
        FlashResults(),
    )
}


def get_format(fmt: FormatId) -> Format:
    try:
        return FORMATS[fmt]
    except KeyError:
        known = ", ".join(sorted(FORMATS))
        raise ValueError(f"no reader for format {fmt!r}; known formats: {known}") from None


__all__ = [
    "FORMATS",
    "DocumentKind",
    "DocumentReading",
    "EntryReading",
    "Format",
    "HeadingReading",
    "ReadContext",
    "SegmentReading",
    "SplitReading",
    "get_format",
]
