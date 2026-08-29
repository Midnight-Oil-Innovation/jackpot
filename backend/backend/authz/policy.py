"""Policy-set evaluation for the authz engine (access_model.md §2.5, §5).

M0 scope: injectable policy lists only. DB-backed loading from the
``authz_policies`` table is deliberately NOT implemented — ``policies=None``
raises so nothing can accidentally reach for a live DB before the engine
is wired (M1+).

Each policy dict has keys: ``effect`` ("ALLOW"|"DENY"), ``capability``,
``scope_ref``, ``conditions``.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.authz.engine import Context, Principal, Resource

_DB_NOT_WIRED = "DB-backed policy loading not wired in M0 — inject policies= in tests"


def _matches(
    policy: dict[str, Any],
    capability: str,
    resource: "Resource",
    context: "Context",
) -> bool:
    from backend.authz.engine import _conditions_satisfied, _scope_contains

    return (
        policy["capability"] == capability
        and _scope_contains(policy["scope_ref"], resource.scope)
        and _conditions_satisfied(policy.get("conditions", {}), context)
    )


def evaluate_allow(
    principal: "Principal",
    capability: str,
    resource: "Resource",
    context: "Context",
    *,
    policies: list[dict] | None = None,
) -> bool:
    if policies is None:
        raise NotImplementedError(_DB_NOT_WIRED)
    return any(
        p["effect"] == "ALLOW" and _matches(p, capability, resource, context) for p in policies
    )


def evaluate_deny(
    principal: "Principal",
    capability: str,
    resource: "Resource",
    context: "Context",
    *,
    policies: list[dict] | None = None,
) -> bool:
    if policies is None:
        raise NotImplementedError(_DB_NOT_WIRED)
    return any(
        p["effect"] == "DENY" and _matches(p, capability, resource, context) for p in policies
    )
