"""I-3a: NCBI + ENA credential predicates and end-to-end validate_required.

The C-1 abstraction handles the mechanics; these tests pin the
predicate matrix so a future predicate change can't silently relax
which credentials are required at startup.
"""

from __future__ import annotations

import pytest

from backend.config import Settings
from backend.credentials.facade import CredentialFacade
from backend.credentials.registry import REQUIRED_CREDENTIALS
from backend.credentials.test_helpers import InMemoryBackend


def _settings(**overrides) -> Settings:
    base = {
        "env": "local",
        "storage_endpoint": "http://localhost:9000",
        "credential_cache_ttl_seconds": 0,
    }
    base.update(overrides)
    return Settings(**base)


def _spec(key: str):
    for spec in REQUIRED_CREDENTIALS:
        if spec.key == key:
            return spec
    raise KeyError(key)


# ── predicate matrix ─────────────────────────────────────────────────


def test_disabled_no_creds_required():
    s = _settings(allow_backend_submission=False, backend_submission_repos=["ncbi", "ena"])
    for key in (
        "ncbi_submission_username",
        "ncbi_submission_password",
        "ena_webin_username",
        "ena_webin_password",
    ):
        assert _spec(key).required_predicate(s) is False


def test_enabled_but_no_repos_no_creds_required():
    s = _settings(allow_backend_submission=True, backend_submission_repos=[])
    for key in (
        "ncbi_submission_username",
        "ncbi_submission_password",
        "ena_webin_username",
        "ena_webin_password",
    ):
        assert _spec(key).required_predicate(s) is False


def test_ncbi_only():
    s = _settings(allow_backend_submission=True, backend_submission_repos=["ncbi"])
    assert _spec("ncbi_submission_username").required_predicate(s) is True
    assert _spec("ncbi_submission_password").required_predicate(s) is True
    assert _spec("ena_webin_username").required_predicate(s) is False
    assert _spec("ena_webin_password").required_predicate(s) is False


def test_ena_only():
    s = _settings(allow_backend_submission=True, backend_submission_repos=["ena"])
    assert _spec("ena_webin_username").required_predicate(s) is True
    assert _spec("ena_webin_password").required_predicate(s) is True
    assert _spec("ncbi_submission_username").required_predicate(s) is False
    assert _spec("ncbi_submission_password").required_predicate(s) is False


def test_both_required():
    s = _settings(allow_backend_submission=True, backend_submission_repos=["ncbi", "ena"])
    for key in (
        "ncbi_submission_username",
        "ncbi_submission_password",
        "ena_webin_username",
        "ena_webin_password",
    ):
        assert _spec(key).required_predicate(s) is True


def test_unrecognized_repo_does_not_require_anything():
    """An unknown repo identifier in backend_submission_repos must not
    fail startup — the runtime path is responsible for surfacing the
    misconfiguration. The credential layer stays permissive."""
    s = _settings(allow_backend_submission=True, backend_submission_repos=["gisaid", "ddbj"])
    for key in (
        "ncbi_submission_username",
        "ncbi_submission_password",
        "ena_webin_username",
        "ena_webin_password",
    ):
        assert _spec(key).required_predicate(s) is False


# ── end-to-end via validate_required ────────────────────────────────


def test_validate_required_raises_when_ncbi_creds_missing():
    s = _settings(allow_backend_submission=True, backend_submission_repos=["ncbi"])
    backend = InMemoryBackend({"jwt_signing_key": "x", "s3_storage_secret_key": "y"})
    facade = CredentialFacade(backend=backend, settings=s)
    with pytest.raises(RuntimeError) as ei:
        facade.validate_required()
    msg = str(ei.value)
    assert "ncbi_submission_username" in msg
    assert "ncbi_submission_password" in msg
    assert "ena_webin" not in msg


def test_validate_required_passes_when_ncbi_creds_present():
    s = _settings(allow_backend_submission=True, backend_submission_repos=["ncbi"])
    backend = InMemoryBackend(
        {
            "jwt_signing_key": "x",
            "s3_storage_secret_key": "y",
            "ncbi_submission_username": "submitter@example.org",
            "ncbi_submission_password": "supersecret",
        }
    )
    facade = CredentialFacade(backend=backend, settings=s)
    facade.validate_required()  # no raise


def test_validate_required_lists_all_missing_for_both_repos():
    s = _settings(allow_backend_submission=True, backend_submission_repos=["ncbi", "ena"])
    backend = InMemoryBackend({"jwt_signing_key": "x", "s3_storage_secret_key": "y"})
    facade = CredentialFacade(backend=backend, settings=s)
    with pytest.raises(RuntimeError) as ei:
        facade.validate_required()
    msg = str(ei.value)
    for key in (
        "ncbi_submission_username",
        "ncbi_submission_password",
        "ena_webin_username",
        "ena_webin_password",
    ):
        assert key in msg


def test_validate_required_silent_for_unknown_repo():
    """allow_backend_submission=True with only unknown repos should pass
    validate_required as long as the C-1 baseline credentials are present."""
    s = _settings(allow_backend_submission=True, backend_submission_repos=["gisaid"])
    backend = InMemoryBackend({"jwt_signing_key": "x", "s3_storage_secret_key": "y"})
    facade = CredentialFacade(backend=backend, settings=s)
    facade.validate_required()  # no raise


# ── legacy env name fallback (proves C-1 envvar backend integration) ─


def test_legacy_env_names_present():
    """Pin the legacy env-name table for the four new credentials so
    operators don't lose backward-compat in a future renumbering."""
    expected = {
        "ncbi_submission_username": (
            "JACKPOT_NCBI_SUBMISSION_USERNAME",
            "NCBI_SUBMISSION_USERNAME",
        ),
        "ncbi_submission_password": (
            "JACKPOT_NCBI_SUBMISSION_PASSWORD",
            "NCBI_SUBMISSION_PASSWORD",
        ),
        "ena_webin_username": ("JACKPOT_ENA_WEBIN_USERNAME", "ENA_WEBIN_USERNAME"),
        "ena_webin_password": ("JACKPOT_ENA_WEBIN_PASSWORD", "ENA_WEBIN_PASSWORD"),
    }
    for key, names in expected.items():
        assert _spec(key).legacy_env_names == names
