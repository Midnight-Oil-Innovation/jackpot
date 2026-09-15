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
def test_sql_is_never_more_permissive_than_the_oracle(predicate: dict, value) -> None:
    """Assert the direction, not equality.

    SQL refusing a row the oracle allows is a visible bug. SQL allowing one
    the oracle refuses is a disclosure — the asymmetry is the whole reason
    this is a direction and not an ``==``.
    """
    assert not (_sql_says(predicate, value) and not _oracle_says(predicate, value)), (
        f"SQL admitted a row the oracle refuses: {predicate!r} against {value!r}"
    )


@pytest.mark.parametrize(("predicate", "value"), list(itertools.product(PREDICATES, ATTR_VALUES)))
def test_sql_and_oracle_agree(predicate: dict, value) -> None:
    """Full equality, so a narrowing divergence fails too rather than passing quietly."""
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
    params: dict = {}
    term = _attr_sql(predicate, COLUMNS, PRINCIPAL.id, "p", params)

    assert "IN ()" not in term.replace("IN( )", "IN ()"), (
        f"{predicate!r} compiled to {term!r}, which PostgreSQL rejects"
    )
