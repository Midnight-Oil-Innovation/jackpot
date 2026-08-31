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
from backend.authz.scope import scope_uri

# ── Canonical scope fixtures (§3.1.1, ADR 0015) ─────────────────────────
# One rooted path per deployment. Ids are database ids, so the §9 examples'
# names become numbers: acme=1, rival=2, wwdb=9, and org 11 is the
# segment-boundary trap against org 1.

INSTANCE = scope_uri()
ACME = scope_uri(org=1)
ACME_LAB1 = scope_uri(org=1, lab=1)
ACME_L1_SAMPLE = scope_uri(org=1, lab=1, project=2, sample=3)
ACME_L2_SAMPLE = scope_uri(org=1, lab=2, project=9, sample=7)
RIVAL_SAMPLE = scope_uri(org=2, lab=1, project=2, sample=3)
TRAP_SAMPLE = scope_uri(org=11, lab=1, project=2, sample=3)
WWDB = scope_uri(org=9)
WWDB_SAMPLE = scope_uri(org=9, lab=1, project=1, sample=1)


def _human(grants: list[CapabilityGrant] | None = None) -> Principal:
    return Principal(kind=PrincipalKind.HUMAN, id="u1", on_behalf_of=None, grants=grants or [])


# ── §9.1 laptop / field worker (instance-scoped grant) ──────────────────


def test_91_laptop_allow():
    p = _human([CapabilityGrant("sample:read_detail", INSTANCE)])
    r = Resource(scope=ACME_L1_SAMPLE)
    assert permit(p, "sample:read_detail", r, Context(), policies=[]) == Decision.ALLOW


def test_91_instance_grant_reaches_every_level():
    """§9.1's second half — "wrong instance" — is gone by construction.

    It asserted that a grant at ``instance://field-laptop`` did not cover
    ``instance://other-laptop/...``. Under ADR 0015 there is exactly one root
    per deployment (``instance://self``); a peer instance is a PEER_INSTANCE
    principal, never a branch of this tree (§3.3), so no resource scope can
    name another instance and there is nothing to be wrong about. What
    replaces it is the property that made the root scheme necessary: an
    instance-root grant reaches every depth. ``test_scope.py`` pins that no
    builder input can produce a second root.
    """
    p = _human([CapabilityGrant("sample:read_detail", INSTANCE)])
    for scope in (ACME, ACME_LAB1, ACME_L1_SAMPLE, RIVAL_SAMPLE, WWDB_SAMPLE):
        r = Resource(scope=scope)
        assert permit(p, "sample:read_detail", r, Context(), policies=[]) == Decision.ALLOW


# ── §9.2 SaaS tenant isolation + surveillance read ──────────────────────


def test_92_tenant_allow_own_org():
    p = _human([CapabilityGrant("sample:read_detail", ACME)])
    r = Resource(scope=ACME_L1_SAMPLE)
    assert permit(p, "sample:read_detail", r, Context(), policies=[]) == Decision.ALLOW


def test_92_tenant_deny_cross_org_isolation():
    p = _human([CapabilityGrant("sample:read_detail", ACME)])
    r = Resource(scope=RIVAL_SAMPLE)
    assert permit(p, "sample:read_detail", r, Context(), policies=[]) == Decision.DENY


def test_92_surveillance_allow():
    p = _human([CapabilityGrant("sample:read_surveillance", ACME)])
    r = Resource(scope=ACME_L1_SAMPLE)
    assert permit(p, "sample:read_surveillance", r, Context(), policies=[]) == Decision.ALLOW


def test_92_surveillance_deny_capability_mismatch():
    p = _human([CapabilityGrant("sample:read_detail", ACME)])
    r = Resource(scope=ACME_L1_SAMPLE)
    assert permit(p, "sample:read_surveillance", r, Context(), policies=[]) == Decision.DENY


# ── §9.4 cryptWWDB compute-without-read ─────────────────────────────────


def test_94_compute_allow_encrypted_only():
    p = _human([CapabilityGrant("compute:he_aggregate", WWDB, {"encrypted_only": True})])
    r = Resource(scope=WWDB_SAMPLE)
    c = Context(conditions={"encrypted_only": True})
    assert permit(p, "compute:he_aggregate", r, c, policies=[]) == Decision.ALLOW


def test_94_compute_deny_no_grants():
    p = _human([])
    r = Resource(scope=WWDB_SAMPLE)
    c = Context(conditions={"encrypted_only": True})
    assert permit(p, "compute:he_aggregate", r, c, policies=[]) == Decision.DENY


def test_94_compute_deny_condition_not_met():
    p = _human([CapabilityGrant("compute:he_aggregate", WWDB, {"encrypted_only": True})])
    r = Resource(scope=WWDB_SAMPLE)
    assert permit(p, "compute:he_aggregate", r, Context(), policies=[]) == Decision.DENY


def test_94_compute_deny_wrong_capability():
    p = _human([CapabilityGrant("sample:read_detail", WWDB)])
    r = Resource(scope=WWDB_SAMPLE)
    c = Context(conditions={"encrypted_only": True})
    assert permit(p, "compute:he_aggregate", r, c, policies=[]) == Decision.DENY


# ── Policy-path ALLOW (step 3) ──────────────────────────────────────────

_ALLOW_POLICY = {
    "effect": "ALLOW",
    "capability": "sample:read_detail",
    "scope_ref": ACME,
    "conditions": {},
}


def test_policy_path_allow_no_grants():
    p = _human([])
    r = Resource(scope=ACME_L1_SAMPLE)
    assert permit(p, "sample:read_detail", r, Context(), policies=[_ALLOW_POLICY]) == Decision.ALLOW


def test_policy_path_deny_when_policy_removed():
    p = _human([])
    r = Resource(scope=ACME_L1_SAMPLE)
    assert permit(p, "sample:read_detail", r, Context(), policies=[]) == Decision.DENY


# ── Deny-wins ───────────────────────────────────────────────────────────


def test_deny_wins_over_matching_grant():
    p = _human([CapabilityGrant("sample:read_detail", ACME)])
    r = Resource(scope=ACME_L1_SAMPLE)
    deny_policy = {
        "effect": "DENY",
        "capability": "sample:read_detail",
        "scope_ref": ACME,
        "conditions": {},
    }
    assert permit(p, "sample:read_detail", r, Context(), policies=[deny_policy]) == Decision.DENY


# ── M0 honesty: DB path not wired ───────────────────────────────────────


def test_policies_none_raises_not_implemented():
    p = _human([])
    r = Resource(scope=ACME_L1_SAMPLE)
    with pytest.raises(NotImplementedError):
        permit(p, "sample:read_detail", r, Context(), policies=None)
