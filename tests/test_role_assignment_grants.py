# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Assigning a role must issue the grants, at every site that assigns one.

M2-B1 made ``authz_capability_grants`` the decision input. Nothing reads
``users.is_platform_admin`` or a ``lab_membership`` row to decide any more, so
a route that writes one of those and stops has not changed anyone's
authorization — it has written a field that means nothing until the next
``reseed()`` runs, at which point it silently starts meaning something. §4.5
scopes ``user:manage`` as "create/modify/deactivate users, **assign
capabilities**": issuing the grants IS the assignment.

M2-B5 wired this for ``labs.py``'s membership routes and left three sites:

- ``PATCH /users/{id}`` writing ``is_platform_admin`` / ``is_data_analyst``
- ``POST /auth/dev-login`` writing the same two flags via its ``role``
- ``POST /auth/dev-login`` writing ``lab_membership`` — the lab half, in the
  same request as the instance half, still unsynced after M2-B5 fixed the
  identical code in ``labs.py``

Every assertion here goes through a route rather than through the grants
table. The grants table is how it works; "can this principal now do the thing
the role names" is what the change is for, and the two came apart precisely
because nothing was standing at the second one.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.config import get_settings
from backend.database import execute_query, execute_write
from backend.main import app

ADMIN = "admin@example.org"
SUBJECT = "roleassign-subject@example.org"
BYSTANDER = "roleassign-bystander@example.org"
DEV = "roleassign-dev@example.org"
EMAILS = (SUBJECT, BYSTANDER, DEV)


def _act_as(email: str, monkeypatch) -> None:
    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()


def _mk_user(email: str) -> int:
    return execute_write(
        "INSERT INTO users (email, name, organization_id, is_platform_admin, "
        "is_data_analyst, is_active) VALUES (:e, :e, 1, FALSE, FALSE, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET is_platform_admin = FALSE, "
        "is_data_analyst = FALSE, is_active = TRUE RETURNING id",
        {"e": email},
    )[0]["id"]


def _purge(email: str) -> None:
    rows = execute_query("SELECT id FROM users WHERE email = :e", {"e": email})
    for row in rows:
        execute_write(
            "DELETE FROM authz_capability_grants WHERE principal_id = :p", {"p": str(row["id"])}
        )
        execute_write("DELETE FROM lab_membership WHERE user_id = :u", {"u": row["id"]})
        execute_write("UPDATE audit_log SET actor_id = NULL WHERE actor_id = :u", {"u": row["id"]})
    execute_write("DELETE FROM users WHERE email = :e", {"e": email})


@pytest.fixture
def users():
    for email in EMAILS:
        _purge(email)
    ids = {SUBJECT: _mk_user(SUBJECT), BYSTANDER: _mk_user(BYSTANDER)}
    yield ids
    for email in EMAILS:
        _purge(email)


async def _can_manage_users(subject_id: int, target_id: int, monkeypatch) -> bool:
    """Does this principal hold user:manage? Asked through a route that needs it."""
    email = execute_query("SELECT email FROM users WHERE id = :i", {"i": subject_id})[0]["email"]
    _act_as(email, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(f"/api/v1/users/{target_id}", json={"name": "renamed by subject"})
    return resp.status_code == 200


@pytest.mark.asyncio
async def test_promoting_a_user_grants_them_instance_capabilities(client, users, monkeypatch):
    """PATCH is_platform_admin=true must take effect on this request.

    Before the fix the field flipped, the response was 200, and the promoted
    user held nothing — until some later migration ran a reseed and quietly
    made it real.
    """
    subject, bystander = users[SUBJECT], users[BYSTANDER]
    assert not await _can_manage_users(subject, bystander, monkeypatch)

    _act_as(ADMIN, monkeypatch)
    resp = await client.patch(f"/api/v1/users/{subject}", json={"is_platform_admin": True})
    assert resp.status_code == 200, resp.text

    assert await _can_manage_users(subject, bystander, monkeypatch), (
        "promoted to platform admin but still cannot act as one — the flag was "
        "written without issuing the grants it stands for"
    )


@pytest.mark.asyncio
async def test_demoting_a_user_revokes_their_instance_capabilities(client, users, monkeypatch):
    """The direction that matters more: revocation must be immediate."""
    subject, bystander = users[SUBJECT], users[BYSTANDER]

    _act_as(ADMIN, monkeypatch)
    assert (
        await client.patch(f"/api/v1/users/{subject}", json={"is_platform_admin": True})
    ).status_code == 200
    assert await _can_manage_users(subject, bystander, monkeypatch)

    _act_as(ADMIN, monkeypatch)
    resp = await client.patch(f"/api/v1/users/{subject}", json={"is_platform_admin": False})
    assert resp.status_code == 200, resp.text

    assert not await _can_manage_users(subject, bystander, monkeypatch), (
        "demoted but still able to act as an admin — a revocation that does not "
        "revoke is worse than one that never happened"
    )


@pytest.mark.asyncio
async def test_data_analyst_promotion_grants_the_surveillance_preset(client, users, monkeypatch):
    """is_data_analyst maps to Surveillance Officer, not to nothing."""
    subject = users[SUBJECT]
    _act_as(ADMIN, monkeypatch)
    resp = await client.patch(f"/api/v1/users/{subject}", json={"is_data_analyst": True})
    assert resp.status_code == 200, resp.text

    held = {
        r["capability"]
        for r in execute_query(
            "SELECT capability FROM authz_capability_grants WHERE principal_id = :p",
            {"p": str(subject)},
        )
    }
    assert "sample:read_surveillance" in held, held


@pytest.mark.asyncio
async def test_admin_flag_wins_over_analyst_flag(client, users, monkeypatch):
    """reseed() reads analysts as ``is_data_analyst AND NOT is_platform_admin``.

    The live path has to apply the same precedence or a principal's grants
    would depend on whether they were last written by a PATCH or by a reseed.
    """
    subject = users[SUBJECT]
    _act_as(ADMIN, monkeypatch)
    resp = await client.patch(
        f"/api/v1/users/{subject}", json={"is_platform_admin": True, "is_data_analyst": True}
    )
    assert resp.status_code == 200, resp.text

    held = {
        r["capability"]
        for r in execute_query(
            "SELECT capability FROM authz_capability_grants WHERE principal_id = :p",
            {"p": str(subject)},
        )
    }
    assert "user:manage" in held, held
    assert "anomaly:triage" not in held, (
        "both presets were issued; reseed would have issued only the admin one"
    )


@pytest.mark.asyncio
async def test_dev_login_lab_role_issues_lab_grants(users, monkeypatch):
    """The lab half of dev-login, unsynced after M2-B5 fixed the same code in labs.py."""
    _purge(DEV)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/dev-login", json={"email": DEV, "role": "Lab Director"}
            )
            assert resp.status_code == 200, resp.text
            lab_id = resp.json()["membership"]["lab_id"]

            # Probe with org:manage at lab scope — held by lab_lead and by no
            # other lab preset, so a 200 means the Lab Director grants landed
            # rather than that any membership at all did. Restored below; the
            # lab row is shared with every other test in the session.
            before = execute_query("SELECT description FROM labs WHERE id = :i", {"i": lab_id})[0][
                "description"
            ]
            _act_as(DEV, monkeypatch)
            try:
                edited = await c.patch(
                    f"/api/v1/labs/{lab_id}", json={"description": "role-assignment probe"}
                )
            finally:
                execute_write(
                    "UPDATE labs SET description = :d WHERE id = :i RETURNING id",
                    {"d": before, "i": lab_id},
                )
        assert edited.status_code == 200, (
            "dev-login made this user a Lab Director but issued no grants, so the "
            f"role is inert: {edited.text}"
        )
    finally:
        _purge(DEV)


@pytest.mark.asyncio
async def test_dev_login_platform_admin_role_issues_instance_grants(users, monkeypatch):
    """And the instance half, via the same ``role`` parameter."""
    _purge(DEV)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/dev-login", json={"email": DEV, "role": "Platform Admin"}
            )
            assert resp.status_code == 200, resp.text
        assert await _can_manage_users(
            execute_query("SELECT id FROM users WHERE email = :e", {"e": DEV})[0]["id"],
            users[BYSTANDER],
            monkeypatch,
        )
    finally:
        _purge(DEV)
