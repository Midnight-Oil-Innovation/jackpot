"""
bactopia wrapper (``bactopia/bactopia``) — bacterial isolate pipeline.

Provides a pipeline-level :func:`parse` + :func:`collect_files`
following the contract every JACKPOT pipeline wrapper exposes.
"""

from .parsers import SUPPORTED_PIPELINE_VERSIONS, collect_files, parse

__all__ = ["SUPPORTED_PIPELINE_VERSIONS", "collect_files", "parse"]
