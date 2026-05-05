# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Credential-value redaction for execution logs.

Two layers of protection apply to backend-execution logs:

1. The Seqsender config file lives outside the per-execution working
   directory, so credential values are never written anywhere
   Seqsender's stdout / stderr can transitively re-read them.
2. Captured stdout / stderr is filtered through this module before
   being written to the log file. Any byte sequence that matches a
   known credential value is replaced with ``***REDACTED***``.

Layer 2 is defense in depth; it protects against:
  - Seqsender accidentally echoing credentials in error messages
  - Future code changes that route credential strings through stdout
  - Unknown future executors that don't follow Seqsender's discipline

This is operational hygiene — not a security boundary. A determined
attacker with code execution could still leak credentials. The point
is to make ordinary log retention safe.
"""

from __future__ import annotations

REDACTED = "***REDACTED***"


def redact_credential_values(text: str, credential_values: list[str]) -> str:
    """Replace every occurrence of any credential value with ``REDACTED``.

    Sorts ``credential_values`` by length, longest first, before
    replacement so that overlapping values do not produce partial-replace
    anomalies (e.g. if both ``"foo"`` and ``"foobar"`` are credentials,
    a naive left-to-right pass over ``"foobar"`` would replace ``foo``
    first and leave a stray ``bar``).

    Empty strings are skipped. Replacing the empty string with anything
    produces nonsense (every gap between characters matches), so we
    guard against that explicitly.
    """
    if not credential_values:
        return text
    values = sorted(
        (v for v in credential_values if v),
        key=len,
        reverse=True,
    )
    out = text
    for v in values:
        out = out.replace(v, REDACTED)
    return out


def redact_credential_values_bytes(data: bytes, credential_values: list[str]) -> bytes:
    """Byte-level variant of :func:`redact_credential_values`.

    Decodes the input as UTF-8 with ``errors="replace"`` so non-UTF-8
    bytes in subprocess output are tolerated rather than raising. Re-encodes
    the redacted text as UTF-8.
    """
    text = data.decode("utf-8", errors="replace")
    return redact_credential_values(text, credential_values).encode("utf-8")
