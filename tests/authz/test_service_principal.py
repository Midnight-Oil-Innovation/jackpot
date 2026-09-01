"""M2-B6 — the SERVICE principal for per-run pipeline callbacks.

The positive check (`pipeline:write_results` at the run's project) cannot
fail today: the principal is built from the same run the token
authenticated against. So the tests that matter here are the NEGATIVE ones.

§8.4: "EXPLICITLY NOT GRANTED: sample:read_detail, sample:read ... The
absence is the security property, not an oversight." A capability set is
only a security property if something breaks when it grows, which is what
this file is for.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from backend.authz import (
    Context,
    Decision,
    PrincipalKind,
    Resource,
    permit,
    scope_uri,
)
from backend.authz.principal import PIPELINE_RUN_CAPABILITIES, pipeline_run_principal

PROJECT = 12
LAB = 5
ORG = 1
RUN = {"run_id": "jp-abc", "project_id": PROJECT}


@pytest.fixture(autouse=True)
def _stub_scope():
    """The scope resolver is the only DB touch; the engine below is pure."""
    with patch(
        "backend.authz.principal.project_resource_scope",
        side_effect=lambda pid, **kw: scope_uri(org=ORG, lab=LAB, project=pid),
    ):
        yield


def _permit(principal, capability, scope):
    return permit(
        principal,
        capability,
        Resource(scope=scope),
        Context(conditions={}, now=datetime.now(UTC)),
        policies=[],
    )


def test_principal_is_a_service_kind():
    p = pipeline_run_principal(RUN)
    assert p.kind is PrincipalKind.SERVICE
    assert p.on_behalf_of is None
    assert p.id == "pipeline-run:jp-abc"


def test_it_may_write_results_for_its_own_run():
    p = pipeline_run_principal(RUN)
    assert _permit(p, "pipeline:write_results", scope_uri(org=ORG, lab=LAB, project=PROJECT)) is (
        Decision.ALLOW
    )


def test_it_may_not_read_the_samples_it_computes_over():
    """The cryptWWDB property (§4.6): computes without seeing.

    Asserted at the sample its own project contains — the closest thing to a
    sample this principal has any claim on. If the capability list ever gains
    a read verb, this is what fails.
    """
    p = pipeline_run_principal(RUN)
    sample = scope_uri(org=ORG, lab=LAB, project=PROJECT, sample=99)
    for capability in ("sample:read", "sample:read_detail", "sample:read_surveillance"):
        assert _permit(p, capability, sample) is Decision.DENY, capability


def test_it_holds_write_results_and_nothing_else():
    """Pins the set itself, so a widening is a test change and not a diff
    detail someone has to notice in review."""
    assert PIPELINE_RUN_CAPABILITIES == ["pipeline:write_results"]
    assert {g.capability for g in pipeline_run_principal(RUN).grants} == {"pipeline:write_results"}


def test_it_cannot_write_results_for_another_project():
    """Scope, not just capability: one run's token authorizes one run's
    project. A grant that reached the lab would let any run in the lab write
    any other run's results."""
    p = pipeline_run_principal(RUN)
    for scope in (
        scope_uri(org=ORG, lab=LAB, project=PROJECT + 1),
        scope_uri(org=ORG, lab=LAB),
        scope_uri(org=ORG),
        scope_uri(),
    ):
        assert _permit(p, "pipeline:write_results", scope) is Decision.DENY, scope


def test_it_cannot_run_or_launch_a_pipeline():
    """Writing results is not running things — the verbs are separate (§4.2)."""
    project = scope_uri(org=ORG, lab=LAB, project=PROJECT)
    p = pipeline_run_principal(RUN)
    for capability in ("pipeline:run", "pipeline:register_custom", "pipeline:promote"):
        assert _permit(p, capability, project) is Decision.DENY, capability


def test_a_run_without_a_project_is_refused_not_rooted():
    """pipeline_runs.project_id is NOT NULL, so a row lacking it means the
    caller did not SELECT the column. Defaulting to the instance root there
    would hand a pipeline callback authority over the whole deployment."""
    with pytest.raises(ValueError, match="no project_id"):
        pipeline_run_principal({"run_id": "jp-xyz"})


def test_grants_carry_their_provenance():
    """source='pipeline_token' distinguishes these from reseeded rows, which
    matters because they are constructed rather than stored — nothing in
    authz_capability_grants should ever match one."""
    for grant in pipeline_run_principal(RUN).grants:
        assert grant.source == "pipeline_token"
        assert grant.not_after is None


def test_the_engine_still_expires_a_time_bounded_service_grant():
    """Not used today — these grants carry no expiry — but the engine must not
    treat a SERVICE principal as exempt from the rule it applies to humans."""
    p = pipeline_run_principal(RUN)
    p.grants[0].not_after = datetime.now(UTC) - timedelta(seconds=1)
    assert (
        _permit(p, "pipeline:write_results", scope_uri(org=ORG, lab=LAB, project=PROJECT))
        is Decision.DENY
    )
