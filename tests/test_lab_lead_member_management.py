# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""A Lab Lead manages their own lab's roster, and only their own lab's.

M2 replaced ``require_lab_director(user, lab_id)`` on the four
``/labs/{id}/members`` routes with ``require_capability("user:manage")`` at Lab
scope. No lab preset holds ``user:manage``, so the capability landed on
instance admins alone and Lab Directors lost the ability to manage the lab they
direct. It is not in the endpoint map's "Deliberate narrowings" list — nobody
decided it, and M2-B5 went on to wire grant issuance into routes that by then
no lab principal could reach.

The fix puts ``user:manage`` in ``lab_lead``, the way ``org:manage`` already
sits there for ``PATCH /labs/{id}``. What makes that safe rather than a
promotion to global user administration is scope, and scope only: the routes
that administer users at large — ``PATCH /users/{id}``, ``DELETE
/users/{id}`` — ask for ``user:manage`` with no scope argument, which resolves
to the instance root, and a ``lab://`` grant does not contain the root. That
asymmetry is the whole safety argument, so it is pinned by
``test_lab_lead_cannot_manage_users_globally`` below rather than left to the
reader.
"""

import pytest

from backend.config import get_settings
from backend.database import execute_query, execute_write

ADMIN = "admin@example.org"
LEAD = "lablead-member-mgmt@example.org"
OTHER_LEAD = "otherlab-lead@example.org"
MEMBER = "lablead-member-target@example.org"
EMAILS = (LEAD, OTHER_LEAD, MEMBER)

SEED_LAB = 1


def _act_as(email: str, monkeypatch) -> None:
    monkeypatch.setenv("MOCK_USER_EMAIL", email)
    get_settings.cache_clear()


def _mk_user(email: str) -> int:
    return execute_write(
        "INSERT INTO users (email, name, organization_id, is_platform_admin, "
        "is_data_analyst, is_active) VALUES (:e, :e, 1, FALSE, FALSE, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET is_platform_admin = FALSE, is_active = TRUE "
        "RETURNING id",
        {"e": email},
    )[0]["id"]


def _mk_lab(name: str) -> int:
    return execute_write(
        "INSERT INTO labs (organization_id, display_name, description, created_by_id) "
        "VALUES (1, :n, 'second lab for scope tests', 1) RETURNING id",
        {"n": name},
    )[0]["id"]


def _make_lead(user_id: int, lab_id: int) -> None:
    """Directorship plus the grants it now conveys, the way the routes do it."""
    from backend.authz.reseed import sync_membership_grants
    from backend.database import _get_engine

    execute_write(
        "INSERT INTO lab_membership (user_id, lab_id, permission_group_id, is_lab_director) "
        "SELECT :u, :l, pg.id, TRUE FROM permission_groups pg WHERE pg.name = 'Lab Director' "
        "ON CONFLICT (user_id, lab_id) DO UPDATE SET "
        "permission_group_id = EXCLUDED.permission_group_id, is_lab_director = TRUE",
        {"u": user_id, "l": lab_id},
    )
    engine, _ = _get_engine()
    with engine.begin() as conn:
        sync_membership_grants(conn, user_id=user_id, lab_id=lab_id, group_name="Lab Director")


def _purge(email: str) -> None:
    for row in execute_query("SELECT id FROM users WHERE email = :e", {"e": email}):
        execute_write(
            "DELETE FROM authz_capability_grants WHERE principal_id = :p", {"p": str(row["id"])}
        )
        execute_write("DELETE FROM lab_membership WHERE user_id = :u", {"u": row["id"]})
        execute_write("UPDATE audit_log SET actor_id = NULL WHERE actor_id = :u", {"u": row["id"]})
    execute_write("DELETE FROM users WHERE email = :e", {"e": email})


@pytest.fixture
def roster():
    for email in EMAILS:
        _purge(email)
    execute_write("DELETE FROM labs WHERE display_name = 'Second Lab (scope test)'")
    ids = {e: _mk_user(e) for e in EMAILS}
    other_lab = _mk_lab("Second Lab (scope test)")
    _make_lead(ids[LEAD], SEED_LAB)
    _make_lead(ids[OTHER_LEAD], other_lab)
    yield {**ids, "other_lab": other_lab}
    for email in EMAILS:
        _purge(email)
    execute_write("DELETE FROM lab_membership WHERE lab_id = :l", {"l": other_lab})
    execute_write("DELETE FROM labs WHERE id = :l", {"l": other_lab})


@pytest.mark.asyncio
async def test_lab_lead_lists_their_own_lab_members(client, roster, monkeypatch):
    _act_as(LEAD, monkeypatch)
    resp = await client.get(f"/api/v1/labs/{SEED_LAB}/members")
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_lab_lead_adds_and_removes_a_member(client, roster, monkeypatch):
    """The round trip, because M2-B5 wired grant issuance into these routes
    while no lab principal could reach them."""
    _act_as(LEAD, monkeypatch)
    target = roster[MEMBER]

    collaborator = execute_query(
        "SELECT id FROM permission_groups WHERE name = 'Lab Collaborator'"
    )[0]["id"]
    added = await client.post(
        f"/api/v1/labs/{SEED_LAB}/members",
        json={"user_id": target, "permission_group_id": collaborator},
    )
    assert added.status_code in (200, 201), added.text

    held = {
        r["capability"]
        for r in execute_query(
            "SELECT capability FROM authz_capability_grants WHERE principal_id = :p",
            {"p": str(target)},
        )
    }
    assert "sample:create" in held, f"member added but granted nothing: {held}"

    removed = await client.delete(f"/api/v1/labs/{SEED_LAB}/members/{target}")
    assert removed.status_code == 200, removed.text
    assert not execute_query(
        "SELECT 1 FROM authz_capability_grants WHERE principal_id = :p AND source = 'reseed'",
        {"p": str(target)},
    ), "membership removed but the grants it conveyed survived"


@pytest.mark.asyncio
async def test_lab_lead_cannot_manage_another_labs_members(client, roster, monkeypatch):
    """Scope containment is doing the work; this is the half that proves it."""
    _act_as(LEAD, monkeypatch)
    resp = await client.get(f"/api/v1/labs/{roster['other_lab']}/members")
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_lab_lead_cannot_manage_users_globally(client, roster, monkeypatch):
    """The safety argument for granting user:manage at Lab scope, pinned.

    ``PATCH /users/{id}`` asks for ``user:manage`` with no scope argument,
    which resolves to ``instance://self``. A ``lab://`` grant does not contain
    the instance root — containment runs downward — so the lab-scoped verb
    cannot reach it. If this ever passes, the preset change promoted every Lab
    Lead to a global user administrator.
    """
    _act_as(LEAD, monkeypatch)
    resp = await client.patch(
        f"/api/v1/users/{roster[OTHER_LEAD]}", json={"name": "renamed by a lab lead"}
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_lab_lead_cannot_promote_themselves_to_platform_admin(client, roster, monkeypatch):
    """The same boundary from the direction someone would actually try."""
    _act_as(LEAD, monkeypatch)
    resp = await client.patch(
        f"/api/v1/users/{roster[LEAD]}", json={"instance_preset": "instance_administrator"}
    )
    assert resp.status_code == 403, resp.text
    still = execute_query("SELECT is_platform_admin FROM users WHERE id = :i", {"i": roster[LEAD]})[
        0
    ]["is_platform_admin"]
    assert not still
