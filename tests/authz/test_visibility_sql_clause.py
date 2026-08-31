"""M1 — cross-checking behavioral-equivalence suite for visibility_sql_clause().

The acceptance gate: a row is list-visible via the SQL fragment iff
permit() says it is detail-accessible, on the SAME §9 fixtures M0 used
(docs/access_model.md §9.1 laptop, §9.2 SaaS + surveillance, §9.4
cryptWWDB compute-without-read, plus deny-wins and default-deny).

The fragment is executed against in-process SQLite (stdlib sqlite3
understands the same ``:name`` bind convention as sqlalchemy.text()).
"""

import sqlite3

import pytest

from authz.scopes import (
    ACME,
    ACME_L1_SAMPLE,
    ACME_L2_SAMPLE,
    ACME_LAB1,
    FIXTURE_ROWS,
    FIXTURE_SCOPES,
    INSTANCE,
    RIVAL_SAMPLE,
    SCOPE_EXPR,
    TRAP_SAMPLE,
    WWDB,
    WWDB_SAMPLE,
)
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
from backend.authz.scope import scope_sql, scope_uri


def _human(grants: list[CapabilityGrant] | None = None) -> Principal:
    return Principal(kind=PrincipalKind.HUMAN, id="u1", on_behalf_of=None, grants=grants or [])


def sql_visible(
    principal: Principal,
    capability: str,
    *,
    context: Context | None = None,
    policies: list[dict],
    rows: list[tuple[int, int, int, int]] = FIXTURE_ROWS,
) -> set[str]:
    """Execute the compiled fragment against SQLite; return visible scopes.

    The harness builds the real shape — ``samples JOIN labs`` with lineage
    columns — rather than a synthetic scope column, so the fragment under test
    is the one production will run (ADR 0015).
    """
    frag, params = visibility_sql_clause(
        principal, capability, SCOPE_EXPR, context=context, policies=policies
    )
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE labs (id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL)")
    conn.execute(
        "CREATE TABLE samples (id INTEGER PRIMARY KEY, lab_id INTEGER NOT NULL, "
        "project_id INTEGER NOT NULL)"
    )
    # labs.id and samples.id are globally unique SERIAL keys, so each lab
    # belongs to exactly one org and no sample id repeats — INSERT OR IGNORE
    # covers labs shared by several samples, and a PK collision here means the
    # fixture rows describe a database state that cannot exist.
    for org_id, lab_id, project_id, sample_id in rows:
        conn.execute(
            "INSERT OR IGNORE INTO labs (id, organization_id) VALUES (?, ?)", (lab_id, org_id)
        )
        conn.execute(
            "INSERT INTO samples (id, lab_id, project_id) VALUES (?, ?, ?)",
            (sample_id, lab_id, project_id),
        )
    got = conn.execute(
        f"SELECT {SCOPE_EXPR} FROM samples s JOIN labs l ON l.id = s.lab_id WHERE {frag}",
        params,
    ).fetchall()
    conn.close()
    return {r[0] for r in got}


def sql_all_scopes(rows: list[tuple[int, int, int, int]] = FIXTURE_ROWS) -> set[str]:
    """Every scope the SQL expression derives from the fixture rows."""
    return sql_visible(
        _human([CapabilityGrant("sample:read_detail", INSTANCE)]),
        "sample:read_detail",
        policies=[],
        rows=rows,
    )


def assert_equivalent(
    principal: Principal,
    capability: str,
    *,
    context: Context | None = None,
    policies: list[dict],
    rows: list[tuple[int, int, int, int]] = FIXTURE_ROWS,
) -> set[str]:
    """Assert permit() == (row in sql_results) for every fixture row."""
    visible = sql_visible(principal, capability, context=context, policies=policies, rows=rows)
    ctx = context or Context()
    scopes = [scope_uri(org=o, lab=lb, project=pr, sample=sm) for o, lb, pr, sm in rows]
    for scope in scopes:
        decision = permit(principal, capability, Resource(scope=scope), ctx, policies=policies)
        assert (decision == Decision.ALLOW) == (scope in visible), (
            f"DIVERGENCE: permit()={decision} but sql_visible={scope in visible} "
            f"for scope={scope!r} capability={capability!r}"
        )
    return visible


# ── 1. grant at Org scope containing the sample's Lab → row included ─────


def test_org_grant_includes_contained_row():
    p = _human([CapabilityGrant("sample:read_detail", ACME)])
    visible = assert_equivalent(p, "sample:read_detail", policies=[])
    assert ACME_L1_SAMPLE in visible
    assert ACME_L2_SAMPLE in visible


# ── 2. grant scope does NOT contain sample scope → row excluded ──────────


def test_noncontaining_grant_excludes_row():
    p = _human([CapabilityGrant("sample:read_detail", ACME)])
    visible = assert_equivalent(p, "sample:read_detail", policies=[])
    assert RIVAL_SAMPLE not in visible
    assert TRAP_SAMPLE not in visible  # prefix trap


# ── 3. DENY policy overrides ALLOW grant — strict deny-wins ──────────────


def test_deny_policy_overrides_allow_grant():
    p = _human([CapabilityGrant("sample:read_detail", ACME)])
    deny = {
        "effect": "DENY",
        "capability": "sample:read_detail",
        "scope_ref": ACME_LAB1,
        "conditions": {},
    }
    visible = assert_equivalent(p, "sample:read_detail", policies=[deny])
    assert ACME_L1_SAMPLE not in visible  # denied despite grant
    assert ACME_L2_SAMPLE in visible  # deny scoped to lab-1 only


# ── 4. PEER_INSTANCE principal, federation:push ──────────────────────────


def test_peer_instance_federation_push():
    p = Principal(
        kind=PrincipalKind.PEER_INSTANCE,
        id="state-a.example",
        on_behalf_of=None,
        grants=[CapabilityGrant("federation:push", ACME_LAB1, source="agreement")],
    )
    visible = assert_equivalent(p, "federation:push", policies=[])
    assert visible == {ACME_L1_SAMPLE}


# ── 5. SERVICE principal, compute:he_aggregate (§9.4) ────────────────────


def test_service_compute_he_aggregate():
    p = Principal(
        kind=PrincipalKind.SERVICE,
        id="cryptwwdb-lab",
        on_behalf_of=None,
        grants=[CapabilityGrant("compute:he_aggregate", WWDB, {"encrypted_only": True})],
    )
    ctx = Context(conditions={"encrypted_only": True})
    visible = assert_equivalent(p, "compute:he_aggregate", context=ctx, policies=[])
    assert visible == {WWDB_SAMPLE}
    # condition not met at compile time → grant dropped → nothing visible
    assert assert_equivalent(p, "compute:he_aggregate", policies=[]) == set()


# ── 6. sample:read_surveillance with surveillance grant ──────────────────


def test_surveillance_grant():
    p = _human([CapabilityGrant("sample:read_surveillance", ACME)])
    visible = assert_equivalent(p, "sample:read_surveillance", policies=[])
    assert ACME_L1_SAMPLE in visible
    assert RIVAL_SAMPLE not in visible


# ── 7. zero grants — default-deny excludes all rows ──────────────────────


def test_zero_grants_default_deny_excludes_all():
    assert assert_equivalent(_human([]), "sample:read_detail", policies=[]) == set()


# ── 8. grant at Lab scope, sample in a different Lab ─────────────────────


def test_lab_grant_excludes_other_lab():
    p = _human([CapabilityGrant("sample:read_detail", ACME_LAB1)])
    visible = assert_equivalent(p, "sample:read_detail", policies=[])
    assert ACME_L1_SAMPLE in visible
    assert ACME_L2_SAMPLE not in visible


# ── 9. grant at Instance scope (widest) covers all instance rows ─────────


def test_instance_grant_sees_every_row_in_the_deployment():
    """Instance-root grant is universal within the deployment.

    Formerly `test_instance_grant_sees_only_its_instance`, which asserted a
    grant at one instance did not see rows in another. ADR 0015 gives each
    deployment exactly one root, so there are no foreign-instance rows to
    exclude — and the property worth pinning inverts: the root grant reaches
    every row, which is what makes admin reach structural rather than a
    bypass branch.
    """
    p = _human([CapabilityGrant("sample:read_detail", INSTANCE)])
    visible = sql_visible(p, "sample:read_detail", policies=[])
    assert visible == set(FIXTURE_SCOPES)


# ── 10. cross-check loop: all §9 (principal, capability, policy) combos ──

_ALLOW_POLICY = {
    "effect": "ALLOW",
    "capability": "sample:read_detail",
    "scope_ref": ACME,
    "conditions": {},
}
_DENY_POLICY = {
    "effect": "DENY",
    "capability": "sample:read_detail",
    "scope_ref": ACME,
    "conditions": {},
}

PRINCIPALS = [
    _human([CapabilityGrant("sample:read_detail", INSTANCE)]),
    _human([CapabilityGrant("sample:read_detail", ACME)]),
    _human([CapabilityGrant("sample:read_detail", ACME_LAB1)]),
    _human([CapabilityGrant("sample:read_surveillance", ACME)]),
    _human([CapabilityGrant("compute:he_aggregate", WWDB, {"encrypted_only": True})]),
    _human([]),
    Principal(
        kind=PrincipalKind.PEER_INSTANCE,
        id="state-a.example",
        on_behalf_of=None,
        grants=[CapabilityGrant("federation:push", ACME_LAB1, source="agreement")],
    ),
    Principal(
        kind=PrincipalKind.SERVICE,
        id="cryptwwdb-lab",
        on_behalf_of=None,
        grants=[CapabilityGrant("compute:he_aggregate", WWDB, {"encrypted_only": True})],
    ),
]

CAPABILITIES = [
    "sample:read_detail",
    "sample:read_surveillance",
    "compute:he_aggregate",
    "federation:push",
]

POLICY_SETS = [[], [_ALLOW_POLICY], [_DENY_POLICY], [_ALLOW_POLICY, _DENY_POLICY]]

CONTEXTS = [Context(), Context(conditions={"encrypted_only": True})]


def test_cross_check_all_pairs_zero_divergence():
    checked = 0
    for principal in PRINCIPALS:
        for capability in CAPABILITIES:
            for policies in POLICY_SETS:
                for ctx in CONTEXTS:
                    assert_equivalent(principal, capability, context=ctx, policies=policies)
                    checked += len(FIXTURE_SCOPES)
    assert checked == len(PRINCIPALS) * len(CAPABILITIES) * len(POLICY_SETS) * len(CONTEXTS) * len(
        FIXTURE_SCOPES
    )


# ── 11. failure paths ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad", ["read_detail", "sample:", ":read", "sample:read:extra", "", "SAMPLE:READ"]
)
def test_malformed_capability_raises(bad):
    with pytest.raises(ValueError, match="malformed capability"):
        visibility_sql_clause(_human([]), bad, SCOPE_EXPR, policies=[])


@pytest.mark.parametrize(
    "bad_expr",
    [
        "s.scope",  # the old alias form — no longer accepted
        "s; DROP TABLE samples",  # statement injection
        SCOPE_EXPR + " OR 1=1",  # appended clause on a genuine expression
        SCOPE_EXPR.replace("s.id", "s.id) OR (1=1"),  # spliced inside it
        "",
    ],
)
def test_non_canonical_scope_expr_raises(bad_expr):
    # The expression is interpolated, not bound, so anything that is not
    # byte-identical to scope_sql() output must be refused.
    with pytest.raises(ValueError, match="scope_expr"):
        visibility_sql_clause(_human([]), "sample:read_detail", bad_expr, policies=[])


def test_scope_expr_from_scope_sql_is_accepted():
    frag, _ = visibility_sql_clause(
        _human([]), "sample:read_detail", scope_sql(samples="smp", labs="lb"), policies=[]
    )
    assert isinstance(frag, str)


def test_policies_none_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        visibility_sql_clause(_human([]), "sample:read_detail", SCOPE_EXPR, policies=None)


def test_fixture_rows_match_scopes():
    """The lineage rows and the scope strings must describe the same world."""
    derived = [scope_uri(org=o, lab=lb, project=pr, sample=sm) for o, lb, pr, sm in FIXTURE_ROWS]
    assert derived == FIXTURE_SCOPES

    # And the SQL expression must agree with the Python builder on every row —
    # the equivalence M1 exists to protect, at the serialization level.
    assert sql_all_scopes() == set(FIXTURE_SCOPES)


# ── Grant expiry in the SQL half (M2-B2-PRE-C) ──────────────────────────


def test_expired_grant_is_dropped_from_the_fragment():
    """The compiler must agree with permit(): an expired grant contributes
    nothing, so its rows are not listed."""
    from datetime import UTC, datetime

    past = datetime(2000, 1, 1, tzinfo=UTC)
    now = datetime(2026, 8, 31, tzinfo=UTC)
    p = _human([CapabilityGrant("sample:read_detail", ACME, not_after=past)])
    assert sql_visible(p, "sample:read_detail", context=Context(now=now), policies=[]) == set()


def test_unexpired_grant_still_lists_its_rows():
    from datetime import UTC, datetime

    future = datetime(2999, 1, 1, tzinfo=UTC)
    now = datetime(2026, 8, 31, tzinfo=UTC)
    p = _human([CapabilityGrant("sample:read_detail", ACME, not_after=future)])
    visible = sql_visible(p, "sample:read_detail", context=Context(now=now), policies=[])
    assert ACME_L1_SAMPLE in visible
