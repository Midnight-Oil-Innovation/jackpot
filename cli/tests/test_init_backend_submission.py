# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""I-3c: ``jackpot init`` backend-submission prompt logic."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from jackpot_scenarios.scenarios import SCENARIO_REGISTRY

from jackpot.init.backend_submission import prompt_for_backend_submission


def _scenario(code: str):
    return SCENARIO_REGISTRY[code]  # type: ignore[index]


# ── No-prompt scenarios (A laptop / F CI) ─────────────────────────────


def test_scenario_a_returns_disabled_without_prompt():
    with patch("click.confirm") as confirm:
        result = prompt_for_backend_submission(_scenario("A"))
    confirm.assert_not_called()
    assert result == {
        "allow_backend_submission": False,
        "backend_submission_repos": [],
    }


def test_scenario_f_returns_disabled_without_prompt():
    with patch("click.confirm") as confirm:
        result = prompt_for_backend_submission(_scenario("F"))
    confirm.assert_not_called()
    assert result == {
        "allow_backend_submission": False,
        "backend_submission_repos": [],
    }


def test_non_interactive_short_circuits_for_any_scenario():
    with patch("click.confirm") as confirm:
        result = prompt_for_backend_submission(_scenario("B"), non_interactive=True)
    confirm.assert_not_called()
    assert result["allow_backend_submission"] is False


# ── Prompted scenarios ────────────────────────────────────────────────


@pytest.mark.parametrize("code", ["B", "C", "D", "E", "T"])
def test_decline_main_toggle_returns_disabled(code):
    """If the operator declines the toggle, the function returns disabled
    and never asks about repos."""
    with patch("click.confirm", side_effect=[False]):
        result = prompt_for_backend_submission(_scenario(code))
    assert result == {
        "allow_backend_submission": False,
        "backend_submission_repos": [],
    }


@pytest.mark.parametrize("code", ["B", "C", "D", "E", "T"])
def test_accept_with_ncbi_only(code):
    """Operator says yes to the toggle, yes to NCBI, no to ENA."""
    with patch("click.confirm", side_effect=[True, True, False]):
        result = prompt_for_backend_submission(_scenario(code))
    assert result == {
        "allow_backend_submission": True,
        "backend_submission_repos": ["ncbi"],
    }


def test_accept_with_both_repos():
    with patch("click.confirm", side_effect=[True, True, True]):
        result = prompt_for_backend_submission(_scenario("B"))
    assert result == {
        "allow_backend_submission": True,
        "backend_submission_repos": ["ncbi", "ena"],
    }


def test_accept_with_ena_only():
    with patch("click.confirm", side_effect=[True, False, True]):
        result = prompt_for_backend_submission(_scenario("B"))
    assert result == {
        "allow_backend_submission": True,
        "backend_submission_repos": ["ena"],
    }


def test_accept_main_but_decline_all_repos_falls_back_to_disabled():
    """The wizard should not produce ``allow=True`` with empty repos —
    that's an unusable state. Falls back to disabled and emits a stderr
    note."""
    with patch("click.confirm", side_effect=[True, False, False]):
        result = prompt_for_backend_submission(_scenario("B"))
    assert result == {
        "allow_backend_submission": False,
        "backend_submission_repos": [],
    }


# ── Closing reminder ─────────────────────────────────────────────────


def test_credential_reminder_lists_ncbi_keys(capsys):
    with patch("click.confirm", side_effect=[True, True, False]):
        prompt_for_backend_submission(_scenario("B"))
    captured = capsys.readouterr()
    assert "JACKPOT_CRED_NCBI_SUBMISSION_USERNAME" in captured.out
    assert "JACKPOT_CRED_NCBI_SUBMISSION_PASSWORD" in captured.out
    # ENA wasn't enabled — its keys should not be mentioned in the reminder.
    assert "JACKPOT_CRED_ENA_WEBIN_USERNAME" not in captured.out


def test_credential_reminder_lists_ena_keys_when_enabled(capsys):
    with patch("click.confirm", side_effect=[True, False, True]):
        prompt_for_backend_submission(_scenario("B"))
    captured = capsys.readouterr()
    assert "JACKPOT_CRED_ENA_WEBIN_USERNAME" in captured.out
    assert "JACKPOT_CRED_ENA_WEBIN_PASSWORD" in captured.out
    assert "JACKPOT_CRED_NCBI" not in captured.out
