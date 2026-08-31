"""require_capability unit tests — the guard's wiring, in isolation (M2-B1).

Before M2-B1 these patched ``get_user_lab_membership`` and asserted the APGAP
ladder's rungs: admin bypass, membership, the project→lab join, the director
flag. The guard no longer contains a ladder — it loads grants and calls
``permit()`` — so testing it that way would assert against code that no longer
runs.

What is worth unit-testing here is the guard's *wiring*: which scope it builds,
how it maps a decision to a status code, and that it holds no shortcut of its
own. Whether the decision itself is right belongs to ``tests/authz/`` — the
engine suite for the rules, and the preflight matrix on PostgreSQL for the
comparison against the old model, including the frozen ``legacy_ladder``
reference that records exactly what changed.
"""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend.auth.guards import require_capability
from backend.authz import CapabilityGrant, Principal, PrincipalKind, scope_uri

LAB_SCOPE = scope_uri(org=1, lab=5)


def make_user(is_platform_admin=False, is_data_analyst=False, uid=1):
    return {
        "id": uid,
        "email": f"user{uid}@test.com",
        "is_platform_admin": is_platform_admin,
        "is_data_analyst": is_data_analyst,
        "is_active": True,
        "organization_id": 1,
    }


def principal_with(*grants: tuple[str, str], uid=1) -> Principal:
    return Principal(
        kind=PrincipalKind.HUMAN,
        id=str(uid),
        on_behalf_of=None,
        grants=[CapabilityGrant(capability=c, scope_ref=s) for c, s in grants],
    )


def guard(capability, user, *, grants=(), lab_id=None, lab_org=1):
    """Run the guard with a stubbed principal and lab lookup."""
    with (
        patch("backend.auth.guards.load_principal", return_value=principal_with(*grants)),
        patch(
            "backend.auth.guards.lab_resource_scope",
            side_effect=lambda lid: scope_uri(org=lab_org, lab=lid),
        ),
    ):
        return require_capability(capability)(user, lab_id=lab_id)


class TestDecisionMapping:
    def test_matching_grant_returns_the_user(self):
        user = make_user()
        assert guard("org:manage", user, grants=[("org:manage", scope_uri())]) is user

    def test_no_grants_is_403(self):
        with pytest.raises(HTTPException) as exc:
            guard("org:manage", make_user())
        assert exc.value.status_code == 403

    def test_wrong_capability_is_403(self):
        with pytest.raises(HTTPException):
            guard("org:manage", make_user(), grants=[("user:manage", scope_uri())])

    def test_no_authenticated_user_is_403(self):
        with pytest.raises(HTTPException) as exc:
            require_capability("org:manage")(None)
        assert exc.value.status_code == 403


class TestNoLegacyShortcut:
    """The role flags must be inert. Each of these passed before M2-B1."""

    def test_platform_admin_flag_alone_does_not_authorize(self):
        with pytest.raises(HTTPException) as exc:
            guard("org:manage", make_user(is_platform_admin=True))
        assert exc.value.status_code == 403

    def test_data_analyst_flag_alone_does_not_authorize(self):
        with pytest.raises(HTTPException):
            guard("sample:read_surveillance", make_user(is_data_analyst=True))

    def test_admin_flag_does_not_bypass_a_lab_scope(self):
        with pytest.raises(HTTPException):
            guard("user:manage", make_user(is_platform_admin=True), lab_id=5)


class TestScopeSelection:
    def test_no_lab_id_uses_the_instance_root(self):
        user = make_user()
        assert guard("org:manage", user, grants=[("org:manage", scope_uri())]) is user

    def test_lab_id_uses_the_lab_path(self):
        user = make_user()
        assert guard("user:manage", user, grants=[("user:manage", LAB_SCOPE)], lab_id=5) is user

    def test_lab_scoped_grant_does_not_reach_the_instance(self):
        """Containment runs downward only — a lab grant is not instance-wide."""
        with pytest.raises(HTTPException):
            guard("user:manage", make_user(), grants=[("user:manage", LAB_SCOPE)])

    def test_instance_grant_reaches_a_lab(self):
        """The rung that replaces the admin bypass, at the guard level."""
        user = make_user()
        assert guard("user:manage", user, grants=[("user:manage", scope_uri())], lab_id=5) is user

    def test_grant_on_another_lab_does_not_reach_this_one(self):
        with pytest.raises(HTTPException):
            guard(
                "user:manage",
                make_user(),
                grants=[("user:manage", scope_uri(org=1, lab=6))],
                lab_id=5,
            )
