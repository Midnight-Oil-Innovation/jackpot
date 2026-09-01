"""SQL list-filtering companion to ``permit()`` (access_model.md §5.2).

Dark in M1: wired into no route. ``visibility_sql_clause()`` is a pure
compiler — it takes a principal and a capability and produces a
parameterized WHERE fragment (``:name`` bind convention, ready for
``sqlalchemy.text()``) that evaluates TRUE for exactly the rows
``permit()`` would ALLOW. It executes nothing itself.

The fragment mirrors permit()'s decision shape over the row's scope
expression (``scope.scope_sql(...)``):

    NOT (any DENY policy covers the row)          -- strict deny-wins
    AND (any grant or ALLOW policy covers the row) -- either path suffices
                                                   -- no terms → default-deny

Grant/policy conditions are compile-time facts (they compare against the
request context, not the row), so condition-unsatisfied grants and
policies are simply dropped from the fragment — identical to permit()
skipping them per row.
"""

import re
from datetime import UTC, datetime

from backend.authz.engine import (
    Context,
    Principal,
    Resource,
    _conditions_satisfied,
    _unexpired,
)
from backend.authz.policy import _DB_NOT_WIRED, PRINCIPAL_ID, _principal_holds
from backend.authz.scope import (
    is_canonical_scope_sql,
    lab_scope_sql,
    project_scope_sql,
    scope_sql,
)

_CAPABILITY_RE = re.compile(r"^[a-z_]+:[a-z_]+$")


def _like_prefix(scope_ref: str) -> str:
    """LIKE pattern matching strict descendants of ``scope_ref`` (segment boundary)."""
    escaped = scope_ref.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return escaped.rstrip("/") + "/%"


_COLUMN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$")


def _attr_sql(
    predicate: dict,
    columns: dict[str, str],
    principal_id: str,
    prefix: str,
    params: dict,
) -> str:
    """Compile a policy's resource predicate into SQL.

    ``columns`` maps attribute name -> qualified column ("s.sharing_level").
    An attribute with no column mapping RAISES rather than being skipped: a
    dropped term silently widens an ALLOW policy and — worse — would neuter a
    DENY, which is the one thing deny-wins must never permit (§5.4).
    """
    terms = []
    for i, (attr, expected) in enumerate(sorted(predicate.items())):
        column = columns.get(attr)
        if column is None:
            raise ValueError(
                f"policy reads resource attribute {attr!r} with no column mapping; "
                f"known: {sorted(columns)}"
            )
        if not _COLUMN_RE.match(column):
            raise ValueError(f"column for {attr!r} must be table.column, got {column!r}")
        key = f"{prefix}_{i}"
        if expected == PRINCIPAL_ID:
            params[key] = principal_id
            terms.append(f"CAST({column} AS TEXT) = :{key}")
        elif isinstance(expected, dict) and "in" in expected:
            names = []
            for j, v in enumerate(expected["in"]):
                params[f"{key}_{j}"] = v
                names.append(f":{key}_{j}")
            terms.append(f"{column} IN ({', '.join(names)})")
        else:
            params[key] = expected
            terms.append(f"{column} = :{key}")
    return " AND ".join(terms) if terms else "1 = 1"


def _scope_term(column: str, scope_ref: str, param: str, params: dict) -> str:
    """SQL mirroring engine._scope_contains: exact match or descendant-by-prefix."""
    params[param] = scope_ref
    params[f"{param}_pre"] = _like_prefix(scope_ref)
    return f"({column} = :{param} OR {column} LIKE :{param}_pre ESCAPE '\\')"


def visibility_sql_clause(
    principal: Principal,
    capability: str,
    scope_expr: str,
    *,
    context: Context | None = None,
    policies: list[dict] | None = None,
    attribute_columns: dict[str, str] | None = None,
) -> tuple[str, dict]:
    """Compile a WHERE fragment behaviorally identical to per-row permit().

    Returns ``(fragment, bind_params)`` for use with ``text()``. A row
    satisfies the fragment iff ``permit(principal, capability,
    Resource(scope=row.scope), context, policies=policies)`` is ALLOW.

    ``scope_expr`` is the SQL computing each row's scope URI — build it with
    ``scope.scope_sql(samples=..., labs=...)``. A sample's scope is derived
    from the lineage columns the query already joins rather than stored
    (ADR 0015), so there is no scope column to name.

    Raises ``ValueError`` on a malformed capability string (must be
    ``domain:action`` per §4) or a scope expression this module did not
    generate. Raises ``NotImplementedError`` when ``policies`` is None —
    DB-backed policy loading is not wired in M1; inject the policy list, as
    permit() does.
    """
    if not _CAPABILITY_RE.match(capability):
        raise ValueError(f"malformed capability string: {capability!r} (expected domain:action)")
    if not is_canonical_scope_sql(scope_expr):
        # The expression is interpolated into the fragment, so it is only ever
        # accepted when byte-identical to scope_sql() output — see
        # scope.is_canonical_scope_sql for why the caller is not trusted.
        raise ValueError(f"scope_expr must be scope.scope_sql(...) output, got {scope_expr!r}")
    if policies is None:
        raise NotImplementedError(_DB_NOT_WIRED)
    context = context or Context()

    column = scope_expr
    params: dict = {}

    def _live(conditions: dict) -> bool:
        # The engine's own predicate, not a copy of it. This was a duplicate
        # of _conditions_satisfied's body until M3 added the {"not": ...}
        # form; two copies of the condition semantics is precisely how the
        # per-row and SQL halves drift apart, which is the failure the M1
        # equivalence suite exists to catch. Call the one definition.
        return _conditions_satisfied(conditions, context)

    columns = attribute_columns or {}

    def _policy_term(pol: dict, prefix: str, index: int) -> str | None:
        """One policy as SQL, or None when it cannot apply to any row.

        Compile-time facts are settled here exactly as permit() settles them
        per row: an unsatisfied ``conditions`` or an unheld
        ``requires_capability`` removes the policy entirely, because neither
        varies row to row.
        """
        if not _live(pol.get("conditions", {})):
            return None
        required = pol.get("requires_capability")
        if required and not _principal_holds(
            principal, required, Resource(scope=pol["scope_ref"]), context
        ):
            return None
        scope_sql_term = _scope_term(column, pol["scope_ref"], f"{prefix}{index}", params)
        attr = pol.get("resource")
        if not attr:
            return scope_sql_term
        return (
            f"({scope_sql_term} AND "
            f"{_attr_sql(attr, columns, principal.id, f'{prefix}{index}_a', params)})"
        )

    allow_terms = [
        _scope_term(column, g.scope_ref, f"vis_g{i}", params)
        for i, g in enumerate(principal.grants)
        if g.capability == capability and _live(g.conditions) and _unexpired(g, context)
    ]
    allow_terms += [
        term
        for i, p in enumerate(policies)
        if p["effect"] == "ALLOW" and p["capability"] == capability
        for term in [_policy_term(p, "vis_pa", i)]
        if term is not None
    ]
    deny_terms = [
        term
        for i, p in enumerate(policies)
        if p["effect"] == "DENY" and p["capability"] == capability
        for term in [_policy_term(p, "vis_pd", i)]
        if term is not None
    ]

    allow_sql = " OR ".join(allow_terms) if allow_terms else "1 = 0"  # default-deny
    if deny_terms:
        return f"(NOT ({' OR '.join(deny_terms)}) AND ({allow_sql}))", params
    return f"({allow_sql})", params


# ── The production shape (M2-B7) ─────────────────────────────────────────


def sample_list_clause(
    principal: Principal,
    capability: str = "sample:read",
    *,
    samples: str = "s",
    labs: str = "l",
    context: Context | None = None,
) -> tuple[str, dict]:
    """The WHERE fragment every sample-rooted list endpoint uses.

    Six lists across five routers filter on the same question — which sample
    rows may this principal see — and the answer has three moving parts that
    must match the row-wise guard exactly: the scope expression, the policy
    set, and the attribute-column mapping. Assembling them at each call site
    is how the two halves drift, and a list that drifts *wider* leaks rows
    with no error and no audit entry. So it is assembled once, here.

    The caller supplies its own table aliases and must join
    ``samples JOIN labs ON labs.id = samples.lab_id`` — the org segment of the
    scope path comes from ``labs.organization_id``, and a sample's scope is
    derived rather than stored (ADR 0015).

    Not I/O: the principal is loaded by the caller, which keeps this module a
    pure compiler.
    """
    from backend.authz.policy import LADDER_POLICIES
    from backend.authz.principal import SAMPLE_ATTRIBUTE_COLUMNS

    columns = {
        attr: column.replace("s.", f"{samples}.", 1)
        for attr, column in SAMPLE_ATTRIBUTE_COLUMNS.items()
    }
    return visibility_sql_clause(
        principal,
        capability,
        scope_sql(samples=samples, labs=labs),
        context=context or Context(conditions={}, now=datetime.now(UTC)),
        policies=LADDER_POLICIES,
        attribute_columns=columns,
    )


def lab_list_clause(
    principal: Principal,
    capability: str,
    *,
    labs: str = "l",
    context: Context | None = None,
) -> tuple[str, dict]:
    """List filter for rows that live at LAB level and have no sample.

    No attribute columns and no policies: every entry in ``LADDER_POLICIES``
    reads a *sample* attribute, so passing them here would compile predicates
    against columns that do not exist on the row. Rows at this level are
    decided by structural grants alone, which is what ``permit()`` does for
    them too.
    """
    return visibility_sql_clause(
        principal,
        capability,
        lab_scope_sql(labs=labs),
        context=context or Context(conditions={}, now=datetime.now(UTC)),
        policies=[],
    )


def project_list_clause(
    principal: Principal,
    capability: str,
    *,
    labs: str = "l",
    rows: str = "pr",
    project_id_column: str = "project_id",
    context: Context | None = None,
) -> tuple[str, dict]:
    """List filter for rows that live at PROJECT level — pipeline runs.

    Same reasoning as :func:`lab_list_clause` on policies. A lab-scoped grant
    still covers these rows by containment, so scoping the filter at project
    level narrows nothing for an ordinary lab member.
    """
    return visibility_sql_clause(
        principal,
        capability,
        project_scope_sql(labs=labs, rows=rows, project_id_column=project_id_column),
        context=context or Context(conditions={}, now=datetime.now(UTC)),
        policies=[],
    )
