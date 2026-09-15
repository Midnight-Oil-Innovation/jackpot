"""Differential test: _attr_sql vs _attr_matches (Critical Rule 73).

``policy._attr_matches`` evaluates a resource predicate in Python.
``visibility._attr_sql`` compiles the same predicate into SQL. Two
implementations of one predicate language, and the docstring on each names
the other — "two halves diverging is the failure M1 exists to prevent".

Neither half's ``{"in": [...]}`` form was exercised by any test before this
file: ``grep '"in"' tests/authz/`` returned nothing.

**On the harness.** These run against SQLite, as the rest of the suite does.
SQLite accepts ``x IN ()`` as a non-standard always-false extension;
PostgreSQL rejects it as a syntax error. So SQLite agreeing with the oracle
is not sufficient evidence here, and `test_no_predicate_compiles_to_empty_in`
asserts on the emitted SQL text rather than on its result — it is the only
assertion in this file that can see a production-only failure.
"""

import itertools
import sqlite3

import pytest

from backend.authz.engine import Principal, PrincipalKind, Resource
from backend.authz.policy import PRINCIPAL_ID, _attr_matches
from backend.authz.visibility import _attr_sql

COLUMNS = {"sharing_level": "s.sharing_level"}
PRINCIPAL = Principal(kind=PrincipalKind.HUMAN, id="7", on_behalf_of=None, grants=[])

# Values a row's attribute might hold, including the ones a well-formed
# fixture never produces.
ATTR_VALUES = ["PUBLIC", "PRIVATE", "", None, "7"]

# Predicate forms the language allows. The empty and single-element `in`
# lists are the point: a hand-written policy set contains neither, so a test
# built from the seeded policies could not reach them.
PREDICATES = [
    {"sharing_level": "PUBLIC"},
    {"sharing_level": {"in": []}},
    {"sharing_level": {"in": ["PUBLIC"]}},
    {"sharing_level": {"in": ["PUBLIC", "PRIVATE"]}},
    {"sharing_level": {"in": ["PUBLIC", "PUBLIC"]}},
    {"sharing_level": {"not": "PUBLIC"}},
    {"sharing_level": {"not": None}},
    {"sharing_level": PRINCIPAL_ID},
    # NULL is a value to the oracle and an absence to SQL — `col = NULL` and
    # `col IN (NULL)` are both NULL, never true. The disagreement is narrower
    # inside an ALLOW and wider inside a DENY, which is negated at clause level.
    {"sharing_level": None},
    {"sharing_level": {"in": [None]}},
    {"sharing_level": {"in": ["PUBLIC", None]}},
]

# Predicates that name two forms at once. Neither half defines this shape, and
# they resolved it in opposite orders — policy.py tested "in" first,
# visibility.py tested "not" first — so the dict compiled to a different rule
# than it evaluated. Both halves must now refuse it rather than pick.
AMBIGUOUS_PREDICATES = [
    {"sharing_level": {"in": [], "not": "PUBLIC"}},
    {"sharing_level": {"in": ["PUBLIC"], "not": "PUBLIC"}},
]


def _sql_says(predicate: dict, value) -> bool:
    """Run the compiled fragment against a one-row table."""
    params: dict = {}
    term = _attr_sql(predicate, COLUMNS, PRINCIPAL.id, "p", params)
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE s (sharing_level TEXT)")
        conn.execute("INSERT INTO s (sharing_level) VALUES (:v)", {"v": value})
        rows = conn.execute(f"SELECT 1 FROM s WHERE {term}", params).fetchall()
        return bool(rows)
    finally:
        conn.close()


def _oracle_says(predicate: dict, value) -> bool:
    resource = Resource(scope="instance://self/org/1", attributes={"sharing_level": value})
    return _attr_matches(predicate, resource, PRINCIPAL)


@pytest.mark.parametrize(("predicate", "value"), list(itertools.product(PREDICATES, ATTR_VALUES)))
def test_sql_and_oracle_agree(predicate: dict, value) -> None:
    """Full equality, so a narrowing divergence fails too rather than passing quietly.

    Equality rather than a DENY-specific direction, and that took two tries to
    settle. visibility.py wraps attribute terms in `NOT (...)` for a DENY, so a
    term narrower than the oracle is a DENY that cannot fire — which argues for
    asserting the inverse direction separately. Both attempts at such a test
    turned out to be entailed by this one: mutating `_attr_sql` every way that
    broke them broke this first. Equality is the strongest statement about
    truth values, and everything directional follows from it.

    What it cannot see is NULL. This compares `bool(rows)`, which folds SQL
    NULL into False, and a term that is NULL rather than FALSE behaves
    differently only once negated. `test_the_null_inventory_is_still_accurate`
    is the guard for that, and it is not redundant: replacing `col = :k` with
    `COALESCE(col, '~~') = :k` leaves every assertion here passing and fails
    only that one.
    """
    assert _sql_says(predicate, value) == _oracle_says(predicate, value), (
        f"{predicate!r} against {value!r}: "
        f"sql={_sql_says(predicate, value)} oracle={_oracle_says(predicate, value)}"
    )


@pytest.mark.parametrize("predicate", PREDICATES)
def test_no_predicate_compiles_to_empty_in(predicate: dict) -> None:
    """The one assertion here that SQLite cannot make for us.

    ``x IN ()`` is a syntax error in PostgreSQL and an always-false extension
    in SQLite, so every result-based assertion above passes on an empty list
    while production raises. Read the emitted text instead.
    """
    # Guard the guard (Rule 74). Only `{"in": []}` can produce `IN ()`, so
    # dropping that one entry from PREDICATES would leave this printing green
    # over ten vacuous parametrizations — verified, it does — and the NULL
    # inventory would not notice, because the empty-in term is not NULL-valued.
    # Assert the case still exists, not merely that the loop found nothing.
    assert _attr_sql({"sharing_level": {"in": []}}, COLUMNS, PRINCIPAL.id, "p", {}) == "1 = 0"

    params: dict = {}
    term = _attr_sql(predicate, COLUMNS, PRINCIPAL.id, "p", params)

    assert "IN ()" not in term, f"{predicate!r} compiled to {term!r}, which PostgreSQL rejects"


@pytest.mark.parametrize("predicate", AMBIGUOUS_PREDICATES)
def test_both_halves_refuse_a_predicate_naming_two_forms(predicate: dict) -> None:
    """Refusing beats choosing, and refusing in both places beats refusing in one.

    Before this, `{"in": [], "not": "PUBLIC"}` against a PRIVATE row was
    SQL=True / oracle=False — the SQL half admitting a row permit() refuses,
    which is the disclosure direction. Measured, not theorised.
    """
    with pytest.raises(ValueError):
        _attr_sql(predicate, COLUMNS, PRINCIPAL.id, "p", {})
    with pytest.raises(ValueError):
        _oracle_says(predicate, "PRIVATE")


def _sql_term_value(predicate: dict, value):
    """The term's SQL value — True/False/**None** — not `bool(rows)`.

    Collapsing NULL to False is what made the first version of this test
    vacuous: at term level a NULL and a False are indistinguishable, and they
    only separate once the term is negated for a DENY.
    """
    params: dict = {}
    term = _attr_sql(predicate, COLUMNS, PRINCIPAL.id, "p", params)
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE s (sharing_level TEXT)")
        conn.execute("INSERT INTO s (sharing_level) VALUES (:v)", {"v": value})
        return conn.execute(f"SELECT ({term}) FROM s", params).fetchone()[0]
    finally:
        conn.close()


# Every (predicate, value) whose term evaluates to SQL NULL rather than to
# TRUE or FALSE. This is an inventory, not an exception list: the assertion
# below holds for all of these too. It exists so that a term newly going
# three-valued — or newly stopping — fails a test instead of passing quietly,
# which is the only way the NULL cases are visible at all under `bool(rows)`.
#
# What NULL costs: visibility.py composes a DENY as `NOT (term)`, and
# `NOT (NULL)` is NULL, so the row drops out of the list. Against a DENY that
# is over-firing, not under-firing — rows disappear that permit() allows.
# In the real clause each deny term is AND-ed with scope and condition terms
# first, and `NULL AND FALSE` is FALSE, so this is a property of the term in
# isolation rather than a demonstrated end-to-end defect.
NULL_VALUED_TERMS = {
    (repr({"sharing_level": "PUBLIC"}), None),
    (repr({"sharing_level": {"in": ["PUBLIC"]}}), None),
    (repr({"sharing_level": {"in": ["PUBLIC", "PRIVATE"]}}), None),
    (repr({"sharing_level": {"in": ["PUBLIC", "PUBLIC"]}}), None),
    (repr({"sharing_level": PRINCIPAL_ID}), None),
}


def test_the_null_inventory_is_still_accurate() -> None:
    """Anti-rot (Rule 74). An entry nothing can produce is a dead rule reading live."""
    reachable = {
        (repr(p), v)
        for p, v in itertools.product(PREDICATES, ATTR_VALUES)
        if _sql_term_value(p, v) is None
    }
    assert reachable == NULL_VALUED_TERMS, (
        "the inventory no longer matches the terms that evaluate to NULL"
    )
