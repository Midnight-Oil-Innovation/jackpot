"""
Shared parser infrastructure for JACKPOT pipeline wrappers.

Every per-pipeline wrapper in ``jackpot-nf/pipelines/`` reuses the two
dataclasses exported from here:

* :class:`RunMetadata` — run-level context (run_id, pipeline name/version)
  passed to every parser; lets parsers stamp tool/pipeline version without
  re-parsing version files on every call.
* :class:`ParsedResult` — the spec-defined return value of ``parse()``.
  ``result_type`` maps one-to-one to the ``/results/{result_type}``
  endpoint path segment, and ``payload`` is the dict shape expected by the
  matching Pydantic schema in :mod:`shared.schemas`.

File artifacts (consensus FASTAs, segment FASTAs, reports) go through
:class:`FileArtifact` rather than ParsedResult — ``sample_files`` is not
a result table, so file registration uses a separate transport.

Shared cross-pipeline parsers (``pangolin``, ``nextclade``) live here so
Cecret and viralrecon can both import them.
"""

from .types import FileArtifact, ParsedResult, RunMetadata

__all__ = ["FileArtifact", "ParsedResult", "RunMetadata"]
