"""Unit tests for jackpot_scenarios.detector — the pure inference logic."""

import pytest
from jackpot_scenarios.detector import (
    DetectorAnswers,
    infer_scenario,
)


def _answers(
    operator_type: str = "a",
    deployment_target: str = "1",
    federation: str = "n",
    pii_handling: str = "o",
    auth_method: str = "m",
) -> DetectorAnswers:
    return DetectorAnswers(
        operator_type=operator_type,
        deployment_target=deployment_target,
        federation=federation,
        pii_handling=pii_handling,
        auth_method=auth_method,
    )


class TestHappyPathInference:
    """Each scenario reachable from a clean answer set with no conflicts."""

    def test_a_laptop(self):
        result = infer_scenario(
            _answers(operator_type="a", deployment_target="1", auth_method="m"),
        )
        assert result.scenario.code == "A"
        assert result.conflicts == ()

    def test_b_single_org_cloud(self):
        result = infer_scenario(
            _answers(
                operator_type="b",
                deployment_target="2",
                federation="n",
                pii_handling="d",
                auth_method="g",
            ),
        )
        assert result.scenario.code == "B"
        assert result.conflicts == ()

    def test_c_multi_lab(self):
        result = infer_scenario(
            _answers(
                operator_type="c",
                deployment_target="2",
                federation="n",
                pii_handling="d",
                auth_method="g",
            ),
        )
        assert result.scenario.code == "C"

    def test_d_saas_via_operator_type(self):
        result = infer_scenario(
            _answers(
                operator_type="d",
                deployment_target="3",
                federation="n",
                pii_handling="d",
                auth_method="s",
            ),
        )
        assert result.scenario.code == "D"

    def test_d_saas_via_target_only(self):
        # operator_type=b but target=3 still gets D — multi-tenant target
        # is the structural signal.
        result = infer_scenario(
            _answers(
                operator_type="b",
                deployment_target="3",
                federation="n",
                pii_handling="d",
                auth_method="g",
            ),
        )
        assert result.scenario.code == "D"

    def test_e_federation_member(self):
        result = infer_scenario(
            _answers(
                operator_type="e",
                deployment_target="2",
                federation="m",
                pii_handling="d",
                auth_method="g",
            ),
        )
        assert result.scenario.code == "E"

    def test_e_federation_hub(self):
        result = infer_scenario(
            _answers(
                operator_type="e",
                deployment_target="2",
                federation="h",
                pii_handling="d",
                auth_method="g",
            ),
        )
        assert result.scenario.code == "E"

    def test_f_ci(self):
        result = infer_scenario(
            _answers(
                operator_type="f",
                deployment_target="1",
                federation="n",
                pii_handling="o",
                auth_method="m",
            ),
        )
        assert result.scenario.code == "F"
        assert result.conflicts == ()

    def test_t_tribal(self):
        result = infer_scenario(
            _answers(
                operator_type="t",
                deployment_target="1",
                federation="n",
                pii_handling="d",
                auth_method="g",
            ),
        )
        assert result.scenario.code == "T"
        assert result.conflicts == ()


class TestTribalDominance:
    """operator_type=t wins regardless of other answers — CARE Principles
    can't be safely retrofitted onto a non-T scenario."""

    def test_t_with_cloud_target(self):
        result = infer_scenario(_answers(operator_type="t", deployment_target="2"))
        assert result.scenario.code == "T"

    def test_t_with_multi_tenant_flags_conflict(self):
        result = infer_scenario(_answers(operator_type="t", deployment_target="3"))
        assert result.scenario.code == "T"
        assert any("multi-tenant" in c for c in result.conflicts)

    def test_t_with_sso_flags_conflict(self):
        result = infer_scenario(_answers(operator_type="t", auth_method="s"))
        assert result.scenario.code == "T"
        assert any("sso" in c.lower() for c in result.conflicts)

    def test_t_with_federation_member_still_t(self):
        # Tribal Epidemiology Center pattern: operator_type=t + federation=m
        # — answer is still T (federation_role inside T is operator's
        # later choice via reconfigure --enable-federation).
        result = infer_scenario(
            _answers(operator_type="t", federation="m", auth_method="g"),
        )
        assert result.scenario.code == "T"


class TestFederationDominance:
    """federation in {member, hub} signals E unless operator is F (CI)."""

    def test_b_with_federation_member_becomes_e(self):
        result = infer_scenario(
            _answers(operator_type="b", deployment_target="2", federation="m"),
        )
        assert result.scenario.code == "E"

    def test_c_with_federation_hub_becomes_e(self):
        result = infer_scenario(
            _answers(operator_type="c", deployment_target="2", federation="h"),
        )
        assert result.scenario.code == "E"

    def test_f_with_federation_stays_f(self):
        # CI never federates — explicit override.
        result = infer_scenario(
            _answers(operator_type="f", federation="m", auth_method="m"),
        )
        assert result.scenario.code == "F"


class TestCiConflicts:
    """Scenario F with non-CI answers should flag but still infer F."""

    def test_f_with_real_oauth_flags_conflict(self):
        result = infer_scenario(
            _answers(operator_type="f", auth_method="g", pii_handling="o"),
        )
        assert result.scenario.code == "F"
        assert any("auth" in c.lower() for c in result.conflicts)

    def test_f_with_pii_dlp_flags_conflict(self):
        result = infer_scenario(
            _answers(operator_type="f", auth_method="m", pii_handling="d"),
        )
        assert result.scenario.code == "F"
        assert any("pii" in c.lower() for c in result.conflicts)


class TestNormalisation:
    """Whitespace + case insensitivity for operator-typed answers."""

    def test_uppercase_normalised(self):
        result = infer_scenario(
            DetectorAnswers(
                operator_type="T",
                deployment_target="1",
                federation="N",
                pii_handling="D",
                auth_method="G",
            ),
        )
        assert result.scenario.code == "T"

    def test_padding_stripped(self):
        result = infer_scenario(
            DetectorAnswers(
                operator_type="  a  ",
                deployment_target="1",
                federation="n",
                pii_handling="o",
                auth_method="m",
            ),
        )
        assert result.scenario.code == "A"


class TestValidation:
    def test_unknown_operator_type_rejected(self):
        with pytest.raises(ValueError, match="operator_type"):
            infer_scenario(_answers(operator_type="z"))

    def test_unknown_target_rejected(self):
        with pytest.raises(ValueError, match="deployment_target"):
            infer_scenario(_answers(deployment_target="9"))

    def test_unknown_federation_rejected(self):
        with pytest.raises(ValueError, match="federation"):
            infer_scenario(_answers(federation="x"))

    def test_unknown_pii_rejected(self):
        with pytest.raises(ValueError, match="pii_handling"):
            infer_scenario(_answers(pii_handling="?"))

    def test_unknown_auth_rejected(self):
        with pytest.raises(ValueError, match="auth_method"):
            infer_scenario(_answers(auth_method="!"))


class TestStrictMode:
    """In strict mode any conflict raises rather than just being recorded."""

    def test_strict_raises_on_conflict(self):
        with pytest.raises(ValueError, match="strict mode"):
            infer_scenario(
                _answers(operator_type="t", deployment_target="3"),
                strict=True,
            )

    def test_strict_passes_on_clean_answer_set(self):
        result = infer_scenario(
            _answers(
                operator_type="b",
                deployment_target="2",
                federation="n",
                pii_handling="d",
                auth_method="g",
            ),
            strict=True,
        )
        assert result.scenario.code == "B"
        assert result.conflicts == ()


class TestRationaleString:
    def test_rationale_includes_all_answers(self):
        result = infer_scenario(_answers(operator_type="a", deployment_target="1"))
        for fragment in (
            "operator_type='a'",
            "deployment_target='1'",
            "federation='n'",
            "pii_handling='o'",
            "auth_method='m'",
        ):
            assert fragment in result.rationale

    def test_rationale_appends_conflicts_when_present(self):
        result = infer_scenario(_answers(operator_type="t", deployment_target="3"))
        assert "flagged conflicts:" in result.rationale
