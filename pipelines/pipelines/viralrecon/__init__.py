"""
viralrecon wrapper (``nf-core/viralrecon``) — SARS-CoV-2 / HIV / RSV.

Pipeline-level :func:`parse` walks a viralrecon output tree and returns
combined :class:`ParsedResult` objects from pangolin, nextclade, iVar
variants, and (in wastewater mode) Freyja.

Reuses the shared pangolin and nextclade parsers — viralrecon's output
format for those steps is byte-compatible with Cecret's.
"""

from .parsers import SUPPORTED_PIPELINE_VERSIONS, collect_files, parse

__all__ = ["SUPPORTED_PIPELINE_VERSIONS", "collect_files", "parse"]
