"""A DENY whose predicate reads a NULL column must not hide the row.

visibility.py composes a DENY as ``NOT (d1 OR d2 ...) AND (allow)``. In SQL a
term over a NULL column is NULL, not FALSE, so ``NOT (NULL)`` is NULL and the
row drops out of the list — while ``permit()`` reaches the opposite verdict,
because ``_attr_matches`` is total and answers False for a predicate that does
not match. The DENY over-fires on exactly the rows it has nothing to say about.

This is reachable with a shipped policy and a shipped column, not a
hypothetical one. ``ACTIVE_POLICIES`` denies ``deletion:approve`` on
``{"deletion_requested_by_user_id": PRINCIPAL_ID}`` (the separation-of-duties
rule: you may not approve your own deletion request), and that column is
``INTEGER REFERENCES users(id)`` — nullable, and NULL for every sample with no
deletion request pending, which is nearly all of them.

The existing cross-check in test_visibility_sql_clause.py could not catch it:
it asserts "all pairs, zero divergence" over scope-only policy sets and never
passes ``attribute_columns`` at all, so no attribute predicate is ever compiled.
"""

import sqlite3

import pytest

from authz.scopes import SCOPE_EXPR
from backend.authz import CapabilityGrant, Context, Decision, Principal, PrincipalKind, permit
from backend.authz.engine import Resource
from backend.authz.policy import PRINCIPAL_ID
from backend.authz.visibility import visibility_sql_clause

CAPABILITY = "deletion:approve"
PRINCIPAL_UID = "7"

# Verbatim shape from policy.ACTIVE_POLICIES.
SELF_APPROVAL_DENY = {
    "effect": "DENY",
    "capability": CAPABILITY,
    "scope_ref": "instance://self",
    "resource": {"deletion_requested_by_user_id": PRINCIPAL_ID},
}
ATTR_COLUMNS = {"deletion_requested_by_user_id": "s.deletion_requested_by_user_id"}

# (sample_id, deletion_requested_by_user_id)
ROWS = [
    (1, None),  # no deletion request pending — the ordinary state
    (2, 7),  # requested by the acting principal: the DENY's actual target
    (3, 9),  # requested by somebody else
]


def _principal() -> Principal:
    return Principal(
        kind=PrincipalKind.HUMAN,
        id=PRINCIPAL_UID,
        on_behalf_of=None,
        grants=[
            CapabilityGrant(
                capability=CAPABILITY,
                scope_ref="instance://self",
                conditions={},
                not_after=None,
            )
        ],
    )


def _sql_visible(principal: Principal) -> set[int]:
    frag, params = visibility_sql_clause(
        principal,
        CAPABILITY,
        SCOPE_EXPR,
        context=Context(),
        policies=[SELF_APPROVAL_DENY],
        attribute_columns=ATTR_COLUMNS,
    )
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE labs (id INTEGER PRIMARY KEY, organization_id INTEGER)")
        conn.execute(
            "CREATE TABLE samples (id INTEGER PRIMARY KEY, lab_id INTEGER, "
            "project_id INTEGER, deletion_requested_by_user_id INTEGER)"
        )
        conn.execute("INSERT INTO labs (id, organization_id) VALUES (1, 1)")
        for sample_id, requester in ROWS:
            conn.execute(
                "INSERT INTO samples (id, lab_id, project_id, "
                "deletion_requested_by_user_id) VALUES (?, 1, 2, ?)",
                (sample_id, requester),
            )
        return {
            row[0]
            for row in conn.execute(
                f"SELECT s.id FROM samples s JOIN labs l ON l.id = s.lab_id WHERE {frag}",
                params,
            )
        }
    finally:
        conn.close()


def _permits(principal: Principal, sample_id: int, requester: int | None) -> bool:
    resource = Resource(
        scope=f"instance://self/org/1/lab/1/project/2/sample/{sample_id}",
        attributes={"deletion_requested_by_user_id": requester},
    )
    return (
        permit(principal, CAPABILITY, resource, Context(), policies=[SELF_APPROVAL_DENY])
        is Decision.ALLOW
    )


@pytest.mark.parametrize(("sample_id", "requester"), ROWS)
def test_list_and_permit_agree_on_every_row(sample_id: int, requester: int | None) -> None:
    principal = _principal()

    assert (sample_id in _sql_visible(principal)) == _permits(principal, sample_id, requester)


def test_the_deny_still_fires_on_the_row_it_exists_for(conn=None) -> None:
    """Narrowing the fix must not neuter the rule.

    Sample 2 is the principal's own deletion request. If a NULL-safety change
    ever turns this DENY off wholesale, this is the assertion that notices —
    the separation-of-duties rule failing open is worse than the rows it hides.
    """
    principal = _principal()
    visible = _sql_visible(principal)

    assert 2 not in visible
    assert not _permits(principal, 2, 7)


def test_rows_the_deny_has_nothing_to_say_about_stay_visible() -> None:
    """The defect, stated directly rather than via the parametrised pair."""
    principal = _principal()
    visible = _sql_visible(principal)

    assert 1 in visible, "a sample with no deletion request must remain listable"
    assert 3 in visible, "a deletion requested by someone else is approvable"
