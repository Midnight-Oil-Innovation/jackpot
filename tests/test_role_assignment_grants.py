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

from backend.authz import ROOT
from backend.authz.reseed import (
    INSTANCE_PRESET_FLAGS,
    PRESET_GRANTS,
    instance_preset,
)
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
    """PATCH instance_preset=instance_administrator takes effect on this request.

    Before the fix the field flipped, the response was 200, and the promoted
    user held nothing — until some later migration ran a reseed and quietly
    made it real.
    """
    subject, bystander = users[SUBJECT], users[BYSTANDER]
    assert not await _can_manage_users(subject, bystander, monkeypatch)

    _act_as(ADMIN, monkeypatch)
    resp = await client.patch(
        f"/api/v1/users/{subject}", json={"instance_preset": "instance_administrator"}
    )
    assert resp.status_code == 200, resp.text

    assert await _can_manage_users(subject, bystander, monkeypatch), (
        "assigned the admin preset but still cannot act as one — the role was "
        "written without issuing the grants it stands for"
    )


@pytest.mark.asyncio
async def test_demoting_a_user_revokes_their_instance_capabilities(client, users, monkeypatch):
    """The direction that matters more: revocation must be immediate."""
    subject, bystander = users[SUBJECT], users[BYSTANDER]

    _act_as(ADMIN, monkeypatch)
    assert (
        await client.patch(
            f"/api/v1/users/{subject}", json={"instance_preset": "instance_administrator"}
        )
    ).status_code == 200
    assert await _can_manage_users(subject, bystander, monkeypatch)

    _act_as(ADMIN, monkeypatch)
    # An explicit null is how the contract says "no Instance role".
    resp = await client.patch(f"/api/v1/users/{subject}", json={"instance_preset": None})
    assert resp.status_code == 200, resp.text

    assert not await _can_manage_users(subject, bystander, monkeypatch), (
        "demoted but still able to act as an admin — a revocation that does not "
        "revoke is worse than one that never happened"
    )


@pytest.mark.asyncio
async def test_data_analyst_promotion_grants_the_surveillance_preset(client, users, monkeypatch):
    """The surveillance_officer preset issues its capabilities, not nothing."""
    subject = users[SUBJECT]
    _act_as(ADMIN, monkeypatch)
    resp = await client.patch(
        f"/api/v1/users/{subject}", json={"instance_preset": "surveillance_officer"}
    )
    assert resp.status_code == 200, resp.text

    held = {
        r["capability"]
        for r in execute_query(
            "SELECT capability FROM authz_capability_grants WHERE principal_id = :p",
            {"p": str(subject)},
        )
    }
    assert "sample:read_surveillance" in held, held


def test_instance_preset_round_trips_through_the_flag_pair():
    """The two representations of an Instance role must agree.

    ``instance_preset()`` maps flags to a preset and ``INSTANCE_PRESET_FLAGS``
    maps back. The forward direction is many-to-one — a user carrying BOTH
    flags is an admin, because that is how ``reseed()`` reads them — so the
    inverse is a canonical representative rather than a true inverse, and the
    round trip is the property that has to hold. Written as a differential
    check because the alternative is two hand-maintained tables that agree
    until someone edits one (Rule 73).

    The precedence this pins used to be reachable from the API, when PATCH
    took both booleans and a caller could send both at once. It no longer is —
    a preset is singular — but ``reseed()`` still reads the columns and
    translates them, so the precedence stays load-bearing until M2-DROP.
    """
    for preset, (admin_flag, analyst_flag) in INSTANCE_PRESET_FLAGS.items():
        assert (
            instance_preset(is_platform_admin=admin_flag, is_data_analyst=analyst_flag) == preset
        ), f"{preset} does not round-trip through its flag pair"

    assert instance_preset(is_platform_admin=False, is_data_analyst=False) is None
    assert (
        instance_preset(is_platform_admin=True, is_data_analyst=True) == "instance_administrator"
    ), "both flags must resolve to admin — reseed reads analysts as NOT is_platform_admin"


def _grants_at_root(email: str) -> set[str]:
    """Capabilities the user holds AT THE INSTANCE ROOT, not anywhere.

    Scope-filtered on purpose: a preset issued at a lab scope instead of the
    root is a different bug that an unfiltered read would call success.
    """
    uid = execute_query("SELECT id FROM users WHERE email = :e", {"e": email})[0]["id"]
    return {
        r["capability"]
        for r in execute_query(
            "SELECT capability FROM authz_capability_grants "
            "WHERE principal_id = :p AND scope_ref = :s",
            {"p": str(uid), "s": ROOT},
        )
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role,preset",
    [
        ("Platform Admin", "instance_administrator"),
        ("Data Analyst", "surveillance_officer"),
    ],
)
async def test_dev_login_global_role_issues_the_instance_preset(role, preset):
    """The instance half of dev-login, after slice 8 moved it onto presets.

    dev-login exists so the E-1 UAT can drive the whole RBAC matrix from a
    script, so a role that grants nothing drives nothing. The response reports
    the preset, and the grants at the instance root must be exactly that
    preset's — a response naming a role the principal does not hold is worse
    than one saying nothing.

    Asserted as set EQUALITY rather than a probe capability. A probe cannot
    detect over-granting, and the obvious probe for surveillance_officer is
    the one capability it SHARES with instance_administrator
    (``sample:read_surveillance``), so wiring Data Analyst to the admin preset
    would have passed. The docstring claims an equality; assert the equality.
    """
    _purge(DEV)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/api/v1/auth/dev-login", json={"email": DEV, "role": role})
        assert resp.status_code == 200, resp.text
        assert resp.json()["instance_preset"] == preset

        assert _grants_at_root(DEV) == set(PRESET_GRANTS[preset])
    finally:
        _purge(DEV)


@pytest.mark.asyncio
async def test_dev_login_switching_down_to_a_lab_role_revokes_the_instance_preset():
    """The direction the UAT actually exercises, and the only one where the
    DELETE in ``sync_instance_preset`` is load-bearing.

    dev-login switches identity repeatedly within one run. Starting from a
    blank slate only ever tests the INSERT; the Platform Admin → Lab Director
    switch is where a failure to revoke leaves a Lab Director holding
    instance-root capabilities over every lab on the deployment.
    """
    _purge(DEV)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            up = await c.post(
                "/api/v1/auth/dev-login", json={"email": DEV, "role": "Platform Admin"}
            )
            assert up.status_code == 200, up.text
            assert _grants_at_root(DEV), "precondition: the admin preset was never issued"

            down = await c.post(
                "/api/v1/auth/dev-login", json={"email": DEV, "role": "Lab Director"}
            )
        assert down.status_code == 200, down.text
        assert down.json()["instance_preset"] is None

        assert _grants_at_root(DEV) == set(), (
            "switched down to a lab role but kept instance-root grants — a Lab "
            "Director with authority over every lab on the deployment"
        )
    finally:
        _purge(DEV)


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
