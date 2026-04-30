"""
walkercreek wrapper (``UPHL-BioNGS/walkercreek``) — influenza / RSV.

Parses IRMA per-segment output into :class:`TypingResult` objects (one
per sample, summarising subtype + clade) and collects per-segment
consensus FASTAs as :class:`FileArtifact`.

walkercreek runs on both Illumina and Nanopore inputs; IRMA writes the
same directory layout in both cases, so the parser does not need to
branch on the sequencing platform.
"""

from .parsers import SUPPORTED_PIPELINE_VERSIONS, collect_files, parse

__all__ = ["SUPPORTED_PIPELINE_VERSIONS", "collect_files", "parse"]
