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


def ancestor_scopes(scope: str) -> list[str]:
    """Every scope that contains ``scope``, itself included (§3.1.1).

    ``instance://self/org/3/lab/7`` yields the three scopes a grant could be
    written at to reach it: the root, the org, and the lab.

    This is ``engine._scope_contains`` turned inside out. Containment by
    prefix has a dual — a path has a bounded, enumerable set of ancestors,
    five levels at most — and the dual is what lets a "who holds this" query
    match on equality instead of a pattern. That matters because the pattern
    form reads its pattern from the grant row: a stored ``scope_ref``
    containing ``%`` or ``_`` becomes a wildcard grant unless every metacharacter
    is escaped, and an authorization query that widens when it should not is
    the wrong place to be one ``REPLACE`` short. Equality cannot widen.

    The trailing-slash rstrip mirrors ``_scope_contains``, which strips before
    comparing; a caller that stored ``instance://self/`` still matches.
    """
    trimmed = scope.rstrip("/")
    # The root test needs the same segment boundary the containment test uses.
    # A bare `startswith(ROOT)` admits `instance://selfish`, which would both
    # claim the root as an ancestor — disagreeing with `_scope_contains` — and
    # split into a fabricated `instance://self/ish/org`.
    if not trimmed.startswith(f"{ROOT}/"):
        return [trimmed]
    # Split AFTER the separator rather than stripping it: an empty segment is a
    # real segment. `.strip("/")` collapsed `instance://self//org/3` into
    # `instance://self/org/3` — an ancestor `_scope_contains` does not agree
    # with, and therefore a grant the SQL would honour and the engine would
    # refuse. Third instance of this shape in one file's history; the pattern
    # is always "normalize on the way in and reconstruct something wider".
    segments = trimmed[len(ROOT) + 1 :].split("/")
    scopes = [ROOT]
    # Segments run level/id, level/id — step in pairs so a partial trailing
    # segment contributes nothing rather than half a level.
    for i in range(0, len(segments) - 1, 2):
        scopes.append(f"{scopes[-1]}/{segments[i]}/{segments[i + 1]}")
    # `_scope_contains` is reflexive and the pair loop is not: a trailing
    # half-level (`.../org`) stops the loop short of the scope itself, so a
    # grant written at that exact scope would not find its own resource. The
    # non-ROOT branch above already returns `[trimmed]` for this reason;
    # without this the two branches disagree about reflexivity.
    if scopes[-1] != trimmed:
        scopes.append(trimmed)
    return scopes


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
    _check_alias("samples", samples)
    _check_alias("labs", labs)
    return (
        f"('{ROOT}/org/' || {labs}.organization_id"
        f" || '/lab/' || {samples}.lab_id"
        f" || '/project/' || {samples}.project_id"
        f" || '/sample/' || {samples}.id)"
    )


def lab_scope_sql(*, labs: str) -> str:
    """SQL expression computing a LAB row's canonical scope URI (M2-B7).

    Only the ``labs`` alias is needed: once a query joins ``labs``, that table
    carries both segments of the path. Used by lists whose rows live at lab
    level and have no sample — import sessions, for one — where
    :func:`scope_sql` would name a sample that does not exist.
    """
    _check_alias("labs", labs)
    return f"('{ROOT}/org/' || {labs}.organization_id || '/lab/' || {labs}.id)"


PROJECT_ID_COLUMNS = ("project_id", "id")
"""Where a project's id lives on the row being scoped.

``project_id`` for a table that references a project (pipeline runs); ``id``
when the row IS the project. Enumerated rather than free-form because
:func:`is_canonical_scope_sql` re-derives every accepted expression from this
list, and an arbitrary column name would be an injection surface.
"""


def project_scope_sql(*, labs: str, rows: str, project_id_column: str = "project_id") -> str:
    """SQL expression computing a PROJECT-level row's scope URI (M2-B7).

    ``rows`` is the alias of the table being scoped; the lab and org segments
    come from ``labs``, which the caller joins on that table's ``lab_id``.

    ``project_id_column`` distinguishes the two shapes: a row that *references*
    a project carries ``project_id`` (pipeline runs), while the ``projects``
    table itself carries ``id``. Getting this wrong is a loud
    ``UndefinedColumn`` rather than a silent mis-scope, but only because the
    column is interpolated — which is why the value is restricted to
    :data:`PROJECT_ID_COLUMNS`.
    """
    _check_alias("labs", labs)
    _check_alias("rows", rows)
    if project_id_column not in PROJECT_ID_COLUMNS:
        raise ValueError(
            f"project_id_column must be one of {PROJECT_ID_COLUMNS}, got {project_id_column!r}"
        )
    return (
        f"('{ROOT}/org/' || {labs}.organization_id"
        f" || '/lab/' || {labs}.id"
        f" || '/project/' || {rows}.{project_id_column})"
    )


def _check_alias(name: str, alias: str) -> None:
    if not _ALIAS_RE.match(alias):
        raise ValueError(f"{name} alias must be a SQL identifier, got {alias!r}")


def is_canonical_scope_sql(expr: str) -> bool:
    """True when ``expr`` is exactly what one of the scope-SQL builders produces.

    ``visibility_sql_clause`` interpolates the expression into a WHERE
    fragment, so it is SQL the caller supplies rather than user input — but
    "not user input today" is how injection sinks are born. Rather than trust
    the caller, the expression is re-derived from the aliases it names and
    compared: anything that is not byte-identical to a generated expression is
    rejected, which admits no room for an appended clause.

    All three levels are accepted (M2-B7). Re-deriving each candidate and
    comparing bytes means adding a level cannot accidentally widen what this
    admits — a regex loosened to cover three shapes could.
    """
    aliases = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\.", expr)
    if not aliases:
        return False
    candidates = []
    for a in set(aliases):
        candidates.append(lab_scope_sql(labs=a))
        for b in set(aliases):
            candidates.append(scope_sql(labs=a, samples=b))
            for column in PROJECT_ID_COLUMNS:
                candidates.append(project_scope_sql(labs=a, rows=b, project_id_column=column))
    return expr in candidates
