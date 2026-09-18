"""Samples router — access control + CRUD tests.

Access model (per spec.md §5 Session H):

* ``can_see_sample`` — list visibility. PUBLIC and DISCOVERABLE are visible
  to any authenticated user; lab/project members + owner see their own.
* ``can_access_sample`` — detail access. DISCOVERABLE alone is NOT sufficient;
  detail requires Platform Admin, lab/project membership, ownership, PUBLIC,
  host-operator oversight (``surveillance_relevant``), or an APPROVED access request.
"""

from urllib.parse import quote

import pytest
from authz_helpers import grant_instance_preset, sync_grants_from_legacy_roles

from backend.authz.reseed import instance_preset
from backend.config import get_settings
from backend.database import execute_query, execute_write
from backend.routers import samples as samples_router

# ─────────────────────────── fixtures / helpers ────────────────────────────

SEED_USER_ID = 1  # admin@example.org, Platform Admin
SEED_LAB_ID = 1  # Example Lab
SEED_PROJECT_ID = 1  # Dev Project


def _cleanup_samples(prefix: str) -> None:
    rows = execute_query(
        "SELECT id FROM samples WHERE sample_id LIKE :p",
        {"p": f"{prefix}%"},
    )
    for r in rows:
        sid = r["id"]
        execute_write("DELETE FROM sample_files WHERE sample_id_fk = :id", {"id": sid})
        execute_write(
            "DELETE FROM sample_access_requests WHERE sample_id = :id",
            {"id": sid},
        )
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
        execute_write("DELETE FROM project_membership WHERE user_id = :u", {"u": uid})
        execute_write(
            "DELETE FROM sample_access_requests WHERE requester_id = :u OR owner_id = :u",
            {"u": uid},
        )
        execute_write(
            "UPDATE audit_log SET actor_id = NULL WHERE actor_id = :u",
            {"u": uid},
        )
        execute_write("DELETE FROM users WHERE id = :u", {"u": uid})


def _ensure_other_lab() -> int:
    """Create 'Other Lab' (distinct from the seeded Example Lab) on demand."""
    rows = execute_query("SELECT id FROM labs WHERE display_name = 'Other Lab'")
    if rows:
        return rows[0]["id"]
    new = execute_write(
        "INSERT INTO labs (organization_id, display_name, description, created_by_id) "
        "VALUES (1, 'Other Lab', 'Test lab for access-control tests', 1) RETURNING id",
    )
    lab_id = new[0]["id"]
    execute_write(
        "INSERT INTO projects (lab_id, display_name, description, created_by_id) "
        "VALUES (:l, 'Other Project', 'Other lab project', 1)",
        {"l": lab_id},
    )
    return lab_id


def _ensure_other_project(lab_id: int) -> int:
    rows = execute_query(
        "SELECT id FROM projects WHERE lab_id = :l ORDER BY id LIMIT 1",
        {"l": lab_id},
    )
    return rows[0]["id"] if rows else SEED_PROJECT_ID


def _make_user(
    email: str,
    *,
    is_platform_admin: bool = False,
    is_data_analyst: bool = False,
) -> int:
    rows = execute_write(
        "INSERT INTO users (email, name, organization_id, is_active) "
        "VALUES (:e, :e, 1, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET is_active = TRUE "
        "RETURNING id",
        {"e": email},
    )
    uid = rows[0]["id"]
    # The role is the grants now, ahead of M2-DROP. Both directions: these
    # helpers upsert on a re-used email, so a demotion must revoke.
    # instance_preset() rather than a hand-written ternary: it exists to be
    # the single answer to "which preset do these two flags mean", and a
    # second copy of that precedence is exactly what Rule 73 is about.
    grant_instance_preset(
        uid,
        instance_preset(is_platform_admin=is_platform_admin, is_data_analyst=is_data_analyst),
    )
    return uid


def _add_membership(user_id: int, lab_id: int, role: str, *, is_director: bool = False) -> None:
    execute_write(
        "INSERT INTO lab_membership (user_id, lab_id, permission_group_id, is_lab_director) "
        "SELECT :u, :l, pg.id, :d FROM permission_groups pg WHERE pg.name = :r "
        "ON CONFLICT (user_id, lab_id) DO UPDATE SET "
        "permission_group_id = EXCLUDED.permission_group_id, "
        "is_lab_director = EXCLUDED.is_lab_director",
        {"u": user_id, "l": lab_id, "r": role, "d": is_director},
    )


def _switch_user(email: str, monkeypatch) -> None:
    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()


def _insert_sample(
    sample_id: str,
    *,
    lab_id: int = SEED_LAB_ID,
    project_id: int = SEED_PROJECT_ID,
    owner_id: int = SEED_USER_ID,
    sharing_level: str = "PRIVATE",
    organism_name: str = "Severe acute respiratory syndrome coronavirus 2",
    surveillance_relevant: bool = False,
    fastq_r1_uri: str = "gs://jackpot-sequences/test/R1.fastq.gz",
    **overrides,
) -> dict:
    payload = {
        "sample_id": sample_id,
        "lab_id": lab_id,
        "project_id": project_id,
        "owner_id": owner_id,
        "source_type": "Human",
        "organism_name": organism_name,
        "type_of_experiment": "WGS",
        "library_preparation_method": "ARTIC",
        "sequencing_protocol": "https://www.protocols.io/view/artic-v4-1",
        "sequencing_platform": "Illumina",
        "sequencing_lab": "Example Sequencing Lab",
        "date_collected": "2026-01-15",
        "date_sequenced": "2026-01-17",
        "collection_facility": "Example Hospital",
        "collection_location_country": "United States",
        "sharing_level": sharing_level,
        "fastq_r1_uri": fastq_r1_uri,
        "surveillance_relevant": surveillance_relevant,
    }
    payload.update(overrides)
    cols = sorted(payload.keys())
    placeholders = [f":{c}" for c in cols]
    rows = execute_write(
        f"INSERT INTO samples ({', '.join(cols)}) VALUES ({', '.join(placeholders)}) RETURNING *",
        payload,
    )
    return rows[0]


def _pii_status(sample_pk: int) -> str:
    """Read the column back, rather than trusting a refusal's status code.

    A guard that returns 403 while still writing the row is the failure the
    negative tests below are actually about.
    """
    rows = execute_query("SELECT pii_scan_status FROM samples WHERE id = :id", {"id": sample_pk})
    return rows[0]["pii_scan_status"]


@pytest.fixture
def as_platform_admin(monkeypatch):
    _switch_user("admin@example.org", monkeypatch)


# ──────────────────────────────── tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_list_samples_returns_200_with_pagination_envelope(client, as_platform_admin):
    prefix = "H-LIST-"
    _cleanup_samples(prefix)
    _insert_sample(f"{prefix}A")
    _insert_sample(f"{prefix}B")
    resp = await client.get("/api/v1/samples/")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert "pagination" in body
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_list_filter_by_organism_name(client, as_platform_admin):
    prefix = "H-FILT-ORG-"
    _cleanup_samples(prefix)
    _insert_sample(f"{prefix}COV", organism_name="SARS-CoV-2-x")
    _insert_sample(f"{prefix}FLU", organism_name="Influenza A virus-x")
    resp = await client.get("/api/v1/samples/?organism_name=SARS-CoV-2-x")
    assert resp.status_code == 200
    names = {r["organism_name"] for r in resp.json()["data"]}
    assert "SARS-CoV-2-x" in names
    assert "Influenza A virus-x" not in names
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_list_select_all_returns_ids_only(client, as_platform_admin):
    prefix = "H-SELALL-"
    _cleanup_samples(prefix)
    a = _insert_sample(f"{prefix}A")
    b = _insert_sample(f"{prefix}B")
    # Filter to just our prefix via organism_name trick — use source_type filter
    # with a unique value so we know the result set is deterministic.
    resp = await client.get(
        f"/api/v1/samples/?select_all=true&lab_id={SEED_LAB_ID}&sharing_level=PRIVATE"
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "ids" in data
    assert a["id"] in data["ids"]
    assert b["id"] in data["ids"]
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_list_hides_other_lab_private_from_non_member(client, monkeypatch):
    prefix = "H-HIDE-"
    _cleanup_samples(prefix)
    other_lab = _ensure_other_lab()
    other_project = _ensure_other_project(other_lab)
    _insert_sample(
        f"{prefix}SECRET",
        lab_id=other_lab,
        project_id=other_project,
        sharing_level="PRIVATE",
    )

    email = "outsider@test.com"
    _cleanup_users([email])
    _make_user(email)
    _switch_user(email, monkeypatch)

    resp = await client.get(f"/api/v1/samples/?lab_id={other_lab}&sharing_level=PRIVATE")
    assert resp.status_code == 200
    ids = [r["sample_id"] for r in resp.json()["data"]]
    assert f"{prefix}SECRET" not in ids

    _cleanup_users([email])
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_list_shows_discoverable_to_outsider(client, monkeypatch):
    prefix = "H-DISC-"
    _cleanup_samples(prefix)
    other_lab = _ensure_other_lab()
    other_project = _ensure_other_project(other_lab)
    _insert_sample(
        f"{prefix}FINDME",
        lab_id=other_lab,
        project_id=other_project,
        sharing_level="DISCOVERABLE",
    )

    email = "finder@test.com"
    _cleanup_users([email])
    _make_user(email)
    _switch_user(email, monkeypatch)

    resp = await client.get(f"/api/v1/samples/?sharing_level=DISCOVERABLE&lab_id={other_lab}")
    assert resp.status_code == 200
    ids = [r["sample_id"] for r in resp.json()["data"]]
    assert f"{prefix}FINDME" in ids

    _cleanup_users([email])
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_get_sample_as_owner_returns_200(client, as_platform_admin):
    sid = "H-GET-OWN"
    _cleanup_samples(sid)
    s = _insert_sample(sid)
    resp = await client.get(f"/api/v1/samples/{s['id']}")
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["sample_id"] == sid
    assert "files" in body
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_get_sample_404_when_not_found(client, as_platform_admin):
    resp = await client.get("/api/v1/samples/99999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_private_other_lab_sample_returns_403(client, monkeypatch):
    sid = "H-GET-403"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _ensure_other_project(other_lab)
    s = _insert_sample(
        sid,
        lab_id=other_lab,
        project_id=other_project,
        sharing_level="PRIVATE",
        owner_id=SEED_USER_ID,  # owned by someone else after we switch
    )

    email = "noaccess@test.com"
    _cleanup_users([email])
    _make_user(email)
    _switch_user(email, monkeypatch)

    resp = await client.get(f"/api/v1/samples/{s['id']}")
    assert resp.status_code == 403

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_get_public_sample_200_for_any_auth_user(client, monkeypatch):
    sid = "H-GET-PUB"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _ensure_other_project(other_lab)
    s = _insert_sample(
        sid,
        lab_id=other_lab,
        project_id=other_project,
        sharing_level="PUBLIC",
    )

    email = "pubreader@test.com"
    _cleanup_users([email])
    _make_user(email)
    _switch_user(email, monkeypatch)

    resp = await client.get(f"/api/v1/samples/{s['id']}")
    assert resp.status_code == 200

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_discoverable_sample_detail_requires_access(client, monkeypatch):
    """DISCOVERABLE is visible in lists, but detail requires an approved request."""
    sid = "H-DISC-DET"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _ensure_other_project(other_lab)
    s = _insert_sample(
        sid,
        lab_id=other_lab,
        project_id=other_project,
        sharing_level="DISCOVERABLE",
    )

    email = "discseeker@test.com"
    _cleanup_users([email])
    uid = _make_user(email)
    _switch_user(email, monkeypatch)

    resp = await client.get(f"/api/v1/samples/{s['id']}")
    assert resp.status_code == 403

    # Grant an APPROVED access request — should now return 200.
    execute_write(
        "INSERT INTO sample_access_requests "
        "(sample_id, requester_id, owner_id, status) "
        "VALUES (:sid, :uid, :owner, 'APPROVED')",
        {"sid": s["id"], "uid": uid, "owner": SEED_USER_ID},
    )
    # Since M2-B2 the route decides on grants and policies, so the approved
    # request has to become the sample-scoped grant reseed() issues for it —
    # an APPROVED row is legacy state, not a decision input.
    sync_grants_from_legacy_roles()
    resp2 = await client.get(f"/api/v1/samples/{s['id']}")
    assert resp2.status_code == 200

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_data_analyst_can_access_surveillance_samples(client, monkeypatch):
    sid = "H-SURV-OPERATOR"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _ensure_other_project(other_lab)
    s = _insert_sample(
        sid,
        lab_id=other_lab,
        project_id=other_project,
        sharing_level="PRIVATE",
        surveillance_relevant=True,
    )

    email = "adhs_oversight@test.com"
    _cleanup_users([email])
    _make_user(email, is_data_analyst=True)
    # The is_data_analyst flag authorizes nothing by itself since M2-B1; it
    # reseeds to a sample:read_surveillance grant, which the surveillance
    # attribute-policy then reads.
    sync_grants_from_legacy_roles()
    _switch_user(email, monkeypatch)

    resp = await client.get(f"/api/v1/samples/{s['id']}")
    assert resp.status_code == 200

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_patch_updates_metadata_and_recomputes_quality(client, as_platform_admin):
    sid = "H-PATCH-01"
    _cleanup_samples(sid)
    s = _insert_sample(sid, strain="original")
    resp = await client.patch(
        f"/api/v1/samples/{s['id']}",
        json={"strain": "updated-strain", "comments": "patched by test"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["strain"] == "updated-strain"
    assert data["comments"] == "patched by test"
    # quality_status was recomputed — still a valid value
    assert data["quality_status"] in ("PRELIMINARY", "ANALYZABLE", "SUBMITTABLE")
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_patch_locked_fields_rejected(client, as_platform_admin):
    sid = "H-PATCH-LOCK"
    _cleanup_samples(sid)
    s = _insert_sample(sid)
    resp = await client.patch(
        f"/api/v1/samples/{s['id']}",
        json={"quality_status": "SUBMITTABLE"},
    )
    assert resp.status_code == 422
    assert "quality_status" in str(resp.json()["error"]["message"])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_patch_requires_lab_membership(client, monkeypatch):
    sid = "H-PATCH-403"
    _cleanup_samples(sid)
    s = _insert_sample(sid)

    email = "outlab@test.com"
    _cleanup_users([email])
    _make_user(email)
    _switch_user(email, monkeypatch)

    resp = await client.patch(
        f"/api/v1/samples/{s['id']}",
        json={"strain": "sneaky"},
    )
    assert resp.status_code == 403

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_patch_writes_audit_log(client, as_platform_admin):
    sid = "H-PATCH-AUD"
    _cleanup_samples(sid)
    s = _insert_sample(sid)
    resp = await client.patch(
        f"/api/v1/samples/{s['id']}",
        json={"comments": "audit test"},
    )
    assert resp.status_code == 200
    rows = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'sample' "
        "AND resource_id = :rid AND action = 'UPDATE_SAMPLE'",
        {"rid": str(s["id"])},
    )
    assert len(rows) >= 1
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_archive_as_lab_director_soft_deletes(client, as_platform_admin):
    sid = "H-ARCH-01"
    _cleanup_samples(sid)
    s = _insert_sample(sid)
    resp = await client.delete(f"/api/v1/samples/{s['id']}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["is_archived"] is True

    # Deleted rows should now be invisible to GET /{id}
    resp2 = await client.get(f"/api/v1/samples/{s['id']}")
    assert resp2.status_code == 404
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_archive_as_collaborator_returns_403(client, monkeypatch):
    sid = "H-ARCH-403"
    _cleanup_samples(sid)
    s = _insert_sample(sid)

    email = "collab@test.com"
    _cleanup_users([email])
    uid = _make_user(email)
    _add_membership(uid, SEED_LAB_ID, "Lab Collaborator", is_director=False)
    _switch_user(email, monkeypatch)

    resp = await client.delete(f"/api/v1/samples/{s['id']}")
    assert resp.status_code == 403

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_archive_writes_audit_log(client, as_platform_admin):
    sid = "H-ARCH-AUD"
    _cleanup_samples(sid)
    s = _insert_sample(sid)
    resp = await client.delete(f"/api/v1/samples/{s['id']}")
    assert resp.status_code == 200
    rows = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'sample' "
        "AND resource_id = :rid AND action = 'ARCHIVE_SAMPLE'",
        {"rid": str(s["id"])},
    )
    assert len(rows) >= 1
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_files_endpoint_returns_list(client, as_platform_admin):
    sid = "H-FILES-01"
    _cleanup_samples(sid)
    s = _insert_sample(sid)
    execute_write(
        "INSERT INTO sample_files (sample_id_fk, uri, filename, file_type, library_layout) "
        "VALUES (:sid, :uri, :fn, 'FASTQ', 'PAIRED')",
        {
            "sid": s["id"],
            "uri": f"gs://jackpot-sequences/{sid}/R1.fastq.gz",
            "fn": f"{sid}_R1.fastq.gz",
        },
    )
    resp = await client.get(f"/api/v1/samples/{s['id']}/files")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["filename"] == f"{sid}_R1.fastq.gz"
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_files_endpoint_403_for_outsider(client, monkeypatch):
    sid = "H-FILES-403"
    _cleanup_samples(sid)
    other_lab = _ensure_other_lab()
    other_project = _ensure_other_project(other_lab)
    s = _insert_sample(
        sid,
        lab_id=other_lab,
        project_id=other_project,
        sharing_level="PRIVATE",
    )

    email = "outsider_files@test.com"
    _cleanup_users([email])
    _make_user(email)
    _switch_user(email, monkeypatch)

    resp = await client.get(f"/api/v1/samples/{s['id']}/files")
    assert resp.status_code == 403

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_download_returns_presigned_url(client, as_platform_admin, monkeypatch):
    sid = "H-DL-01"
    _cleanup_samples(sid)
    s = _insert_sample(
        sid,
        fastq_r1_uri="gs://jackpot-sequences/test-bucket/R1.fastq.gz",
    )

    def _fake_sign(bucket, key, ttl_seconds=3600):
        return f"https://example.com/{bucket}/{key}?sig=fake&ttl={ttl_seconds}"

    monkeypatch.setattr("backend.routers.samples.generate_presigned_url", _fake_sign)

    resp = await client.get(f"/api/v1/samples/{s['id']}/download")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["url"].startswith("https://example.com/")
    assert data["expires_in"] == 3600
    assert data["file_type"] == "fastq_r1"
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_download_rejects_unknown_file_type(client, as_platform_admin):
    sid = "H-DL-BAD"
    _cleanup_samples(sid)
    s = _insert_sample(sid)
    resp = await client.get(f"/api/v1/samples/{s['id']}/download?file_type=bogus")
    assert resp.status_code == 422
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_download_404_when_uri_missing(client, as_platform_admin):
    sid = "H-DL-MISS"
    _cleanup_samples(sid)
    s = _insert_sample(sid)  # no assembly_uri set
    resp = await client.get(f"/api/v1/samples/{s['id']}/download?file_type=assembly")
    assert resp.status_code == 404
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_raw_fastq_download_restricted_to_lab_director(client, monkeypatch):
    sid = "H-DL-RAW"
    _cleanup_samples(sid)
    s = _insert_sample(
        sid,
        raw_fastq_uri="gs://jackpot-staging/test-bucket/raw_R1.fastq.gz",
    )

    email = "collab_dl@test.com"
    _cleanup_users([email])
    uid = _make_user(email)
    _add_membership(uid, SEED_LAB_ID, "Lab Collaborator", is_director=False)
    _switch_user(email, monkeypatch)

    resp = await client.get(f"/api/v1/samples/{s['id']}/download?file_type=raw_fastq")
    assert resp.status_code == 403

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_platform_admin_sees_all_labs(client, as_platform_admin):
    """Platform Admin short-circuits the visibility clause (TRUE) and sees all."""
    prefix = "H-ADMIN-"
    _cleanup_samples(prefix)
    other_lab = _ensure_other_lab()
    other_project = _ensure_other_project(other_lab)
    _insert_sample(
        f"{prefix}HIDDEN",
        lab_id=other_lab,
        project_id=other_project,
        sharing_level="PRIVATE",
    )
    resp = await client.get(f"/api/v1/samples/?lab_id={other_lab}&sharing_level=PRIVATE")
    assert resp.status_code == 200
    ids = [r["sample_id"] for r in resp.json()["data"]]
    assert f"{prefix}HIDDEN" in ids
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_patch_rejects_empty_body(client, as_platform_admin):
    sid = "H-PATCH-EMP"
    _cleanup_samples(sid)
    s = _insert_sample(sid)
    resp = await client.patch(f"/api/v1/samples/{s['id']}", json={})
    assert resp.status_code == 422
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_patch_rejects_invalid_json(client, as_platform_admin):
    sid = "H-PATCH-JSN"
    _cleanup_samples(sid)
    s = _insert_sample(sid)
    resp = await client.patch(
        f"/api/v1/samples/{s['id']}",
        content=b"{not valid",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_patch_nonexistent_sample_returns_404(client, as_platform_admin):
    resp = await client.patch(
        "/api/v1/samples/88888888",
        json={"strain": "x"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_archive_nonexistent_returns_404(client, as_platform_admin):
    resp = await client.delete("/api/v1/samples/77777777")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_filter_by_surveillance_relevant(client, as_platform_admin):
    prefix = "H-SURV-"
    _cleanup_samples(prefix)
    _insert_sample(f"{prefix}YES", surveillance_relevant=True)
    _insert_sample(f"{prefix}NO", surveillance_relevant=False)
    resp = await client.get(f"/api/v1/samples/?lab_id={SEED_LAB_ID}&surveillance_relevant=true")
    assert resp.status_code == 200
    ids = {r["sample_id"] for r in resp.json()["data"]}
    assert f"{prefix}YES" in ids
    assert f"{prefix}NO" not in ids
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_filter_by_date_range(client, as_platform_admin):
    prefix = "H-DT-"
    _cleanup_samples(prefix)
    _insert_sample(f"{prefix}JAN", date_collected="2026-01-15")
    _insert_sample(f"{prefix}FEB", date_collected="2026-02-15")
    resp = await client.get("/api/v1/samples/?date_from=2026-02-01&date_to=2026-02-28")
    assert resp.status_code == 200
    ids = {r["sample_id"] for r in resp.json()["data"]}
    assert f"{prefix}FEB" in ids
    assert f"{prefix}JAN" not in ids
    _cleanup_samples(prefix)


# quick smoke test to ensure the stub-era response was replaced cleanly
@pytest.mark.asyncio
async def test_list_returns_pagination_not_stub(client, as_platform_admin):
    resp = await client.get("/api/v1/samples/")
    body = resp.json()
    assert "router" not in body  # stub had {"router": "samples"}
    assert body.get("success") is True
    assert "data" in body


@pytest.mark.asyncio
async def test_patching_a_scanned_field_requeues_a_flagged_sample(client, as_platform_admin):
    """Critical Rule 43's second way off PII_DETECTED: the submitter fixes it.

    Nothing else moves a row back into ``run_pii_scan_job``'s queue, so
    without this a sample whose offending text is already gone stays
    blocked from pipelines and export behind a Lab Director override.
    """
    sid = "H-PATCH-PII"
    _cleanup_samples(sid)
    s = _insert_sample(sid, comments="call Jane Roe", pii_scan_status="PII_DETECTED")

    resp = await client.patch(
        f"/api/v1/samples/{s['id']}",
        json={"comments": "redacted"},
    )
    assert resp.status_code == 200, resp.text
    # The PATCH response is built from the second UPDATE in
    # _recompute_sample_derived_fields, so it reflects the requeue too.
    assert resp.json()["data"]["pii_scan_status"] == "PENDING"

    rows = execute_query(
        "SELECT metadata FROM audit_log WHERE resource_type = 'sample' "
        "AND resource_id = :rid AND action = 'UPDATE_SAMPLE' ORDER BY id DESC LIMIT 1",
        {"rid": str(s["id"])},
    )
    assert rows[0]["metadata"]["pii_rescan_requeued"] is True
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_patching_a_field_the_dlp_never_reads_leaves_the_flag(client, as_platform_admin):
    """``host_sex`` is enum-backed, so the scan never looked at it.

    Editing it cannot have removed the PII, and clearing the flag would
    hand every flagged submitter a one-field way around the block.
    """
    sid = "H-PATCH-PII-NOOP"
    _cleanup_samples(sid)
    s = _insert_sample(sid, comments="call Jane Roe", pii_scan_status="PII_DETECTED")

    resp = await client.patch(f"/api/v1/samples/{s['id']}", json={"host_sex": "F"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["pii_scan_status"] == "PII_DETECTED"
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_patching_a_clean_sample_does_not_send_it_back_for_scanning(
    client, as_platform_admin
):
    """Only PII_DETECTED is requeued — COMPLETE stays COMPLETE.

    Re-scanning every edit would be defensible policy, but it is not this
    change, and doing it accidentally would put the whole platform's edit
    traffic through Cloud DLP.
    """
    sid = "H-PATCH-PII-CLEAN"
    _cleanup_samples(sid)
    s = _insert_sample(sid, pii_scan_status="COMPLETE")

    resp = await client.patch(f"/api/v1/samples/{s['id']}", json={"comments": "edited"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["pii_scan_status"] == "COMPLETE"
    _cleanup_samples(sid)


# ─────────────── Critical Rule 43 — the Lab Director override ────────────────


def _make_lab_director(email: str, monkeypatch) -> int:
    _cleanup_users([email])
    uid = _make_user(email)
    _add_membership(uid, SEED_LAB_ID, "Lab Director", is_director=True)
    sync_grants_from_legacy_roles()
    _switch_user(email, monkeypatch)
    return uid


@pytest.mark.asyncio
async def test_a_lab_director_can_release_a_flagged_sample(client, monkeypatch):
    """Rule 43's first way off PII_DETECTED, and the reason for OVERRIDDEN.

    The new status is not COMPLETE: the scanner reporting it found nothing
    and a person deciding what it found is releasable are different facts,
    and only one of them needs a name attached.
    """
    sid = "H-PII-OVERRIDE"
    email = "pii_director@test.com"
    _cleanup_samples(sid)
    s = _insert_sample(sid, comments="call Jane Roe", pii_scan_status="PII_DETECTED")
    uid = _make_lab_director(email, monkeypatch)

    resp = await client.post(
        f"/api/v1/samples/{s['id']}/pii-override",
        json={"reason": "Reviewed; the name is the submitting PI, not a subject."},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["pii_scan_status"] == "OVERRIDDEN"

    rows = execute_query(
        "SELECT actor_id, metadata FROM audit_log WHERE resource_type = 'sample' "
        "AND resource_id = :rid AND action = 'OVERRIDE_PII_FLAG' ORDER BY id DESC LIMIT 1",
        {"rid": str(s["id"])},
    )
    assert rows, "the override must be audited — it is the record of the decision"
    assert rows[0]["actor_id"] == uid
    assert "submitting PI" in rows[0]["metadata"]["reason"]

    _cleanup_samples(sid)
    _cleanup_users([email])


@pytest.mark.asyncio
async def test_a_collaborator_cannot_release_a_flagged_sample(client, monkeypatch):
    sid = "H-PII-OVERRIDE-DENY"
    email = "pii_collab@test.com"
    _cleanup_samples(sid)
    s = _insert_sample(sid, pii_scan_status="PII_DETECTED")
    _cleanup_users([email])
    uid = _make_user(email)
    _add_membership(uid, SEED_LAB_ID, "Lab Collaborator", is_director=False)
    sync_grants_from_legacy_roles()
    _switch_user(email, monkeypatch)

    resp = await client.post(
        f"/api/v1/samples/{s['id']}/pii-override", json={"reason": "looks fine to me"}
    )
    assert resp.status_code == 403, resp.text
    assert _pii_status(s["id"]) == "PII_DETECTED"

    _cleanup_samples(sid)
    _cleanup_users([email])


@pytest.mark.asyncio
async def test_the_platform_admin_does_not_hold_the_override(client, monkeypatch):
    """Deliberate, and the canary for it.

    ``sample:pii_override`` is in the lab_lead preset alone. The instance
    administrator holds no content-plane sample verb (§8.2's note), and
    judging whether flagged free text is releasable means reading it. If
    someone later adds the verb to the admin preset, this test is what says
    so — nothing else would notice.

    A fresh admin with no lab membership, NOT the ``as_platform_admin``
    fixture: the baseline migration seeds ``admin@example.org`` as Lab
    Director of lab 1 as well, so that identity holds the verb through its
    membership. Reusing it would make this pass on the admin preset's
    behalf while actually proving nothing about the admin preset.
    """
    sid = "H-PII-OVERRIDE-ADMIN"
    email = "pii_pure_admin@test.com"
    _cleanup_samples(sid)
    _cleanup_users([email])
    s = _insert_sample(sid, pii_scan_status="PII_DETECTED")
    _make_user(email, is_platform_admin=True)
    _switch_user(email, monkeypatch)

    resp = await client.post(
        f"/api/v1/samples/{s['id']}/pii-override", json={"reason": "admin override"}
    )
    assert resp.status_code == 403, resp.text
    assert _pii_status(s["id"]) == "PII_DETECTED"
    _cleanup_samples(sid)
    _cleanup_users([email])


@pytest.mark.asyncio
async def test_releasing_a_sample_that_was_never_flagged_is_refused(client, monkeypatch):
    """409, not a no-op.

    On PENDING it would pre-empt a scan that has not run yet; on COMPLETE it
    would record a decision nobody had to make.
    """
    sid = "H-PII-OVERRIDE-UNFLAGGED"
    email = "pii_director2@test.com"
    _cleanup_samples(sid)
    s = _insert_sample(sid, pii_scan_status="PENDING")
    _make_lab_director(email, monkeypatch)

    resp = await client.post(
        f"/api/v1/samples/{s['id']}/pii-override", json={"reason": "pre-emptive"}
    )
    assert resp.status_code == 409, resp.text
    assert _pii_status(s["id"]) == "PENDING"

    _cleanup_samples(sid)
    _cleanup_users([email])


@pytest.mark.asyncio
async def test_an_override_without_a_reason_is_refused(client, monkeypatch):
    """The reason is the whole audit value of the endpoint."""
    sid = "H-PII-OVERRIDE-NOREASON"
    email = "pii_director3@test.com"
    _cleanup_samples(sid)
    s = _insert_sample(sid, pii_scan_status="PII_DETECTED")
    _make_lab_director(email, monkeypatch)

    resp = await client.post(f"/api/v1/samples/{s['id']}/pii-override", json={"reason": "   "})
    assert resp.status_code == 422, resp.text
    assert _pii_status(s["id"]) == "PII_DETECTED"

    _cleanup_samples(sid)
    _cleanup_users([email])


@pytest.mark.asyncio
async def test_an_overridden_sample_is_not_sent_back_for_scanning_by_an_edit(
    client, as_platform_admin
):
    """The PATCH requeue fires on PII_DETECTED only.

    Requeueing an overridden sample would let a later scan silently revoke a
    decision a person made and signed for.
    """
    sid = "H-PII-OVERRIDE-PATCH"
    _cleanup_samples(sid)
    s = _insert_sample(sid, pii_scan_status="OVERRIDDEN")

    resp = await client.patch(f"/api/v1/samples/{s['id']}", json={"comments": "edited"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["pii_scan_status"] == "OVERRIDDEN"
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_an_override_racing_a_fix_does_not_force_the_status_back(client, monkeypatch):
    """The UPDATE carries the status in its WHERE, not just the pre-check.

    Rule 43's two exits race each other: a PATCH that fixes the flagged field
    requeues the sample to PENDING, and an override that read PII_DETECTED a
    moment earlier would otherwise write OVERRIDDEN over it — recording a
    decision about text that no longer exists, with a ``before`` snapshot the
    audit row presents as current. Simulated by handing the route a stale read
    rather than by timing two requests.
    """
    sid = "H-PII-OVERRIDE-RACE"
    email = "pii_director_race@test.com"
    _cleanup_samples(sid)
    s = _insert_sample(sid, pii_scan_status="PII_DETECTED")
    _make_lab_director(email, monkeypatch)

    # What the route read a moment before the PATCH landed — the row as
    # inserted, still flagged.
    stale = dict(s)
    execute_write("UPDATE samples SET pii_scan_status = 'PENDING' WHERE id = :id", {"id": s["id"]})
    monkeypatch.setattr(samples_router, "_get_sample", lambda sample_id, db: stale)

    resp = await client.post(f"/api/v1/samples/{s['id']}/pii-override", json={"reason": "released"})
    assert resp.status_code == 409, resp.text
    assert _pii_status(s["id"]) == "PENDING"

    _cleanup_samples(sid)
    _cleanup_users([email])


# ───────────────── Rule 43's query gate: the open rungs close ──────────────
#
# The gate is five resource predicates in LADDER_POLICIES, tested row-wise and
# SQL-wise in tests/authz/test_pii_flag_suspends_open_rungs.py. What those
# cannot show is that the route reads the same verdict, which is the point of
# the three below: /{id} and the list are separate code paths (permit() vs
# visibility_sql_clause) and Rule 73 is about exactly that pair disagreeing.

_PII_ORGANISM = "Rule43 query-gate organism"
# Its own value: a list test that aborts before its cleanup would otherwise
# leave a row the owner test's narrowing filter picks up.
_OWNER_ORGANISM = "Rule43 query-gate organism, owned"


@pytest.mark.asyncio
async def test_a_stranger_cannot_read_a_flagged_public_sample(client, monkeypatch):
    """PUBLIC is what let the stranger in; the flag takes that rung away.

    And it comes back on OVERRIDDEN — same request, same principal, one
    column different — because a gate nothing reopens is a gate that hides
    the sample forever.
    """
    sid = "H-PII-GATE-DETAIL"
    email = "pii_stranger@test.com"
    _cleanup_samples(sid)
    _cleanup_users([email])
    other_lab = _ensure_other_lab()
    s = _insert_sample(
        sid,
        lab_id=other_lab,
        project_id=_ensure_other_project(other_lab),
        sharing_level="PUBLIC",
        pii_scan_status="PII_DETECTED",
    )
    _make_user(email)
    _switch_user(email, monkeypatch)

    resp = await client.get(f"/api/v1/samples/{s['id']}")
    assert resp.status_code == 403, resp.text

    execute_write(
        "UPDATE samples SET pii_scan_status = 'OVERRIDDEN' WHERE id = :id", {"id": s["id"]}
    )
    released = await client.get(f"/api/v1/samples/{s['id']}")
    assert released.status_code == 200, released.text

    _cleanup_users([email])
    _cleanup_samples(sid)


@pytest.mark.asyncio
async def test_the_list_drops_a_flagged_sample_and_keeps_its_clean_twin(client, monkeypatch):
    """Two PUBLIC samples differing only in the flag — one comes back.

    The clean twin is what makes this a test of the flag rather than of the
    fixture: a list that returned neither would pass a one-sample assertion.
    """
    prefix = "H-PII-GATE-LIST-"
    email = "pii_lister@test.com"
    _cleanup_samples(prefix)
    _cleanup_users([email])
    other_lab = _ensure_other_lab()
    other_project = _ensure_other_project(other_lab)
    for suffix, status in (("CLEAN", "COMPLETE"), ("FLAGGED", "PII_DETECTED")):
        _insert_sample(
            f"{prefix}{suffix}",
            lab_id=other_lab,
            project_id=other_project,
            sharing_level="PUBLIC",
            organism_name=_PII_ORGANISM,
            pii_scan_status=status,
        )
    _make_user(email)
    _switch_user(email, monkeypatch)

    resp = await client.get(f"/api/v1/samples/?organism_name={quote(_PII_ORGANISM)}")
    assert resp.status_code == 200, resp.text
    returned = {row["sample_id"] for row in resp.json()["data"]}
    assert returned == {f"{prefix}CLEAN"}

    _cleanup_users([email])
    _cleanup_samples(prefix)


@pytest.mark.asyncio
async def test_the_owner_still_sees_their_own_flagged_sample(client, monkeypatch):
    """The half of Rule 43 a DENY would have broken.

    "until the submitter fixes the flagged fields" is only reachable if the
    submitter can still read the fields. The suspension is on the rungs that
    open a row to someone with no tie to it, and ownership is not one of
    those — asserted here against the route, not against permit(), because
    the route is where a later DENY would show up.
    """
    sid = "H-PII-GATE-OWNER"
    email = "pii_owner@test.com"
    _cleanup_samples(sid)
    _cleanup_users([email])
    uid = _make_user(email)
    other_lab = _ensure_other_lab()
    s = _insert_sample(
        sid,
        lab_id=other_lab,
        project_id=_ensure_other_project(other_lab),
        owner_id=uid,
        sharing_level="PRIVATE",
        organism_name=_OWNER_ORGANISM,
        pii_scan_status="PII_DETECTED",
    )
    _switch_user(email, monkeypatch)

    resp = await client.get(f"/api/v1/samples/{s['id']}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["pii_scan_status"] == "PII_DETECTED"

    listed = await client.get(f"/api/v1/samples/?organism_name={quote(_OWNER_ORGANISM)}")
    assert listed.status_code == 200, listed.text
    assert {row["sample_id"] for row in listed.json()["data"]} == {sid}

    # Samples first here, unlike the tests above: this user owns the row, and
    # samples_owner_id_fkey has no ON DELETE.
    _cleanup_samples(sid)
    _cleanup_users([email])
