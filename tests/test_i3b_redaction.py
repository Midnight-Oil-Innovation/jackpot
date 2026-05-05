"""I-3b: credential-value redaction for execution logs.

The redaction layer is defense-in-depth. The Seqsender config file
already lives outside the working directory, so credential values
shouldn't appear in subprocess output — but if they ever do (because
of a Seqsender bug, or a future executor that's less disciplined),
this module catches them before the log is persisted.
"""

from __future__ import annotations

from backend.submission_executors.redaction import (
    REDACTED,
    redact_credential_values,
    redact_credential_values_bytes,
)


def test_empty_credential_list_returns_input_unchanged():
    text = "hello world"
    assert redact_credential_values(text, []) == text


def test_single_value_replaced():
    out = redact_credential_values("password is hunter2 and that's it", ["hunter2"])
    assert "hunter2" not in out
    assert REDACTED in out


def test_value_not_present_input_unchanged():
    text = "no credentials here"
    assert redact_credential_values(text, ["hunter2"]) == text


def test_overlapping_values_longest_first():
    """If both 'foo' and 'foobar' are credentials, a naive left-to-right
    pass over 'foobar' would replace 'foo' first and leave 'bar'.
    Sorting longest-first prevents that."""
    out = redact_credential_values("foobar", ["foo", "foobar"])
    assert out == REDACTED
    assert "bar" not in out


def test_multiple_values_all_replaced():
    out = redact_credential_values(
        "user=admin password=hunter2 token=abc123",
        ["admin", "hunter2", "abc123"],
    )
    for v in ("admin", "hunter2", "abc123"):
        assert v not in out
    assert out.count(REDACTED) == 3


def test_empty_string_in_values_skipped():
    """Replacing the empty string with anything would explode every
    output. Empties must be skipped."""
    out = redact_credential_values("normal text", ["", "secret"])
    assert out == "normal text"


def test_value_appears_multiple_times_all_replaced():
    out = redact_credential_values("hunter2 and again hunter2 here", ["hunter2"])
    assert "hunter2" not in out
    assert out.count(REDACTED) == 2


def test_bytes_variant_basic():
    out = redact_credential_values_bytes(b"password=hunter2 ok", ["hunter2"])
    assert isinstance(out, bytes)
    assert b"hunter2" not in out
    assert REDACTED.encode() in out


def test_bytes_variant_tolerates_invalid_utf8():
    """Subprocess stdout occasionally contains non-UTF-8 bytes (binary
    progress chars, broken locales, etc.). The bytes variant must not
    raise on those — errors='replace' on decode."""
    invalid = b"\xff\xfe\xfd hunter2 \xc3\x28"
    out = redact_credential_values_bytes(invalid, ["hunter2"])
    assert b"hunter2" not in out
    # Round-trip succeeded; that's the contract.
    assert isinstance(out, bytes)


def test_substring_within_word_redacted():
    """Redaction is value-level, not word-level. If a credential value
    happens to be a substring of a longer word in stdout, redact it.
    The redaction is operational hygiene, not lexical analysis."""
    out = redact_credential_values("prefix-secret-suffix", ["secret"])
    assert "secret" not in out
    assert REDACTED in out


def test_unicode_credential_value():
    out = redact_credential_values("token=zażółć and gęślą", ["zażółć"])
    assert "zażółć" not in out
    assert REDACTED in out
