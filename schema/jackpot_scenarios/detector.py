"""
Scenario detector — pure inference from operator-answer dicts to a Scenario.

This module is the policy ("what answer set maps to what scenario") and is
deliberately UI-free. The CLI wraps it with Click prompts in
`cli/jackpot/init/detector.py`; tests exercise it directly with answer
dicts. Per design Decision 8 (B-STLT-4 in todo.md).

Question keys (canonical strings — operators answer with single-letter
codes):

    operator_type        a / b / c / d / e / f / t   (see Question 1 in
                         docs/architecture/jackpot-init-cli.md §2)
    deployment_target    1 / 2 / 3                    (laptop / cloud-single / cloud-multi)
    federation           n / m / h                    (off / member / hub)
    pii_handling         d / s / o                    (dlp / scrub / off)
    auth_method          g / s / m                    (google-oauth / sso / mock)

The detector is deterministic: same answer dict → same scenario. When
answers are inconsistent (e.g. operator=t + target=3 + auth=sso), it
prefers the operator_type signal — Tribal sovereignty trumps deployment
shape. Set `strict=True` to raise instead of inferring under conflict.
"""

from __future__ import annotations

from dataclasses import dataclass

from jackpot_scenarios.scenarios import (
    SCENARIO_REGISTRY,
    Scenario,
    ScenarioCode,
)


@dataclass(frozen=True)
class DetectorAnswers:
    """The 5-question answer set the detector consumes."""

    operator_type: str
    deployment_target: str
    federation: str
    pii_handling: str
    auth_method: str

    def normalised(self) -> DetectorAnswers:
        """Return a copy with all values lowercased and stripped."""
        return DetectorAnswers(
            operator_type=self.operator_type.strip().lower(),
            deployment_target=self.deployment_target.strip().lower(),
            federation=self.federation.strip().lower(),
            pii_handling=self.pii_handling.strip().lower(),
            auth_method=self.auth_method.strip().lower(),
        )


@dataclass(frozen=True)
class DetectionResult:
    """Output of `infer_scenario` — the proposed scenario plus the
    chain-of-reasoning the detector followed (for the rationale string
    in the CLI's confirm prompt)."""

    scenario: Scenario
    rationale: str
    conflicts: tuple[str, ...] = ()


_OPERATOR_VALID = {"a", "b", "c", "d", "e", "f", "t"}
_TARGET_VALID = {"1", "2", "3"}
_FEDERATION_VALID = {"n", "m", "h"}
_PII_VALID = {"d", "s", "o"}
_AUTH_VALID = {"g", "s", "m"}


def _validate(answers: DetectorAnswers) -> None:
    """Raise ValueError on out-of-range answer values. Pure validation —
    no scenario inference yet."""
    failures: list[str] = []
    if answers.operator_type not in _OPERATOR_VALID:
        failures.append(f"operator_type={answers.operator_type!r} not in {sorted(_OPERATOR_VALID)}")
    if answers.deployment_target not in _TARGET_VALID:
        failures.append(
            f"deployment_target={answers.deployment_target!r} not in {sorted(_TARGET_VALID)}"
        )
    if answers.federation not in _FEDERATION_VALID:
        failures.append(f"federation={answers.federation!r} not in {sorted(_FEDERATION_VALID)}")
    if answers.pii_handling not in _PII_VALID:
        failures.append(f"pii_handling={answers.pii_handling!r} not in {sorted(_PII_VALID)}")
    if answers.auth_method not in _AUTH_VALID:
        failures.append(f"auth_method={answers.auth_method!r} not in {sorted(_AUTH_VALID)}")
    if failures:
        raise ValueError("Invalid detector answers: " + "; ".join(failures))


def _infer_code(answers: DetectorAnswers) -> tuple[ScenarioCode, list[str]]:
    """Map the answer set to a scenario code; collect any conflicts as
    diagnostic strings. operator_type is the dominant signal for T;
    federation is the dominant signal for E; otherwise (operator_type,
    deployment_target) determines the choice."""

    conflicts: list[str] = []

    # 1. Tribal-sovereignty wins regardless of the other answers — CARE
    #    Principles requirements (deletion-on-request, no auto-publish)
    #    cannot be retrofitted onto another scenario without retrofit.
    if answers.operator_type == "t":
        if answers.deployment_target == "3":
            conflicts.append(
                "operator=tribal + target=cloud-multi-tenant: T usually "
                "runs as A or E variant; SaaS posture conflicts with "
                "sovereignty."
            )
        if answers.auth_method == "s":
            conflicts.append(
                "operator=tribal + auth=sso: T defaults to OAuth; SSO "
                "is supported but uncommon outside enterprise IT."
            )
        return "T", conflicts

    # 2. Federation membership wins next — Scenario E is "primary
    #    purpose is federating with peers." If federation=member or hub
    #    and operator isn't F (CI), it's E.
    if answers.federation in {"m", "h"} and answers.operator_type != "f":
        return "E", conflicts

    # 3. CI test scenario.
    if answers.operator_type == "f":
        if answers.auth_method != "m":
            conflicts.append(
                f"operator=ci + auth={answers.auth_method!r}: CI "
                "scenarios use mock auth by default; non-mock auth "
                "requires real credentials in CI runners."
            )
        if answers.pii_handling != "o":
            conflicts.append(
                f"operator=ci + pii={answers.pii_handling!r}: CI "
                "scenarios opt out of PII handling; the test data is "
                "synthetic."
            )
        return "F", conflicts

    # 4. SaaS multi-tenant.
    if answers.operator_type == "d" or answers.deployment_target == "3":
        return "D", conflicts

    # 5. Single-org cloud (B) vs multi-lab agency (C) vs laptop (A).
    if answers.deployment_target == "1":
        if answers.operator_type not in {"a"}:
            conflicts.append(
                f"operator={answers.operator_type!r} + target=laptop: "
                "non-academic operators usually want a cloud target."
            )
        return "A", conflicts

    if answers.operator_type == "c":
        return "C", conflicts

    return "B", conflicts


def infer_scenario(
    answers: DetectorAnswers,
    *,
    strict: bool = False,
) -> DetectionResult:
    """Run the deterministic answer-to-scenario mapping.

    `strict=False` (default): inconsistencies become diagnostic strings
    in `DetectionResult.conflicts`; the detector still returns a best-fit
    scenario.

    `strict=True`: any conflict raises ValueError. Useful in CI / tests
    where ambiguity should fail loudly.
    """
    normalised = answers.normalised()
    _validate(normalised)

    code, conflicts = _infer_code(normalised)
    scenario = SCENARIO_REGISTRY[code]

    rationale_parts = [
        f"operator_type={normalised.operator_type!r}",
        f"deployment_target={normalised.deployment_target!r}",
        f"federation={normalised.federation!r}",
        f"pii_handling={normalised.pii_handling!r}",
        f"auth_method={normalised.auth_method!r}",
    ]
    rationale = f"Inferred scenario {code} ({scenario.name}) from: " + ", ".join(rationale_parts)
    if conflicts:
        rationale += " — flagged conflicts: " + "; ".join(conflicts)

    if strict and conflicts:
        raise ValueError("Detector conflicts in strict mode: " + "; ".join(conflicts))

    return DetectionResult(
        scenario=scenario,
        rationale=rationale,
        conflicts=tuple(conflicts),
    )
