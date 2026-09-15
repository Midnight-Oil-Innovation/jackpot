"""Differential fuzz: _scope_term vs engine._scope_contains (Critical Rule 73).

``engine._scope_contains`` decides hierarchical containment in Python.
``visibility._scope_term`` compiles the same decision into SQL, and every list
endpoint routes through it. Two implementations of one predicate — and before
this file, ``grep -rn _scope_term tests/`` returned nothing. The Python half is
fuzzed in test_scope.py and the ``capability_holders`` variant got a
differential in #190/#191; this was the untested third.

Rule 73's anchor is the reason the alphabet below is built the way it is. Four
defects lived in ~30 lines of this exact shape, and every one of them was in a
string ``scope_uri()`` cannot emit — so a corpus built from ``scope_uri()``
output could not have found any of them. The pieces here deliberately include
``//``, a trailing ``/``, the empty string, and the three characters LIKE
treats specially.

**On the dialect.** SQLite's ``LIKE`` is case-insensitive for ASCII by default;
PostgreSQL's is case-sensitive. Left alone, this harness reports
``instance://self`` as containing ``INSTANCE://SELF/org/1`` — a divergence that
does not exist in production, and one a reader could easily "fix" in the
compiler and thereby break it. ``PRAGMA case_sensitive_like = ON`` makes the
harness agree with PostgreSQL, so case variants can stay in the corpus rather
than being quietly excluded from it. Verified against a real postgres:16
container, both with and without the pragma.
"""

import itertools
import sqlite3

import pytest

from backend.authz.engine import _scope_contains
from backend.authz.visibility import _scope_term

# Fragments composed into scope strings. Most of these cannot come out of
# scope_uri(); that is the point (Rule 73's corollary — a test written from the
# constructor tests the constructor).
PIECES = [
    "instance://self",
    "INSTANCE://SELF",  # case: only meaningful with the pragma below
    "/org",
    "/1",
    "//",  # doubled separator
    "/",  # trailing separator
    "%",  # LIKE wildcard, must be matched literally
    "_",  # LIKE single-char wildcard, must be matched literally
    "\\",  # the ESCAPE character itself
    "",
]


def _corpus() -> list[str]:
    seen = {"".join(c) for n in (1, 2) for c in itertools.product(PIECES, repeat=n)}
    return sorted(seen)


CORPUS = _corpus()


@pytest.fixture(scope="module")
def conn():
    connection = sqlite3.connect(":memory:")
    # Without this, SQLite's LIKE is case-insensitive and this suite would
    # report a divergence PostgreSQL does not have. See the module docstring.
    connection.execute("PRAGMA case_sensitive_like = ON")
    connection.execute("CREATE TABLE r (scope TEXT)")
    try:
        yield connection
    finally:
        connection.close()


def _sql_says(conn, grant: str, resource: str) -> bool:
    params: dict = {}
    term = _scope_term("r.scope", grant, "p", params)
    conn.execute("DELETE FROM r")
    conn.execute("INSERT INTO r (scope) VALUES (:v)", {"v": resource})
    return bool(conn.execute(f"SELECT 1 FROM r WHERE {term}", params).fetchall())


def test_the_pragma_is_actually_in_effect(conn) -> None:
    """Guard the guard (Rule 74).

    If the pragma stops applying — a future fixture rewrite, a connection
    created elsewhere — the fuzz below starts comparing against a LIKE that
    is not production's, and its agreement stops meaning anything. Silence
    from a check that can no longer fire looks exactly like a pass.
    """
    conn.execute("DELETE FROM r")
    conn.execute("INSERT INTO r (scope) VALUES ('ABC')")
    assert not conn.execute("SELECT 1 FROM r WHERE scope LIKE 'abc'").fetchall()


def test_the_corpus_reaches_strict_containment(conn) -> None:
    """A fuzz that never exercises the LIKE arm proves nothing about it.

    The obvious form of this check — that both True and False are reachable —
    is vacuous: ``grant == resource`` is in the product, so True is guaranteed
    no matter how degenerate the corpus becomes. It passed against a corpus of
    ``["%", "_"]``, which exercises the exact-match arm only.

    What has to be reachable is *strict* descendant containment, because that
    is the arm ``_scope_term`` compiles into LIKE and the one every defect in
    Rule 73's anchor lived in.
    """
    strict = [
        (g, r) for g, r in itertools.product(CORPUS, repeat=2) if g != r and _scope_contains(g, r)
    ]
    non_contained = [
        (g, r) for g, r in itertools.product(CORPUS, repeat=2) if not _scope_contains(g, r)
    ]

    assert len(strict) > 50, f"only {len(strict)} strict-descendant pairs — corpus has gone thin"
    assert non_contained, "no non-containing pairs — the differential cannot detect over-matching"


@pytest.mark.parametrize("grant", CORPUS)
def test_sql_containment_never_admits_more_than_the_oracle(conn, grant: str) -> None:
    """The direction that is a disclosure.

    A row the SQL admits but permit() would refuse is data leaving the
    deployment. The reverse is a row missing from a list — visible, and a bug,
    but not a breach. Equality is asserted separately.
    """
    for resource in CORPUS:
        assert not (_sql_says(conn, grant, resource) and not _scope_contains(grant, resource)), (
            f"SQL admits a scope the engine refuses: grant={grant!r} resource={resource!r}"
        )


@pytest.mark.parametrize("grant", CORPUS)
def test_sql_containment_agrees_with_the_oracle(conn, grant: str) -> None:
    for resource in CORPUS:
        assert _sql_says(conn, grant, resource) == _scope_contains(grant, resource), (
            f"grant={grant!r} resource={resource!r}: "
            f"sql={_sql_says(conn, grant, resource)} oracle={_scope_contains(grant, resource)}"
        )
