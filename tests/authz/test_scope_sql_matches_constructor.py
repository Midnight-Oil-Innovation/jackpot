"""Differential: the three scope-SQL builders vs scope_uri() (Critical Rule 73).

``scope_uri()`` constructs a canonical scope URI in Python. ``scope_sql()``,
``lab_scope_sql()`` and ``project_scope_sql()`` reconstruct the same string in
SQL from lineage columns. Four implementations of one format, and nothing
asserted they produce the same bytes.

They do — 0 divergences over every combination below, confirmed on SQLite and
on a real postgres:16 container. This file is the assertion that was missing,
not a fix.

Why it matters more than "two functions agree": the SQL forms feed
``_scope_term``, so a single character of drift — a separator, a segment name,
a stray space — silently changes which rows a grant contains. Nothing would
raise. The list would just be wrong, in whichever direction the drift went.
"""

import itertools
import sqlite3

import pytest

from backend.authz.scope import lab_scope_sql, project_scope_sql, scope_sql, scope_uri

# Database ids are SERIAL, so production values are positive. Spread includes a
# multi-digit id and a value past 2^31 to catch any text/integer rendering
# difference between the constructor and the `||` chain.
IDS = [1, 2, 11, 12345, 999999999999]


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE labs (id INTEGER, organization_id INTEGER)")
    connection.execute("CREATE TABLE samples (id INTEGER, lab_id INTEGER, project_id INTEGER)")
    connection.execute("CREATE TABLE projects (id INTEGER, lab_id INTEGER)")
    try:
        yield connection
    finally:
        connection.close()


def _scalar(conn, query: str) -> str:
    return conn.execute(query).fetchone()[0]


@pytest.mark.parametrize("org", IDS)
def test_sample_scope_sql_matches_the_constructor(conn, org: int) -> None:
    expr = scope_sql(samples="s", labs="l")
    for lab, project, sample in itertools.product(IDS, repeat=3):
        conn.execute("DELETE FROM labs")
        conn.execute("DELETE FROM samples")
        conn.execute("INSERT INTO labs VALUES (?, ?)", (lab, org))
        conn.execute("INSERT INTO samples VALUES (?, ?, ?)", (sample, lab, project))

        built = _scalar(conn, f"SELECT {expr} FROM samples s JOIN labs l ON l.id = s.lab_id")

        assert built == scope_uri(org=org, lab=lab, project=project, sample=sample)


def test_lab_scope_sql_matches_the_constructor(conn) -> None:
    expr = lab_scope_sql(labs="l")
    for org, lab in itertools.product(IDS, repeat=2):
        conn.execute("DELETE FROM labs")
        conn.execute("INSERT INTO labs VALUES (?, ?)", (lab, org))

        assert _scalar(conn, f"SELECT {expr} FROM labs l") == scope_uri(org=org, lab=lab)


@pytest.mark.parametrize("project_id_column", ["id", "project_id"])
def test_project_scope_sql_matches_the_constructor(conn, project_id_column: str) -> None:
    """Both shapes from PROJECT_ID_COLUMNS, since each is a separate expression."""
    column = "id" if project_id_column == "id" else "project_id"
    conn.execute(f"CREATE TABLE rows_under_test (lab_id INTEGER, {column} INTEGER)")
    expr = project_scope_sql(labs="l", rows="r", project_id_column=project_id_column)

    for org, lab, project in itertools.product(IDS, repeat=3):
        conn.execute("DELETE FROM labs")
        conn.execute("DELETE FROM rows_under_test")
        conn.execute("INSERT INTO labs VALUES (?, ?)", (lab, org))
        conn.execute("INSERT INTO rows_under_test VALUES (?, ?)", (lab, project))

        built = _scalar(
            conn,
            f"SELECT {expr} FROM rows_under_test r JOIN labs l ON l.id = r.lab_id",
        )

        assert built == scope_uri(org=org, lab=lab, project=project)


def test_the_sql_forms_cannot_enforce_what_the_constructor_rejects(conn) -> None:
    """The asymmetry, pinned rather than left to be discovered.

    ``scope_uri`` refuses a non-positive id, because a forged one could fake
    containment. The SQL forms cannot refuse anything — they concatenate
    whatever the columns hold — so a row with id 0 yields a scope URI the
    constructor would have rejected.

    Unreachable today: every id column is SERIAL, which starts at 1. That is
    the whole guarantee, and it lives in the DDL rather than in either of
    these functions, so it is written down here where someone adding a scope
    level or a non-SERIAL key will meet it.
    """
    expr = scope_sql(samples="s", labs="l")
    conn.execute("INSERT INTO labs VALUES (1, 1)")
    conn.execute("INSERT INTO samples VALUES (0, 1, 1)")  # sample id 0

    built = _scalar(conn, f"SELECT {expr} FROM samples s JOIN labs l ON l.id = s.lab_id")

    assert built == "instance://self/org/1/lab/1/project/1/sample/0"
    with pytest.raises(ValueError):
        scope_uri(org=1, lab=1, project=1, sample=0)
