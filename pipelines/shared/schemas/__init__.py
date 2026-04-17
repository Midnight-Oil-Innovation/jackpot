"""
Pydantic result payload schemas.

One schema per result table; each mirrors the corresponding JACKPOT
database table exactly. Schemas are imported by:

- parsers in ``jackpot-nf/pipelines/*/parsers/*.py`` (Sessions J-M)
- the ``jackpot-backend`` registration endpoint (Session I)

The ``RESULT_SCHEMAS`` dict at the bottom maps a ``result_type`` path
segment to its Pydantic class. The registration endpoint looks up the
class from this dict to validate incoming payloads.
"""

from .amr import AMRResult
from .assembly_qc import AssemblyQC
from .mag_qc import MAGQC
from .nextclade import NextcladeResult
from .pangolin import PangolinResult
from .taxonomic_profile import TaxonomicProfile
from .tb_typing import TBTypingResult
from .typing_result import TypingResult
from .wastewater import WastewaterLineageAbundance

RESULT_SCHEMAS: dict[str, type] = {
    "amr_results": AMRResult,
    "typing_results": TypingResult,
    "pangolin_results": PangolinResult,
    "nextclade_results": NextcladeResult,
    "tb_typing_results": TBTypingResult,
    "assembly_qc": AssemblyQC,
    "mag_qc": MAGQC,
    "taxonomic_profile": TaxonomicProfile,
    "wastewater_lineage_abundance": WastewaterLineageAbundance,
}

__all__ = [
    "RESULT_SCHEMAS",
    "AMRResult",
    "AssemblyQC",
    "MAGQC",
    "NextcladeResult",
    "PangolinResult",
    "TaxonomicProfile",
    "TBTypingResult",
    "TypingResult",
    "WastewaterLineageAbundance",
]
