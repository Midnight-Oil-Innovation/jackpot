"""
Per-run Nextflow configuration package.

P0g G-3+G-4 split the original single-file ``pipeline_config.py`` module
into a package so the profile-driven renderer (``profile_renderer``,
``profile_resolver``, ``profile_templates/``) can sit alongside the
existing legacy GCP-Batch config generator without bloating one file.
The legacy path (``legacy.generate_run_config`` +
``batch_submitter.submit_to_batch``) remains the fallback for the
``/launch`` endpoint when the profile resolution chain finds nothing
applicable; per the G-4 spec, the legacy code path is preserved
verbatim and only retires once every deployment has at least one
execution profile configured.

Every public name on the pre-P0g module is re-exported here so the
historical ``from backend.pipeline_config import …`` import lines in
``backend/routers/pipelines.py`` and elsewhere keep working unchanged
(Critical Rules 25/26/27).
"""

from __future__ import annotations

from backend.pipeline_config.batch_submitter import submit_to_batch
from backend.pipeline_config.compatibility import (
    CompatibilityReport,
    compute_pipeline_compatibility,
)
from backend.pipeline_config.legacy import generate_run_config
from backend.pipeline_config.profile_renderer import (
    render_nextflow_config,
    write_run_config,
)
from backend.pipeline_config.profile_resolver import (
    NoProfileAvailableError,
    ProfileNotFoundError,
    resolve_profile,
)
from backend.pipeline_config.run_id import (
    new_pipeline_token,
    new_run_id,
    result_uri_for,
    work_dir_for,
)
from backend.pipeline_config.types import ExecutionProfile

__all__ = [
    "CompatibilityReport",
    "ExecutionProfile",
    "NoProfileAvailableError",
    "ProfileNotFoundError",
    "compute_pipeline_compatibility",
    "generate_run_config",
    "new_pipeline_token",
    "new_run_id",
    "render_nextflow_config",
    "resolve_profile",
    "result_uri_for",
    "submit_to_batch",
    "work_dir_for",
    "write_run_config",
]
