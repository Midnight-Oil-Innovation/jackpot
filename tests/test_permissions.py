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
from backend.authz import CapabilityGrant, Principal, PrincipalKind, Resource, scope_uri

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


def guard(capability, user, *, grants=(), lab_id=None, sample_id=None, lab_org=1, attributes=None):
    """Run the guard with a stubbed principal and resource lookups.

    ``attributes`` stands in for the sample row the real
    ``sample_resource`` reads. Default empty, so a test that says nothing
    about the row gets a decision from grants alone — which is what every
    pre-M2-B2 test in this file assumes.
    """
    with (
        patch(
            "backend.auth.guards.load_principal",
            # The principal carries the caller's own id — the ownership policy
            # compares the row against it, so a fixed id would make every
            # ownership test vacuous.
            return_value=principal_with(*grants, uid=user["id"]),
        ),
        patch(
            "backend.auth.guards.lab_resource_scope",
            side_effect=lambda lid: scope_uri(org=lab_org, lab=lid),
        ),
        patch(
            "backend.auth.guards.sample_resource",
            side_effect=lambda sid: Resource(
                scope=scope_uri(org=lab_org, lab=5, project=2, sample=sid),
                attributes=dict(attributes or {}),
            ),
        ),
    ):
        return require_capability(capability)(user, lab_id=lab_id, sample_id=sample_id)


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


SAMPLE_SCOPE = scope_uri(org=1, lab=5, project=2, sample=42)


class TestSampleScope:
    """M2-B2-PRE-B — the guard can name a Sample-scoped resource."""

    def test_sample_scoped_grant_authorizes_that_sample(self):
        user = make_user()
        assert (
            guard(
                "sample:read_detail",
                user,
                grants=[("sample:read_detail", SAMPLE_SCOPE)],
                sample_id=42,
            )
            is user
        )

    def test_sample_scoped_grant_does_not_reach_another_sample(self):
        with pytest.raises(HTTPException):
            guard(
                "sample:read_detail",
                make_user(),
                grants=[("sample:read_detail", SAMPLE_SCOPE)],
                sample_id=43,
            )

    def test_lab_grant_covers_a_sample_in_that_lab(self):
        """Containment downward: the ordinary lab-member case."""
        user = make_user()
        assert (
            guard(
                "sample:read_detail",
                user,
                grants=[("sample:read_detail", scope_uri(org=1, lab=5))],
                sample_id=42,
            )
            is user
        )

    def test_sample_grant_is_invisible_when_checked_at_lab_scope(self):
        """Why sample scope had to exist rather than being approximated.

        A per-sample grant — what an approved access request becomes (§5) —
        does not contain the lab. Checking the lab instead would deny the
        holder while appearing to work for everyone with lab membership, so
        the bug would look like "that one user's access is broken".
        """
        with pytest.raises(HTTPException):
            guard(
                "sample:read_detail",
                make_user(),
                grants=[("sample:read_detail", SAMPLE_SCOPE)],
                lab_id=5,
            )

    def test_both_identifiers_is_a_programming_error(self):
        with pytest.raises(ValueError, match="not both"):
            guard("sample:read_detail", make_user(), lab_id=5, sample_id=42)


class TestAttributeRungs:
    """M2-B2: the permissive rungs of the legacy ladder, now attribute-policies.

    Each of these is a path no grant expresses — the caller holds nothing at
    the sample's scope, and is authorized (or not) purely by what the row is.
    """

    def test_public_sample_is_detail_readable_by_a_stranger(self):
        user = make_user(uid=7)
        assert (
            guard(
                "sample:read_detail",
                user,
                sample_id=42,
                attributes={"sharing_level": "PUBLIC"},
            )
            is user
        )

    def test_private_sample_is_not(self):
        with pytest.raises(HTTPException) as exc:
            guard(
                "sample:read_detail",
                make_user(uid=7),
                sample_id=42,
                attributes={"sharing_level": "PRIVATE"},
            )
        assert exc.value.status_code == 403

    def test_discoverable_is_list_visible_but_not_detail_readable(self):
        """can_access_sample's rule: DISCOVERABLE alone is NOT sufficient."""
        attrs = {"sharing_level": "DISCOVERABLE"}
        assert guard("sample:read", make_user(uid=7), sample_id=42, attributes=attrs)
        with pytest.raises(HTTPException):
            guard("sample:read_detail", make_user(uid=7), sample_id=42, attributes=attrs)

    def test_owner_reads_their_own_sample_without_any_grant(self):
        user = make_user(uid=7)
        assert guard("sample:read_detail", user, sample_id=42, attributes={"owner_id": 7}) is user

    def test_a_different_owner_does_not(self):
        with pytest.raises(HTTPException):
            guard(
                "sample:read_detail",
                make_user(uid=7),
                sample_id=42,
                attributes={"owner_id": 8},
            )

    def test_surveillance_row_needs_the_capability_as_well(self):
        attrs = {"surveillance_relevant": True}
        with pytest.raises(HTTPException):
            guard("sample:read_detail", make_user(uid=7), sample_id=42, attributes=attrs)
        assert guard(
            "sample:read_detail",
            make_user(uid=7),
            sample_id=42,
            attributes=attrs,
            grants=[("sample:read_surveillance", scope_uri())],
        )

    def test_surveillance_capability_does_not_reach_a_non_surveillance_row(self):
        with pytest.raises(HTTPException):
            guard(
                "sample:read_detail",
                make_user(uid=7),
                sample_id=42,
                attributes={"surveillance_relevant": False},
                grants=[("sample:read_surveillance", scope_uri())],
            )

    def test_discoverable_sample_may_be_requested_by_a_stranger(self):
        """access:request appears in no preset — a policy is the only path."""
        user = make_user(uid=7)
        assert (
            guard(
                "access:request",
                user,
                sample_id=42,
                attributes={"sharing_level": "DISCOVERABLE"},
            )
            is user
        )

    def test_private_sample_may_not_be_requested(self):
        with pytest.raises(HTTPException) as exc:
            guard(
                "access:request",
                make_user(uid=7),
                sample_id=42,
                attributes={"sharing_level": "PRIVATE"},
            )
        assert exc.value.status_code == 403

    def test_attributes_do_not_widen_a_write(self):
        """The permissive rungs are read-plane only. PUBLIC is not writable."""
        for capability in ("sample:update", "sample:archive"):
            with pytest.raises(HTTPException):
                guard(
                    capability,
                    make_user(uid=7),
                    sample_id=42,
                    attributes={"sharing_level": "PUBLIC", "owner_id": 7},
                )

    def test_policies_cannot_fire_on_a_lab_scoped_check(self):
        """A lab resource carries no attributes, so no policy can match it."""
        with pytest.raises(HTTPException):
            guard("sample:read_detail", make_user(uid=7), lab_id=5)
