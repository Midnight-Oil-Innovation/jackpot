"""
jackpot_scenarios — install-scenario defaults registry for JACKPOT.

The 7 install scenarios (A laptop / B single-org cloud / C multi-lab agency
/ D hosted SaaS / E federation member / F CI test / T Tribal-sovereignty)
each have a canonical `ScenarioDefaults` model exposing the install-time
config knobs (federation_role, deletion_on_request, dlp_enabled, etc.).

Consumers:
- `jackpot init` (cli/jackpot/init/) — reads scenarios + runs detector
- backend/backend/config.py — may import scenario names for runtime checks
- CI — `jackpot init scenario-info F --json` for non-Python consumers

This package is part of the `jackpot-schema` workspace member (Decision 8
in docs/architecture/jackpot-init-cli.md).
"""

from jackpot_scenarios.scenarios import (
    ALL_SCENARIOS,
    SCENARIO_REGISTRY,
    Scenario,
    ScenarioCode,
    ScenarioDefaults,
    get_scenario,
)

__all__ = [
    "ALL_SCENARIOS",
    "SCENARIO_REGISTRY",
    "Scenario",
    "ScenarioCode",
    "ScenarioDefaults",
    "get_scenario",
]
