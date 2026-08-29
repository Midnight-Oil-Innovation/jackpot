"""M0 — permit() engine unit tests in full isolation (no DB, no HTTP).

The §9 worked examples from docs/access_model.md as fixtures:
§9.1 laptop, §9.2 SaaS tenant isolation + surveillance read,
§9.4 cryptWWDB compute-without-read — plus policy-path isolation
and deny-wins.
"""

import pytest

from backend.authz import (
    CapabilityGrant,
    Context,
    Decision,
    Principal,
    PrincipalKind,
    Resource,
    permit,
)


def _human(grants: list[CapabilityGrant] | None = None) -> Principal:
    return Principal(kind=PrincipalKind.HUMAN, id="u1", on_behalf_of=None, grants=grants or [])


# ── §9.1 laptop / field worker (instance-scoped grant) ──────────────────


def test_91_laptop_allow():
    p = _human([CapabilityGrant("sample:read_detail", "instance://field-laptop")])
    r = Resource(scope="instance://field-laptop/org-x/lab-y/proj-z/sample-1")
    assert permit(p, "sample:read_detail", r, Context(), policies=[]) == Decision.ALLOW


def test_91_laptop_deny_wrong_instance():
    p = _human([CapabilityGrant("sample:read_detail", "instance://field-laptop")])
    r = Resource(scope="instance://other-laptop/org-x/lab-y/proj-z/sample-1")
    assert permit(p, "sample:read_detail", r, Context(), policies=[]) == Decision.DENY


# ── §9.2 SaaS tenant isolation + surveillance read ──────────────────────


def test_92_tenant_allow_own_org():
    p = _human([CapabilityGrant("sample:read_detail", "org://acme")])
    r = Resource(scope="org://acme/lab-1/proj-2/sample-3")
    assert permit(p, "sample:read_detail", r, Context(), policies=[]) == Decision.ALLOW


def test_92_tenant_deny_cross_org_isolation():
    p = _human([CapabilityGrant("sample:read_detail", "org://acme")])
    r = Resource(scope="org://rival/lab-1/proj-2/sample-3")
    assert permit(p, "sample:read_detail", r, Context(), policies=[]) == Decision.DENY


def test_92_surveillance_allow():
    p = _human([CapabilityGrant("sample:read_surveillance", "org://acme")])
    r = Resource(scope="org://acme/lab-1/proj-2/sample-3")
    assert permit(p, "sample:read_surveillance", r, Context(), policies=[]) == Decision.ALLOW


def test_92_surveillance_deny_capability_mismatch():
    p = _human([CapabilityGrant("sample:read_detail", "org://acme")])
    r = Resource(scope="org://acme/lab-1/proj-2/sample-3")
    assert permit(p, "sample:read_surveillance", r, Context(), policies=[]) == Decision.DENY


# ── §9.4 cryptWWDB compute-without-read ─────────────────────────────────


def test_94_compute_allow_encrypted_only():
    p = _human([CapabilityGrant("compute:he_aggregate", "org://wwdb", {"encrypted_only": True})])
    r = Resource(scope="org://wwdb/lab-x/proj-y/sample-z")
    c = Context(conditions={"encrypted_only": True})
    assert permit(p, "compute:he_aggregate", r, c, policies=[]) == Decision.ALLOW


def test_94_compute_deny_no_grants():
    p = _human([])
    r = Resource(scope="org://wwdb/lab-x/proj-y/sample-z")
    c = Context(conditions={"encrypted_only": True})
    assert permit(p, "compute:he_aggregate", r, c, policies=[]) == Decision.DENY


def test_94_compute_deny_condition_not_met():
    p = _human([CapabilityGrant("compute:he_aggregate", "org://wwdb", {"encrypted_only": True})])
    r = Resource(scope="org://wwdb/lab-x/proj-y/sample-z")
    assert permit(p, "compute:he_aggregate", r, Context(), policies=[]) == Decision.DENY


def test_94_compute_deny_wrong_capability():
    p = _human([CapabilityGrant("sample:read_detail", "org://wwdb")])
    r = Resource(scope="org://wwdb/lab-x/proj-y/sample-z")
    c = Context(conditions={"encrypted_only": True})
    assert permit(p, "compute:he_aggregate", r, c, policies=[]) == Decision.DENY


# ── Policy-path ALLOW (step 3) ──────────────────────────────────────────

_ALLOW_POLICY = {
    "effect": "ALLOW",
    "capability": "sample:read_detail",
    "scope_ref": "org://acme",
    "conditions": {},
}


def test_policy_path_allow_no_grants():
    p = _human([])
    r = Resource(scope="org://acme/lab-1/proj-2/sample-3")
    assert permit(p, "sample:read_detail", r, Context(), policies=[_ALLOW_POLICY]) == Decision.ALLOW


def test_policy_path_deny_when_policy_removed():
    p = _human([])
    r = Resource(scope="org://acme/lab-1/proj-2/sample-3")
    assert permit(p, "sample:read_detail", r, Context(), policies=[]) == Decision.DENY


# ── Deny-wins ───────────────────────────────────────────────────────────


def test_deny_wins_over_matching_grant():
    p = _human([CapabilityGrant("sample:read_detail", "org://acme")])
    r = Resource(scope="org://acme/lab-1/proj-2/sample-3")
    deny_policy = {
        "effect": "DENY",
        "capability": "sample:read_detail",
        "scope_ref": "org://acme",
        "conditions": {},
    }
    assert permit(p, "sample:read_detail", r, Context(), policies=[deny_policy]) == Decision.DENY


# ── M0 honesty: DB path not wired ───────────────────────────────────────


def test_policies_none_raises_not_implemented():
    p = _human([])
    r = Resource(scope="org://acme/lab-1/proj-2/sample-3")
    with pytest.raises(NotImplementedError):
        permit(p, "sample:read_detail", r, Context(), policies=None)
