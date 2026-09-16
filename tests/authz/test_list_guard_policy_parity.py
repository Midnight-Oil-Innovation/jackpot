"""The list half and the row guard must filter on the same policy set.

``sample_list_clause``'s own docstring states the contract:

    the answer is only right if three moving parts match the row-wise guard
    exactly: the scope expression, the policy set, and the attribute-column
    mapping. ... a list that drifts *wider* leaks rows with no error and no
    audit entry.

It then passed ``LADDER_POLICIES`` while ``auth/guards.py`` passes
``ACTIVE_POLICIES`` — a mismatch on one of the three parts it names. Nothing
asserted the two agreed, so the drift was invisible.

It was harmless: ``LADDER_POLICIES`` is a subset of ``ACTIVE_POLICIES``, and the
two differ only on ``deletion:approve`` and ``federation:push`` — the two DENY
policies, both keying capabilities no list filtered on. The failure mode was
entirely in the future: the day someone adds a DENY on ``sample:read``,
``permit()`` would enforce it and every list would ignore it.

The lab and project helpers legitimately pass ``policies=[]``: the ladder
policies read ``sharing_level``, which those rows do not have, so
``_attr_sql`` raises rather than skipping the term. That is the documented
"raise rather than silently widen" behaviour, not the same drift.
"""

from datetime import UTC, datetime

import pytest

from authz.scopes import SCOPE_EXPR
from backend.authz.engine import CapabilityGrant, Context, Principal, PrincipalKind
from backend.authz.policy import ACTIVE_POLICIES, LADDER_POLICIES
from backend.authz.principal import SAMPLE_ATTRIBUTE_COLUMNS
from backend.authz.visibility import sample_list_clause, visibility_sql_clause

# Capabilities whose policies read only attributes a sample row has. Derived,
# not hand-listed, so a new policy is covered the day it is added.
#
# `pipeline:register_custom` is excluded by this and should be: its policy reads
# `registered_by_user_id`, which is not in SAMPLE_ATTRIBUTE_COLUMNS, so
# sample_list_clause raises for it — today, and with either policy set. That is
# _attr_sql's "raise rather than silently skip a term" behaviour working, not a
# drift, and a parity test that included it would be asserting on a call the
# function is not meant to serve.
POLICY_CAPABILITIES = sorted(
    {
        p["capability"]
        for p in ACTIVE_POLICIES
        if all(attr in SAMPLE_ATTRIBUTE_COLUMNS for attr in (p.get("resource") or {}))
    }
)

# Fixed, so the fragments are comparable: sample_list_clause defaults to
# `now=datetime.now(UTC)`, which would otherwise differ between the two calls.
CONTEXT = Context(conditions={}, now=datetime(2026, 1, 1, tzinfo=UTC))


def _principal() -> Principal:
    return Principal(
        kind=PrincipalKind.HUMAN,
        id="7",
        on_behalf_of=None,
        grants=[
            CapabilityGrant(
                capability=cap, scope_ref="instance://self", conditions={}, not_after=None
            )
            for cap in POLICY_CAPABILITIES
        ],
    )


@pytest.mark.parametrize("capability", POLICY_CAPABILITIES)
def test_the_sample_list_compiles_the_same_policies_the_guard_evaluates(capability: str) -> None:
    """Compare the emitted SQL, not the policy list.

    Asserting `LADDER_POLICIES == ACTIVE_POLICIES` would be a statement about
    two constants. What matters is that the fragment a list runs is the one the
    guard's policy set produces — so the comparison is against
    visibility_sql_clause driven with the guard's own set.
    """
    listed, list_params = sample_list_clause(_principal(), capability, context=CONTEXT)
    guarded, guard_params = visibility_sql_clause(
        _principal(),
        capability,
        SCOPE_EXPR,
        context=CONTEXT,
        policies=ACTIVE_POLICIES,
        attribute_columns=SAMPLE_ATTRIBUTE_COLUMNS,
    )

    assert listed == guarded
    assert list_params == guard_params


def test_the_two_sets_still_differ_somewhere() -> None:
    """Anti-rot (Rule 74).

    If LADDER_POLICIES and ACTIVE_POLICIES ever become the same object, the
    test above passes for a reason that has nothing to do with what it checks,
    and would keep passing if sample_list_clause went back to the narrower set.
    """
    assert LADDER_POLICIES != ACTIVE_POLICIES, (
        "the sets are identical — the parity test above can no longer fail"
    )
    differing = {p["capability"] for p in ACTIVE_POLICIES if p not in LADDER_POLICIES}

    # Not merely "the sets differ somewhere" — they must differ on a capability
    # the parametrized test actually walks. Measured: mutate both DENY policies
    # to read an unmapped attribute, which drops them out of
    # POLICY_CAPABILITIES, then revert sample_list_clause to the narrower set —
    # the parity test goes fully vacuous at 6 passed while a "differ somewhere"
    # canary stays green. What prevents that today lives in another file
    # (test_sovereignty_policies.py::test_every_deny_reads_only_loaded_attributes),
    # and a canary leaning on a neighbour's invariant is not a canary.
    assert differing & set(POLICY_CAPABILITIES), (
        "no parametrized capability distinguishes the sets — the parity test "
        "above can no longer fail"
    )
