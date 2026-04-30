"""Tests for Settings.cors_origins multi-form validator (Q-10).

Pydantic-settings v2 unconditionally json.loads() list-typed fields
populated from env vars. cors_origins uses Annotated[list[str],
NoDecode] plus a mode="before" field_validator so it accepts the four
shapes operators actually ship: JSON arrays, comma-separated strings,
empty strings, and real lists. See Critical Rules 45 + 53.

The constructor-input tests pass non-list values to a `list[str]`
field on purpose to exercise the mode="before" validator end-to-end;
that's what the validator exists for, so the type-checker noise on
those calls is suppressed.
"""

# pyright: reportArgumentType=false

import pytest

from backend.config import Settings


class TestCorsOriginsConstructorInput:
    def test_empty_string_yields_empty_list(self):
        assert Settings(cors_origins="").cors_origins == []

    def test_none_yields_empty_list(self):
        assert Settings(cors_origins=None).cors_origins == []

    def test_json_array_string(self):
        result = Settings(cors_origins='["https://a.com","https://b.com"]').cors_origins
        assert result == ["https://a.com", "https://b.com"]

    def test_comma_separated_string(self):
        result = Settings(cors_origins="https://a.com,https://b.com").cors_origins
        assert result == ["https://a.com", "https://b.com"]

    def test_real_list_passed_through(self):
        result = Settings(cors_origins=["https://a.com"]).cors_origins
        assert result == ["https://a.com"]

    def test_whitespace_trimmed_in_csv(self):
        result = Settings(cors_origins="  https://a.com , https://b.com  ").cors_origins
        assert result == ["https://a.com", "https://b.com"]

    def test_malformed_json_array_raises(self):
        with pytest.raises(ValueError, match="looks like JSON but won't parse"):
            Settings(cors_origins="[not, valid, json")


class TestCorsOriginsEnvVarInput:
    """Prove NoDecode disables pydantic-settings' eager json.loads().

    Pre-Q-10, env-var ingestion of `cors_origins=plain,csv` raised
    JSONDecodeError before the validator could run. These tests
    guard against that regression.
    """

    def test_csv_via_env(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "https://a.com,https://b.com")
        assert Settings().cors_origins == ["https://a.com", "https://b.com"]

    def test_json_array_via_env(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", '["https://a.com","https://b.com"]')
        assert Settings().cors_origins == ["https://a.com", "https://b.com"]

    def test_empty_string_via_env(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "")
        assert Settings().cors_origins == []

    def test_single_origin_via_env(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "https://only.example.org")
        assert Settings().cors_origins == ["https://only.example.org"]
