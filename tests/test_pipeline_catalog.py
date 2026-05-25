"""R-1 #7 — pipeline catalog field validators reject Groovy-injection
chars before the value lands in the database.

The validator is exercised through ``CustomPipelineRequest`` (the
user-facing BYOP write path), and directly against
:func:`validate_groovy_safe` for the field names that don't currently
have an API endpoint but will be subject to the same constraint
(work_dir, pipeline_description, profile name).

Test fixtures construct dangerous-character literals via :func:`chr`
so the source itself doesn't embed payloads — the brief's pattern.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.pipeline_config.groovy_safe import validate_groovy_safe
from backend.routers.pipelines import CustomPipelineRequest

# Dangerous characters by chr() to keep this source file portable
# across encoding-sensitive tooling. See the brief's note.
DANGEROUS_DOUBLE_QUOTE = chr(34)
DANGEROUS_DOLLAR = chr(36)
DANGEROUS_SEMICOLON = chr(59)
DANGEROUS_BACKTICK = chr(96)
DANGEROUS_BACKSLASH = chr(92)
DANGEROUS_NEWLINE = chr(10)
DANGEROUS_SINGLE_QUOTE = chr(39)
DANGEROUS_CARRIAGE_RETURN = chr(13)


def _payload(pipeline_name: str) -> dict:
    return {
        "project_id": 1,
        "pipeline_name": pipeline_name,
        "github_url": "https://github.com/example/pipeline",
        "revision": "v1.0.0",
        "parameter_schema": {"a": {"type": "string"}},
    }


# ───────────────────── pipeline_name (CustomPipelineRequest) ────────────────


def test_pipeline_name_rejects_double_quote():
    bad_name = f"foo{DANGEROUS_DOUBLE_QUOTE}bar"
    with pytest.raises(ValidationError):
        CustomPipelineRequest(**_payload(bad_name))


def test_pipeline_name_rejects_backslash():
    bad_name = f"foo{DANGEROUS_BACKSLASH}bar"
    with pytest.raises(ValidationError):
        CustomPipelineRequest(**_payload(bad_name))


def test_pipeline_name_rejects_dollar_sign():
    bad_name = f"price{DANGEROUS_DOLLAR}eval"
    with pytest.raises(ValidationError):
        CustomPipelineRequest(**_payload(bad_name))


def test_pipeline_name_rejects_semicolon():
    bad_name = f"foo{DANGEROUS_SEMICOLON} bar"
    with pytest.raises(ValidationError):
        CustomPipelineRequest(**_payload(bad_name))


def test_pipeline_name_rejects_backtick():
    bad_name = f"foo{DANGEROUS_BACKTICK}whoami{DANGEROUS_BACKTICK}"
    with pytest.raises(ValidationError):
        CustomPipelineRequest(**_payload(bad_name))


def test_pipeline_name_rejects_single_quote():
    bad_name = f"foo{DANGEROUS_SINGLE_QUOTE}bar"
    with pytest.raises(ValidationError):
        CustomPipelineRequest(**_payload(bad_name))


def test_pipeline_name_rejects_newline():
    bad_name = f"foo{DANGEROUS_NEWLINE}bar"
    with pytest.raises(ValidationError):
        CustomPipelineRequest(**_payload(bad_name))


def test_pipeline_name_accepts_safe_characters():
    """Spelling out the allowed shape: alphanumeric + hyphen + period
    + underscore + space + slash. Must not trip the validator."""
    CustomPipelineRequest(**_payload("sc2-illumina_v1.0.0/main"))


# ───────────────────── work_dir (validate_groovy_safe direct) ───────────────


@pytest.mark.parametrize(
    "ch",
    [
        DANGEROUS_BACKSLASH,
        DANGEROUS_DOUBLE_QUOTE,
        DANGEROUS_SINGLE_QUOTE,
        DANGEROUS_DOLLAR,
        DANGEROUS_SEMICOLON,
        DANGEROUS_BACKTICK,
        DANGEROUS_NEWLINE,
        DANGEROUS_CARRIAGE_RETURN,
    ],
)
def test_work_dir_rejects_dangerous_chars(ch):
    """The same character set rejected for pipeline_name applies to
    work_dir at the model layer (via validate_groovy_safe)."""
    bad = f"/srv/work{ch}injected"
    with pytest.raises(ValueError):
        validate_groovy_safe(bad, field_name="work_dir")


def test_work_dir_accepts_normal_path():
    assert validate_groovy_safe("/srv/jackpot/work", field_name="work_dir") == ("/srv/jackpot/work")


# ───────────────────── pipeline_description / profile.name ──────────────────


@pytest.mark.parametrize(
    "ch",
    [
        DANGEROUS_BACKSLASH,
        DANGEROUS_DOUBLE_QUOTE,
        DANGEROUS_SINGLE_QUOTE,
        DANGEROUS_DOLLAR,
        DANGEROUS_SEMICOLON,
        DANGEROUS_BACKTICK,
        DANGEROUS_NEWLINE,
    ],
)
def test_pipeline_description_rejects_dangerous_chars(ch):
    bad = f"A test pipeline{ch}with payload"
    with pytest.raises(ValueError):
        validate_groovy_safe(bad, field_name="pipeline_description")


@pytest.mark.parametrize(
    "ch",
    [
        DANGEROUS_BACKSLASH,
        DANGEROUS_DOUBLE_QUOTE,
        DANGEROUS_SINGLE_QUOTE,
        DANGEROUS_DOLLAR,
        DANGEROUS_SEMICOLON,
        DANGEROUS_BACKTICK,
        DANGEROUS_NEWLINE,
    ],
)
def test_profile_name_rejects_dangerous_chars(ch):
    bad = f"prod-profile{ch}injected"
    with pytest.raises(ValueError):
        validate_groovy_safe(bad, field_name="profile.name")


def test_validate_groovy_safe_passes_through_none():
    """Optional fields land here as None; pass through unchanged."""
    assert validate_groovy_safe(None, field_name="optional") is None


def test_validate_groovy_safe_rejects_control_character():
    """Defense in depth: bytes below 0x20 (other than tab) are
    rejected even though they aren't in the explicit Groovy danger
    set, since they could disrupt log parsers / consumers."""
    bad = f"foo{chr(0x07)}bar"  # bell
    with pytest.raises(ValueError):
        validate_groovy_safe(bad, field_name="profile.name")
