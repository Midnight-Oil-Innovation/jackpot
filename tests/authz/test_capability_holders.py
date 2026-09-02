# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""``capability_holders`` — the reverse lookup, and why it is not a decision.

``load_principal`` answers "what does this principal hold". A background job
that needs to notify the operators of something needs the other direction:
"who holds this". M2-DROP-PRE converts the one site that asked it — B-CARE-4's
non-compliant-peer alert, which selected on ``users.is_platform_admin`` — onto
the grant table.

The direction of containment is the thing to get right, and it is the opposite
of what "who are the admins" makes you reach for. A grant covers a resource
when the GRANT scope contains the RESOURCE scope — so asking at the instance
root selects only instance-root grants, while asking at a lab selects the
instance, org and lab grants above it. Getting this backwards would turn a
lab-scoped grant into instance-wide reach, which is exactly the widening the
scope-URI redesign exists to make impossible.

The exclusions each pin a way this could quietly return the wrong set: an
expired grant, a deactivated user, a peer principal that is not a user at all,
and a conditional grant whose condition nobody evaluated.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from backend.authz.principal import capability_holders
from backend.authz.scope import scope_uri
from backend.database import execute_write

CAP = "federation:configure_peer"


def _user(prefix: str, *, active: bool = True) -> int:
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@test.com"
    return execute_write(
        "INSERT INTO users (email, name, organization_id, is_active) "
        "VALUES (:e, :e, 1, :a) RETURNING id",
        {"e": email, "a": active},
    )[0]["id"]


def _grant(
    principal_id: str,
    scope: str,
    *,
    capability: str = CAP,
    not_after=None,
    conditions: str = "{}",
) -> None:
    execute_write(
        "INSERT INTO authz_capability_grants "
        "(principal_id, capability, scope_ref, source, not_after, conditions) "
        "VALUES (:p, :c, :s, 'test', :n, CAST(:j AS JSONB))",
        {"p": principal_id, "c": capability, "s": scope, "n": not_after, "j": conditions},
    )


@pytest.fixture
def cleanup():
    """Drop every row this module created, whichever way the test exits."""
    users: list[int] = []
    principals: list[str] = []
    yield users, principals
    for pid in principals:
        execute_write("DELETE FROM authz_capability_grants WHERE principal_id = :p", {"p": pid})
    for uid in users:
        execute_write(
            "DELETE FROM authz_capability_grants WHERE principal_id = :p", {"p": str(uid)}
        )
        execute_write("DELETE FROM notifications WHERE recipient_id = :u", {"u": uid})
        execute_write("DELETE FROM users WHERE id = :u", {"u": uid})


def test_instance_grant_holder_is_found_at_the_instance_root(cleanup):
    users, _ = cleanup
    uid = _user("ch-inst")
    users.append(uid)
    _grant(str(uid), scope_uri())
    assert uid in capability_holders(CAP, scope_uri())


def test_org_grant_does_not_reach_the_instance_root(cleanup):
    """Containment runs downward only. This is the whole safety property: an
    org-scoped holder must not be treated as an instance-wide operator."""
    users, _ = cleanup
    uid = _user("ch-org")
    users.append(uid)
    _grant(str(uid), scope_uri(org=1))
    assert uid not in capability_holders(CAP, scope_uri())


def test_instance_grant_reaches_a_lab_below_it(cleanup):
    users, _ = cleanup
    uid = _user("ch-down")
    users.append(uid)
    _grant(str(uid), scope_uri())
    assert uid in capability_holders(CAP, scope_uri(org=1, lab=1))


def test_containment_requires_a_segment_boundary(cleanup):
    """``org/1`` must not contain ``org/12`` — the prefix match has to stop at
    a separator or every scope leaks into its numeric neighbours."""
    users, _ = cleanup
    uid = _user("ch-boundary")
    users.append(uid)
    _grant(str(uid), scope_uri(org=1))
    assert uid not in capability_holders(CAP, scope_uri(org=12))
    assert uid in capability_holders(CAP, scope_uri(org=1, lab=3))


def test_a_stored_scope_ref_is_data_not_a_pattern(cleanup):
    """A ``%`` or ``_`` in a stored ``scope_ref`` must match itself, literally.

    The containment test is a prefix match, and the obvious SQL for a prefix
    match is LIKE — which reads its pattern from the grant row, so a stored
    scope_ref containing a LIKE metacharacter becomes a wildcard grant.
    ``visibility.py::_like_prefix`` escapes for this reason and this query
    initially did not: a row with ``instance://self/org/%`` was returned as a
    holder for every org.

    ``scope_uri()`` cannot produce such a string, so reaching it takes a
    hand-written or migrated row. That is not much comfort — it widens in the
    one direction authorization must never widen, and it silently disagrees
    with the ``_scope_contains`` this query claims to transcribe.
    """
    users, _ = cleanup
    uid = _user("ch-meta")
    users.append(uid)
    _grant(str(uid), "instance://self/org/%")
    assert uid not in capability_holders(CAP, scope_uri(org=999, lab=1))
    # The literal reading still works: the row covers exactly itself.
    assert uid in capability_holders(CAP, "instance://self/org/%")

    other = _user("ch-meta-underscore")
    users.append(other)
    _grant(str(other), "instance://self/org/_")
    assert other not in capability_holders(CAP, scope_uri(org=7, lab=1))


def test_a_different_capability_is_not_a_match(cleanup):
    users, _ = cleanup
    uid = _user("ch-othercap")
    users.append(uid)
    _grant(str(uid), scope_uri(), capability="audit:read")
    assert uid not in capability_holders(CAP, scope_uri())


def test_an_expired_grant_does_not_count(cleanup):
    users, _ = cleanup
    uid = _user("ch-expired")
    users.append(uid)
    _grant(str(uid), scope_uri(), not_after=datetime.now(UTC) - timedelta(days=1))
    assert uid not in capability_holders(CAP, scope_uri())


def test_an_unexpired_grant_still_counts(cleanup):
    users, _ = cleanup
    uid = _user("ch-live")
    users.append(uid)
    _grant(str(uid), scope_uri(), not_after=datetime.now(UTC) + timedelta(days=1))
    assert uid in capability_holders(CAP, scope_uri())


def test_a_deactivated_user_does_not_count(cleanup):
    users, _ = cleanup
    uid = _user("ch-inactive", active=False)
    users.append(uid)
    _grant(str(uid), scope_uri())
    assert uid not in capability_holders(CAP, scope_uri())


def test_a_peer_principal_is_not_returned(cleanup):
    """Peer grants share the table but their principal_id is a
    ``federated_instances`` UUID. The join to ``users`` is what keeps a peer
    out of a list of people to notify."""
    _, principals = cleanup
    peer_id = str(uuid.uuid4())
    principals.append(peer_id)
    _grant(peer_id, scope_uri())
    # No exception, and nothing non-numeric comes back.
    assert all(isinstance(h, int) for h in capability_holders(CAP, scope_uri()))


def test_a_conditional_grant_does_not_count(cleanup):
    """A condition is a fact about a request. This lookup has no request, so
    it cannot evaluate one, and the engine's rule for an unevaluable condition
    is to refuse rather than assume — see ``Context.now``."""
    users, _ = cleanup
    uid = _user("ch-conditional")
    users.append(uid)
    _grant(str(uid), scope_uri(), conditions='{"break_glass": true}')
    assert uid not in capability_holders(CAP, scope_uri())


def test_holders_are_deduplicated(cleanup):
    """Two grants that both cover the scope are one person to notify."""
    users, _ = cleanup
    uid = _user("ch-dedup")
    users.append(uid)
    _grant(str(uid), scope_uri())
    _grant(str(uid), scope_uri(org=1))
    assert capability_holders(CAP, scope_uri(org=1)).count(uid) == 1
