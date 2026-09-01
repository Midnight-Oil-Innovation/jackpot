"""M3 — deletion-governance policies on the M0 engine (access_model.md §6.2).

Scope note, because the section describes three policies and this file pins
one. Verified against the code while implementing:

* ``deletion.separation_of_duties`` (§6.2-1b) — implemented here. Its routes
  resolve a Sample resource, so a per-row DENY is the right shape.
* ``deletion.no_publish_while_deleting`` (§6.2-2) — deliberately NOT a policy.
  ``submission:approve`` is checked once at Lab scope while the rule is
  per-sample across the submission's whole set; the shipped set-level check in
  ``submissions.py`` (a 422 naming each blocked sample) is the correct shape
  and already enforces it.
* ``sovereignty.no_federate_deleting`` (§6.2-3) — premature. ``federation:push``
  exists nowhere in the codebase outside a comment; the capability arrives
  with M4's sharing agreements, and a policy keyed to a verb no route checks
  would be untestable decoration.
"""

import pytest

from backend.authz import Context, Decision, Resource, permit
from backend.authz.engine import CapabilityGrant, Principal, PrincipalKind
from backend.authz.policy import ACTIVE_POLICIES, DELETION_POLICIES
from backend.authz.scope import scope_uri

REQUESTER = "77"
APPROVER = "88"
SAMPLE_SCOPE = scope_uri(org=1, lab=2, project=3, sample=4)


def _principal(pid: str) -> Principal:
    return Principal(
        kind=PrincipalKind.HUMAN,
        id=pid,
        on_behalf_of=None,
        grants=[CapabilityGrant(capability="deletion:approve", scope_ref=scope_uri())],
    )


def _sample(requested_by: str | None) -> Resource:
    return Resource(
        scope=SAMPLE_SCOPE,
        attributes={
            "deletion_status": "DELETION_REQUESTED",
            "deletion_requested_by_user_id": requested_by,
        },
    )


def _decide(principal: Principal, resource: Resource, **conditions) -> Decision:
    return permit(
        principal,
        "deletion:approve",
        resource,
        Context(conditions=conditions),
        policies=ACTIVE_POLICIES,
    )


def test_a_different_approver_is_allowed():
    """The ordinary path: holding the grant is enough when you did not ask."""
    assert _decide(_principal(APPROVER), _sample(REQUESTER)) is Decision.ALLOW


def test_the_requester_cannot_approve_their_own_deletion():
    """§6.2-1b. The DENY subtracts a path the grant would otherwise permit."""
    assert _decide(_principal(REQUESTER), _sample(REQUESTER)) is Decision.DENY


def test_the_audited_self_approve_flag_lifts_the_deny():
    assert (
        _decide(_principal(REQUESTER), _sample(REQUESTER), platform_admin_self_approve=True)
        is Decision.ALLOW
    )


def test_a_missing_self_approve_flag_does_not_lift_the_deny():
    """The reason the condition language needed a negation form.

    With equality-only conditions, ``{"platform_admin_self_approve": False}``
    would not match a context that never set the key — so the DENY would
    silently not fire for every caller that forgot the flag, which is every
    caller but one. Absent must mean the rule APPLIES. This test is the
    difference between the escape hatch being explicit and being the default.
    """
    assert _decide(_principal(REQUESTER), _sample(REQUESTER)) is Decision.DENY


def test_an_explicit_false_flag_does_not_lift_the_deny():
    assert (
        _decide(_principal(REQUESTER), _sample(REQUESTER), platform_admin_self_approve=False)
        is Decision.DENY
    )


def test_deny_does_not_fire_when_nobody_requested_the_deletion():
    """A NULL requester must not read as "matches the caller".

    ``deletion_requested_by_user_id`` is NULL on an ACTIVE sample. The
    PRINCIPAL_ID sentinel compares as strings, so a None here has to fail the
    comparison rather than coincide with it.
    """
    assert _decide(_principal(APPROVER), _sample(None)) is Decision.ALLOW


def test_the_deny_is_scoped_to_deletion_approve_only():
    """A DENY in the shared policy set must not leak onto other capabilities.

    ``guards.py`` passes ACTIVE_POLICIES on every call, including lab- and
    instance-scoped ones carrying no resource attributes. That was free while
    the set held only ALLOWs. The invariant that keeps it free now is that no
    DENY names a capability whose routes lack a Sample resource — this asserts
    the half of it that a future policy could break by copy-paste.
    """
    for policy in DELETION_POLICIES:
        assert policy["effect"] == "DENY"
        assert policy["capability"] == "deletion:approve", (
            f"{policy['id']} keys on {policy['capability']}, whose routes may not resolve "
            "a Sample resource; a DENY reading absent attributes decides on absence"
        )


def test_every_deny_reads_only_loaded_attributes():
    """The other half of the same invariant, mechanically.

    A DENY that reads an attribute ``sample_resource`` does not load gets None
    and compares against it — firing or not for a reason unrelated to the row.
    """
    from backend.authz.principal import SAMPLE_ATTRIBUTE_COLUMNS

    for policy in ACTIVE_POLICIES:
        if policy["effect"] != "DENY":
            continue
        for attr in policy.get("resource", {}):
            assert attr in SAMPLE_ATTRIBUTE_COLUMNS, (
                f"{policy.get('id')} reads {attr!r}, which sample_resource does not load"
            )


def test_sovereignty_policies_are_auditable_by_id():
    """§6.3: 'a sovereignty audit is a policy audit' — which needs ids."""
    for policy in DELETION_POLICIES:
        assert policy.get("id"), "every governance policy needs an id to be auditable"
        assert policy["id"].startswith(("deletion.", "sovereignty."))


@pytest.mark.parametrize("capability", ["submission:approve", "federation:push"])
def test_no_policy_keys_on_the_deferred_capabilities(capability):
    """Guards the two §6.2 policies deliberately not implemented.

    If one is later added, it must come with the route work that makes it
    meaningful — a DENY on submission:approve evaluated at Lab scope reads an
    absent deletion_status and denies every submission approval.
    """
    assert not [p for p in ACTIVE_POLICIES if p["capability"] == capability]
