"""
Resolve which execution profile a launch should use (P0g G-4).

Resolution order, matching Critical Rule 59 and the spec.md
"Phase P0g — Execution profiles" section:

  1. Explicit ``profile_id`` (wins over ``profile_name`` when both are
     supplied — documented).
  2. Explicit ``profile_name``.
  3. Pipeline's lowest-priority default profile from
     ``pipeline_default_profile`` (active rows only).
  4. Deployment's ``is_default=true`` profile (active rows only).
  5. Raise :class:`NoProfileAvailableError`.

Errors carry the names of profiles that the operator could plausibly
want — :class:`ProfileNotFoundError` lists every active profile,
:class:`NoProfileAvailableError` lists the active profiles configured
as defaults for the pipeline plus the deployment default. Endpoint
handlers surface those names back to the caller so a Lab Director can
correct a typo without having to query the catalog.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from backend.database import execute_query
from backend.pipeline_config.types import ExecutionProfile


def _coerce_uuid(pipeline_id: str) -> str | None:
    """Return the canonical UUID string, or None if the value is not a UUID.

    The G-1+G-2 migration declares ``pipeline_default_profile.pipeline_id``
    as ``UUID NOT NULL`` without an FK because the current pipeline
    surface (``pipeline_catalog``) carries a SERIAL integer id. Until a
    follow-up migration aligns the keys, the resolver silently skips the
    pipeline-default lookup whenever the caller supplies a non-UUID
    pipeline id (e.g., a stringified SERIAL); the deployment-default
    branch and the legacy fallback still apply.
    """
    try:
        return str(UUID(pipeline_id))
    except (ValueError, AttributeError, TypeError):
        return None


class ProfileNotFoundError(Exception):
    """Explicit profile_name/profile_id missing or inactive."""

    def __init__(self, requested: str, available_profile_names: list[str]):
        super().__init__(f"Profile {requested!r} not found or inactive")
        self.requested = requested
        self.available_profile_names = available_profile_names


class NoProfileAvailableError(Exception):
    """Resolution chain exhausted — no profile usable."""

    def __init__(self, configured_profile_names: list[str]):
        super().__init__("No execution profile available for this pipeline")
        self.configured_profile_names = configured_profile_names


def _row_to_profile(row: dict[str, Any]) -> ExecutionProfile:
    return ExecutionProfile.from_row(row)


def _list_active_profile_names(db_conn) -> list[str]:
    rows = execute_query(
        "SELECT name FROM execution_profiles WHERE active = TRUE ORDER BY name",
        conn=db_conn,
    )
    return [r["name"] for r in rows]


def _fetch_by_id(db_conn, profile_id: str) -> ExecutionProfile | None:
    rows = execute_query(
        """
        SELECT profile_id, name, executor_type, container_engine,
               work_dir, config_overrides, is_default, created_by_id,
               created_at, active
        FROM execution_profiles
        WHERE profile_id = :pid AND active = TRUE
        LIMIT 1
        """,
        {"pid": profile_id},
        conn=db_conn,
    )
    return _row_to_profile(rows[0]) if rows else None


def _fetch_by_name(db_conn, profile_name: str) -> ExecutionProfile | None:
    rows = execute_query(
        """
        SELECT profile_id, name, executor_type, container_engine,
               work_dir, config_overrides, is_default, created_by_id,
               created_at, active
        FROM execution_profiles
        WHERE name = :name AND active = TRUE
        LIMIT 1
        """,
        {"name": profile_name},
        conn=db_conn,
    )
    return _row_to_profile(rows[0]) if rows else None


def _fetch_pipeline_default(db_conn, pipeline_id: str) -> ExecutionProfile | None:
    """Lowest priority value wins; ties broken by created_at then name."""
    rows = execute_query(
        """
        SELECT p.profile_id, p.name, p.executor_type, p.container_engine,
               p.work_dir, p.config_overrides, p.is_default, p.created_by_id,
               p.created_at, p.active
        FROM pipeline_default_profile pdp
        JOIN execution_profiles p ON p.profile_id = pdp.profile_id
        WHERE pdp.pipeline_id = :pid AND p.active = TRUE
        ORDER BY pdp.priority ASC, p.created_at ASC, p.name ASC
        LIMIT 1
        """,
        {"pid": pipeline_id},
        conn=db_conn,
    )
    return _row_to_profile(rows[0]) if rows else None


def _fetch_deployment_default(db_conn) -> ExecutionProfile | None:
    rows = execute_query(
        """
        SELECT profile_id, name, executor_type, container_engine,
               work_dir, config_overrides, is_default, created_by_id,
               created_at, active
        FROM execution_profiles
        WHERE is_default = TRUE AND active = TRUE
        LIMIT 1
        """,
        conn=db_conn,
    )
    return _row_to_profile(rows[0]) if rows else None


def _list_pipeline_default_names(db_conn, pipeline_id: str) -> list[str]:
    rows = execute_query(
        """
        SELECT p.name
        FROM pipeline_default_profile pdp
        JOIN execution_profiles p ON p.profile_id = pdp.profile_id
        WHERE pdp.pipeline_id = :pid AND p.active = TRUE
        ORDER BY pdp.priority ASC, p.name ASC
        """,
        {"pid": pipeline_id},
        conn=db_conn,
    )
    return [r["name"] for r in rows]


def resolve_profile(
    *,
    db_conn,
    pipeline_id: str,
    profile_name: str | None = None,
    profile_id: str | None = None,
) -> ExecutionProfile:
    """Resolve which execution profile to use for this launch.

    Resolution order:

    1. If ``profile_id`` is provided, use it (must be active). When both
       ``profile_id`` and ``profile_name`` are supplied, ``profile_id``
       wins — the ID is the unambiguous identifier.
    2. Else if ``profile_name`` is provided, use it (must be active).
    3. Else the pipeline's lowest-priority default profile.
    4. Else the deployment's ``is_default=true`` profile.
    5. Else raise :class:`NoProfileAvailableError`.

    Steps 1 and 2 raise :class:`ProfileNotFoundError` (with the full
    list of active profile names) when no active row matches.
    """
    if profile_id:
        profile = _fetch_by_id(db_conn, profile_id)
        if profile is None:
            raise ProfileNotFoundError(
                requested=profile_id,
                available_profile_names=_list_active_profile_names(db_conn),
            )
        return profile

    if profile_name:
        profile = _fetch_by_name(db_conn, profile_name)
        if profile is None:
            raise ProfileNotFoundError(
                requested=profile_name,
                available_profile_names=_list_active_profile_names(db_conn),
            )
        return profile

    canonical_pipeline_id = _coerce_uuid(pipeline_id)
    if canonical_pipeline_id is not None:
        pipeline_default = _fetch_pipeline_default(db_conn, canonical_pipeline_id)
        if pipeline_default is not None:
            return pipeline_default

    deployment_default = _fetch_deployment_default(db_conn)
    if deployment_default is not None:
        return deployment_default

    configured: list[str] = []
    if canonical_pipeline_id is not None:
        configured.extend(_list_pipeline_default_names(db_conn, canonical_pipeline_id))
    deployment_default_row = execute_query(
        "SELECT name FROM execution_profiles WHERE is_default = TRUE AND active = TRUE LIMIT 1",
        conn=db_conn,
    )
    if deployment_default_row:
        configured.append(deployment_default_row[0]["name"])
    raise NoProfileAvailableError(configured_profile_names=configured)
