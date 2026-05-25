"""C-1: EnvVarBackend lookup order, legacy fallback, list_keys."""

from __future__ import annotations

import pytest

from backend.credentials.base import CredentialNotFoundError
from backend.credentials.env_backend import EnvVarBackend


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch):
    """Clear every env var EnvVarBackend might consult so each test starts
    from a known-empty state regardless of the host shell."""
    for name in [
        "JACKPOT_CRED_JWT_SIGNING_KEY",
        "JACKPOT_CRED_GOOGLE_OAUTH_CLIENT_SECRET",
        "JACKPOT_CRED_S3_STORAGE_SECRET_KEY",
        "JACKPOT_CRED_GCS_HMAC_ACCESS_KEY",
        "JACKPOT_CRED_GCS_HMAC_SECRET",
        "JACKPOT_CRED_LOCAL_STORAGE_PRESIGN_SECRET",
        "JACKPOT_SECRET_KEY",
        "SECRET_KEY",
        "JACKPOT_GOOGLE_OAUTH_CLIENT_SECRET",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "JACKPOT_STORAGE_SECRET_KEY",
        "STORAGE_SECRET_KEY",
        "GCS_HMAC_ACCESS_KEY",
        "GCS_HMAC_SECRET",
        "JACKPOT_PRESIGN_SECRET",
    ]:
        monkeypatch.delenv(name, raising=False)
    yield


def test_canonical_lookup_wins(monkeypatch):
    monkeypatch.setenv("JACKPOT_CRED_JWT_SIGNING_KEY", "canonical")
    monkeypatch.setenv("JACKPOT_SECRET_KEY", "legacy")
    monkeypatch.setenv("SECRET_KEY", "even-older")
    assert EnvVarBackend().get("jwt_signing_key") == "canonical"


def test_legacy_fallback_when_canonical_unset(monkeypatch):
    monkeypatch.setenv("JACKPOT_SECRET_KEY", "legacy")
    assert EnvVarBackend().get("jwt_signing_key") == "legacy"


def test_legacy_lookup_in_declared_order(monkeypatch):
    # JACKPOT_SECRET_KEY is the first legacy name; SECRET_KEY second.
    monkeypatch.setenv("JACKPOT_SECRET_KEY", "first")
    monkeypatch.setenv("SECRET_KEY", "second")
    assert EnvVarBackend().get("jwt_signing_key") == "first"


def test_falls_through_to_second_legacy(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "second")
    assert EnvVarBackend().get("jwt_signing_key") == "second"


def test_not_found_lists_tried_names():
    with pytest.raises(CredentialNotFoundError) as ei:
        EnvVarBackend().get("jwt_signing_key")
    msg = str(ei.value)
    assert "JACKPOT_CRED_JWT_SIGNING_KEY" in msg
    assert "JACKPOT_SECRET_KEY" in msg
    assert "SECRET_KEY" in msg


def test_empty_string_treated_as_not_set(monkeypatch):
    monkeypatch.setenv("JACKPOT_CRED_JWT_SIGNING_KEY", "")
    monkeypatch.setenv("JACKPOT_SECRET_KEY", "real-value")
    assert EnvVarBackend().get("jwt_signing_key") == "real-value"


def test_list_keys_returns_only_set_credentials(monkeypatch):
    monkeypatch.setenv("JACKPOT_CRED_JWT_SIGNING_KEY", "v1")
    monkeypatch.setenv("STORAGE_SECRET_KEY", "v2")
    keys = set(EnvVarBackend().list_keys())
    assert "jwt_signing_key" in keys
    assert "s3_storage_secret_key" in keys
    assert "google_oauth_client_secret" not in keys


def test_unregistered_key_uses_canonical_only(monkeypatch):
    monkeypatch.setenv("JACKPOT_CRED_AD_HOC_KEY", "ad-hoc-value")
    assert EnvVarBackend().get("ad_hoc_key") == "ad-hoc-value"


def test_unregistered_key_not_found_when_unset():
    with pytest.raises(CredentialNotFoundError):
        EnvVarBackend().get("ad_hoc_key")
