# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""M2-DROP-PRE slice 7: PATCH /users/{id} assigns a preset, not a flag pair.

A role write is a capability ASSIGNMENT, and the model's unit of assignment
is a preset (access_model.md §8). The endpoint used to take
``is_platform_admin`` / ``is_data_analyst`` booleans, which meant the API
spoke in the legacy storage representation rather than in the model's own.

What this file pins is the boundary of the new vocabulary — the cases where
accepting a plausible-looking name would be wrong. The happy paths live in
``tests/test_role_assignment_grants.py``, which asserts that assigning a
preset issues its grants on the same request.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.authz.reseed import INSTANCE_PRESETS, PRESET_GRANTS
from backend.database import execute_query, execute_write
from backend.main import app

#: Presets that are NOT issuable at Instance scope. Derived, so §8.3's
#: Org-scoped Scenario-T preset is covered automatically when it lands — with
#: the right expectation, since it is equally wrong at the instance root.
#: Named for the property rather than "lab-scoped": identical today, but the
#: Org-scoped preset makes those differ and then the name would lie.
NON_INSTANCE_PRESETS = sorted(set(PRESET_GRANTS) - INSTANCE_PRESETS)
# An empty parametrize collects as one SKIPPED item, not as a failure, so the
# file would keep passing while testing nothing.
assert NON_INSTANCE_PRESETS, "no non-instance presets left to test the boundary with"


@pytest.fixture
def subject() -> int:
    row = execute_write(
        "INSERT INTO users (email, name, organization_id, is_active) "
        "VALUES (:e, 'Preset Subject', 1, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET is_active = TRUE RETURNING id",
        {"e": "preset_subject@example.org"},
    )
    uid = row[0]["id"]
    yield uid
    execute_write("DELETE FROM authz_capability_grants WHERE principal_id = :p", {"p": str(uid)})
    execute_write("DELETE FROM users WHERE id = :i", {"i": uid})


async def _patch(uid: int, body: dict):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        return await c.patch(f"/api/v1/users/{uid}", json=body)


@pytest.mark.asyncio
@pytest.mark.parametrize("preset", NON_INSTANCE_PRESETS)
async def test_a_non_instance_preset_is_refused_at_instance_scope(subject, preset):
    """``lab_lead`` is a real preset — just not one this endpoint may issue.

    Lab roles are assigned through membership (M2-B5), where the scope comes
    from the lab being joined. Accepting one here would issue a lab preset's
    capabilities at INSTANCE scope, which is a privilege escalation dressed as
    a typo: ``lab_lead`` holds ``sample:read_unscrubbed`` and
    ``deletion:approve``, and at the instance root those reach every sample on
    the deployment.
    """
    resp = await _patch(subject, {"instance_preset": preset})

    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "INVALID_PRESET"
    held = execute_query(
        "SELECT capability FROM authz_capability_grants WHERE principal_id = :p",
        {"p": str(subject)},
    )
    assert held == [], f"{preset} issued grants despite being refused"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["", "Platform Admin", "instance_admin", "INSTANCE_ADMINISTRATOR"])
async def test_an_unknown_preset_name_is_refused(subject, name):
    """No near-miss is silently coerced.

    ``Platform Admin`` is the APGAP role name and ``instance_admin`` the
    obvious abbreviation; both are wrong, and a 422 naming the valid set is
    the only answer that does not leave the caller believing a role was
    assigned.
    """
    resp = await _patch(subject, {"instance_preset": name})

    assert resp.status_code == 422, resp.text
    assert "instance_administrator" in resp.json()["error"]["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"is_platform_admin": True},
        {"name": "renamed", "is_platform_admin": True},
        {"instance_preset": "instance_administrator", "is_data_analyst": True},
    ],
    ids=["legacy-only", "legacy-alongside-a-valid-field", "legacy-alongside-the-new-field"],
)
@pytest.mark.asyncio
async def test_the_legacy_booleans_are_no_longer_a_way_in(subject, body):
    """The old contract must fail loudly, not quietly.

    Pydantic drops unknown fields by default, so every one of these bodies
    would otherwise return 200 with the boolean ignored — the caller believing
    they promoted someone who holds none of it. ``extra="forbid"`` on
    ``UserUpdate`` is what makes a stale client an error instead of a no-op.

    The middle case is the one a single-field test misses: the request is
    partly valid, so it 200s on the valid part while silently discarding the
    role. The third is worse still — it would have assigned a role, just not
    the one the caller asked for.
    """
    resp = await _patch(subject, body)

    assert resp.status_code == 422, resp.text
    held = execute_query(
        "SELECT capability FROM authz_capability_grants WHERE principal_id = :p",
        {"p": str(subject)},
    )
    assert held == [], "a rejected body still issued grants"
    # The column the legacy field used to reach no longer exists (M2-DROP),
    # so "it did not reach it" is now structural. The grant assertion above is
    # what still has content: a rejected body must assign nothing.
