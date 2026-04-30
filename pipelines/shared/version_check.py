"""
Shared pipeline-version validation used by every jackpot-nf wrapper
at run start.

Per spec.md §Version pinning:

    Each parser declares ``SUPPORTED_PIPELINE_VERSIONS: list[str]``.
    Wrapper validates pipeline version at run start, emits warning
    to ``pipeline_events`` if unsupported, continues anyway
    (doesn't hard-block).

This module is the single implementation of that "validate + warn"
step.  Wrappers call :func:`check_pipeline_version` after
constructing :class:`RunMetadata` and before invoking the parser —
a mismatch produces a ``VersionCheckResult`` whose ``is_supported``
flag is False and whose ``warning_message`` is ready to post to
``pipeline_events`` via the register client.

The function is intentionally side-effect free: it *builds* the
warning message but does not post it.  The caller owns the HTTP
transport so tests can exercise the check logic without mocking
the network.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class VersionCheckResult:
    """Outcome of a :func:`check_pipeline_version` call.

    Attributes:
        is_supported: True when ``pipeline_version`` appears in the
            parser's ``SUPPORTED_PIPELINE_VERSIONS`` list.
        pipeline_name: Echoed from the caller — useful for log lines.
        pipeline_version: Version the wrapper was asked to parse.
        supported_versions: Snapshot of the parser's allowlist at
            call time.  Makes the warning event self-describing.
        warning_message: Human-readable explanation, or ``None``
            when ``is_supported`` is True.  Safe to drop into a
            ``pipeline_events`` payload ``message`` field.
    """

    is_supported: bool
    pipeline_name: str
    pipeline_version: str
    supported_versions: tuple[str, ...]
    warning_message: str | None


def check_pipeline_version(
    pipeline_name: str,
    pipeline_version: str,
    supported_versions: Iterable[str],
) -> VersionCheckResult:
    """Validate ``pipeline_version`` against a parser's allowlist.

    The check is exact-string — no semver range resolution.  The spec
    defines ``SUPPORTED_PIPELINE_VERSIONS`` as an enumerated list,
    and bactopia/Grandeur/etc. tag releases with strings that do not
    always parse as semver (e.g. Cecret tags '3.66', viralrecon tags
    '2.6' and '2.6.0' as distinct releases).  Exact match keeps the
    behaviour obvious at the cost of a little maintenance — the
    parser authors are the source of truth for the list.
    """
    allow = tuple(supported_versions)
    if pipeline_version in allow:
        return VersionCheckResult(
            is_supported=True,
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            supported_versions=allow,
            warning_message=None,
        )
    message = (
        f"Pipeline version {pipeline_version!r} for {pipeline_name!r} is not in "
        f"the parser's SUPPORTED_PIPELINE_VERSIONS list "
        f"({', '.join(allow) if allow else '<empty>'}). "
        "Parsing will continue, but output field coverage may be incomplete — "
        "update the parser or pin the pipeline to a supported release."
    )
    return VersionCheckResult(
        is_supported=False,
        pipeline_name=pipeline_name,
        pipeline_version=pipeline_version,
        supported_versions=allow,
        warning_message=message,
    )


__all__ = ["VersionCheckResult", "check_pipeline_version"]
