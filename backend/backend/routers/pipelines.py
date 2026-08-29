"""
Pipelines router — launch, monitor, resume, BYOP skeleton, promotion.

Implements:
  GET    /api/v1/pipelines/                                 — paginated runs list
  POST   /api/v1/pipelines/launch                           — GCP Batch launch
  POST   /api/v1/pipelines/events                           — Nextflow weblog receiver
  GET    /api/v1/pipelines/{run_id}                         — run detail
  GET    /api/v1/pipelines/{run_id}/tasks                   — paginated task list
  GET    /api/v1/pipelines/{run_id}/events                  — paginated events
  POST   /api/v1/pipelines/{run_id}/resume                  — resume FAILED run
  POST   /api/v1/pipelines/custom                           — BYOP skeleton
  POST   /api/v1/pipelines/{catalog_id}/promote             — promote tier
  POST   /api/v1/pipelines/{run_id}/results/{result_type}   — parser registration
"""

from __future__ import annotations

import hmac
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, ValidationError, field_validator

from backend.audit import AuditActions, log_audit
from backend.auth.guards import (
    get_current_user,
    get_user_lab_membership,
    require_capability,
)
from backend.config import get_settings
from backend.database import execute_query, execute_write, get_db_dep
from backend.pagination import paginate
from backend.pipeline_config import (
    NoProfileAvailableError,
    ProfileNotFoundError,
    compute_pipeline_compatibility,
    generate_run_config,
    new_pipeline_token,
    new_run_id,
    render_nextflow_config,
    resolve_profile,
    result_uri_for,
    submit_to_batch,
    work_dir_for,
    write_run_config,
)
from backend.pipeline_config.groovy_safe import validate_groovy_safe
from backend.pipeline_results_loader import load_pipeline_results
from backend.pipeline_schemas import RESULT_SCHEMAS
from backend.responses import error, success, success_list

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pipelines", tags=["pipelines"])


# ── Serialisation helpers ─────────────────────────────────────────────────────


def _serialise(row: dict | None) -> dict:
    """Turn datetime / Decimal values into JSON-friendly scalars."""
    if row is None:
        return {}
    out: dict[str, Any] = {}
    for key, value in row.items():
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def _user_has_lab_access(user: dict, lab_id: int | None, db) -> bool:
    if user.get("is_platform_admin"):
        return True
    if lab_id is None:
        return False
    if get_user_lab_membership(user["id"], lab_id):
        return True
    rows = execute_query(
        "SELECT 1 FROM project_membership pm "
        "JOIN projects p ON p.id = pm.project_id "
        "WHERE pm.user_id = :uid AND p.lab_id = :lid LIMIT 1",
        {"uid": user["id"], "lid": lab_id},
        conn=db,
    )
    return bool(rows)


def _fetch_run(run_id: str, db) -> dict | None:
    rows = execute_query(
        "SELECT * FROM pipeline_runs WHERE run_id = :rid LIMIT 1",
        {"rid": run_id},
        conn=db,
    )
    return rows[0] if rows else None


# ── GET / ────────────────────────────────────────────────────────────────────


@router.get("/")
def list_pipeline_runs(
    request: Request,
    user_id: int | None = None,
    lab_id: int | None = None,
    project_id: int | None = None,
    status: str | None = None,
    pipeline_name: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort_by: str = "launched_at",
    sort_dir: str = "desc",
    db=Depends(get_db_dep),  # noqa: B008
):
    """Paginated run list scoped to the caller's visibility.

    Platform admins see every run; everyone else sees only runs in labs
    they belong to (matching the lab_id stored on each run) OR runs they
    launched themselves. Query params are additive filters inside that
    visibility window.
    """
    user = get_current_user(request)

    where: list[str] = []
    params: dict = {}
    if not user.get("is_platform_admin"):
        where.append(
            "(launched_by_id = :me OR lab_id IN "
            "(SELECT lab_id FROM lab_membership WHERE user_id = :me))"
        )
        params["me"] = user["id"]

    if user_id is not None:
        where.append("launched_by_id = :user_id")
        params["user_id"] = user_id
    if lab_id is not None:
        where.append("lab_id = :lab_id")
        params["lab_id"] = lab_id
    if project_id is not None:
        where.append("project_id = :project_id")
        params["project_id"] = project_id
    if status:
        where.append("status = :status")
        params["status"] = status
    if pipeline_name:
        where.append("pipeline_name = :pipeline_name")
        params["pipeline_name"] = pipeline_name

    where_sql = " WHERE " + " AND ".join(where) if where else ""
    base_query = f"SELECT * FROM pipeline_runs{where_sql}"
    rows, total = paginate(
        query=base_query,
        params=params,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    # strip the pipeline token — only the wrapper needs it
    out = []
    for r in rows:
        d = _serialise(r)
        d.pop("pipeline_token", None)
        out.append(d)
    return success_list(data=out, page=page, per_page=per_page, total=total)


# ── POST /launch ──────────────────────────────────────────────────────────────


class LaunchRequest(BaseModel):
    pipeline_id: int
    sample_ids: list[str] = Field(..., min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    project_id: int
    override_soft_warnings: bool = False
    # P0g G-4: optional execution-profile selectors. profile_id wins when
    # both are provided. When neither is supplied, the resolver falls back
    # to (a) the pipeline's lowest-priority default profile, then (b) the
    # deployment-default profile, then (c) the legacy GCP-Batch generator.
    profile_name: str | None = None
    profile_id: str | None = None
    # P0h H-3: per-launch Slurm account override. The active execution
    # profile carries a default ``config_overrides.account`` (the lab
    # or department's ledger); ``launch_account`` lets a lab member
    # charge a specific grant for one run without mutating the profile.
    # Only meaningful when the resolved profile's executor is SLURM —
    # rejecting the field on other executors keeps the override surface
    # narrow to the only place it has semantics.
    #
    # P0c multi-tenancy middleware will validate the override against
    # the user's lab memberships before this PR ships in production;
    # today the override is accepted verbatim with an audit row capturing
    # the actor + value (see SLURM_LAUNCH_ACCOUNT_OVERRIDE).
    launch_account: str | None = None


def _authorize_and_resolve_launch_inputs(
    payload: LaunchRequest, user: dict, db: Any
) -> tuple[int | None, dict | None, list[dict] | None, list[int] | None, Any]:
    """Project/lab access, catalog lookup, sample resolution + access, broken-inputs gate.

    Returns (lab_id, catalog, sample_rows, sample_pks, err). Exactly one of
    (lab_id, catalog, sample_rows, sample_pks) vs err is populated.
    """
    # Project + lab scope
    proj_rows = execute_query(
        "SELECT id, lab_id FROM projects WHERE id = :id LIMIT 1",
        {"id": payload.project_id},
        conn=db,
    )
    if not proj_rows:
        return (
            None,
            None,
            None,
            None,
            error("NOT_FOUND", f"Project {payload.project_id} not found.", status_code=404),
        )
    lab_id = proj_rows[0]["lab_id"]

    if not _user_has_lab_access(user, lab_id, db):
        return (
            None,
            None,
            None,
            None,
            error(
                "ACCESS_DENIED",
                "You do not have access to this project's lab.",
                status_code=403,
            ),
        )

    catalog_rows = execute_query(
        "SELECT * FROM pipeline_catalog WHERE id = :id AND is_active = TRUE LIMIT 1",
        {"id": payload.pipeline_id},
        conn=db,
    )
    if not catalog_rows:
        return (
            None,
            None,
            None,
            None,
            error(
                "NOT_FOUND",
                f"Pipeline {payload.pipeline_id} not found or inactive.",
                status_code=404,
            ),
        )
    catalog = catalog_rows[0]

    # Resolve requested samples — use sample_id (string) since that's canonical
    sample_rows = execute_query(
        "SELECT id, sample_id, organism_name, source_type, scrub_status, "
        "quality_status, lab_id FROM samples WHERE sample_id = ANY(:ids)",
        {"ids": payload.sample_ids},
        conn=db,
    )
    missing = set(payload.sample_ids) - {s["sample_id"] for s in sample_rows}
    if missing:
        return (
            None,
            None,
            None,
            None,
            error(
                "NOT_FOUND",
                "One or more samples do not exist.",
                detail={"missing_sample_ids": sorted(missing)},
                status_code=404,
            ),
        )

    # Every sample must belong to a lab the caller can access
    for sample in sample_rows:
        if not _user_has_lab_access(user, sample.get("lab_id"), db):
            return (
                None,
                None,
                None,
                None,
                error(
                    "ACCESS_DENIED",
                    f"You do not have access to sample {sample['sample_id']}.",
                    status_code=403,
                ),
            )

    # Phase P0f F-8: refuse the launch if any input sample_files row is
    # already known-BROKEN. The verification job (F-5) is the source of
    # truth for storage_state; this is a fast read of that state, not a
    # re-stat. See spec.md Phase P0f "Pre-launch verification" rule.
    sample_pks = [s["id"] for s in sample_rows]
    broken_files = execute_query(
        "SELECT sf.id AS sample_files_id, s.sample_id AS sample_id, "
        "       sf.uri, sf.last_verification_status "
        "FROM sample_files sf "
        "JOIN samples s ON s.id = sf.sample_id_fk "
        "WHERE sf.sample_id_fk = ANY(:sids) "
        "  AND sf.is_archived = FALSE "
        "  AND sf.storage_state = 'BROKEN' "
        "ORDER BY s.sample_id, sf.id",
        {"sids": sample_pks},
        conn=db,
    )
    if broken_files:
        n = len(broken_files)
        return (
            None,
            None,
            None,
            None,
            error(
                "BROKEN_INPUTS",
                f"Cannot launch pipeline: {n} input "
                f"file{'s' if n != 1 else ''} "
                f"{'are' if n != 1 else 'is'} in BROKEN state.",
                detail={
                    "broken_files": [
                        {
                            "sample_files_id": row["sample_files_id"],
                            "sample_id": row["sample_id"],
                            "uri": row["uri"],
                            "last_verification_status": row["last_verification_status"],
                        }
                        for row in broken_files
                    ],
                    "suggestion": (
                        "Re-locate or re-upload the broken files, or remove "
                        "the affected samples from the launch request. Run "
                        "`jackpot files verify --sample <sample_id>` to "
                        "re-check current state."
                    ),
                },
                status_code=400,
            ),
        )

    return lab_id, catalog, sample_rows, sample_pks, None


def _resolve_launch_parameters(
    catalog: dict, sample_rows: list[dict], payload: LaunchRequest, db: Any
) -> tuple[Any, Any, Any, Any]:
    """Compatibility gate, P0g G-4 profile resolution, P0h H-3 account override,
    P0h H-6 reachability.

    Returns (report, profile, effective_profile, err). Exactly one of
    (report, profile, effective_profile) vs err is populated.
    """
    report = compute_pipeline_compatibility(catalog, sample_rows)
    if report.is_hard_blocked:
        return (
            None,
            None,
            None,
            error(
                "INCOMPATIBLE_SAMPLES",
                "Pipeline is incompatible with one or more selected samples.",
                detail=report.to_dict(),
                status_code=422,
            ),
        )
    if report.has_warnings and not payload.override_soft_warnings:
        return (
            None,
            None,
            None,
            error(
                "SOFT_WARNINGS",
                "Pipeline launch has warnings; re-submit with "
                "override_soft_warnings=true to proceed.",
                detail=report.to_dict(),
                status_code=202,
            ),
        )

    # ── P0g G-4: profile resolution ─────────────────────────────────────
    # The pipeline_default_profile association uses UUID pipeline_id;
    # the catalog table is SERIAL-keyed, so we stringify the integer id
    # for now (matches the FK-fallback documented in migration
    # bac8dbb11c0b). Falls through cleanly to NoProfileAvailableError
    # when nothing is associated.
    profile = None
    try:
        profile = resolve_profile(
            db_conn=db,
            pipeline_id=str(catalog["id"]),
            profile_name=payload.profile_name,
            profile_id=payload.profile_id,
        )
    except ProfileNotFoundError as exc:
        return (
            None,
            None,
            None,
            error(
                "PROFILE_NOT_FOUND",
                str(exc),
                detail={
                    "requested": exc.requested,
                    "available_profiles": exc.available_profile_names,
                },
                status_code=400,
            ),
        )
    except NoProfileAvailableError:
        # Resolution chain exhausted — fall through to the legacy
        # GCP-Batch path below. Coexistence is intentional per the G-4
        # design; deletion of the legacy path is a follow-up PR.
        profile = None

    # ── P0h H-3: Slurm per-launch account override ──────────────────────
    # ``launch_account`` only carries semantics when the active profile
    # is SLURM. Reject the field on every other code path so an operator
    # cannot pass a value that silently does nothing — the rejection is
    # the single signal that the field was misused. The legacy
    # GCP-Batch fallback (profile is None) is also a non-Slurm path and
    # rejected here.
    if payload.launch_account is not None and (
        profile is None or (profile.executor_type or "").upper() != "SLURM"
    ):
        return (
            None,
            None,
            None,
            error(
                "LAUNCH_ACCOUNT_NOT_APPLICABLE",
                "launch_account override is only valid when the resolved "
                "execution profile uses the SLURM executor.",
                status_code=400,
            ),
        )
    # P0c stub: per-launch override is accepted verbatim. P0c
    # multi-tenancy middleware, when it lands, will validate the
    # supplied account against the user's lab memberships and reject
    # values the user is not authorised to charge against.
    effective_profile = profile
    if profile is not None and payload.launch_account is not None:
        from dataclasses import replace as _dc_replace

        merged_overrides = dict(profile.config_overrides or {})
        merged_overrides["account"] = payload.launch_account
        effective_profile = _dc_replace(profile, config_overrides=merged_overrides)

    # ── P0h H-6: pre-launch Slurm reachability ──────────────────────────
    # Refines F-8 (broken-inputs check). When the resolved profile
    # targets SLURM, run ``sinfo`` on the API host before queueing the
    # run so a downed cluster fails fast at submit time rather than
    # after a 15-minute Slurm client timeout. The check is cached for
    # ``slurm_reachability_cache_seconds`` to keep bulk launches cheap.
    if effective_profile is not None and (effective_profile.executor_type or "").upper() == "SLURM":
        from backend.pipeline_config.cluster_reachability import (
            check_slurm_reachability,
        )

        overrides = effective_profile.config_overrides or {}
        reach = check_slurm_reachability(
            account=overrides.get("account"),
            partition=overrides.get("queue") or overrides.get("partition"),
        )
        if not reach.reachable:
            return (
                None,
                None,
                None,
                error(
                    "SLURM_UNREACHABLE",
                    "Slurm cluster is not reachable from the API host; refusing "
                    "to queue the launch. Run `jackpot doctor slurm "
                    "--check-cluster` to diagnose.",
                    detail={
                        "code": reach.code,
                        "detail": reach.detail,
                    },
                    status_code=400,
                ),
            )

    return report, profile, effective_profile, None


def _resolve_lab_slug(lab_id: int, db: Any) -> str:
    lab_rows = execute_query(
        "SELECT project_prefix, display_name FROM labs WHERE id = :id LIMIT 1",
        {"id": lab_id},
        conn=db,
    )
    return lab_rows[0].get("project_prefix") or lab_rows[0].get("display_name") or f"lab-{lab_id}"


def _render_launch_config(
    profile: Any,
    effective_profile: Any,
    catalog: dict,
    run_id: str,
    pipeline_token: str,
    lab_slug: str,
    weblog_url: str,
    result_registration_url: str,
    settings: Any,
) -> tuple[str, str, str, dict[str, Any]]:
    """Legacy-vs-profile-driven Nextflow config generation. Returns
    (work_dir, result_uri, config_path, launch_metadata_extra)."""
    if profile is None:
        # Legacy path — single hardcoded GCP-Batch generator.
        work_dir = work_dir_for(run_id)
        result_uri = result_uri_for(run_id)
        config_text = generate_run_config(
            run_id=run_id,
            pipeline_name=catalog["pipeline_name"],
            pipeline_version=catalog.get("pipeline_version"),
            lab_slug=lab_slug,
            pipeline_token=pipeline_token,
            work_dir=work_dir,
            result_uri=result_uri,
        )
        config_path = f"/tmp/jackpot_{run_id}.config"  # noqa: S108
        try:
            Path(config_path).write_text(config_text)
        except OSError as exc:
            logger.warning("Could not write run config to %s: %s", config_path, exc)
        launch_metadata_extra: dict[str, Any] = {}
    else:
        # Profile-driven path — render via profile_renderer + write
        # via fsspec into <work_dir>/runs/<run_id>/jackpot_run.config.
        # When H-3's launch_account override applied, ``effective_profile``
        # is a copy of ``profile`` with ``config_overrides.account``
        # replaced; otherwise the two are the same object.
        assert effective_profile is not None  # narrowed by `profile is None` branch above
        profile_work_dir_base = effective_profile.work_dir or settings.work_dir
        work_dir = f"{profile_work_dir_base.rstrip('/')}/runs/{run_id}/work"
        result_uri = result_uri_for(run_id)
        config_text = render_nextflow_config(
            profile=effective_profile,
            pipeline=catalog,
            run_id=run_id,
            weblog_url=weblog_url,
            result_registration_url=result_registration_url,
            pipeline_token=pipeline_token,
            work_dir=profile_work_dir_base,
        )
        try:
            config_path = write_run_config(
                rendered_config=config_text,
                work_dir=profile_work_dir_base,
                run_id=run_id,
            )
        except (OSError, ValueError) as exc:
            logger.warning("Could not write profile run config: %s", exc)
            config_path = f"/tmp/jackpot_{run_id}.config"  # noqa: S108
        launch_metadata_extra = {
            "profile_id": str(profile.profile_id),
            "profile_name": profile.name,
            "executor_type": profile.executor_type,
            "container_engine": profile.container_engine,
        }

    return work_dir, result_uri, config_path, launch_metadata_extra


def _persist_run_row(
    payload: LaunchRequest,
    lab_id: int,
    user: dict,
    catalog: dict,
    sample_pks: list[int],
    run_id: str,
    pipeline_token: str,
    work_dir: str,
    result_uri: str,
    report: Any,
    db: Any,
) -> dict:
    insert_rows = execute_write(
        """
        INSERT INTO pipeline_runs
            (lab_id, project_id, launched_by_id,
             pipeline_name, pipeline_version,
             sample_ids, status, launcher_type,
             result_uri, work_dir, run_id, pipeline_token,
             parameters, soft_warnings, pipeline_catalog_id,
             parser_version_used)
        VALUES
            (:lab_id, :project_id, :launched_by_id,
             :pipeline_name, :pipeline_version,
             :sample_ids, 'QUEUED', 'native',
             :result_uri, :work_dir, :run_id, :pipeline_token,
             CAST(:parameters AS JSONB), CAST(:soft_warnings AS JSONB),
             :catalog_id, :parser_version)
        RETURNING *
        """,
        {
            "lab_id": lab_id,
            "project_id": payload.project_id,
            "launched_by_id": user["id"],
            "pipeline_name": catalog["pipeline_name"],
            "pipeline_version": catalog.get("pipeline_version"),
            "sample_ids": sample_pks,
            "result_uri": result_uri,
            "work_dir": work_dir,
            "run_id": run_id,
            "pipeline_token": pipeline_token,
            "parameters": json.dumps(payload.parameters),
            "soft_warnings": json.dumps(report.soft_warnings),
            "catalog_id": catalog["id"],
            "parser_version": catalog.get("parser_version"),
        },
        conn=db,
    )
    return insert_rows[0]


def _log_launch_audit(
    user: dict,
    run_id: str,
    catalog: dict,
    payload: LaunchRequest,
    lab_id: int,
    report: Any,
    profile: Any,
    effective_profile: Any,
    launch_metadata_extra: dict[str, Any],
    db: Any,
) -> None:
    log_audit(
        action=AuditActions.CREATE_PIPELINE_RUN,
        actor_id=user["id"],
        resource_type="pipeline_run",
        resource_id=run_id,
        before=None,
        after={
            "pipeline_name": catalog["pipeline_name"],
            "pipeline_version": catalog.get("pipeline_version"),
            "sample_ids": payload.sample_ids,
        },
        metadata={
            "lab_id": lab_id,
            "project_id": payload.project_id,
            "soft_warnings": report.soft_warnings,
            "overridden": payload.override_soft_warnings,
            **launch_metadata_extra,
        },
        db_conn=db,
    )
    if profile is not None:
        # P0g G-4: supplemental audit row recording the profile path was
        # taken. CREATE_PIPELINE_RUN above is the canonical "run created"
        # event; LAUNCH_WITH_PROFILE makes profile-usage queries cheap
        # without forcing analysts to crack open the metadata column.
        log_audit(
            action=AuditActions.LAUNCH_WITH_PROFILE,
            actor_id=user["id"],
            resource_type="pipeline_run",
            resource_id=run_id,
            before=None,
            after={
                "profile_id": str(profile.profile_id),
                "profile_name": profile.name,
                "executor_type": profile.executor_type,
                "container_engine": profile.container_engine,
            },
            metadata={
                "lab_id": lab_id,
                "project_id": payload.project_id,
            },
            db_conn=db,
        )

    # P0h H-3: separate audit row for launch_account overrides so a
    # security review can grep for SLURM_LAUNCH_ACCOUNT_OVERRIDE rows
    # without joining audit_log against pipeline_runs.metadata. The row
    # captures actor + before (profile default) and after (override
    # value); P0c will add validation context once it lands.
    if payload.launch_account is not None and effective_profile is not None and profile is not None:
        log_audit(
            action=AuditActions.SLURM_LAUNCH_ACCOUNT_OVERRIDE,
            actor_id=user["id"],
            resource_type="pipeline_run",
            resource_id=run_id,
            before={"account": (profile.config_overrides or {}).get("account")},
            after={"account": payload.launch_account},
            metadata={
                "lab_id": lab_id,
                "project_id": payload.project_id,
                "profile_id": str(profile.profile_id),
                "profile_name": profile.name,
            },
            db_conn=db,
        )


@router.post("/launch")
def launch_pipeline(
    payload: LaunchRequest,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)

    lab_id, catalog, sample_rows, sample_pks, err = _authorize_and_resolve_launch_inputs(
        payload, user, db
    )
    if err is not None:
        return err
    # Narrowed by `err is None`: _authorize_and_resolve_launch_inputs only
    # returns an err-less tuple when all four are populated.
    assert lab_id is not None
    assert catalog is not None
    assert sample_rows is not None
    assert sample_pks is not None

    report, profile, effective_profile, err = _resolve_launch_parameters(
        catalog, sample_rows, payload, db
    )
    if err is not None:
        return err
    # Narrowed by `err is None`; profile/effective_profile legitimately
    # stay None on the legacy (no-profile) launch path — only report is
    # guaranteed non-None here.
    assert report is not None

    lab_slug = _resolve_lab_slug(lab_id, db)

    run_id = new_run_id()
    pipeline_token = new_pipeline_token()
    settings = get_settings()
    api_url = settings.jackpot_api_url
    weblog_url = f"{api_url.rstrip('/')}/api/v1/pipelines/events"
    result_registration_url = f"{api_url.rstrip('/')}/api/v1/pipelines/{run_id}/results"

    work_dir, result_uri, config_path, launch_metadata_extra = _render_launch_config(
        profile,
        effective_profile,
        catalog,
        run_id,
        pipeline_token,
        lab_slug,
        weblog_url,
        result_registration_url,
        settings,
    )

    run = _persist_run_row(
        payload,
        lab_id,
        user,
        catalog,
        sample_pks,
        run_id,
        pipeline_token,
        work_dir,
        result_uri,
        report,
        db,
    )

    submit_to_batch(
        run_id=run_id,
        pipeline_uri=catalog.get("pipeline_uri") or catalog["pipeline_name"],
        pipeline_version=catalog.get("pipeline_version"),
        pipeline_profile=(profile.name if profile else catalog.get("default_profile")),
        config_path=config_path,
        work_dir=work_dir,
        result_uri=result_uri,
    )

    _log_launch_audit(
        user,
        run_id,
        catalog,
        payload,
        lab_id,
        report,
        profile,
        effective_profile,
        launch_metadata_extra,
        db,
    )

    response_payload: dict[str, Any] = {
        "run_id": run_id,
        "status": "QUEUED",
        "pipeline_run": _serialise(run),
    }
    if profile is not None:
        response_payload["profile"] = {
            "profile_id": str(profile.profile_id),
            "name": profile.name,
            "executor_type": profile.executor_type,
            "container_engine": profile.container_engine,
        }
    return success(
        data=response_payload,
        status_code=201,
    )


# ── POST /events (Nextflow weblog) ────────────────────────────────────────────


def _handle_workflow_complete(
    run_id: str,
    event_body: dict[str, Any],
    conn: Any,
) -> None:
    """Workflow-complete handler: updates run status and loads results."""
    rows = execute_query(
        """
        SELECT result_uri, pipeline_name, pipeline_version, launched_by_id
        FROM pipeline_runs
        WHERE run_id = :run_id
        """,
        {"run_id": run_id},
        conn=conn,
    )
    if not rows:
        logger.error("workflow.complete received for unknown run_id: %s", run_id)
        return

    run = rows[0]
    workflow_stats = event_body.get("workflow", {})
    success_flag = workflow_stats.get("success", False)
    status = "COMPLETED" if success_flag else "FAILED"

    execute_write(
        """
        UPDATE pipeline_runs
        SET status = :status, completed_at = NOW()
        WHERE run_id = :run_id
        """,
        {"status": status, "run_id": run_id},
        conn=conn,
    )

    if not success_flag or not run.get("result_uri"):
        if not run.get("result_uri"):
            logger.warning("pipeline_run %s has no result_uri — skipping result load", run_id)
        return

    loader_result = load_pipeline_results(
        run_id=run_id,
        result_uri=run["result_uri"],
        pipeline_name=run["pipeline_name"],
        pipeline_version=run["pipeline_version"],
        launched_by_id=run["launched_by_id"],
        conn=conn,
    )
    if not loader_result.success:
        logger.error("Result loader errors for run %s: %s", run_id, loader_result.errors)


@router.post("/events")
def receive_pipeline_event(
    body: dict[str, Any],
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
) -> dict:
    """
    Nextflow weblog receiver.

    No user JWT — the per-run ``X-Pipeline-Token`` minted at launch
    authenticates the callback. The run_id must be present in the body
    and must match an existing pipeline_runs row with a matching token.

    P0h H-4 redundancy contract
    ---------------------------

    The H-4 sidecar log poller (``backend.log_poller``) tails
    ``<work_dir>/runs/<run_id>/.nextflow.log`` on a 30-second cadence
    and emits the same workflow-state transitions for clusters whose
    compute nodes can't reach this endpoint. Both paths can fire for
    the same run; the receiver tolerates duplicate events because:

    - ``pipeline_runs.status`` transitions are idempotent — re-applying
      ``status = 'RUNNING'`` is a no-op, and ``_handle_workflow_complete``
      re-sets the same terminal status when called twice.
    - ``pipeline_tasks`` upserts on ``(run_id, task_id)`` so duplicate
      ``process.*`` events update the same row.
    - ``pipeline_events`` accepts duplicate inserts; the table is
      diagnostic and a small replay overhead is acceptable. Consumers
      that need uniqueness should derive over ``run_id + event_type
      + trace.taskId`` themselves.
    """
    event = body.get("event", "")
    run_id = body.get("runId") or body.get("run_id", "")
    if not run_id:
        raise HTTPException(status_code=400, detail="Missing runId in event body")

    run = _fetch_run(run_id, db)
    if not run:
        raise HTTPException(status_code=404, detail=f"Unknown run_id: {run_id}")

    supplied_token = request.headers.get("X-Pipeline-Token", "")
    expected_token = run.get("pipeline_token") or ""
    if not expected_token or not hmac.compare_digest(supplied_token, expected_token):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Pipeline-Token")

    # Always persist the raw event
    execute_write(
        """
        INSERT INTO pipeline_events (run_id, event_type, event_json)
        VALUES (:run_id, :event_type, CAST(:event_json AS JSONB))
        """,
        {
            "run_id": run_id,
            "event_type": event,
            "event_json": json.dumps(body),
        },
        conn=db,
    )

    if event == "workflow.started":
        execute_write(
            """
            UPDATE pipeline_runs
            SET status = 'RUNNING', launched_at = NOW()
            WHERE run_id = :run_id
            """,
            {"run_id": run_id},
            conn=db,
        )

    elif event == "workflow.complete":
        _handle_workflow_complete(run_id=run_id, event_body=body, conn=db)

    elif event in ("process.submitted", "process.started", "process.completed", "process.failed"):
        trace = body.get("trace", {})
        if trace:
            mem_bytes = trace.get("memory") or 0
            memory_mb = mem_bytes // (1024 * 1024) if mem_bytes else None
            execute_write(
                """
                INSERT INTO pipeline_tasks
                    (run_id, task_id, task_name, status,
                     container, cpus, memory_mb, duration_ms,
                     submitted_at, started_at, completed_at, updated_at)
                VALUES
                    (:run_id, :task_id, :task_name, :status,
                     :container, :cpus, :memory_mb, :duration_ms,
                     :submitted_at, :started_at, :completed_at, NOW())
                ON CONFLICT (run_id, task_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    duration_ms = EXCLUDED.duration_ms,
                    completed_at = EXCLUDED.completed_at,
                    updated_at = NOW()
                """,
                {
                    "run_id": run_id,
                    "task_id": str(trace.get("taskId", "")),
                    "task_name": trace.get("name", ""),
                    "status": trace.get("status", ""),
                    "container": trace.get("container", ""),
                    "cpus": trace.get("cpus"),
                    "memory_mb": memory_mb,
                    "duration_ms": trace.get("duration"),
                    "submitted_at": trace.get("submit"),
                    "started_at": trace.get("start"),
                    "completed_at": trace.get("complete"),
                },
                conn=db,
            )
        if event == "process.failed":
            execute_write(
                "UPDATE pipeline_runs SET status = 'FAILED' "
                "WHERE run_id = :run_id AND status NOT IN ('COMPLETED', 'FAILED')",
                {"run_id": run_id},
                conn=db,
            )

    return {"status": "ok", "event": event, "run_id": run_id}


# ── GET /{run_id} ─────────────────────────────────────────────────────────────


@router.get("/{run_id}")
def get_pipeline_run(
    run_id: str,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    run = _fetch_run(run_id, db)
    if not run:
        return error("NOT_FOUND", f"Run {run_id} not found.", status_code=404)
    if not _user_has_lab_access(user, run.get("lab_id"), db):
        return error("ACCESS_DENIED", "You do not have access to this run.", status_code=403)

    recent_events = execute_query(
        "SELECT id, event_type, received_at FROM pipeline_events "
        "WHERE run_id = :rid ORDER BY received_at DESC LIMIT 20",
        {"rid": run_id},
        conn=db,
    )

    task_summary_rows = execute_query(
        "SELECT status, COUNT(*) AS count FROM pipeline_tasks WHERE run_id = :rid GROUP BY status",
        {"rid": run_id},
        conn=db,
    )
    task_summary = {r["status"] or "UNKNOWN": r["count"] for r in task_summary_rows}

    run_dict = _serialise(run)
    run_dict.pop("pipeline_token", None)
    run_dict["recent_events"] = [_serialise(e) for e in recent_events]
    run_dict["task_summary"] = task_summary
    return success(data=run_dict)


# ── GET /{run_id}/tasks ───────────────────────────────────────────────────────


@router.get("/{run_id}/tasks")
def list_pipeline_tasks(
    run_id: str,
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort_by: str = "updated_at",
    sort_dir: str = "desc",
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    run = _fetch_run(run_id, db)
    if not run:
        return error("NOT_FOUND", f"Run {run_id} not found.", status_code=404)
    if not _user_has_lab_access(user, run.get("lab_id"), db):
        return error("ACCESS_DENIED", "You do not have access to this run.", status_code=403)

    base_query = "SELECT * FROM pipeline_tasks WHERE run_id = :rid"
    rows, total = paginate(
        query=base_query,
        params={"rid": run_id},
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return success_list(
        data=[_serialise(r) for r in rows],
        page=page,
        per_page=per_page,
        total=total,
    )


# ── GET /{run_id}/events ──────────────────────────────────────────────────────


@router.get("/{run_id}/events")
def list_pipeline_events(
    run_id: str,
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort_dir: str = "desc",
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    run = _fetch_run(run_id, db)
    if not run:
        return error("NOT_FOUND", f"Run {run_id} not found.", status_code=404)
    if not _user_has_lab_access(user, run.get("lab_id"), db):
        return error("ACCESS_DENIED", "You do not have access to this run.", status_code=403)

    base_query = "SELECT * FROM pipeline_events WHERE run_id = :rid"
    rows, total = paginate(
        query=base_query,
        params={"rid": run_id},
        page=page,
        per_page=per_page,
        sort_by="received_at",
        sort_dir=sort_dir,
    )
    return success_list(
        data=[_serialise(r) for r in rows],
        page=page,
        per_page=per_page,
        total=total,
    )


# ── POST /{run_id}/resume ─────────────────────────────────────────────────────


class ResumeRequest(BaseModel):
    parameters: dict[str, Any] | None = None


@router.post("/{run_id}/resume", status_code=201)
def resume_pipeline(
    run_id: str,
    payload: ResumeRequest,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    previous = _fetch_run(run_id, db)
    if not previous:
        return error("NOT_FOUND", f"Run {run_id} not found.", status_code=404)
    if not _user_has_lab_access(user, previous.get("lab_id"), db):
        return error("ACCESS_DENIED", "You do not have access to this run.", status_code=403)

    if (previous.get("status") or "").upper() != "FAILED":
        return error(
            "INVALID_STATE",
            f"Only FAILED runs can be resumed — this run is {previous.get('status')!r}.",
            status_code=400,
        )

    new_id = new_run_id()
    pipeline_token = new_pipeline_token()
    # Reuse the original work_dir for Nextflow -resume (cache hit)
    work_dir = previous.get("work_dir") or work_dir_for(new_id)
    result_uri = result_uri_for(new_id)

    lab_rows = execute_query(
        "SELECT project_prefix, display_name FROM labs WHERE id = :id LIMIT 1",
        {"id": previous.get("lab_id")},
        conn=db,
    )
    lab_slug = "unknown"
    if lab_rows:
        lab_slug = lab_rows[0].get("project_prefix") or lab_rows[0].get("display_name") or "unknown"

    config_text = generate_run_config(
        run_id=new_id,
        pipeline_name=previous["pipeline_name"],
        pipeline_version=previous.get("pipeline_version"),
        lab_slug=lab_slug,
        pipeline_token=pipeline_token,
        work_dir=work_dir,
        result_uri=result_uri,
    )
    config_path = f"/tmp/jackpot_{new_id}.config"  # noqa: S108
    try:
        Path(config_path).write_text(config_text)
    except OSError as exc:
        logger.warning("Could not write resume config to %s: %s", config_path, exc)

    merged_params = dict(previous.get("parameters") or {})
    if payload.parameters:
        merged_params.update(payload.parameters)

    new_rows = execute_write(
        """
        INSERT INTO pipeline_runs
            (lab_id, project_id, launched_by_id,
             pipeline_name, pipeline_version,
             sample_ids, status, launcher_type,
             result_uri, work_dir, run_id, pipeline_token,
             parameters, soft_warnings, pipeline_catalog_id,
             parser_version_used)
        VALUES
            (:lab_id, :project_id, :launched_by_id,
             :pipeline_name, :pipeline_version,
             :sample_ids, 'QUEUED', 'native',
             :result_uri, :work_dir, :run_id, :pipeline_token,
             CAST(:parameters AS JSONB), CAST(:soft_warnings AS JSONB),
             :catalog_id, :parser_version)
        RETURNING *
        """,
        {
            "lab_id": previous.get("lab_id"),
            "project_id": previous.get("project_id"),
            "launched_by_id": user["id"],
            "pipeline_name": previous["pipeline_name"],
            "pipeline_version": previous.get("pipeline_version"),
            "sample_ids": previous.get("sample_ids") or [],
            "result_uri": result_uri,
            "work_dir": work_dir,
            "run_id": new_id,
            "pipeline_token": pipeline_token,
            "parameters": json.dumps(merged_params),
            "soft_warnings": json.dumps(previous.get("soft_warnings") or []),
            "catalog_id": previous.get("pipeline_catalog_id"),
            "parser_version": previous.get("parser_version_used"),
        },
        conn=db,
    )
    new_run = new_rows[0]

    execute_write(
        """
        INSERT INTO pipeline_restarts (new_run_id, previous_run_id, resumed_by_id)
        VALUES (:new_id, :prev_id, :uid)
        """,
        {"new_id": new_id, "prev_id": run_id, "uid": user["id"]},
        conn=db,
    )

    submit_to_batch(
        run_id=new_id,
        pipeline_uri=previous["pipeline_name"],
        pipeline_version=previous.get("pipeline_version"),
        pipeline_profile=None,
        config_path=config_path,
        work_dir=work_dir,
        result_uri=result_uri,
        resume=True,
    )

    log_audit(
        action=AuditActions.RESUME_PIPELINE_RUN,
        actor_id=user["id"],
        resource_type="pipeline_run",
        resource_id=new_id,
        before=None,
        after={"resumed_from": run_id},
        metadata={"lab_id": previous.get("lab_id"), "work_dir": work_dir},
        db_conn=db,
    )

    return success(
        data={
            "run_id": new_id,
            "status": "QUEUED",
            "resumed_from": run_id,
            "pipeline_run": _serialise(new_run),
        },
        status_code=201,
    )


# ── POST /custom (BYOP skeleton) ──────────────────────────────────────────────


class CustomPipelineRequest(BaseModel):
    project_id: int
    pipeline_name: str = Field(..., min_length=1, max_length=255)
    github_url: str = Field(..., min_length=1)
    revision: str = Field(..., min_length=1)
    parameter_schema: dict[str, Any] = Field(default_factory=dict)

    # R-1 #7: pipeline_name lands in pipeline_catalog and is later
    # interpolated into a Nextflow Groovy config. Reject characters
    # dangerous in Groovy string contexts at write time so a malicious
    # value can't reach the renderer in the first place. The
    # render-time groovy_escape filter is the second line of defense.
    @field_validator("pipeline_name")
    @classmethod
    def _validate_pipeline_name_groovy_safe(cls, v: str) -> str:
        return validate_groovy_safe(v, field_name="pipeline_name") or v


@router.post("/custom", status_code=202)
def register_custom_pipeline(
    payload: CustomPipelineRequest,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    proj_rows = execute_query(
        "SELECT id, lab_id FROM projects WHERE id = :id LIMIT 1",
        {"id": payload.project_id},
        conn=db,
    )
    if not proj_rows:
        return error("NOT_FOUND", f"Project {payload.project_id} not found.", status_code=404)
    require_capability("pipeline:register_custom")(user, lab_id=proj_rows[0]["lab_id"])

    if not (payload.github_url.startswith("https://") or payload.github_url.startswith("git@")):
        return error(
            "INVALID_URL",
            "github_url must start with https:// or git@.",
            status_code=422,
        )

    try:
        rows = execute_write(
            """
            INSERT INTO project_pipelines
                (project_id, pipeline_name, github_url, revision,
                 parameter_schema, status, created_by_id)
            VALUES
                (:project_id, :pipeline_name, :github_url, :revision,
                 CAST(:parameter_schema AS JSONB), 'UNVERIFIED', :uid)
            RETURNING *
            """,
            {
                "project_id": payload.project_id,
                "pipeline_name": payload.pipeline_name,
                "github_url": payload.github_url,
                "revision": payload.revision,
                "parameter_schema": json.dumps(payload.parameter_schema),
                "uid": user["id"],
            },
            conn=db,
        )
    except Exception as exc:  # duplicate (project_id, pipeline_name) → UniqueViolation
        logger.info(
            "BYOP insert failed for %s/%s: %s",
            payload.project_id,
            payload.pipeline_name,
            exc,
        )
        return error(
            "DUPLICATE_PIPELINE",
            f"Pipeline {payload.pipeline_name!r} already registered for this project.",
            status_code=409,
        )
    bp = rows[0]

    log_audit(
        action=AuditActions.REGISTER_CUSTOM_PIPELINE,
        actor_id=user["id"],
        resource_type="project_pipeline",
        resource_id=str(bp["id"]),
        before=None,
        after=_serialise(bp),
        metadata={"project_id": payload.project_id},
        db_conn=db,
    )

    return success(
        data={
            "status": "UNVERIFIED",
            "project_pipeline_id": bp["id"],
            "message": "BYOP registered pending verification (Month 3 feature).",
            "project_pipeline": _serialise(bp),
        },
        status_code=202,
    )


# ── POST /{catalog_id}/promote ────────────────────────────────────────────────


class PromoteRequest(BaseModel):
    target_tier: str = Field(..., pattern="^(lab|zoo)$")
    lab_id: int | None = None


@router.post("/{catalog_id}/promote")
def promote_pipeline(
    catalog_id: int,
    payload: PromoteRequest,
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    catalog_rows = execute_query(
        "SELECT * FROM pipeline_catalog WHERE id = :id LIMIT 1",
        {"id": catalog_id},
        conn=db,
    )
    if not catalog_rows:
        return error("NOT_FOUND", f"Pipeline {catalog_id} not found.", status_code=404)
    catalog = catalog_rows[0]
    current_tier = (catalog.get("tier") or "").lower()
    target = payload.target_tier.lower()

    if target == "lab":
        if current_tier != "project":
            return error(
                "INVALID_PROMOTION",
                "Only project-tier pipelines can be promoted to lab; "
                f"current tier is {current_tier!r}.",
                status_code=400,
            )
        target_lab_id = payload.lab_id or catalog.get("scope_lab_id")
        if not target_lab_id:
            return error(
                "INVALID_PROMOTION",
                "lab_id required when promoting project → lab.",
                status_code=422,
            )
        require_capability("pipeline:promote")(user, lab_id=target_lab_id)

        execute_write(
            """
            UPDATE pipeline_catalog
            SET tier = 'lab', scope_lab_id = :lid, scope_project_id = NULL,
                updated_at = NOW()
            WHERE id = :id
            """,
            {"id": catalog_id, "lid": target_lab_id},
            conn=db,
        )
        execute_write(
            """
            INSERT INTO lab_pipelines
                (lab_id, pipeline_catalog_id, promoted_by_id)
            VALUES (:lab_id, :cat_id, :uid)
            ON CONFLICT (lab_id, pipeline_catalog_id) DO NOTHING
            """,
            {"lab_id": target_lab_id, "cat_id": catalog_id, "uid": user["id"]},
            conn=db,
        )
    else:  # zoo
        if current_tier != "lab":
            return error(
                "INVALID_PROMOTION",
                "Only lab-tier pipelines can be promoted to zoo; "
                f"current tier is {current_tier!r}.",
                status_code=400,
            )
        require_capability("pipeline:promote")(user)
        execute_write(
            """
            UPDATE pipeline_catalog
            SET tier = 'zoo', scope_lab_id = NULL, scope_project_id = NULL,
                updated_at = NOW()
            WHERE id = :id
            """,
            {"id": catalog_id},
            conn=db,
        )

    log_audit(
        action=AuditActions.PROMOTE_PIPELINE,
        actor_id=user["id"],
        resource_type="pipeline_catalog",
        resource_id=str(catalog_id),
        before={"tier": current_tier},
        after={"tier": target},
        metadata={
            "lab_id": payload.lab_id,
            "promoted_from": current_tier,
            "promoted_to": target,
        },
        db_conn=db,
    )

    refreshed = execute_query(
        "SELECT * FROM pipeline_catalog WHERE id = :id LIMIT 1",
        {"id": catalog_id},
        conn=db,
    )
    return success(data=_serialise(refreshed[0] if refreshed else catalog))


# ── POST /{run_id}/results/{result_type} (parser registration) ────────────────


def _split_jsonb_fields(payload: dict) -> tuple[list[str], list[str], dict]:
    cols: list[str] = []
    placeholders: list[str] = []
    params: dict = {}
    for key, value in payload.items():
        cols.append(key)
        if isinstance(value, dict | list):
            placeholders.append(f"CAST(:{key} AS JSONB)")
            params[key] = json.dumps(value)
        else:
            placeholders.append(f":{key}")
            params[key] = value
    return cols, placeholders, params


@router.post("/{run_id}/results/{result_type}")
def register_pipeline_result(
    run_id: str,
    result_type: str,
    body: dict[str, Any],
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    """
    Parser registration endpoint.

    Parsers running inside a pipeline POST canonical result payloads here.
    The run is authenticated with a per-run ``X-Pipeline-Token`` minted
    when the pipeline was launched.
    """
    schema_cls = RESULT_SCHEMAS.get(result_type)
    if schema_cls is None:
        return error(
            "UNKNOWN_RESULT_TYPE",
            f"Unknown result_type: {result_type}",
            detail={"allowed": sorted(RESULT_SCHEMAS.keys())},
            status_code=422,
        )

    rows = execute_query(
        """
        SELECT pipeline_token, pipeline_name, pipeline_version
        FROM pipeline_runs
        WHERE run_id = :run_id
        """,
        {"run_id": run_id},
        conn=db,
    )
    if not rows:
        return error("RUN_NOT_FOUND", f"Unknown run_id: {run_id}", status_code=404)
    run = rows[0]

    supplied_token = request.headers.get("X-Pipeline-Token", "")
    expected_token = run.get("pipeline_token") or ""
    if not expected_token or not hmac.compare_digest(supplied_token, expected_token):
        return error("INVALID_TOKEN", "Invalid or missing X-Pipeline-Token", status_code=401)

    try:
        validated = schema_cls(**body)
    except ValidationError as exc:
        return error(
            "INVALID_PAYLOAD",
            "Payload failed schema validation",
            detail={"errors": exc.errors()},
            status_code=422,
        )

    record = validated.model_dump(exclude_unset=True)
    record["run_id"] = run_id  # URL is authoritative

    cols, placeholders, params = _split_jsonb_fields(record)
    insert_sql = (
        f"INSERT INTO {result_type} ({', '.join(cols)}) "
        f"VALUES ({', '.join(placeholders)}) "
        "ON CONFLICT DO NOTHING RETURNING id"
    )
    try:
        inserted = execute_write(insert_sql, params, conn=db)
    except Exception as exc:
        logger.error("Typed-table insert failed for %s/%s: %s", run_id, result_type, exc)
        raise HTTPException(status_code=500, detail="Result persistence failed") from exc

    if not inserted:
        return error(
            "DUPLICATE_RESULT",
            "Result already registered for this run/sample",
            status_code=409,
        )
    result_id = inserted[0]["id"]

    sample_id = record.get("sample_id")
    metrics_payload = json.dumps({result_type: {"registered": True}})
    execute_write(
        """
        INSERT INTO pipeline_results
            (run_id, sample_id, pipeline_name, pipeline_version, metrics)
        VALUES
            (:run_id, :sample_id, :pipeline_name, :pipeline_version,
             CAST(:metrics AS JSONB))
        ON CONFLICT (run_id, sample_id) DO UPDATE SET
            metrics = pipeline_results.metrics || EXCLUDED.metrics,
            pipeline_name = COALESCE(pipeline_results.pipeline_name, EXCLUDED.pipeline_name),
            pipeline_version = COALESCE(
                pipeline_results.pipeline_version, EXCLUDED.pipeline_version
            ),
            updated_at = NOW()
        """,
        {
            "run_id": run_id,
            "sample_id": sample_id,
            "pipeline_name": run.get("pipeline_name"),
            "pipeline_version": run.get("pipeline_version"),
            "metrics": metrics_payload,
        },
        conn=db,
    )

    log_audit(
        action=AuditActions.REGISTER_PIPELINE_RESULT,
        actor_id=None,
        resource_type="pipeline_result",
        resource_id=f"{run_id}:{result_type}:{result_id}",
        before=None,
        after={"result_type": result_type, "sample_id": sample_id},
        metadata={"run_id": run_id},
        db_conn=db,
    )
    return success(
        {"status": "registered", "result_id": result_id},
        status_code=201,
    )
