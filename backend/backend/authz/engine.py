"""Capability-first authorization decision engine (access_model.md §5).

Dark in M0: wired into no route. The old ``permissions.py`` ladder still
serves every request. ``permit()`` is pure — no I/O, no DB — callers
resolve grants and policies up front and pass them in, which keeps the
decision deterministic and testable against the §9 worked examples.
"""

from dataclasses import dataclass, field
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
    # surveillance_relevant, owner_id, deletion_status, contains_pii… The
    # engine never enumerates them — policies declare what they read.
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Context:
    conditions: dict[str, Any] = field(default_factory=dict)


def _scope_contains(grant_scope: str, resource_scope: str) -> bool:
    """Hierarchical containment by URI prefix (§3.1: Instance > Org > Lab > Project > Sample).

    Exact match, or the resource scope sits strictly below the grant scope
    (segment boundary required so "org://acme" does not contain "org://acmecorp").
    """
    if grant_scope == resource_scope:
        return True
    return resource_scope.startswith(grant_scope.rstrip("/") + "/")


def _conditions_satisfied(conditions: dict[str, Any], context: Context) -> bool:
    """Every key in the grant's conditions must appear in context with equal value."""
    return all(context.conditions.get(k) == v for k, v in conditions.items())


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
        for grant in principal.grants
    )

    # Step 3 — policy-based ALLOW (independent path; do not collapse into step 2).
    policy_allow = evaluate_allow(principal, capability, resource, context, policies=policies)

    # Step 4 — either path suffices; Step 5 — default-deny.
    if grant_allow or policy_allow:
        return Decision.ALLOW
    return Decision.DENY
