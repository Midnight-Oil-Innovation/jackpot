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


PRINCIPAL_ID = {"principal_id": True}
"""Sentinel for a resource predicate comparing an attribute to the principal.

``{"owner_id": PRINCIPAL_ID}`` means "this row's owner_id equals the acting
principal's id" — the ownership rung of the legacy ladder. It cannot be a
grant: §5's mapping table calls ownership "a Sample-scope grant", but that
would mean issuing a row into the grants table on every sample creation and
deleting it on every transfer. As a policy it is one rule that stays true.
"""


def _attr_matches(predicate: dict[str, Any], resource: "Resource", principal: "Principal") -> bool:
    """Evaluate a policy's resource predicate against a row's attributes.

    Deliberately tiny and declarative — equality, ``{"in": [...]}``, and the
    principal sentinel. Anything richer (a lambda, an expression string) could
    not be compiled into the SQL half, and the two halves diverging is the
    failure M1 exists to prevent.
    """
    for attr, expected in predicate.items():
        actual = resource.attributes.get(attr)
        if expected == PRINCIPAL_ID:
            # Compare as strings: principal ids are strings, row ids are ints.
            if actual is None or str(actual) != str(principal.id):
                return False
        elif isinstance(expected, dict) and "in" in expected:
            if actual not in expected["in"]:
                return False
        elif actual != expected:
            return False
    return True


def _principal_holds(
    principal: "Principal", capability: str, resource: "Resource", context: "Context"
) -> bool:
    """Does the principal hold ``capability`` at a scope covering the resource?

    Used by a policy's ``requires_capability``: the surveillance rung reads
    "a surveillance-relevant row is detail-readable by someone holding
    sample:read_surveillance", which is a fact about the principal, not the
    row. The principal's grants do not vary per row, so the SQL compiler can
    settle it once and include or drop the whole term — the same treatment
    grant conditions already get.
    """
    from backend.authz.engine import _conditions_satisfied, _scope_contains

    return any(
        g.capability == capability
        and _scope_contains(g.scope_ref, resource.scope)
        and _conditions_satisfied(g.conditions, context)
        for g in principal.grants
    )


def _matches(
    policy: dict[str, Any],
    capability: str,
    resource: "Resource",
    context: "Context",
    principal: "Principal",
) -> bool:
    from backend.authz.engine import _conditions_satisfied, _scope_contains

    if policy["capability"] != capability:
        return False
    if not _scope_contains(policy["scope_ref"], resource.scope):
        return False
    if not _conditions_satisfied(policy.get("conditions", {}), context):
        return False
    if not _attr_matches(policy.get("resource", {}), resource, principal):
        return False
    required = policy.get("requires_capability")
    return not required or _principal_holds(principal, required, resource, context)


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
        p["effect"] == "ALLOW" and _matches(p, capability, resource, context, principal)
        for p in policies
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
        p["effect"] == "DENY" and _matches(p, capability, resource, context, principal)
        for p in policies
    )


# ── The legacy ladder's permissive rungs, as policies (§2.5, §5) ─────────
#
# permissions.py._base_access mixes structural rungs (ownership, membership)
# with attribute rungs (sharing level, surveillance relevance). The structural
# ones became scope-grants at reseed; these are the rest. They are fixed
# today, not operator-configurable, so they live here as constants — M3
# replaces this list with DB-backed loading from authz_policies.
#
# Every entry is scoped at the instance root because these rules are
# deployment-wide: what makes them selective is the resource predicate, not
# the scope.

_ROOT = "instance://self"

LADDER_POLICIES: list[dict[str, Any]] = [
    # PUBLIC is readable by anyone — §5 names this as THE example of an ALLOW
    # policy granting a path the scope-grants alone would not.
    {
        "effect": "ALLOW",
        "capability": "sample:read",
        "scope_ref": _ROOT,
        "resource": {"sharing_level": "PUBLIC"},
    },
    {
        "effect": "ALLOW",
        "capability": "sample:read_detail",
        "scope_ref": _ROOT,
        "resource": {"sharing_level": "PUBLIC"},
    },
    # DISCOVERABLE is list-visible only. can_see_sample allows it;
    # can_access_sample explicitly does not ("DISCOVERABLE alone is NOT
    # sufficient — detail requires an approved request"), so there is
    # deliberately no sample:read_detail twin here.
    {
        "effect": "ALLOW",
        "capability": "sample:read",
        "scope_ref": _ROOT,
        "resource": {"sharing_level": "DISCOVERABLE"},
    },
    # Surveillance oversight: the legacy rung was `is_data_analyst AND
    # surveillance_relevant`. The flag becomes a held capability, so the rule
    # is "surveillance-relevant rows are readable by a sample:read_surveillance
    # holder" — the row half is the resource predicate, the principal half is
    # requires_capability.
    {
        "effect": "ALLOW",
        "capability": "sample:read",
        "scope_ref": _ROOT,
        "resource": {"surveillance_relevant": True},
        "requires_capability": "sample:read_surveillance",
    },
    {
        "effect": "ALLOW",
        "capability": "sample:read_detail",
        "scope_ref": _ROOT,
        "resource": {"surveillance_relevant": True},
        "requires_capability": "sample:read_surveillance",
    },
    # Ownership. §5's mapping table calls this "a Sample-scope grant", but
    # that would mean writing a grant row on every sample creation and
    # deleting it on every transfer; as a policy it is one rule that stays
    # true. Note this is the ONLY rung where the row is compared against the
    # acting principal rather than against a constant.
    {
        "effect": "ALLOW",
        "capability": "sample:read",
        "scope_ref": _ROOT,
        "resource": {"owner_id": PRINCIPAL_ID},
    },
    {
        "effect": "ALLOW",
        "capability": "sample:read_detail",
        "scope_ref": _ROOT,
        "resource": {"owner_id": PRINCIPAL_ID},
    },
    # Asking for access to a DISCOVERABLE sample. This one cannot be a grant
    # and cannot come from a preset: the requester is, by definition, not a
    # member of the sample's lab — that is why they are asking — so a
    # lab-scoped grant would never contain the sample's scope, and an
    # instance-scoped one issued to everybody is the same thing as no check.
    # The rule is a fact about the row ("this sample invites requests"), which
    # is what an attribute-policy is for. Mirrors the sharing_level test the
    # route performed in-line before M2-B2, and is now the only definition of
    # "requestable" — the router's REQUESTABLE_SHARING_LEVELS set is gone.
    {
        "effect": "ALLOW",
        "capability": "access:request",
        "scope_ref": _ROOT,
        "resource": {"sharing_level": "DISCOVERABLE"},
    },
]
