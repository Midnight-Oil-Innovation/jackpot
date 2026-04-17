"""Parser-side dataclasses shared across every pipeline wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True)
class RunMetadata:
    """Run-level context stamped onto every parsed result."""

    run_id: str
    pipeline_name: str
    pipeline_version: str


@dataclass(frozen=True)
class ParsedResult:
    """
    One typed result bound for the JACKPOT registration endpoint.

    ``result_type`` is the path segment (e.g. ``pangolin_results``) and
    must be a key of :data:`shared.schemas.RESULT_SCHEMAS`.  ``payload``
    is a plain dict shaped for the matching Pydantic schema — parsers
    build via :meth:`from_model` so validation happens before the HTTP
    round-trip.
    """

    result_type: str
    payload: dict[str, Any]

    @classmethod
    def from_model(cls, result_type: str, model: BaseModel) -> ParsedResult:
        return cls(result_type=result_type, payload=model.model_dump(exclude_none=True))


@dataclass(frozen=True)
class FileArtifact:
    """
    A pipeline-produced file destined for ``sample_files``.

    ``relative_path`` is relative to the pipeline's output directory so
    the wrapper can stage it from any working tree.  ``file_subtype``
    disambiguates artifacts of the same ``file_type`` — e.g. flu
    segments share ``file_type='fasta'`` but differ by
    ``file_subtype='segment_HA'`` / ``'segment_NA'``.
    """

    sample_id: str
    relative_path: str
    file_type: str
    file_subtype: str | None = None
