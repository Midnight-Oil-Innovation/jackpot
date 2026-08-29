"""SQL list-filtering companion to ``permit()`` (access_model.md §5.2).

Dark in M1: wired into no route. ``visibility_sql_clause()`` is a pure
compiler — it takes a principal and a capability and produces a
parameterized WHERE fragment (``:name`` bind convention, ready for
``sqlalchemy.text()``) that evaluates TRUE for exactly the rows
``permit()`` would ALLOW. It executes nothing itself.

The fragment mirrors permit()'s decision shape over the row's scope
column (``<alias>.scope``):

    NOT (any DENY policy covers the row)          -- strict deny-wins
    AND (any grant or ALLOW policy covers the row) -- either path suffices
                                                   -- no terms → default-deny

Grant/policy conditions are compile-time facts (they compare against the
request context, not the row), so condition-unsatisfied grants and
policies are simply dropped from the fragment — identical to permit()
skipping them per row.
"""

import re

from backend.authz.engine import Context, Principal
from backend.authz.policy import _DB_NOT_WIRED

_CAPABILITY_RE = re.compile(r"^[a-z_]+:[a-z_]+$")


def _like_prefix(scope_ref: str) -> str:
    """LIKE pattern matching strict descendants of ``scope_ref`` (segment boundary)."""
    escaped = scope_ref.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return escaped.rstrip("/") + "/%"


def _scope_term(column: str, scope_ref: str, param: str, params: dict) -> str:
    """SQL mirroring engine._scope_contains: exact match or descendant-by-prefix."""
    params[param] = scope_ref
    params[f"{param}_pre"] = _like_prefix(scope_ref)
    return f"({column} = :{param} OR {column} LIKE :{param}_pre ESCAPE '\\')"


def visibility_sql_clause(
    principal: Principal,
    capability: str,
    alias: str,
    *,
    context: Context | None = None,
    policies: list[dict] | None = None,
) -> tuple[str, dict]:
    """Compile a WHERE fragment behaviorally identical to per-row permit().

    Returns ``(fragment, bind_params)`` for use with ``text()``. A row
    satisfies the fragment iff ``permit(principal, capability,
    Resource(scope=row.scope), context, policies=policies)`` is ALLOW.

    Raises ``ValueError`` on a malformed capability string (must be
    ``domain:action`` per §4) or a non-identifier alias. Raises
    ``NotImplementedError`` when ``policies`` is None — DB-backed policy
    loading is not wired in M1; inject the policy list, as permit() does.
    """
    if not _CAPABILITY_RE.match(capability):
        raise ValueError(f"malformed capability string: {capability!r} (expected domain:action)")
    if not alias.isidentifier():
        raise ValueError(f"alias must be a SQL identifier, got {alias!r}")
    if policies is None:
        raise NotImplementedError(_DB_NOT_WIRED)
    context = context or Context()

    column = f"{alias}.scope"
    params: dict = {}

    def _live(conditions: dict) -> bool:
        return all(context.conditions.get(k) == v for k, v in conditions.items())

    allow_terms = [
        _scope_term(column, g.scope_ref, f"vis_g{i}", params)
        for i, g in enumerate(principal.grants)
        if g.capability == capability and _live(g.conditions)
    ]
    allow_terms += [
        _scope_term(column, p["scope_ref"], f"vis_pa{i}", params)
        for i, p in enumerate(policies)
        if p["effect"] == "ALLOW"
        and p["capability"] == capability
        and _live(p.get("conditions", {}))
    ]
    deny_terms = [
        _scope_term(column, p["scope_ref"], f"vis_pd{i}", params)
        for i, p in enumerate(policies)
        if p["effect"] == "DENY"
        and p["capability"] == capability
        and _live(p.get("conditions", {}))
    ]

    allow_sql = " OR ".join(allow_terms) if allow_terms else "1 = 0"  # default-deny
    if deny_terms:
        return f"(NOT ({' OR '.join(deny_terms)}) AND ({allow_sql}))", params
    return f"({allow_sql})", params
