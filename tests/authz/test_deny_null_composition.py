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
from backend.authz.policy import DELETION_POLICIES, PRINCIPAL_ID
from backend.authz.visibility import visibility_sql_clause

CAPABILITY = "deletion:approve"
PRINCIPAL_UID = "7"

# Taken from the shipped policy set rather than copied. A hand-written copy
# under a comment claiming it is "verbatim" is Rule 74's third anchor exactly:
# the shipped policy also carries an "id" and a "conditions" key, so the copy
# was already not verbatim, and if DELETION_POLICIES changes shape a copy keeps
# passing against a policy that no longer exists.
(SELF_APPROVAL_DENY,) = [p for p in DELETION_POLICIES if p["capability"] == CAPABILITY]
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


def test_the_deny_still_fires_on_the_row_it_exists_for() -> None:
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


# ── the invariant the COALESCE makes load-bearing ────────────────────────────

# Every predicate form the language supports, including the ones no shipped
# policy uses. The forms that matter are those whose oracle MATCHES on a NULL
# attribute: those must compile to NULL-total SQL, or COALESCE turns a firing
# DENY into a silent pass.
PREDICATE_FORMS = [
    {"attr": "X"},
    {"attr": None},
    {"attr": {"in": []}},
    {"attr": {"in": ["X"]}},
    {"attr": {"in": ["X", "Y"]}},
    {"attr": {"in": [None]}},
    {"attr": {"in": ["X", None]}},
    {"attr": {"not": "X"}},
    {"attr": {"not": None}},
    {"attr": PRINCIPAL_ID},
]
ATTR_VALUES = ["X", "Y", None, PRINCIPAL_UID]


def _deny_sql_hides(predicate: dict, value) -> bool:
    """Run the real DENY composition over a one-row table."""
    policy = {
        "effect": "DENY",
        "capability": CAPABILITY,
        "scope_ref": "instance://self",
        "resource": predicate,
    }
    frag, params = visibility_sql_clause(
        _principal(),
        CAPABILITY,
        SCOPE_EXPR,
        context=Context(),
        policies=[policy],
        attribute_columns={"attr": "s.attr"},
    )
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE labs (id INTEGER PRIMARY KEY, organization_id INTEGER)")
        conn.execute(
            "CREATE TABLE samples (id INTEGER PRIMARY KEY, lab_id INTEGER, "
            "project_id INTEGER, attr TEXT)"
        )
        conn.execute("INSERT INTO labs (id, organization_id) VALUES (1, 1)")
        conn.execute(
            "INSERT INTO samples (id, lab_id, project_id, attr) VALUES (1, 1, 2, :v)",
            {"v": value},
        )
        rows = conn.execute(
            f"SELECT s.id FROM samples s JOIN labs l ON l.id = s.lab_id WHERE {frag}", params
        ).fetchall()
        return not rows
    finally:
        conn.close()


def _oracle_denies(predicate: dict, value) -> bool:
    policy = {
        "effect": "DENY",
        "capability": CAPABILITY,
        "scope_ref": "instance://self",
        "resource": predicate,
    }
    resource = Resource(
        scope="instance://self/org/1/lab/1/project/2/sample/1", attributes={"attr": value}
    )
    decision = permit(_principal(), CAPABILITY, resource, Context(), policies=[policy])
    return decision is not Decision.ALLOW


@pytest.mark.parametrize("predicate", PREDICATE_FORMS)
@pytest.mark.parametrize("value", ATTR_VALUES)
def test_a_deny_hides_exactly_what_permit_denies(predicate: dict, value) -> None:
    """Differential over every predicate form (Rule 73).

    COALESCE(deny_chain, FALSE) is only correct while NULL implies the oracle
    said False. That holds today because the three forms whose oracle matches
    a NULL attribute — ``None``, ``{"not": v}``, ``{"in": [..., None]}`` —
    compile to IS NULL / IS DISTINCT FROM / an IS NULL disjunct, all total.

    Nothing enforced that. Before the COALESCE a NULL term failed closed, so a
    non-total compilation was merely a hidden row; now it is a DENY that stops
    firing. This is what catches the next branch added to _attr_matches without
    a matching total compilation in _attr_sql.
    """
    assert _deny_sql_hides(predicate, value) == _oracle_denies(predicate, value), (
        f"DENY {predicate!r} against {value!r}: "
        f"sql_hides={_deny_sql_hides(predicate, value)} "
        f"oracle_denies={_oracle_denies(predicate, value)}"
    )


def test_the_fuzz_reaches_both_verdicts() -> None:
    """Guard the guard. A corpus that never denies would pass against anything."""
    verdicts = {_oracle_denies(p, v) for p in PREDICATE_FORMS for v in ATTR_VALUES}
    assert verdicts == {True, False}
