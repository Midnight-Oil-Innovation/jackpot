"""
Render a complete ``nextflow.config`` for a launch (P0g G-4).

The renderer pairs an :class:`ExecutionProfile` with the pipeline
metadata and runtime parameters needed by Nextflow's weblog and the
JACKPOT result-registration env vars, then emits the rendered config
through ``fsspec`` so local filesystems, ``gs://``, and ``s3://``
targets are written through the same code path.

Templates live in ``profile_templates/`` and are loaded via Jinja2's
``PackageLoader``. ``StrictUndefined`` is used deliberately — a
template referencing a missing variable should fail loudly during the
test sweep instead of rendering an empty string into a Nextflow
config the operator then has to debug.
"""

from __future__ import annotations

import logging
from typing import Any

import fsspec
from jinja2 import Environment, PackageLoader, StrictUndefined

from backend.pipeline_config.groovy_safe import groovy_escape, validate_groovy_safe
from backend.pipeline_config.types import ExecutionProfile

logger = logging.getLogger(__name__)

_TEMPLATE_ENV: Environment | None = None

# R-1 #1: executor_type comes from a database row that an operator with
# write access to ``execution_profiles`` controls. Without an allowlist,
# a malicious value containing path-traversal sequences would resolve
# through ``PackageLoader.get_template`` to an arbitrary readable file.
# The allowlist is the security boundary; new executor types ship via a
# code change, never via runtime extension.
_ALLOWED_EXECUTOR_TYPES: frozenset[str] = frozenset(
    {"local", "slurm", "lsf", "pbs", "kubernetes", "gcp_batch", "aws_batch"}
)


def _env() -> Environment:
    global _TEMPLATE_ENV
    if _TEMPLATE_ENV is None:
        # bandit B701 flags autoescape=False as a blanket XSS risk — a false
        # positive here. These templates render Groovy/Nextflow config text,
        # not HTML; Jinja2's HTML-entity autoescaping would mean nothing to
        # the Groovy parser (it doesn't protect against injection) while
        # actively corrupting legitimate values containing &, <, or > (e.g.
        # a pipeline description like "R&D pipeline"). The real defense is
        # groovy_escape / validate_groovy_safe above — every interpolation
        # point is covered by one of: an allowlist check before render
        # (executor_type), a DB CHECK constraint (container_engine), the
        # groovy_escape filter, or validate_groovy_safe rejection. See this
        # module's docstring and groovy_safe.py for the full R-1 #7 design.
        _TEMPLATE_ENV = Environment(
            loader=PackageLoader("backend.pipeline_config", "profile_templates"),
            undefined=StrictUndefined,
            autoescape=False,  # nosec B701 — see comment above
            keep_trailing_newline=True,
        )
        # R-1 #7: defense-in-depth Groovy injection escape. Templates
        # apply this filter to every catalog/profile-field
        # interpolation so a malicious value can't break out of its
        # Groovy string context. Pairs with the write-time
        # validate_groovy_safe check.
        _TEMPLATE_ENV.filters["groovy_escape"] = groovy_escape
    return _TEMPLATE_ENV


def _template_name_for(executor_type: str) -> str:
    """Map ``ExecutorTypeEnum`` value to the per-executor template file.

    Validates against ``_ALLOWED_EXECUTOR_TYPES`` before constructing
    the filename. Rejected values raise ``ValueError`` with a generic
    message — the user-supplied value is intentionally not echoed
    back so an attacker cannot confirm what they tried.
    """
    normalized = executor_type.lower()
    if normalized not in _ALLOWED_EXECUTOR_TYPES:
        raise ValueError("Unknown executor_type")
    return f"{normalized}.config.j2"


def _reject_unsafe_scheduler_values(profile: ExecutionProfile, work_dir: str) -> None:
    """Reject values that Nextflow forwards to a scheduler or a shell.

    Validates ``work_dir``, ``profile.name``, and **every** string
    value in ``config_overrides`` — not just the keys known to reach a
    shell today, so a new template interpolation can't quietly open a
    hole. Non-string overrides (``cpus``, ``queue_size``) are skipped;
    the templates coerce those with ``| int``.

    Deliberately NOT validated here: the free-text manifest fields
    (``description``, ``author``), which are escaped rather than
    rejected. See ``groovy_safe``'s module docstring for why the two
    classes of value get different treatment.

    Execution profiles are DB-seeded and have no HTTP write path, so
    this render-time check — not a Pydantic ``field_validator`` — is
    the choke point every launch routes through.
    """
    validate_groovy_safe(work_dir, field_name="work_dir")
    validate_groovy_safe(profile.name, field_name="profile.name")
    for key, value in profile.config_overrides.items():
        if isinstance(value, str):
            validate_groovy_safe(value, field_name=f"config_overrides.{key}")


def render_nextflow_config(
    *,
    profile: ExecutionProfile,
    pipeline: dict[str, Any],
    run_id: str,
    weblog_url: str,
    result_registration_url: str,
    pipeline_token: str,
    work_dir: str,
) -> str:
    """Render a full ``nextflow.config`` body for this launch.

    ``pipeline`` is the catalog-row mapping (``pipeline_name``,
    ``pipeline_version``, optional ``description`` / ``author`` /
    ``main_script``). The renderer pulls the manifest fields out and
    leaves the rest of the row untouched.
    """
    _reject_unsafe_scheduler_values(profile, work_dir)
    env = _env()
    template = env.get_template(_template_name_for(profile.executor_type))
    return template.render(
        run_id=run_id,
        pipeline_name=pipeline.get("pipeline_name") or "",
        pipeline_version=pipeline.get("pipeline_version"),
        pipeline_main_script=pipeline.get("main_script"),
        pipeline_author=pipeline.get("author"),
        pipeline_description=pipeline.get("description"),
        weblog_url=weblog_url,
        result_registration_url=result_registration_url,
        pipeline_token=pipeline_token,
        work_dir=work_dir,
        profile=profile,
    )


def write_run_config(
    *,
    rendered_config: str,
    work_dir: str,
    run_id: str,
) -> str:
    """Write a rendered config to ``<work_dir>/runs/<run_id>/jackpot_run.config``.

    Uses ``fsspec`` so local paths, ``gs://`` URIs, and ``s3://`` URIs
    work through the same call. Parent directories are created
    on-demand. Returns the absolute path/URI written, suitable for
    passing to ``nextflow run -c <path>``.
    """
    target = f"{work_dir.rstrip('/')}/runs/{run_id}/jackpot_run.config"
    fs, fs_path = fsspec.core.url_to_fs(target)
    parent = fs_path.rsplit("/", 1)[0]
    if parent:
        # makedirs is a no-op on object stores (gs, s3) but required
        # for local filesystems where the run dir doesn't exist yet.
        try:
            fs.makedirs(parent, exist_ok=True)
        except (FileExistsError, OSError) as exc:  # pragma: no cover — safety net
            logger.debug("fsspec.makedirs(%s) noop/fail: %s", parent, exc)
    with fs.open(fs_path, "w") as fh:
        fh.write(rendered_config)
    return target
