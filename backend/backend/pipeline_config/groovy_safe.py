"""R-1 #7 — defense against Groovy code injection in rendered configs.

The profile renderer interpolates pipeline catalog and profile fields
(``pipeline_name``, ``pipeline_description``, ``work_dir``,
``profile.name``, etc.) into a Nextflow ``.config`` file that
Nextflow's Groovy parser evaluates at launch time. A value containing
a Groovy string-terminator character followed by a function invocation
breaks out of the intended string context and gets executed as code.

This module provides two related defenses:

1. :func:`groovy_escape` — a Jinja2 filter applied at render time to
   every catalog/profile field interpolation. Escapes characters
   dangerous in both single- and double-quoted Groovy string contexts.
2. :func:`validate_groovy_safe` — a write-time validator callable from
   Pydantic ``field_validator`` hooks (or any other pre-DB-write check)
   that rejects values containing the same dangerous characters.

Both ship together. Validation catches new bad values before they
land in the database; the render-time filter is the universal defense
against any value that pre-dated the validator.

Dangerous character set (rationale per char):

- backslash (``\\``): begins an escape sequence in any Groovy string
- double-quote (``"``): terminates a Groovy GString
- single-quote (``'``): terminates a Groovy literal string
- dollar-sign (``$``): triggers Groovy GString interpolation
- semicolon (``;``): statement separator — the canonical breakout
- backtick (`` ` ``): used in some Groovy versions for shell exec
- newline / carriage return: terminates single-line literal strings,
  enables multi-statement injection
"""

from __future__ import annotations

# Character set rejected by ``validate_groovy_safe``. Order is the same
# as the ``groovy_escape`` replacement order (backslash first so we
# don't double-escape). Plus general C0 control characters: any byte
# below 0x20 except the explicitly allowed tab is rejected.
_DANGEROUS_GROOVY_CHARS: tuple[str, ...] = (
    "\\",
    '"',
    "'",
    "$",
    ";",
    "`",
    "\n",
    "\r",
)


def groovy_escape(value: str | None) -> str:
    """Escape ``value`` for safe inclusion in any Groovy string literal.

    Designed to be used as a Jinja2 filter. The replacement order is
    significant: backslash MUST be first or the escape characters
    introduced by the other replacements would themselves be
    re-escaped on the next pass.
    """
    if value is None:
        return ""
    return (
        value.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace('"', '\\"')
        .replace("$", "\\$")
        .replace("`", "\\`")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def validate_groovy_safe(value: str | None, *, field_name: str) -> str | None:
    """Reject ``value`` if it contains any character dangerous in
    Groovy string contexts. Returns the value untouched on success.

    Designed for use inside Pydantic ``field_validator`` hooks. The
    error message names the field but does not echo the offending
    character (a generic message is sufficient for the user; the
    audit trail can capture specifics from the request log).
    """
    if value is None:
        return None
    for ch in _DANGEROUS_GROOVY_CHARS:
        if ch in value:
            raise ValueError(
                f"{field_name} contains a character not permitted in "
                "pipeline configuration. Allowed: letters, digits, "
                "spaces, hyphen, underscore, period, slash."
            )
    # Reject general C0 control characters except tab. \n and \r are
    # already covered above; this catches the rest of the < 0x20 range.
    for ch in value:
        if ch < " " and ch != "\t":
            raise ValueError(
                f"{field_name} contains a control character not "
                "permitted in pipeline configuration."
            )
    return value
