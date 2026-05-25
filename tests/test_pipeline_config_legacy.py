"""R-1 #4 — operator-specific defaults must not live in source.

The legacy GCP-Batch fallback (``backend.pipeline_config.legacy``) used
to fall back to ``"jackpot-dev"`` when ``gcp_project_id`` was unset.
Critical Rule 55 forbids operator-specific defaults in production code;
the renderer now raises at config time so missing-config errors surface
loudly instead of as obscure GCP API failures mid-run.
"""

from __future__ import annotations

import pytest

from backend.config import get_settings
from backend.pipeline_config.legacy import generate_run_config

_RENDER_KWARGS = {
    "run_id": "jp-legacy-test",
    "pipeline_name": "jp-sc2",
    "pipeline_version": "1.0.0",
    "lab_slug": "test-lab",
    "pipeline_token": "pt_test",
    "work_dir": "gs://jackpot-work",
    "result_uri": "gs://jackpot-results/test-run",
}


def test_missing_gcp_project_id_raises_at_config_load(monkeypatch):
    """An empty ``gcp_project_id`` must cause a loud failure rather than
    silently rendering with the previous ``"jackpot-dev"`` fallback."""
    monkeypatch.setenv("GCP_PROJECT_ID", "")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="gcp_project_id not configured"):
        generate_run_config(**_RENDER_KWARGS)


def test_configured_gcp_project_id_renders(monkeypatch):
    """When ``gcp_project_id`` is set, the legacy renderer emits it
    verbatim — no operator-specific default substituted."""
    monkeypatch.setenv("GCP_PROJECT_ID", "operator-prod-99")
    get_settings.cache_clear()
    rendered = generate_run_config(**_RENDER_KWARGS)
    assert 'project = "operator-prod-99"' in rendered
    # Defense in depth: the retired default string must not appear
    # anywhere in the rendered config.
    assert "jackpot-dev" not in rendered
