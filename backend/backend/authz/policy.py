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
        elif isinstance(expected, dict) and "not" in expected:
            # Absent counts as "not equal", deliberately. Used by
            # sovereignty.no_federate_deleting, where the attribute missing
            # means the caller did not establish the sample is ACTIVE — and
            # the safe answer for an export is no. Note this is the opposite
            # of what the same form would mean on a permissive rule, which is
            # why the DENY invariant in DELETION_POLICIES exists.
            if actual == expected["not"]:
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
    # M2-DROP-PRE slice 2. _require_lab_tie's three rungs were "platform
    # admin, owner, or lab member". Admin and member become grants; ownership
    # cannot, for the reason stated on the two rungs above — it would mean a
    # grant row per sample. Without this the owner of a sample in a lab they
    # have since left would lose the report, which is a narrowing nobody
    # asked for and which no test would have caught, because the presets
    # cover every owner who is still a member.
    {
        "effect": "ALLOW",
        "capability": "deletion:read_report",
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
    # A BYOP pipeline's registrant may manage what they registered (M2-B3).
    # Same shape as sample ownership above and for the same reason: as a grant
    # it would need a row written per registration and deleted per transfer.
    #
    # It also settles what a lab-less pipeline is. `byop_pipelines.owner_lab_id`
    # is nullable because `sharing_scope` admits 'private' — a pipeline that
    # belongs to a person, not a lab. Such a row has no lab scope, so the only
    # thing that can authorize it is this rung or an instance-wide grant, which
    # is exactly right. The column stays nullable; the policy is what makes
    # that safe rather than a hole.
    {
        "effect": "ALLOW",
        "capability": "pipeline:register_custom",
        "scope_ref": _ROOT,
        "resource": {"registered_by_user_id": PRINCIPAL_ID},
    },
]


# ── Deletion governance (§6.2-1b, M3) ────────────────────────────────────
#
# The first DENY policies in the set, which changes an invariant guards.py
# used to rely on: LADDER_POLICIES could only ever WIDEN, so passing it on
# every call — including lab- and instance-scoped ones carrying no resource
# attributes — was free. A DENY inverts that. "A resource carrying no
# attributes matches nothing" is true for an equality predicate and FALSE for
# a negation one, because absent != "ACTIVE".
#
# Hence the rule this family follows: **a DENY policy here may only read
# attributes that SAMPLE_ATTRIBUTE_COLUMNS loads, and may only be keyed to a
# capability whose routes resolve a Sample resource.** deletion:approve does
# (samples.py names sample_id). submission:approve deliberately does NOT get a
# policy: it is checked once at Lab scope while §6.2-2's rule is per-sample
# across the submission's whole set, so it stays the set-level 422 in
# submissions.py — see docs/endpoint_capability_map.md.

DELETION_POLICIES: list[dict[str, Any]] = [
    {
        # §6.2-1b. The approver of a deletion must differ from the requester.
        # A DENY, not a missing grant: it subtracts a path that a legitimate
        # deletion:approve grant would otherwise permit, which is exactly what
        # "intentional friction" means here.
        "id": "deletion.separation_of_duties",
        "effect": "DENY",
        "capability": "deletion:approve",
        "scope_ref": _ROOT,
        "resource": {"deletion_requested_by_user_id": PRINCIPAL_ID},
        # The audited platform-admin escape. {"not": True} rather than False
        # because absent must mean the DENY APPLIES — a route that forgets to
        # pass the flag must lose the escape hatch, never gain it. With plain
        # equality this rule would fail open on every caller that never set
        # the key, which is every caller but one.
        "conditions": {"platform_admin_self_approve": {"not": True}},
    },
]

# ── Sovereignty (§6.2-3, M3-FEDERATION-DELETION-GUARD) ───────────────────

SOVEREIGNTY_POLICIES: list[dict[str, Any]] = [
    {
        # A sample in the deletion lifecycle must never leave via federation,
        # regardless of any sharing agreement. This is §5.4's
        # unconditionally-unoverridable property made concrete: an agreement
        # produces a structural ALLOW for the peer principal, and deny-wins
        # beats it here and nowhere else.
        #
        # Deferred out of M3 because federation:push had no call site —
        # it existed only as an example string in an engine.py comment.
        # M4-B's FederationPushJob.may_push_sample is that call site.
        #
        # Not gated on sovereignty_mode. A non-ACTIVE sample should never
        # federate out whether or not sovereignty policy is on: tombstone
        # propagation (B-CARE-4) is a push of the deletion EVENT, and closing
        # the data path is what forces those to stay separate channels.
        "id": "sovereignty.no_federate_deleting",
        "effect": "DENY",
        "capability": "federation:push",
        "scope_ref": _ROOT,
        # Absent reads as "not ACTIVE" and therefore DENIES. That is the safe
        # direction for an export: a caller that did not establish the
        # sample's deletion state does not get to push it.
        "resource": {"deletion_status": {"not": "ACTIVE"}},
    },
]

# What guards.py evaluates. Kept as one name so a policy added to any family
# reaches the decision path without a second edit somewhere else.
ACTIVE_POLICIES: list[dict[str, Any]] = LADDER_POLICIES + DELETION_POLICIES + SOVEREIGNTY_POLICIES
