"""
Session N — pipelines router end-to-end tests.

Covers every endpoint introduced in Session N:
    POST   /api/v1/pipelines/launch
    POST   /api/v1/pipelines/events             (weblog token check)
    GET    /api/v1/pipelines/{run_id}
    GET    /api/v1/pipelines/{run_id}/tasks
    GET    /api/v1/pipelines/{run_id}/events
    POST   /api/v1/pipelines/{run_id}/resume
    POST   /api/v1/pipelines/custom
    POST   /api/v1/pipelines/{catalog_id}/promote

The seed DB has admin@example.org (uid 1, Platform Admin) as
Lab Director of Example Lab (id 1) + Dev Project (id 1). Non-admin
scenarios create throw-away users and switch MOCK_USER_EMAIL via
monkeypatch + get_settings.cache_clear() — same pattern as
test_samples_router_api.py.
"""

from __future__ import annotations

import uuid

import pytest
from authz_helpers import ADMIN_PRESET, grant_instance_preset

from backend.config import get_settings
from backend.database import execute_query, execute_write

SEED_USER_ID = 1
SEED_LAB_ID = 1
SEED_PROJECT_ID = 1


# ────────────────────────── helpers ──────────────────────────


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _switch_user(email: str, monkeypatch) -> None:
    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()


def _make_user(
    email: str,
    *,
    is_platform_admin: bool = False,
) -> int:
    rows = execute_write(
        "INSERT INTO users (email, name, organization_id, is_active) "
        "VALUES (:e, :e, 1, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET is_active = TRUE "
        "RETURNING id",
        {"e": email},
    )
    uid = rows[0]["id"]
    grant_instance_preset(uid, ADMIN_PRESET if is_platform_admin else None)
    return uid


def _add_lab_membership(user_id: int, lab_id: int, role: str, *, is_director: bool = False) -> None:
    execute_write(
        "INSERT INTO lab_membership (user_id, lab_id, permission_group_id, is_lab_director) "
        "SELECT :u, :l, pg.id, :d FROM permission_groups pg WHERE pg.name = :r "
        "ON CONFLICT (user_id, lab_id) DO UPDATE SET "
        "permission_group_id = EXCLUDED.permission_group_id, "
        "is_lab_director = EXCLUDED.is_lab_director",
        {"u": user_id, "l": lab_id, "r": role, "d": is_director},
    )


def _ensure_other_lab() -> int:
    rows = execute_query("SELECT id FROM labs WHERE display_name = 'Other Lab N'")
    if rows:
        return rows[0]["id"]
    new = execute_write(
        "INSERT INTO labs (organization_id, display_name, description, created_by_id) "
        "VALUES (1, 'Other Lab N', 'Pipelines-router tests', 1) RETURNING id"
    )
    lab_id = new[0]["id"]
    execute_write(
        "INSERT INTO projects (lab_id, display_name, description, created_by_id) "
        "VALUES (:l, 'Other Project N', 'Other lab project', 1)",
        {"l": lab_id},
    )
    return lab_id


def _other_project_id(lab_id: int) -> int:
    rows = execute_query(
        "SELECT id FROM projects WHERE lab_id = :l ORDER BY id LIMIT 1",
        {"l": lab_id},
    )
    return rows[0]["id"]


def _insert_catalog(
    *,
    pipeline_name: str,
    pipeline_version: str = "1.0.0",
    tier: str = "zoo",
    is_active: bool = True,
    compatibility_rules: dict | None = None,
    pipeline_uri: str | None = None,
    default_profile: str | None = None,
    scope_lab_id: int | None = None,
) -> int:
    import json

    rows = execute_write(
        """
        INSERT INTO pipeline_catalog
            (pipeline_name, pipeline_version, parser_version, tier, is_active,
             compatibility_rules, pipeline_uri, default_profile, scope_lab_id)
        VALUES
            (:n, :v, '1.0.0', :t, :a,
             CAST(:rules AS JSONB), :uri, :prof, :slab)
        RETURNING id
        """,
        {
            "n": pipeline_name,
            "v": pipeline_version,
            "t": tier,
            "a": is_active,
            "rules": json.dumps(compatibility_rules or {}),
            "uri": pipeline_uri,
            "prof": default_profile,
            "slab": scope_lab_id,
        },
    )
    return rows[0]["id"]


def _insert_sample(
    sample_id: str,
    *,
    lab_id: int = SEED_LAB_ID,
    project_id: int = SEED_PROJECT_ID,
    owner_id: int = SEED_USER_ID,
    organism_name: str = "Severe acute respiratory syndrome coronavirus 2",
    source_type: str = "Human",
    scrub_status: str = "COMPLETE",
    quality_status: str = "ANALYZABLE",
) -> dict:
    rows = execute_write(
        """
        INSERT INTO samples
            (sample_id, lab_id, project_id, owner_id, source_type, organism_name,
             type_of_experiment, library_preparation_method, sequencing_protocol,
             sequencing_platform, sequencing_lab, date_collected, date_sequenced,
             collection_facility, collection_location_country, sharing_level,
             fastq_r1_uri, scrub_status, quality_status)
        VALUES
            (:sid, :lid, :pid, :oid, :src, :org,
             'WGS', 'ARTIC', 'https://www.protocols.io/view/artic-v4-1',
             'Illumina', 'Example Sequencing Lab', '2026-01-15', '2026-01-17',
             'Example Hospital', 'United States', 'PRIVATE',
             'gs://jackpot-sequences/test/R1.fastq.gz', :scrub, :qual)
        RETURNING *
        """,
        {
            "sid": sample_id,
            "lid": lab_id,
            "pid": project_id,
            "oid": owner_id,
            "src": source_type,
            "org": organism_name,
            "scrub": scrub_status,
            "qual": quality_status,
        },
    )
    return rows[0]


def _cleanup_run(run_id: str) -> None:
    execute_write("DELETE FROM pipeline_events WHERE run_id = :r", {"r": run_id})
    execute_write("DELETE FROM pipeline_tasks WHERE run_id = :r", {"r": run_id})
    execute_write("DELETE FROM pipeline_files WHERE run_id = :r", {"r": run_id})
    execute_write(
        "DELETE FROM pipeline_restarts WHERE new_run_id = :r OR previous_run_id = :r", {"r": run_id}
    )
    execute_write("DELETE FROM pipeline_results WHERE run_id = :r", {"r": run_id})
    execute_write("DELETE FROM pipeline_runs WHERE run_id = :r", {"r": run_id})
    execute_write(
        "DELETE FROM audit_log WHERE resource_type = 'pipeline_run' AND resource_id = :r",
        {"r": run_id},
    )


def _cleanup_samples(prefix: str) -> None:
    rows = execute_query(
        "SELECT id FROM samples WHERE sample_id LIKE :p",
        {"p": f"{prefix}%"},
    )
    for r in rows:
        sid = r["id"]
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'sample' AND resource_id = :rid",
            {"rid": str(sid)},
        )
        execute_write("DELETE FROM samples WHERE id = :id", {"id": sid})


def _cleanup_catalog_by_id(cat_id: int) -> None:
    execute_write("DELETE FROM lab_pipelines WHERE pipeline_catalog_id = :c", {"c": cat_id})
    execute_write(
        "UPDATE pipeline_runs SET pipeline_catalog_id = NULL WHERE pipeline_catalog_id = :c",
        {"c": cat_id},
    )
    execute_write(
        "UPDATE audit_log SET actor_id = NULL "
        "WHERE resource_type = 'pipeline_catalog' AND resource_id = :rid",
        {"rid": str(cat_id)},
    )
    execute_write("DELETE FROM pipeline_catalog WHERE id = :id", {"id": cat_id})


def _cleanup_users(emails: list[str]) -> None:
    for e in emails:
        rows = execute_query("SELECT id FROM users WHERE email = :e", {"e": e})
        if not rows:
            continue
        uid = rows[0]["id"]
        execute_write("DELETE FROM lab_membership WHERE user_id = :u", {"u": uid})
        execute_write("DELETE FROM project_membership WHERE user_id = :u", {"u": uid})
        execute_write("UPDATE audit_log SET actor_id = NULL WHERE actor_id = :u", {"u": uid})
        execute_write(
            "UPDATE pipeline_runs SET launched_by_id = 1 WHERE launched_by_id = :u", {"u": uid}
        )
        execute_write("DELETE FROM users WHERE id = :u", {"u": uid})


def _cleanup_project_pipeline(project_id: int, name: str) -> None:
    rows = execute_query(
        "SELECT id FROM project_pipelines WHERE project_id = :p AND pipeline_name = :n",
        {"p": project_id, "n": name},
    )
    for r in rows:
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'project_pipeline' AND resource_id = :rid",
            {"rid": str(r["id"])},
        )
        execute_write("DELETE FROM project_pipelines WHERE id = :id", {"id": r["id"]})


@pytest.fixture
def as_platform_admin(monkeypatch):
    _switch_user("admin@example.org", monkeypatch)


# ───────────────────────── POST /launch ─────────────────────────


@pytest.mark.asyncio
async def test_launch_happy_path_returns_201(client, as_platform_admin):
    prefix = _unique("LAU")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(
        pipeline_name=_unique("jp-sc2"),
        compatibility_rules={"source_types": ["Human"]},
        pipeline_uri="https://github.com/jackpot-surv/pipelines",
        default_profile="gcp",
    )
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["success"] is True
        run_id = body["data"]["run_id"]
        assert run_id.startswith("jp-")
        assert body["data"]["status"] == "QUEUED"

        rows = execute_query(
            "SELECT status, pipeline_catalog_id, launched_by_id "
            "FROM pipeline_runs WHERE run_id = :r",
            {"r": run_id},
        )
        assert rows[0]["status"] == "QUEUED"
        assert rows[0]["pipeline_catalog_id"] == cat_id

        audits = execute_query(
            "SELECT action FROM audit_log WHERE resource_type = 'pipeline_run' "
            "AND resource_id = :r",
            {"r": run_id},
        )
        assert any(a["action"] == "CREATE_PIPELINE_RUN" for a in audits)
        _cleanup_run(run_id)
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_hard_block_returns_422(client, as_platform_admin):
    prefix = _unique("BLK")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A", source_type="Environmental")
    cat_id = _insert_catalog(
        pipeline_name=_unique("jp-hmn"),
        compatibility_rules={"source_types": ["Human"]},
    )
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
            },
        )
        assert resp.status_code == 422, resp.text
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "INCOMPATIBLE_SAMPLES"
        assert body["error"]["detail"]["hard_blocks"]
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_soft_warning_then_override(client, as_platform_admin):
    prefix = _unique("SFT")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A", quality_status="PRELIMINARY")
    cat_id = _insert_catalog(
        pipeline_name=_unique("jp-min-anal"),
        compatibility_rules={"min_quality_status": "ANALYZABLE"},
    )
    try:
        first = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
            },
        )
        assert first.status_code == 202, first.text
        body = first.json()
        assert body["error"]["code"] == "SOFT_WARNINGS"
        assert body["error"]["detail"]["soft_warnings"]

        second = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
                "override_soft_warnings": True,
            },
        )
        assert second.status_code == 201, second.text
        run_id = second.json()["data"]["run_id"]
        _cleanup_run(run_id)
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_unknown_pipeline_returns_404(client, as_platform_admin):
    prefix = _unique("NOP")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": 999_999,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
            },
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"
    finally:
        _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_launch_missing_sample_returns_404(client, as_platform_admin):
    cat_id = _insert_catalog(pipeline_name=_unique("jp-any"))
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": ["DOES-NOT-EXIST"],
                "project_id": SEED_PROJECT_ID,
            },
        )
        assert resp.status_code == 404
        body = resp.json()
        assert "DOES-NOT-EXIST" in body["error"]["detail"]["missing_sample_ids"]
    finally:
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_other_lab_project_returns_403(client, monkeypatch):
    email = _unique("outsider") + "@test.com"
    _cleanup_users([email])
    _make_user(email)
    other_lab = _ensure_other_lab()
    other_proj = _other_project_id(other_lab)
    _switch_user(email, monkeypatch)

    cat_id = _insert_catalog(pipeline_name=_unique("jp-out"))
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": ["IRRELEVANT"],
                "project_id": other_proj,
            },
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ACCESS_DENIED"
    finally:
        _cleanup_catalog_by_id(cat_id)
        _cleanup_users([email])


# ────────────── POST /launch — Phase P0f F-8 BROKEN_INPUTS ──────────────


def _insert_sample_file(
    *,
    sample_pk: int,
    uri: str,
    storage_state: str = "EXTERNAL",
    last_verification_status: str | None = None,
    file_size_bytes: int | None = None,
) -> int:
    # MANAGED/STAGED rows require file_size_bytes per the
    # sample_files_managed_size_not_null check constraint.
    if storage_state in ("MANAGED", "STAGED") and file_size_bytes is None:
        file_size_bytes = 1024
    rows = execute_write(
        "INSERT INTO sample_files "
        "    (sample_id_fk, uri, filename, file_type, library_layout, "
        "     storage_state, last_verification_status, file_size_bytes) "
        "VALUES (:sid, :uri, :fn, 'FASTQ', 'PAIRED', "
        "        CAST(:state AS file_storage_state), :lvs, :sz) "
        "RETURNING id",
        {
            "sid": sample_pk,
            "uri": uri,
            "fn": uri.rsplit("/", 1)[-1],
            "state": storage_state,
            "lvs": last_verification_status,
            "sz": file_size_bytes,
        },
    )
    return rows[0]["id"]


@pytest.mark.asyncio
async def test_launch_refuses_broken_inputs_returns_400(client, as_platform_admin):
    """F-8: launch must refuse if any input sample_files row is BROKEN."""
    prefix = _unique("BRK")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    ok_uri = f"file:///srv/seq/{prefix}/R1.fastq.gz"
    broken_uri = f"file:///srv/seq/{prefix}/R2.fastq.gz"
    _insert_sample_file(sample_pk=sample["id"], uri=ok_uri)
    broken_id = _insert_sample_file(
        sample_pk=sample["id"],
        uri=broken_uri,
        storage_state="BROKEN",
        last_verification_status="MISSING_3",
    )
    cat_id = _insert_catalog(
        pipeline_name=_unique("jp-brk"),
        compatibility_rules={"source_types": ["Human"]},
        pipeline_uri="https://github.com/jackpot-surv/pipelines",
    )
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
            },
        )
        assert resp.status_code == 400, resp.text
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "BROKEN_INPUTS"
        broken = body["error"]["detail"]["broken_files"]
        assert len(broken) == 1
        assert broken[0]["sample_files_id"] == broken_id
        assert broken[0]["sample_id"] == sample["sample_id"]
        assert broken[0]["uri"] == broken_uri
        assert broken[0]["last_verification_status"] == "MISSING_3"
        assert "suggestion" in body["error"]["detail"]

        # No pipeline_run row should exist for the refused launch.
        runs = execute_query(
            "SELECT 1 FROM pipeline_runs WHERE pipeline_catalog_id = :c",
            {"c": cat_id},
        )
        assert runs == []
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_with_only_external_sample_files_succeeds(client, as_platform_admin):
    """F-8 control: non-BROKEN sample_files rows must NOT trigger refusal."""
    prefix = _unique("OKF")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    _insert_sample_file(
        sample_pk=sample["id"],
        uri=f"file:///srv/seq/{prefix}/R1.fastq.gz",
    )
    _insert_sample_file(
        sample_pk=sample["id"],
        uri=f"file:///srv/seq/{prefix}/R2.fastq.gz",
        storage_state="MANAGED",
    )
    cat_id = _insert_catalog(
        pipeline_name=_unique("jp-okf"),
        compatibility_rules={"source_types": ["Human"]},
        pipeline_uri="https://github.com/jackpot-surv/pipelines",
        default_profile="gcp",
    )
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
            },
        )
        assert resp.status_code == 201, resp.text
        run_id = resp.json()["data"]["run_id"]
        _cleanup_run(run_id)
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_broken_input_lists_every_broken_row(client, as_platform_admin):
    """F-8: all BROKEN rows across all requested samples are surfaced."""
    prefix = _unique("MBR")
    _cleanup_samples(prefix)
    sample_a = _insert_sample(f"{prefix}-A")
    sample_b = _insert_sample(f"{prefix}-B")
    _insert_sample_file(
        sample_pk=sample_a["id"],
        uri=f"file:///srv/seq/{prefix}/A_R1.fastq.gz",
        storage_state="BROKEN",
        last_verification_status="MISSING_3",
    )
    _insert_sample_file(
        sample_pk=sample_b["id"],
        uri=f"file:///srv/seq/{prefix}/B_R1.fastq.gz",
        storage_state="BROKEN",
        last_verification_status="SIZE_CHANGED",
    )
    cat_id = _insert_catalog(pipeline_name=_unique("jp-mbr"))
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample_a["sample_id"], sample_b["sample_id"]],
                "project_id": SEED_PROJECT_ID,
            },
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "BROKEN_INPUTS"
        sample_ids_in_error = {r["sample_id"] for r in body["error"]["detail"]["broken_files"]}
        assert sample_ids_in_error == {sample_a["sample_id"], sample_b["sample_id"]}
        assert "2 input files" in body["error"]["message"]
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_ignores_deleted_broken_rows(client, as_platform_admin):
    """F-8: soft-deleted (is_archived=TRUE) BROKEN rows must not block launch."""
    prefix = _unique("DBR")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    sf_id = _insert_sample_file(
        sample_pk=sample["id"],
        uri=f"file:///srv/seq/{prefix}/old.fastq.gz",
        storage_state="BROKEN",
        last_verification_status="MISSING_3",
    )
    execute_write(
        "UPDATE sample_files SET is_archived = TRUE WHERE id = :id",
        {"id": sf_id},
    )
    _insert_sample_file(
        sample_pk=sample["id"],
        uri=f"file:///srv/seq/{prefix}/new.fastq.gz",
    )
    cat_id = _insert_catalog(
        pipeline_name=_unique("jp-dbr"),
        compatibility_rules={"source_types": ["Human"]},
        pipeline_uri="https://github.com/jackpot-surv/pipelines",
        default_profile="gcp",
    )
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
            },
        )
        assert resp.status_code == 201, resp.text
        run_id = resp.json()["data"]["run_id"]
        _cleanup_run(run_id)
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_succeeds_with_only_managed_inputs(client, as_platform_admin):
    """F-8: pure-MANAGED storage_state must not trigger refusal."""
    prefix = _unique("MGD")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    _insert_sample_file(
        sample_pk=sample["id"],
        uri=f"gs://jackpot-managed/{prefix}/R1.fastq.gz",
        storage_state="MANAGED",
    )
    _insert_sample_file(
        sample_pk=sample["id"],
        uri=f"gs://jackpot-managed/{prefix}/R2.fastq.gz",
        storage_state="MANAGED",
    )
    cat_id = _insert_catalog(
        pipeline_name=_unique("jp-mgd"),
        compatibility_rules={"source_types": ["Human"]},
        pipeline_uri="https://github.com/jackpot-surv/pipelines",
        default_profile="gcp",
    )
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
            },
        )
        assert resp.status_code == 201, resp.text
        run_id = resp.json()["data"]["run_id"]
        _cleanup_run(run_id)
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_lists_all_broken_files_on_one_sample(client, as_platform_admin):
    """F-8: a single sample with two BROKEN sample_files rows surfaces both."""
    prefix = _unique("PAIR")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    r1_id = _insert_sample_file(
        sample_pk=sample["id"],
        uri=f"file:///srv/seq/{prefix}/R1.fastq.gz",
        storage_state="BROKEN",
        last_verification_status="MISSING_3",
    )
    r2_id = _insert_sample_file(
        sample_pk=sample["id"],
        uri=f"file:///srv/seq/{prefix}/R2.fastq.gz",
        storage_state="BROKEN",
        last_verification_status="MISSING_3",
    )
    cat_id = _insert_catalog(pipeline_name=_unique("jp-pair"))
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
            },
        )
        assert resp.status_code == 400, resp.text
        body = resp.json()
        assert body["error"]["code"] == "BROKEN_INPUTS"
        ids_in_error = {row["sample_files_id"] for row in body["error"]["detail"]["broken_files"]}
        assert ids_in_error == {r1_id, r2_id}
        sample_ids_in_error = {row["sample_id"] for row in body["error"]["detail"]["broken_files"]}
        assert sample_ids_in_error == {sample["sample_id"]}
        assert "2 input files" in body["error"]["message"]
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_response_includes_suggestion(client, as_platform_admin):
    """F-8: the error response must surface a non-empty suggestion field."""
    prefix = _unique("SUGG")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    _insert_sample_file(
        sample_pk=sample["id"],
        uri=f"file:///srv/seq/{prefix}/missing.fastq.gz",
        storage_state="BROKEN",
        last_verification_status="MISSING_3",
    )
    cat_id = _insert_catalog(pipeline_name=_unique("jp-sugg"))
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
            },
        )
        assert resp.status_code == 400
        suggestion = resp.json()["error"]["detail"]["suggestion"]
        assert isinstance(suggestion, str) and suggestion.strip()
        assert "jackpot files verify" in suggestion
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_mixed_inputs_only_broken_listed(client, as_platform_admin):
    """F-8: with 4 inputs (3 OK, 1 BROKEN), only the BROKEN row is reported."""
    prefix = _unique("MIX")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    ok_ids = [
        _insert_sample_file(
            sample_pk=sample["id"],
            uri=f"file:///srv/seq/{prefix}/ok_{i}.fastq.gz",
            storage_state="EXTERNAL",
        )
        for i in range(3)
    ]
    broken_uri = f"file:///srv/seq/{prefix}/broken.fastq.gz"
    broken_id = _insert_sample_file(
        sample_pk=sample["id"],
        uri=broken_uri,
        storage_state="BROKEN",
        last_verification_status="SIZE_CHANGED",
    )
    cat_id = _insert_catalog(pipeline_name=_unique("jp-mix"))
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
            },
        )
        assert resp.status_code == 400, resp.text
        body = resp.json()
        broken_files = body["error"]["detail"]["broken_files"]
        assert len(broken_files) == 1
        assert broken_files[0]["sample_files_id"] == broken_id
        assert broken_files[0]["uri"] == broken_uri
        assert broken_files[0]["last_verification_status"] == "SIZE_CHANGED"
        ids_in_error = {row["sample_files_id"] for row in broken_files}
        assert ids_in_error.isdisjoint(set(ok_ids))
        assert "1 input file is in BROKEN" in body["error"]["message"]
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_launch_proceeds_when_sample_has_no_sample_files(client, as_platform_admin):
    """F-8 edge case: sample with zero sample_files rows must not be refused.

    The launch endpoint requires at least one sample_id (Pydantic
    min_length=1), so a truly input-less launch isn't reachable; the
    analogous degenerate case is a sample whose sample_files set is
    empty. F-8's BROKEN check finds nothing and lets the launch proceed.
    """
    prefix = _unique("EMP")
    _cleanup_samples(prefix)
    sample = _insert_sample(f"{prefix}-A")
    cat_id = _insert_catalog(
        pipeline_name=_unique("jp-emp"),
        compatibility_rules={"source_types": ["Human"]},
        pipeline_uri="https://github.com/jackpot-surv/pipelines",
        default_profile="gcp",
    )
    try:
        resp = await client.post(
            "/api/v1/pipelines/launch",
            json={
                "pipeline_id": cat_id,
                "sample_ids": [sample["sample_id"]],
                "project_id": SEED_PROJECT_ID,
            },
        )
        assert resp.status_code == 201, resp.text
        run_id = resp.json()["data"]["run_id"]
        _cleanup_run(run_id)
    finally:
        _cleanup_samples(prefix)
        _cleanup_catalog_by_id(cat_id)


# ───────────────────────── POST /events ─────────────────────────


def _seed_run(
    *,
    status: str = "QUEUED",
    pipeline_name: str | None = None,
    sample_ids: list[int] | None = None,
) -> tuple[str, str]:
    run_id = f"jp-{uuid.uuid4()}"
    token = f"pt_{uuid.uuid4().hex}"
    execute_write(
        """
        INSERT INTO pipeline_runs
            (lab_id, project_id, launched_by_id, pipeline_name, pipeline_version,
             sample_ids, status, launcher_type, run_id, pipeline_token, work_dir,
             result_uri)
        VALUES
            (1, 1, 1, :pn, '1.0.0', :sids, :status, 'native', :rid, :tok,
             'gs://jackpot-work/some/work', 'gs://jackpot-results/some/')
        """,
        {
            "pn": pipeline_name or f"jp-{uuid.uuid4().hex[:6]}",
            "sids": sample_ids or [],
            "status": status,
            "rid": run_id,
            "tok": token,
        },
    )
    return run_id, token


@pytest.mark.asyncio
async def test_events_valid_token_writes_row(client):
    run_id, token = _seed_run(status="QUEUED")
    try:
        resp = await client.post(
            "/api/v1/pipelines/events",
            headers={"X-Pipeline-Token": token},
            json={"event": "workflow.started", "runId": run_id, "runName": "r1"},
        )
        assert resp.status_code == 200, resp.text
        events = execute_query(
            "SELECT event_type FROM pipeline_events WHERE run_id = :r",
            {"r": run_id},
        )
        assert len(events) == 1
        assert events[0]["event_type"] == "workflow.started"
        run = execute_query("SELECT status FROM pipeline_runs WHERE run_id = :r", {"r": run_id})
        assert run[0]["status"] == "RUNNING"
    finally:
        _cleanup_run(run_id)


@pytest.mark.asyncio
async def test_events_wrong_token_returns_401(client):
    run_id, _ = _seed_run()
    try:
        resp = await client.post(
            "/api/v1/pipelines/events",
            headers={"X-Pipeline-Token": "bogus"},
            json={"event": "workflow.started", "runId": run_id},
        )
        assert resp.status_code == 401
        events = execute_query("SELECT id FROM pipeline_events WHERE run_id = :r", {"r": run_id})
        assert events == []
    finally:
        _cleanup_run(run_id)


@pytest.mark.asyncio
async def test_events_missing_token_returns_401(client):
    run_id, _ = _seed_run()
    try:
        resp = await client.post(
            "/api/v1/pipelines/events",
            json={"event": "workflow.started", "runId": run_id},
        )
        assert resp.status_code == 401
    finally:
        _cleanup_run(run_id)


@pytest.mark.asyncio
async def test_events_unknown_run_returns_404(client):
    resp = await client.post(
        "/api/v1/pipelines/events",
        headers={"X-Pipeline-Token": "whatever"},
        json={"event": "workflow.started", "runId": "does-not-exist"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_events_missing_runid_returns_400(client):
    resp = await client.post(
        "/api/v1/pipelines/events",
        headers={"X-Pipeline-Token": "whatever"},
        json={"event": "workflow.started"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_events_process_trace_creates_task(client):
    run_id, token = _seed_run(status="RUNNING")
    try:
        resp = await client.post(
            "/api/v1/pipelines/events",
            headers={"X-Pipeline-Token": token},
            json={
                "event": "process.completed",
                "runId": run_id,
                "trace": {
                    "taskId": "42",
                    "name": "FASTP",
                    "status": "COMPLETED",
                    "container": "biocontainers/fastp:0.23.4",
                    "cpus": 4,
                    "memory": 8 * 1024 * 1024 * 1024,
                    "duration": 12345,
                    "submit": "2026-04-17T10:00:00Z",
                    "start": "2026-04-17T10:00:10Z",
                    "complete": "2026-04-17T10:00:22Z",
                },
            },
        )
        assert resp.status_code == 200
        tasks = execute_query(
            "SELECT task_name, status, memory_mb FROM pipeline_tasks "
            "WHERE run_id = :r AND task_id = '42'",
            {"r": run_id},
        )
        assert len(tasks) == 1
        assert tasks[0]["task_name"] == "FASTP"
        assert tasks[0]["memory_mb"] == 8 * 1024
    finally:
        _cleanup_run(run_id)


# ───────────────────────── GET /{run_id} ─────────────────────────


@pytest.mark.asyncio
async def test_get_run_detail_includes_events_and_task_summary(client, as_platform_admin):
    run_id, token = _seed_run()
    try:
        execute_write(
            "INSERT INTO pipeline_events (run_id, event_type, event_json) "
            "VALUES (:r, 'workflow.started', CAST(:j AS JSONB))",
            {"r": run_id, "j": '{"event": "workflow.started"}'},
        )
        execute_write(
            "INSERT INTO pipeline_tasks (run_id, task_id, status) "
            "VALUES (:r, 't1', 'COMPLETED'), (:r, 't2', 'RUNNING')",
            {"r": run_id},
        )

        resp = await client.get(f"/api/v1/pipelines/{run_id}")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["run_id"] == run_id
        assert "pipeline_token" not in data
        assert len(data["recent_events"]) >= 1
        assert data["task_summary"].get("COMPLETED") == 1
        assert data["task_summary"].get("RUNNING") == 1
    finally:
        _cleanup_run(run_id)


@pytest.mark.asyncio
async def test_get_run_other_lab_returns_403(client, monkeypatch):
    other_lab = _ensure_other_lab()
    other_proj = _other_project_id(other_lab)
    run_id = f"jp-{uuid.uuid4()}"
    execute_write(
        """
        INSERT INTO pipeline_runs
            (lab_id, project_id, launched_by_id, pipeline_name, pipeline_version,
             run_id, pipeline_token, status)
        VALUES (:l, :p, 1, 'jp-x', '1.0', :r, 'pt-x', 'QUEUED')
        """,
        {"l": other_lab, "p": other_proj, "r": run_id},
    )

    email = _unique("lurker") + "@test.com"
    _cleanup_users([email])
    _make_user(email)
    _switch_user(email, monkeypatch)
    try:
        resp = await client.get(f"/api/v1/pipelines/{run_id}")
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ACCESS_DENIED"
    finally:
        _cleanup_run(run_id)
        _cleanup_users([email])


@pytest.mark.asyncio
async def test_get_run_not_found(client, as_platform_admin):
    resp = await client.get("/api/v1/pipelines/does-not-exist")
    assert resp.status_code == 404


# ─────────────────── GET /{run_id}/tasks and /events ───────────────────


@pytest.mark.asyncio
async def test_list_tasks_paginated(client, as_platform_admin):
    run_id, _ = _seed_run()
    try:
        for i in range(3):
            execute_write(
                "INSERT INTO pipeline_tasks (run_id, task_id, task_name, status) "
                "VALUES (:r, :t, :n, 'COMPLETED')",
                {"r": run_id, "t": f"t{i}", "n": f"proc_{i}"},
            )
        resp = await client.get(f"/api/v1/pipelines/{run_id}/tasks?per_page=2")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["pagination"]["total"] == 3
    finally:
        _cleanup_run(run_id)


@pytest.mark.asyncio
async def test_list_events_paginated(client, as_platform_admin):
    run_id, _ = _seed_run()
    try:
        for _i in range(4):
            execute_write(
                "INSERT INTO pipeline_events (run_id, event_type, event_json) "
                "VALUES (:r, 'workflow.started', CAST('{}' AS JSONB))",
                {"r": run_id},
            )
        resp = await client.get(f"/api/v1/pipelines/{run_id}/events?per_page=3")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 3
        assert body["pagination"]["total"] == 4
    finally:
        _cleanup_run(run_id)


# ───────────────────── POST /{run_id}/resume ─────────────────────


@pytest.mark.asyncio
async def test_resume_failed_creates_new_run(client, as_platform_admin):
    run_id, _ = _seed_run(status="FAILED")
    try:
        resp = await client.post(
            f"/api/v1/pipelines/{run_id}/resume",
            json={},
        )
        assert resp.status_code == 201, resp.text
        new_id = resp.json()["data"]["run_id"]
        assert new_id != run_id
        assert resp.json()["data"]["resumed_from"] == run_id

        restarts = execute_query(
            "SELECT new_run_id, previous_run_id FROM pipeline_restarts WHERE new_run_id = :n",
            {"n": new_id},
        )
        assert len(restarts) == 1
        assert restarts[0]["previous_run_id"] == run_id

        audits = execute_query(
            "SELECT action FROM audit_log WHERE resource_type = 'pipeline_run' "
            "AND resource_id = :r",
            {"r": new_id},
        )
        assert any(a["action"] == "RESUME_PIPELINE_RUN" for a in audits)

        _cleanup_run(new_id)
    finally:
        _cleanup_run(run_id)


@pytest.mark.asyncio
async def test_resume_non_failed_returns_400(client, as_platform_admin):
    run_id, _ = _seed_run(status="COMPLETED")
    try:
        resp = await client.post(f"/api/v1/pipelines/{run_id}/resume", json={})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_STATE"
    finally:
        _cleanup_run(run_id)


@pytest.mark.asyncio
async def test_resume_unknown_returns_404(client, as_platform_admin):
    resp = await client.post("/api/v1/pipelines/does-not-exist/resume", json={})
    assert resp.status_code == 404


# ───────────────────────── POST /custom ─────────────────────────


@pytest.mark.asyncio
async def test_custom_pipeline_registered_as_unverified(client, as_platform_admin):
    name = _unique("byop")
    try:
        resp = await client.post(
            "/api/v1/pipelines/custom",
            json={
                "project_id": SEED_PROJECT_ID,
                "pipeline_name": name,
                "github_url": "https://github.com/example/custom-pipeline",
                "revision": "v1.0.0",
                "parameter_schema": {"param_a": {"type": "string"}},
            },
        )
        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert body["data"]["status"] == "UNVERIFIED"
        assert isinstance(body["data"]["project_pipeline_id"], int)

        rows = execute_query(
            "SELECT status FROM project_pipelines WHERE project_id = :p AND pipeline_name = :n",
            {"p": SEED_PROJECT_ID, "n": name},
        )
        assert rows[0]["status"] == "UNVERIFIED"
    finally:
        _cleanup_project_pipeline(SEED_PROJECT_ID, name)


@pytest.mark.asyncio
async def test_custom_pipeline_bad_url_returns_422(client, as_platform_admin):
    name = _unique("bad")
    try:
        resp = await client.post(
            "/api/v1/pipelines/custom",
            json={
                "project_id": SEED_PROJECT_ID,
                "pipeline_name": name,
                "github_url": "ftp://example.com/repo",
                "revision": "main",
            },
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INVALID_URL"
    finally:
        _cleanup_project_pipeline(SEED_PROJECT_ID, name)


@pytest.mark.asyncio
async def test_custom_pipeline_duplicate_returns_409(client, as_platform_admin):
    name = _unique("dup")
    try:
        r1 = await client.post(
            "/api/v1/pipelines/custom",
            json={
                "project_id": SEED_PROJECT_ID,
                "pipeline_name": name,
                "github_url": "https://github.com/example/dup",
                "revision": "v1",
            },
        )
        assert r1.status_code == 202
        r2 = await client.post(
            "/api/v1/pipelines/custom",
            json={
                "project_id": SEED_PROJECT_ID,
                "pipeline_name": name,
                "github_url": "https://github.com/example/dup",
                "revision": "v2",
            },
        )
        assert r2.status_code == 409
        assert r2.json()["error"]["code"] == "DUPLICATE_PIPELINE"
    finally:
        _cleanup_project_pipeline(SEED_PROJECT_ID, name)


@pytest.mark.asyncio
async def test_a_non_duplicate_failure_is_not_reported_as_a_duplicate(client, monkeypatch):
    """The other direction, which the broad catch could not distinguish.

    `except Exception` reported every insert failure as DUPLICATE_PIPELINE — a
    dropped connection, a serialization failure, a constraint on some other
    column. The client is told the pipeline is already registered, and the real
    fault is hidden behind a 409 nobody investigates.
    """
    from backend.routers import pipelines

    def _boom(*args, **kwargs):
        raise RuntimeError("connection reset")

    monkeypatch.setattr(pipelines, "execute_write", _boom)

    with pytest.raises(RuntimeError, match="connection reset"):
        await client.post(
            "/api/v1/pipelines/custom",
            json={
                "project_id": SEED_PROJECT_ID,
                "pipeline_name": f"not-a-dup-{uuid.uuid4().hex[:6]}",
                "github_url": "https://github.com/example/boom",
                "revision": "v1",
            },
        )


@pytest.mark.asyncio
async def test_custom_pipeline_groovy_unsafe_name_returns_422_not_500(client, as_platform_admin):
    """A Groovy-unsafe pipeline_name must be a clean 422.

    validate_groovy_safe raises ValueError inside a field_validator.
    Pydantic v2 puts that exception object in ctx["error"], which is not
    JSON serializable — so before the app's RequestValidationError
    handler stringified ctx, this endpoint answered 500 instead of 422
    and the caller got no usable message.
    """
    resp = await client.post(
        "/api/v1/pipelines/custom",
        json={
            "project_id": SEED_PROJECT_ID,
            "pipeline_name": "evil" + chr(39) + chr(59) + "whoami",
            "github_url": "https://github.com/example/evil",
            "revision": "v1",
        },
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["success"] is False
    assert "pipeline_name" in body["error"]["message"]


@pytest.mark.asyncio
async def test_custom_pipeline_requires_lab_director(client, monkeypatch):
    email = _unique("collab") + "@test.com"
    _cleanup_users([email])
    uid = _make_user(email)
    _add_lab_membership(uid, SEED_LAB_ID, "Lab Collaborator", is_director=False)
    _switch_user(email, monkeypatch)

    name = _unique("block")
    try:
        resp = await client.post(
            "/api/v1/pipelines/custom",
            json={
                "project_id": SEED_PROJECT_ID,
                "pipeline_name": name,
                "github_url": "https://github.com/example/block",
                "revision": "v1",
            },
        )
        assert resp.status_code == 403
    finally:
        _cleanup_project_pipeline(SEED_PROJECT_ID, name)
        _cleanup_users([email])


# ───────────────────── POST /{catalog_id}/promote ─────────────────────


@pytest.mark.asyncio
async def test_promote_project_to_lab_as_director_200(client, as_platform_admin):
    cat_id = _insert_catalog(
        pipeline_name=_unique("jp-proj"),
        tier="project",
        scope_lab_id=SEED_LAB_ID,
    )
    try:
        resp = await client.post(
            f"/api/v1/pipelines/{cat_id}/promote",
            json={"target_tier": "lab", "lab_id": SEED_LAB_ID},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["tier"] == "lab"

        links = execute_query(
            "SELECT lab_id FROM lab_pipelines WHERE pipeline_catalog_id = :c",
            {"c": cat_id},
        )
        assert any(r["lab_id"] == SEED_LAB_ID for r in links)
    finally:
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_promote_project_to_lab_as_collaborator_403(client, monkeypatch):
    email = _unique("collab2") + "@test.com"
    _cleanup_users([email])
    uid = _make_user(email)
    _add_lab_membership(uid, SEED_LAB_ID, "Lab Collaborator", is_director=False)
    _switch_user(email, monkeypatch)

    cat_id = _insert_catalog(
        pipeline_name=_unique("jp-proj-2"),
        tier="project",
        scope_lab_id=SEED_LAB_ID,
    )
    try:
        resp = await client.post(
            f"/api/v1/pipelines/{cat_id}/promote",
            json={"target_tier": "lab", "lab_id": SEED_LAB_ID},
        )
        assert resp.status_code == 403
    finally:
        _cleanup_catalog_by_id(cat_id)
        _cleanup_users([email])


@pytest.mark.asyncio
async def test_promote_lab_to_zoo_as_admin_200(client, as_platform_admin):
    cat_id = _insert_catalog(
        pipeline_name=_unique("jp-lab"),
        tier="lab",
        scope_lab_id=SEED_LAB_ID,
    )
    try:
        resp = await client.post(
            f"/api/v1/pipelines/{cat_id}/promote",
            json={"target_tier": "zoo"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["tier"] == "zoo"
    finally:
        _cleanup_catalog_by_id(cat_id)


@pytest.mark.asyncio
async def test_promote_lab_to_zoo_as_non_admin_403(client, monkeypatch):
    email = _unique("dir") + "@test.com"
    _cleanup_users([email])
    uid = _make_user(email)
    _add_lab_membership(uid, SEED_LAB_ID, "Lab Director", is_director=True)
    _switch_user(email, monkeypatch)

    cat_id = _insert_catalog(
        pipeline_name=_unique("jp-lab-2"),
        tier="lab",
        scope_lab_id=SEED_LAB_ID,
    )
    try:
        resp = await client.post(
            f"/api/v1/pipelines/{cat_id}/promote",
            json={"target_tier": "zoo"},
        )
        assert resp.status_code == 403
    finally:
        _cleanup_catalog_by_id(cat_id)
        _cleanup_users([email])


@pytest.mark.asyncio
async def test_promote_zoo_to_lab_invalid_state_returns_400(client, as_platform_admin):
    cat_id = _insert_catalog(pipeline_name=_unique("jp-zoo-x"), tier="zoo")
    try:
        resp = await client.post(
            f"/api/v1/pipelines/{cat_id}/promote",
            json={"target_tier": "lab", "lab_id": SEED_LAB_ID},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_PROMOTION"
    finally:
        _cleanup_catalog_by_id(cat_id)
