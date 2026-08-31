"""Canonical scope-URI construction (access_model.md §3.1.1, ADR 0015).

Every scope reference — in a grant, in a policy, and for a resource — is a
path under one root. There is exactly one root per deployment, spelled
``instance://self``: a scope ref is only ever interpreted inside the instance
that stores it, and federation peers are principals rather than branches of
the tree (§3.3).

    instance://self
    instance://self/org/3
    instance://self/org/3/lab/7
    instance://self/org/3/lab/7/project/12
    instance://self/org/3/lab/7/project/12/sample/55

Containment is unchanged by this module: ``engine._scope_contains`` matches on
equality or a prefix at a segment boundary, which is exactly what a single
rooted path makes correct. Building the strings in one place is what keeps the
prefix relation meaningful — the four hand-written shapes that preceded this
(``instance://field-laptop/org-x/…``, ``org://acme/lab-1/…``,
``instance://self``, ``lab://7``) could not contain one another at all.
"""

import re

ROOT = "instance://self"

# Ordered outermost-first; a level may only be given when every level above it
# is also given, which is what makes the resulting path a real ancestor chain.
_LEVELS = ("org", "lab", "project", "sample")


def scope_uri(
    *,
    org: int | None = None,
    lab: int | None = None,
    project: int | None = None,
    sample: int | None = None,
) -> str:
    """Build the canonical scope URI for a level of the tree.

    ``scope_uri()`` is the instance root. Each deeper level requires its
    ancestors: ``scope_uri(lab=7)`` raises, because a lab's path runs through
    its org and a grant written without it would not be contained by any
    org-scoped grant.

    Ids must be positive ``int`` — the database's own SERIAL keys. Anything
    else is rejected rather than coerced: a string id could carry a ``/`` and
    silently forge containment (``org/3/lab/7`` from ``org="3/lab/7"``), and
    ``bool`` is an ``int`` subclass that would render as ``org/True``.
    """
    parts = [ROOT]
    missing: str | None = None
    for level, value in zip(_LEVELS, (org, lab, project, sample), strict=True):
        if value is None:
            missing = missing or level
            continue
        if missing is not None:
            raise ValueError(
                f"{level}={value} given without {missing} — a scope path must "
                f"name every level above it (§3.1.1)"
            )
        if type(value) is not int:
            raise TypeError(f"{level} id must be int, got {type(value).__name__}: {value!r}")
        if value < 1:
            raise ValueError(f"{level} id must be a positive database id, got {value}")
        parts.append(f"{level}/{value}")
    return "/".join(parts)


# ── SQL form (M2-PRE-2) ──────────────────────────────────────────────────
#
# A sample's scope is DERIVED, not stored (ADR 0015): it is computed from the
# lineage columns the list query already joins, so ``samples`` needs no scope
# column, no backfill, and no trigger that could drift. ``||`` is the string
# concatenation operator in both PostgreSQL and SQLite, so the same expression
# serves production and the in-process test harness.

_ALIAS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def scope_sql(*, samples: str, labs: str) -> str:
    """SQL expression computing a sample row's canonical scope URI.

    ``samples`` and ``labs`` are the query's table aliases; the caller is
    responsible for the ``samples JOIN labs ON labs.id = samples.lab_id`` that
    puts ``organization_id`` in reach.
    """
    for name, alias in (("samples", samples), ("labs", labs)):
        if not _ALIAS_RE.match(alias):
            raise ValueError(f"{name} alias must be a SQL identifier, got {alias!r}")
    return (
        f"('{ROOT}/org/' || {labs}.organization_id"
        f" || '/lab/' || {samples}.lab_id"
        f" || '/project/' || {samples}.project_id"
        f" || '/sample/' || {samples}.id)"
    )


def is_canonical_scope_sql(expr: str) -> bool:
    """True when ``expr`` is exactly what :func:`scope_sql` produces.

    ``visibility_sql_clause`` interpolates the expression into a WHERE
    fragment, so it is SQL the caller supplies rather than user input — but
    "not user input today" is how injection sinks are born. Rather than trust
    the caller, the expression is re-derived from the aliases it names and
    compared: anything that is not byte-identical to a generated expression is
    rejected, which admits no room for an appended clause.
    """
    m = re.match(
        r"^\('[^']*/org/' \|\| ([A-Za-z_][A-Za-z0-9_]*)\.organization_id"
        r" \|\| '/lab/' \|\| ([A-Za-z_][A-Za-z0-9_]*)\.lab_id",
        expr,
    )
    if not m:
        return False
    return expr == scope_sql(labs=m.group(1), samples=m.group(2))
