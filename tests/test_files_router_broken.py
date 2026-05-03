"""Tests for GET /api/v1/files/broken (Phase P0f F-10).

The broken-files endpoint scopes results to the user's accessible labs
via the same visibility ladder used by /api/v1/samples/. Pagination,
filter parameters, and the empty-state response are exercised here.
"""

import pytest

from backend.config import get_settings
from backend.database import execute_query, execute_write

SEED_USER_ID = 1
SEED_LAB_ID = 1
SEED_PROJECT_ID = 1


def _cleanup_samples(prefix: str) -> None:
    rows = execute_query(
        "SELECT id FROM samples WHERE sample_id LIKE :p",
        {"p": f"{prefix}%"},
    )
    for r in rows:
        sid = r["id"]
        execute_write("DELETE FROM sample_files WHERE sample_id_fk = :id", {"id": sid})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'sample' AND resource_id = :rid",
            {"rid": str(sid)},
        )
        execute_write("DELETE FROM samples WHERE id = :id", {"id": sid})


def _cleanup_users(emails: list[str]) -> None:
    for e in emails:
        rows = execute_query("SELECT id FROM users WHERE email = :e", {"e": e})
        if not rows:
            continue
        uid = rows[0]["id"]
        execute_write("DELETE FROM lab_membership WHERE user_id = :u", {"u": uid})
        execute_write("UPDATE audit_log SET actor_id = NULL WHERE actor_id = :u", {"u": uid})
        execute_write("DELETE FROM users WHERE id = :u", {"u": uid})


def _ensure_other_lab() -> int:
    rows = execute_query("SELECT id FROM labs WHERE display_name = 'Other Lab'")
    if rows:
        return rows[0]["id"]
    new = execute_write(
        "INSERT INTO labs (organization_id, display_name, description, created_by_id) "
        "VALUES (1, 'Other Lab', 'Test lab for broken-files tests', 1) RETURNING id",
    )
    return new[0]["id"]


def _make_user(email: str, *, is_platform_admin: bool = False) -> int:
    rows = execute_write(
        "INSERT INTO users (email, name, organization_id, "
        "is_platform_admin, is_active) "
        "VALUES (:e, :e, 1, :pa, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET "
        "is_platform_admin = EXCLUDED.is_platform_admin, is_active = TRUE "
        "RETURNING id",
        {"e": email, "pa": is_platform_admin},
    )
    return rows[0]["id"]


def _add_membership(user_id: int, lab_id: int) -> None:
    execute_write(
        "INSERT INTO lab_membership (user_id, lab_id, permission_group_id, is_lab_director) "
        "SELECT :u, :l, pg.id, FALSE FROM permission_groups pg "
        "WHERE pg.name = 'Lab Collaborator' "
        "ON CONFLICT (user_id, lab_id) DO NOTHING",
        {"u": user_id, "l": lab_id},
    )


def _insert_sample(sample_id: str, *, lab_id: int = SEED_LAB_ID) -> int:
    rows = execute_write(
        """
        INSERT INTO samples (
            sample_id, lab_id, project_id, owner_id, source_type, organism_name,
            type_of_experiment, library_preparation_method, sequencing_protocol,
            sequencing_platform, sequencing_lab, date_collected, date_sequenced,
            collection_facility, collection_location_country, sharing_level,
            fastq_r1_uri, surveillance_relevant
        ) VALUES (
            :sid, :lab, 1, 1, 'Human',
            'Severe acute respiratory syndrome coronavirus 2',
            'WGS', 'ARTIC', 'https://www.protocols.io/view/artic-v4-1',
            'Illumina', 'Example Sequencing Lab', '2026-01-15', '2026-01-17',
            'Example Hospital', 'United States', 'PRIVATE',
            'gs://test/R1.fastq.gz', FALSE
        ) RETURNING id
        """,
        {"sid": sample_id, "lab": lab_id},
    )
    return rows[0]["id"]


def _insert_broken_file(
    sample_id_fk: int,
    *,
    uri: str,
    status: str = "MISSING",
) -> int:
    rows = execute_write(
        """
        INSERT INTO sample_files (
            sample_id_fk, uri, filename, file_size_bytes,
            file_type, library_layout, read_direction,
            storage_state, last_verification_status, last_verified_at,
            scrub_status, ingest_method
        ) VALUES (
            :sid, :uri, :fn, 1024,
            'FASTQ', 'PAIRED', 'R1',
            CAST('BROKEN' AS file_storage_state), :st, NOW(),
            'PENDING', 'register'
        ) RETURNING id
        """,
        {"sid": sample_id_fk, "uri": uri, "fn": uri.rsplit("/", 1)[-1], "st": status},
    )
    return rows[0]["id"]


def _switch_user(email: str, monkeypatch) -> None:
    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()


@pytest.fixture
def as_platform_admin(monkeypatch):
    _switch_user("admin@example.org", monkeypatch)


@pytest.mark.asyncio
async def test_list_broken_files_returns_user_accessible_only(client, monkeypatch):
    """A user in lab A only sees broken files from lab A — not lab B."""
    prefix = "F10-SCOPE-"
    _cleanup_samples(prefix)
    other_lab_id = _ensure_other_lab()

    sample_a_id = _insert_sample(f"{prefix}A", lab_id=SEED_LAB_ID)
    sample_b_id = _insert_sample(f"{prefix}B", lab_id=other_lab_id)
    _insert_broken_file(sample_a_id, uri="file:///srv/A_R1.fastq")
    _insert_broken_file(sample_b_id, uri="file:///srv/B_R1.fastq")

    email = "f10-scope-user@test.com"
    user_id = _make_user(email)
    _add_membership(user_id, SEED_LAB_ID)
    _switch_user(email, monkeypatch)

    resp = await client.get("/api/v1/files/broken")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    sample_ids = {row["sample_id"] for row in body["data"]}
    assert f"{prefix}A" in sample_ids
    assert f"{prefix}B" not in sample_ids

    _cleanup_users([email])
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_list_broken_files_pagination(client, as_platform_admin):
    prefix = "F10-PAGE-"
    _cleanup_samples(prefix)
    sample_id = _insert_sample(f"{prefix}A")
    for i in range(7):
        _insert_broken_file(sample_id, uri=f"file:///srv/page_{i}.fastq")

    resp = await client.get("/api/v1/files/broken?per_page=3&page=1")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["data"]) == 3
    assert body["pagination"]["total"] >= 7
    assert body["pagination"]["per_page"] == 3
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_list_broken_files_empty_returns_empty_list(client, as_platform_admin):
    """No BROKEN rows at all → empty data list, 200 OK, pagination total 0."""
    prefix = "F10-EMPTY-"
    _cleanup_samples(prefix)
    # Clear any pre-existing BROKEN rows so the assertion is deterministic.
    execute_write(
        "UPDATE sample_files SET storage_state = CAST('EXTERNAL' AS file_storage_state) "
        "WHERE storage_state = CAST('BROKEN' AS file_storage_state)"
    )
    resp = await client.get("/api/v1/files/broken")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == []
    assert body["pagination"]["total"] == 0


@pytest.mark.asyncio
async def test_list_broken_files_filter_by_lab_id(client, as_platform_admin):
    prefix = "F10-LAB-"
    _cleanup_samples(prefix)
    other_lab_id = _ensure_other_lab()

    sample_a = _insert_sample(f"{prefix}A", lab_id=SEED_LAB_ID)
    sample_b = _insert_sample(f"{prefix}B", lab_id=other_lab_id)
    _insert_broken_file(sample_a, uri="file:///srv/lab_a.fastq")
    _insert_broken_file(sample_b, uri="file:///srv/lab_b.fastq")

    resp = await client.get(f"/api/v1/files/broken?lab_id={other_lab_id}")
    assert resp.status_code == 200, resp.text
    sample_ids = {row["sample_id"] for row in resp.json()["data"]}
    assert sample_ids == {f"{prefix}B"}
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_list_broken_files_filter_by_project_id(client, as_platform_admin):
    prefix = "F10-PROJ-"
    _cleanup_samples(prefix)
    sample_id = _insert_sample(f"{prefix}A")
    _insert_broken_file(sample_id, uri="file:///srv/proj.fastq")

    resp = await client.get(f"/api/v1/files/broken?project_id={SEED_PROJECT_ID}")
    assert resp.status_code == 200, resp.text
    sample_ids = {row["sample_id"] for row in resp.json()["data"]}
    assert f"{prefix}A" in sample_ids

    # A non-matching project_id should exclude the row.
    resp = await client.get("/api/v1/files/broken?project_id=999999")
    sample_ids = {row["sample_id"] for row in resp.json()["data"]}
    assert f"{prefix}A" not in sample_ids
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_list_broken_files_filter_by_status(client, as_platform_admin):
    prefix = "F10-STAT-"
    _cleanup_samples(prefix)
    sample_id = _insert_sample(f"{prefix}A")
    _insert_broken_file(sample_id, uri="file:///srv/missing.fastq", status="MISSING")
    _insert_broken_file(sample_id, uri="file:///srv/sized.fastq", status="SIZE_CHANGED")

    resp = await client.get("/api/v1/files/broken?status_filter=SIZE_CHANGED")
    assert resp.status_code == 200, resp.text
    statuses = {row["last_verification_status"] for row in resp.json()["data"]}
    assert statuses == {"SIZE_CHANGED"}

    # Invalid status_filter must be rejected with 422 to prevent SQL noise.
    bad = await client.get("/api/v1/files/broken?status_filter=GARBAGE")
    assert bad.status_code == 422
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_samples_filter_show_only_with_broken_files(client, as_platform_admin):
    """Phase P0f F-10: ?has_broken_files=true on /api/v1/samples/."""
    prefix = "F10-SHF-"
    _cleanup_samples(prefix)
    healthy = _insert_sample(f"{prefix}HEALTHY")
    broken = _insert_sample(f"{prefix}BROKEN")
    _insert_broken_file(broken, uri="file:///srv/shf.fastq")
    # Healthy sample also has a sample_files row, but in EXTERNAL state.
    execute_write(
        """
        INSERT INTO sample_files (
            sample_id_fk, uri, filename, file_size_bytes,
            file_type, library_layout, read_direction,
            storage_state, scrub_status, ingest_method
        ) VALUES (
            :sid, 'file:///srv/healthy.fastq', 'healthy.fastq', 1024,
            'FASTQ', 'PAIRED', 'R1',
            CAST('EXTERNAL' AS file_storage_state), 'PENDING', 'register'
        )
        """,
        {"sid": healthy},
    )

    resp = await client.get("/api/v1/samples/?has_broken_files=true&per_page=200")
    assert resp.status_code == 200, resp.text
    sample_ids = {row["sample_id"] for row in resp.json()["data"]}
    assert f"{prefix}BROKEN" in sample_ids
    assert f"{prefix}HEALTHY" not in sample_ids
    _cleanup_samples(prefix)
