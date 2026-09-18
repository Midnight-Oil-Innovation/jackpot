"""Capability-first authorization decision engine (access_model.md §5).

Dark in M0: wired into no route. The old ``permissions.py`` ladder still
serves every request. ``permit()`` is pure — no I/O, no DB — callers
resolve grants and policies up front and pass them in, which keeps the
decision deterministic and testable against the §9 worked examples.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from backend.authz.policy import evaluate_allow, evaluate_deny


class PrincipalKind(str, Enum):
    HUMAN = "HUMAN"
    PEER_INSTANCE = "PEER_INSTANCE"
    SERVICE = "SERVICE"


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass
class CapabilityGrant:
    capability: str  # domain:action string from §4 catalog, e.g. "sample:read_detail"
    scope_ref: str  # scope URI, e.g. "instance://acme" or "org://acme/path-lab"
    conditions: dict[str, Any] = field(default_factory=dict)
    source: str = ""  # "role:lab_member", "direct", "federation:push", etc.
    # Wall-clock expiry (§5: approved access requests are "time-bounded").
    # None means the grant does not expire. Checked against ``context.now``,
    # which is a compile-time fact — expiry does not vary per row — so the SQL
    # compiler drops an expired grant exactly as permit() skips one.
    not_after: datetime | None = None


@dataclass
class Principal:
    kind: PrincipalKind
    id: str  # stable identifier (user UUID, instance FQDN, service name)
    on_behalf_of: str | None  # OBO chain, None if acting for self
    grants: list[CapabilityGrant] = field(default_factory=list)
    # NO roles field — roles are presets that pre-populate grants, not engine state


@dataclass
class Resource:
    scope: str  # canonical scope URI locating this resource (§3.1.1)
    # Attributes the attribute-policies read (§2.4): sharing_level,
    # surveillance_relevant, owner_id, deletion_status, pii_scan_status… The
    # engine never enumerates them — policies declare what they read.
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Context:
    conditions: dict[str, Any] = field(default_factory=dict)
    # Decision time. Required to evaluate a grant's ``not_after``; leaving it
    # None means "no time known", and a time-bounded grant is then refused
    # rather than assumed live — a caller that forgets to pass a clock must
    # lose access, never keep expired access.
    now: datetime | None = None


def _scope_contains(grant_scope: str, resource_scope: str) -> bool:
    """Hierarchical containment by URI prefix (§3.1: Instance > Org > Lab > Project > Sample).

    Exact match, or the resource scope sits strictly below the grant scope
    (segment boundary required so "org://acme" does not contain "org://acmecorp").
    """
    if grant_scope == resource_scope:
        return True
    return resource_scope.startswith(grant_scope.rstrip("/") + "/")


def _conditions_satisfied(conditions: dict[str, Any], context: Context) -> bool:
    """Every key must appear in context with the required value.

    Two forms, mirroring the resource-predicate language in ``policy.py``:

    * ``{"k": v}`` — equality. The default.
    * ``{"k": {"not": v}}`` — the context value is anything but ``v``,
      **including absent**.

    The negation form exists because §6.2-1b's separation-of-duties DENY reads
    "unless a Platform Admin explicitly self-approves". Absent must mean the
    DENY applies: with equality only, ``{"platform_admin_self_approve": False}``
    would not match a context that never set the key, so the DENY would
    silently not fire and the rule would fail OPEN. A caller forgetting to
    pass a flag must lose the escape hatch, never gain it.

    Deliberately still tiny and declarative — ``visibility.py`` compiles the
    same dict into SQL, and a form that cannot be compiled there would split
    the two halves apart (the failure M1 exists to prevent).
    """
    for key, expected in conditions.items():
        actual = context.conditions.get(key)
        if isinstance(expected, dict) and "not" in expected:
            if actual == expected["not"]:
                return False
        elif actual != expected:
            return False
    return True


def _unexpired(grant: "CapabilityGrant", context: Context) -> bool:
    """False once a time-bounded grant has lapsed.

    Deliberately fails closed on a missing clock: `not_after` set with
    `context.now` unset means the decision cannot be made safely, and the
    safe answer for an expiring grant is no.
    """
    if grant.not_after is None:
        return True
    return context.now is not None and context.now < grant.not_after


def permit(
    principal: Principal,
    capability: str,
    resource: Resource,
    context: Context,
    *,
    policies: list[dict] | None = None,
) -> Decision:
    """Pure authorization decision. Strict deny-wins; default-deny (§5.1, §5.4)."""
    # Step 1 — deny-wins: any matching DENY policy ends it.
    if evaluate_deny(principal, capability, resource, context, policies=policies):
        return Decision.DENY

    # Step 2 — grant-based ALLOW (structural check).
    grant_allow = any(
        grant.capability == capability
        and _scope_contains(grant.scope_ref, resource.scope)
        and _conditions_satisfied(grant.conditions, context)
        and _unexpired(grant, context)
        for grant in principal.grants
    )

    # Step 3 — policy-based ALLOW (independent path; do not collapse into step 2).
    policy_allow = evaluate_allow(principal, capability, resource, context, policies=policies)

    # Step 4 — either path suffices; Step 5 — default-deny.
    if grant_allow or policy_allow:
        return Decision.ALLOW
    return Decision.DENY
