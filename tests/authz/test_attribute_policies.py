"""M2-B2-PRE-A — attribute-policies, row-wise and in SQL (§2.4, §2.5).

The legacy ladder's permissive rungs (PUBLIC, DISCOVERABLE, surveillance
relevance, ownership) are attribute rules: they depend on the row, not on
what the principal was granted. This suite holds the property that makes
them safe to ship — permit() and visibility_sql_clause reach the same verdict
on the same rows — because a policy that exists in only one of the two halves
is exactly the divergence M1 was built to prevent.
"""

import sqlite3

import pytest

from authz.scopes import INSTANCE, SCOPE_EXPR
from backend.authz import (
    CapabilityGrant,
    Context,
    Decision,
    Principal,
    PrincipalKind,
    Resource,
    permit,
    visibility_sql_clause,
)
from backend.authz.policy import LADDER_POLICIES
from backend.authz.scope import scope_uri

ATTR_COLUMNS = {
    "sharing_level": "s.sharing_level",
    "surveillance_relevant": "s.surveillance_relevant",
    "owner_id": "s.owner_id",
}

# (sharing_level, surveillance_relevant, owner_id) for one lab-1 sample.
ROWS = [
    ("PRIVATE", False, 100),
    ("PRIVATE", True, 100),
    ("DISCOVERABLE", False, 100),
    ("PUBLIC", False, 100),
    ("PRIVATE", False, 7),  # owned by the acting principal
]


def _principal(uid="7", grants=()):
    return Principal(
        kind=PrincipalKind.HUMAN,
        id=uid,
        on_behalf_of=None,
        grants=[CapabilityGrant(c, s) for c, s in grants],
    )


def _row_scope(i: int) -> str:
    """Each fixture row is its own sample, exactly as the SQL derives it."""
    return scope_uri(org=1, lab=1, project=2, sample=i)


def _resource(row, i):
    sharing, surveillance, owner = row
    return Resource(
        scope=_row_scope(i),
        attributes={
            "sharing_level": sharing,
            "surveillance_relevant": surveillance,
            "owner_id": owner,
        },
    )


def _sql_visible(principal, capability):
    frag, params = visibility_sql_clause(
        principal,
        capability,
        SCOPE_EXPR,
        policies=LADDER_POLICIES,
        attribute_columns=ATTR_COLUMNS,
    )
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE labs (id INTEGER PRIMARY KEY, organization_id INTEGER)")
    conn.execute(
        "CREATE TABLE samples (id INTEGER PRIMARY KEY, lab_id INTEGER, project_id INTEGER, "
        "sharing_level TEXT, surveillance_relevant BOOLEAN, owner_id INTEGER)"
    )
    conn.execute("INSERT INTO labs (id, organization_id) VALUES (1, 1)")
    for i, (sharing, surveillance, owner) in enumerate(ROWS, start=1):
        conn.execute(
            "INSERT INTO samples (id, lab_id, project_id, sharing_level, "
            "surveillance_relevant, owner_id) VALUES (?, 1, 2, ?, ?, ?)",
            (i, sharing, 1 if surveillance else 0, owner),
        )
    got = {
        r[0]
        for r in conn.execute(
            f"SELECT s.id FROM samples s JOIN labs l ON l.id = s.lab_id WHERE {frag}", params
        )
    }
    conn.close()
    return got


PRINCIPALS = {
    "stranger": _principal(),
    "surveillance officer": _principal(grants=[("sample:read_surveillance", INSTANCE)]),
    # Lab-scoped grant: covers every row in lab 1 by containment.
    "lab member": _principal(grants=[("sample:read", scope_uri(org=1, lab=1))]),
}


class TestLadderRungs:
    def test_public_is_readable_by_a_stranger(self):
        """The rung that would have silently vanished without this work."""
        r = _resource(("PUBLIC", False, 100), 1)
        p = PRINCIPALS["stranger"]
        for cap in ("sample:read", "sample:read_detail"):
            assert permit(p, cap, r, Context(), policies=LADDER_POLICIES) is Decision.ALLOW

    def test_discoverable_is_list_visible_but_not_detail_readable(self):
        """can_access_sample: "DISCOVERABLE alone is NOT sufficient"."""
        r = _resource(("DISCOVERABLE", False, 100), 1)
        p = PRINCIPALS["stranger"]
        assert permit(p, "sample:read", r, Context(), policies=LADDER_POLICIES) is Decision.ALLOW
        assert (
            permit(p, "sample:read_detail", r, Context(), policies=LADDER_POLICIES) is Decision.DENY
        )

    def test_surveillance_needs_both_the_row_and_the_capability(self):
        r = _resource(("PRIVATE", True, 100), 1)
        assert (
            permit(
                PRINCIPALS["surveillance officer"],
                "sample:read_detail",
                r,
                Context(),
                policies=LADDER_POLICIES,
            )
            is Decision.ALLOW
        )
        assert (
            permit(
                PRINCIPALS["stranger"],
                "sample:read_detail",
                r,
                Context(),
                policies=LADDER_POLICIES,
            )
            is Decision.DENY
        )

    def test_surveillance_capability_does_not_unlock_non_surveillance_rows(self):
        r = _resource(("PRIVATE", False, 100), 1)
        assert (
            permit(
                PRINCIPALS["surveillance officer"],
                "sample:read_detail",
                r,
                Context(),
                policies=LADDER_POLICIES,
            )
            is Decision.DENY
        )

    def test_owner_reads_their_own_private_sample(self):
        r = _resource(("PRIVATE", False, 7), 1)  # principal id "7"
        assert (
            permit(
                PRINCIPALS["stranger"],
                "sample:read_detail",
                r,
                Context(),
                policies=LADDER_POLICIES,
            )
            is Decision.ALLOW
        )

    def test_ownership_does_not_leak_to_another_principal(self):
        r = _resource(("PRIVATE", False, 7), 1)
        other = _principal(uid="8")
        assert (
            permit(other, "sample:read_detail", r, Context(), policies=LADDER_POLICIES)
            is Decision.DENY
        )


class TestPermitSqlEquivalence:
    """The M1 property, extended to attribute-policies."""

    @pytest.mark.parametrize("pkey", sorted(PRINCIPALS))
    @pytest.mark.parametrize("capability", ["sample:read", "sample:read_detail"])
    def test_no_divergence_on_any_row(self, pkey, capability):
        principal = PRINCIPALS[pkey]
        sql_visible = _sql_visible(principal, capability)
        for i, row in enumerate(ROWS, start=1):
            allowed = (
                permit(
                    principal, capability, _resource(row, i), Context(), policies=LADDER_POLICIES
                )
                is Decision.ALLOW
            )
            assert allowed == (i in sql_visible), (
                f"DIVERGENCE {pkey} × {capability} × row {i} {row}: "
                f"permit={allowed} sql={i in sql_visible}"
            )


class TestUnmappedAttributeIsFatal:
    def test_missing_column_mapping_raises(self):
        """Silently dropping the term would widen an ALLOW and neuter a DENY."""
        policy = [
            {
                "effect": "DENY",
                "capability": "sample:read",
                "scope_ref": INSTANCE,
                "resource": {"contains_pii": True},
            }
        ]
        with pytest.raises(ValueError, match="contains_pii"):
            visibility_sql_clause(
                PRINCIPALS["stranger"],
                "sample:read",
                SCOPE_EXPR,
                policies=policy,
                attribute_columns=ATTR_COLUMNS,
            )

    def test_non_identifier_column_is_rejected(self):
        policy = [
            {
                "effect": "ALLOW",
                "capability": "sample:read",
                "scope_ref": INSTANCE,
                "resource": {"sharing_level": "PUBLIC"},
            }
        ]
        with pytest.raises(ValueError, match="table.column"):
            visibility_sql_clause(
                PRINCIPALS["stranger"],
                "sample:read",
                SCOPE_EXPR,
                policies=policy,
                attribute_columns={"sharing_level": "s.x; DROP TABLE samples"},
            )


class TestDenyStillWins:
    def test_attribute_deny_beats_an_attribute_allow(self):
        policies = [
            *LADDER_POLICIES,
            {
                "effect": "DENY",
                "capability": "sample:read_detail",
                "scope_ref": INSTANCE,
                "resource": {"sharing_level": "PUBLIC"},
            },
        ]
        r = _resource(("PUBLIC", False, 100), 1)
        assert (
            permit(PRINCIPALS["stranger"], "sample:read_detail", r, Context(), policies=policies)
            is Decision.DENY
        )

    def test_attribute_deny_beats_a_structural_grant(self):
        """Sovereignty's enforceability rests on this (§5.4, §6)."""
        policies = [
            {
                "effect": "DENY",
                "capability": "sample:read_detail",
                "scope_ref": INSTANCE,
                "resource": {"sharing_level": "PUBLIC"},
            }
        ]
        holder = _principal(grants=[("sample:read_detail", INSTANCE)])
        r = _resource(("PUBLIC", False, 100), 1)
        assert (
            permit(holder, "sample:read_detail", r, Context(), policies=policies) is Decision.DENY
        )
