"""
Cecret wrapper (``UPHL-BioNGS/Cecret``) — SARS-CoV-2 / MPX consensus pipeline.

Provides a pipeline-level :func:`parse` that walks a Cecret output tree
and returns the combined :class:`ParsedResult` list. File-style
artifacts (consensus FASTAs) are returned by :func:`collect_files`.
"""

from .parsers import SUPPORTED_PIPELINE_VERSIONS, collect_files, parse

__all__ = ["SUPPORTED_PIPELINE_VERSIONS", "collect_files", "parse"]
