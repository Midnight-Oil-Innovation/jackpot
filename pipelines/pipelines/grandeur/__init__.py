"""
Grandeur wrapper (``UPHL-BioNGS/Grandeur``) — bacterial isolate pipeline
with AMRFinderPlus, Tseemann mlst, Kraken2 species ID, and a BLAST
confirmation step.
"""

from .parsers import SUPPORTED_PIPELINE_VERSIONS, collect_files, parse

__all__ = ["SUPPORTED_PIPELINE_VERSIONS", "collect_files", "parse"]
