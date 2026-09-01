"""M2-B5 — governance route guards, and membership as a grant-issuing act.

Two things here are new rather than converted.

The **split routes**: `tokens` and `users` gate only the half that reaches
another principal. Gating the whole route would break every user's control of
their own credentials, so the tests stand on both sides of that line.

**Membership now issues grants.** A `lab_membership` row stopped being a
decision input at M2-B1, so before this batch a member added after cutover
held nothing until someone ran a reseed — the row said Lab Collaborator and
every route disagreed.
"""

import uuid

import pytest

from backend.config import get_settings
from backend.database import execute_query, execute_write

SEED_LAB_ID = 1


def _switch_user(email: str, monkeypatch) -> None:
    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()


def _make_user(prefix: str) -> tuple[int, str]:
    email = f"{prefix}-{uuid.uuid4().hex[:6]}@test.com"
    uid = execute_write(
        "INSERT INTO users (email, name, organization_id, is_platform_admin, "
        "is_data_analyst, is_active) VALUES (:e, :e, 1, FALSE, FALSE, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET is_active = TRUE RETURNING id",
        {"e": email},
    )[0]["id"]
    return uid, email


def _pg_id(name: str) -> int:
    return execute_query("SELECT id FROM permission_groups WHERE name = :n", {"n": name})[0]["id"]


def _grants(user_id: int) -> set[str]:
    return {
        r["capability"]
        for r in execute_query(
            "SELECT capability FROM authz_capability_grants WHERE principal_id = :p",
            {"p": str(user_id)},
        )
    }


def _cleanup(emails: list[str]) -> None:
    for e in emails:
        rows = execute_query("SELECT id FROM users WHERE email = :e", {"e": e})
        if not rows:
            continue
        uid = rows[0]["id"]
        execute_write("DELETE FROM personal_tokens WHERE user_id = :u", {"u": uid})
        execute_write("DELETE FROM lab_membership WHERE user_id = :u", {"u": uid})
        execute_write(
            "DELETE FROM authz_capability_grants WHERE principal_id = :u", {"u": str(uid)}
        )
        execute_write("UPDATE audit_log SET actor_id = NULL WHERE actor_id = :u", {"u": uid})
        execute_write("DELETE FROM users WHERE id = :u", {"u": uid})


# ──────────────── membership issues, changes and revokes grants ───────────


@pytest.mark.asyncio
async def test_adding_a_member_issues_their_grants(client):
    """The M2-B1 finding this batch closes: membership is not access under the
    new model, so creating one has to create the access too."""
    emails: list[str] = []
    try:
        uid, email = _make_user("b5new")
        emails.append(email)
        assert _grants(uid) == set(), "fixture user should start with nothing"

        resp = await client.post(
            f"/api/v1/labs/{SEED_LAB_ID}/members",
            json={"user_id": uid, "permission_group_id": _pg_id("Lab Collaborator")},
        )
        assert resp.status_code == 201, resp.text
        caps = _grants(uid)
        assert "sample:read" in caps
        assert "sample:update" in caps
        # lab_member_rw, not lab_lead.
        assert "submission:approve" not in caps
    finally:
        _cleanup(emails)


@pytest.mark.asyncio
async def test_changing_a_members_role_changes_their_grants(client):
    """A promotion that left the old grants in place would be a director in
    the row and a collaborator to every route."""
    emails: list[str] = []
    try:
        uid, email = _make_user("b5prom")
        emails.append(email)
        await client.post(
            f"/api/v1/labs/{SEED_LAB_ID}/members",
            json={"user_id": uid, "permission_group_id": _pg_id("Lab Collaborator")},
        )
        assert "submission:approve" not in _grants(uid)

        resp = await client.patch(
            f"/api/v1/labs/{SEED_LAB_ID}/members/{uid}",
            json={"permission_group_id": _pg_id("Lab Director"), "is_lab_director": True},
        )
        assert resp.status_code == 200, resp.text
        caps = _grants(uid)
        assert "submission:approve" in caps
        assert "deletion:approve" in caps
    finally:
        _cleanup(emails)


@pytest.mark.asyncio
async def test_removing_a_member_removes_their_grants(client):
    """Otherwise removal is cosmetic — 'membership is not access', in reverse."""
    emails: list[str] = []
    try:
        uid, email = _make_user("b5rm")
        emails.append(email)
        await client.post(
            f"/api/v1/labs/{SEED_LAB_ID}/members",
            json={"user_id": uid, "permission_group_id": _pg_id("Lab Reader")},
        )
        assert _grants(uid), "member should hold grants before removal"

        resp = await client.delete(f"/api/v1/labs/{SEED_LAB_ID}/members/{uid}")
        assert resp.status_code == 200, resp.text
        assert _grants(uid) == set()
    finally:
        _cleanup(emails)


@pytest.mark.asyncio
async def test_membership_sync_does_not_touch_per_sample_grants(client):
    """Removal is scoped by source='reseed', so a per-sample access grant
    (source='direct') issued by the access-request workflow survives."""
    emails: list[str] = []
    try:
        uid, email = _make_user("b5keep")
        emails.append(email)
        await client.post(
            f"/api/v1/labs/{SEED_LAB_ID}/members",
            json={"user_id": uid, "permission_group_id": _pg_id("Lab Reader")},
        )
        execute_write(
            "INSERT INTO authz_capability_grants "
            "(principal_id, capability, scope_ref, source) "
            "VALUES (:p, 'sample:read_detail', :s, 'direct')",
            {"p": str(uid), "s": "instance://self/org/1/lab/1/project/1/sample/424242"},
        )
        await client.delete(f"/api/v1/labs/{SEED_LAB_ID}/members/{uid}")
        remaining = execute_query(
            "SELECT source FROM authz_capability_grants WHERE principal_id = :p",
            {"p": str(uid)},
        )
        assert [r["source"] for r in remaining] == ["direct"]
    finally:
        _cleanup(emails)


# ─────────────────────── the split routes: self vs other ──────────────────


@pytest.mark.asyncio
async def test_a_user_may_always_revoke_their_own_token(client, monkeypatch):
    """The self path is AUTH-ONLY BY DESIGN (§4.7). Gating the whole route on
    token:manage would take every user's control of their own credentials."""
    emails: list[str] = []
    try:
        uid, email = _make_user("b5tok")
        emails.append(email)
        _switch_user(email, monkeypatch)
        created = await client.post("/api/v1/tokens/", json={"name": "mine"})
        assert created.status_code == 201, created.text
        token_id = created.json()["data"]["id"]
        # Holds no capability at all, and still governs its own token.
        assert _grants(uid) == set()
        assert (await client.delete(f"/api/v1/tokens/{token_id}")).status_code == 200
    finally:
        _cleanup(emails)


@pytest.mark.asyncio
async def test_reaching_another_users_token_needs_token_manage(client, monkeypatch):
    emails: list[str] = []
    try:
        owner_id, owner_email = _make_user("b5towner")
        other_id, other_email = _make_user("b5tother")
        emails += [owner_email, other_email]

        _switch_user(owner_email, monkeypatch)
        created = await client.post("/api/v1/tokens/", json={"name": "owned"})
        token_id = created.json()["data"]["id"]

        _switch_user(other_email, monkeypatch)
        assert (await client.delete(f"/api/v1/tokens/{token_id}")).status_code == 403

        # token:manage sits in instance_administrator and nowhere else.
        execute_write(
            "INSERT INTO authz_capability_grants "
            "(principal_id, capability, scope_ref, source) "
            "VALUES (:p, 'token:manage', 'instance://self', 'reseed')",
            {"p": str(other_id)},
        )
        assert (await client.delete(f"/api/v1/tokens/{token_id}")).status_code == 200
    finally:
        _cleanup(emails)


@pytest.mark.asyncio
async def test_a_user_reads_themselves_without_any_capability(client, monkeypatch):
    """Self is not a capability — §3.1's scope tree has no user level, so
    'you are yourself' stays an identity comparison."""
    emails: list[str] = []
    try:
        uid, email = _make_user("b5self")
        emails.append(email)
        _switch_user(email, monkeypatch)
        assert _grants(uid) == set()
        assert (await client.get(f"/api/v1/users/{uid}")).status_code == 200
    finally:
        _cleanup(emails)


@pytest.mark.asyncio
async def test_reading_another_user_needs_user_manage(client, monkeypatch):
    emails: list[str] = []
    try:
        target_id, target_email = _make_user("b5target")
        nosy_id, nosy_email = _make_user("b5nosy")
        emails += [target_email, nosy_email]

        _switch_user(nosy_email, monkeypatch)
        assert (await client.get(f"/api/v1/users/{target_id}")).status_code == 403

        execute_write(
            "INSERT INTO authz_capability_grants "
            "(principal_id, capability, scope_ref, source) "
            "VALUES (:p, 'user:manage', 'instance://self', 'reseed')",
            {"p": str(nosy_id)},
        )
        assert (await client.get(f"/api/v1/users/{target_id}")).status_code == 200
    finally:
        _cleanup(emails)


# ────────────────────────── lab and project reads ─────────────────────────


@pytest.mark.asyncio
async def test_lab_detail_needs_lab_read_at_that_lab(client, monkeypatch):
    emails: list[str] = []
    try:
        uid, email = _make_user("b5lab")
        emails.append(email)
        _switch_user(email, monkeypatch)
        assert (await client.get(f"/api/v1/labs/{SEED_LAB_ID}")).status_code == 403

        execute_write(
            "INSERT INTO authz_capability_grants "
            "(principal_id, capability, scope_ref, source) "
            "VALUES (:p, 'lab:read', :s, 'reseed')",
            {"p": str(uid), "s": "instance://self/org/1/lab/1"},
        )
        assert (await client.get(f"/api/v1/labs/{SEED_LAB_ID}")).status_code == 200
    finally:
        _cleanup(emails)


@pytest.mark.asyncio
async def test_lab_directory_lists_only_what_you_can_read(client, monkeypatch):
    emails: list[str] = []
    try:
        uid, email = _make_user("b5dir")
        emails.append(email)
        _switch_user(email, monkeypatch)
        empty = await client.get("/api/v1/labs/?per_page=200")
        assert empty.status_code == 200, empty.text
        assert empty.json()["data"] == []

        execute_write(
            "INSERT INTO authz_capability_grants "
            "(principal_id, capability, scope_ref, source) "
            "VALUES (:p, 'lab:read', :s, 'reseed')",
            {"p": str(uid), "s": "instance://self/org/1/lab/1"},
        )
        listed = await client.get("/api/v1/labs/?per_page=200")
        assert {r["id"] for r in listed.json()["data"]} == {SEED_LAB_ID}
    finally:
        _cleanup(emails)
