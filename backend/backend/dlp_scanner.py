"""
JACKPOT Cloud DLP metadata scanner.

Scans free-text metadata fields for PII before database commit.
Uses Google Cloud DLP API to detect person names, email addresses,
phone numbers, SSNs, MRNs, and other sensitive identifiers.

Single-sample scans are synchronous (~200-500ms).
Batch CSV scans concatenate all rows into one API call for efficiency.

Local dev: DLP_ENABLED=false (default) returns CLEAN immediately.
Production: calls GCP Cloud DLP API.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from google.api_core.exceptions import BadRequest, InvalidArgument
from jackpot_schema import SCHEMA_JSON_PATH as SCHEMA_PATH

logger = logging.getLogger(__name__)

# DLP infoTypes to detect
SCAN_INFO_TYPES = [
    "PERSON_NAME",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "US_SOCIAL_SECURITY_NUMBER",
    "US_INDIVIDUAL_TAXPAYER_IDENTIFICATION_NUMBER",
    "MEDICAL_RECORD_NUMBER",
    "US_DRIVERS_LICENSE_NUMBER",
    "STREET_ADDRESS",
    "DATE_OF_BIRTH",
    "CREDIT_CARD_NUMBER",
]

# Minimum confidence to trigger a finding
MIN_LIKELIHOOD = "LIKELY"

# Fields where specific infoTypes are expected and should be skipped
FIELD_EXCEPTIONS: dict[str, list[str]] = {
    "pi_name": ["PERSON_NAME"],
}

LIKELIHOOD_ORDER = [
    "VERY_UNLIKELY",
    "UNLIKELY",
    "POSSIBLE",
    "LIKELY",
    "VERY_LIKELY",
]


@dataclass
class DLPFinding:
    """A single PII finding in a metadata field."""

    field_name: str
    info_type: str
    likelihood: str
    matched_text: str  # redacted to first/last char only for audit
    quote_offset: int


@dataclass
class DLPScanResult:
    """Result of scanning one sample's metadata."""

    clean: bool
    findings: list[DLPFinding] = field(default_factory=list)
    error: str | None = None
    scan_time_ms: float = 0.0
    #: Set only when ``error`` is set: True when retrying this row cannot
    #: help, because what Cloud DLP refused is the row itself. Callers
    #: that queue on the error (``run_pii_scan_job``) need the exception
    #: *type* to tell an outage from a bad payload, and ``error`` is
    #: ``str(e)`` with the type already thrown away. See issue #263.
    permanent: bool = False


def _get_free_text_fields() -> set[str]:
    """
    Parse JSON Schema to find all string fields not backed by an enum.
    Returns set of field names that should be DLP-scanned.
    """
    if not SCHEMA_PATH.exists():
        logger.warning("Schema file not found at %s, using empty field set", SCHEMA_PATH)
        return set()

    schema = json.loads(SCHEMA_PATH.read_text())

    enum_fields: set[str] = set()
    free_text_fields: set[str] = set()

    for _class_name, class_def in schema.get("$defs", {}).items():
        if "properties" not in class_def:
            continue
        for field_name, field_def in class_def["properties"].items():
            if "$ref" in field_def:
                enum_fields.add(field_name)
            elif field_def.get("type") == "string":
                free_text_fields.add(field_name)

    return free_text_fields - enum_fields


_FREE_TEXT_FIELDS: set[str] | None = None


def get_scannable_fields() -> set[str]:
    """Return cached set of free-text field names."""
    global _FREE_TEXT_FIELDS  # noqa: PLW0603
    if _FREE_TEXT_FIELDS is None:
        _FREE_TEXT_FIELDS = _get_free_text_fields()
    return _FREE_TEXT_FIELDS


def _build_content_item(
    sample: dict[str, Any],
    scannable_fields: set[str],
) -> tuple[str, dict[str, tuple[int, int]]]:
    """
    Build a single content string from all free-text fields.
    Returns the content string and a mapping of field_name -> (start, end)
    UTF-8 byte offsets so findings can be mapped back to specific fields.

    The offsets MUST be byte offsets, not character offsets: Cloud DLP
    reports findings at `location.byte_range`, which counts UTF-8 bytes.
    A character-based table drifts behind the byte offsets by one per
    continuation byte, so a finding near the end of one field lands in
    the next field's range — which silently grants it that field's
    FIELD_EXCEPTIONS entry and drops the finding.
    """
    parts: list[str] = []
    field_offsets: dict[str, tuple[int, int]] = {}
    cursor = 0

    for field_name in sorted(scannable_fields):
        value = sample.get(field_name)
        if value is None or not isinstance(value, str) or not value.strip():
            continue

        chunk = f"[{field_name}]: {value}\n"
        start = cursor
        cursor += len(chunk.encode("utf-8"))
        field_offsets[field_name] = (start, cursor)
        parts.append(chunk)

    return "".join(parts), field_offsets


def _offset_to_field(
    offset: int,
    field_offsets: dict[str, tuple[int, int]],
) -> str:
    """Map a UTF-8 byte offset back to the field name it came from."""
    for field_name, (start, end) in field_offsets.items():
        if start <= offset < end:
            return field_name
    return "unknown"


def _redact_matched_text(text: str) -> str:
    """
    Redact matched text for audit logging.
    Keep first and last character, replace middle with asterisks.
    'John Smith' -> 'J********h'
    """
    if len(text) <= 2:
        return "*" * len(text)
    return text[0] + "*" * (len(text) - 2) + text[-1]


def _is_permanent_error(exc: Exception) -> bool:
    """True when re-running this scan unchanged would fail the same way.

    Deliberately one status code. ``INVALID_ARGUMENT`` is Cloud DLP
    rejecting the request it was given -- an oversized or otherwise
    unacceptable payload -- and once ``scan_sample_metadata`` has
    established that its own half of the request is well formed, what is
    left of it is this one sample's fields. Everything else is the
    service or the deployment: ``UNAVAILABLE`` and ``RESOURCE_EXHAUSTED``
    clear on their own, ``PERMISSION_DENIED`` and a missing client
    library clear when an operator fixes them, and all of them affect
    every row equally. Calling one of those permanent writes FAILED on
    samples nothing ever looked at, and FAILED only comes back out of an
    edit to the sample.

    Both spellings of a 400 are named. The DLP client is gRPC, which
    raises ``InvalidArgument``; ``from_http_status(400)`` raises plain
    ``BadRequest``, so a future REST transport would otherwise silently
    restore the head-block with no test going red. ``BadRequest``'s
    other subclasses are matched by name rather than by isinstance:
    ``FailedPrecondition`` is a 400 about system state ("DLP API not
    enabled"), which is the whole deployment, not one row.
    """
    return isinstance(exc, InvalidArgument) or type(exc) is BadRequest


def _is_exception(field_name: str, info_type: str) -> bool:
    """Check if this infoType is expected for this field."""
    exceptions = FIELD_EXCEPTIONS.get(field_name, [])
    return info_type in exceptions


def _likelihood_meets_threshold(likelihood: str) -> bool:
    """Check if the finding likelihood meets our minimum threshold."""
    try:
        return LIKELIHOOD_ORDER.index(likelihood) >= LIKELIHOOD_ORDER.index(MIN_LIKELIHOOD)
    except ValueError:
        return False


def scan_sample_metadata(sample: dict[str, Any], timeout: float | None = None) -> DLPScanResult:
    """
    Scan a single sample's metadata for PII using Cloud DLP.

    In local dev (DLP_ENABLED=false), returns CLEAN immediately.
    In production, calls the Cloud DLP API.

    ``timeout`` bounds the Cloud DLP call in seconds. Callers working to a
    wall-clock budget (``run_pii_scan_job``) pass what is left of it; None
    leaves the client library's own default in place.
    """
    from backend.config import get_settings

    start = time.monotonic()
    settings = get_settings()

    if not settings.dlp_enabled:
        return DLPScanResult(clean=True, scan_time_ms=0.0)

    if not settings.gcp_project_id:
        # Without it the request carries parent="projects//locations/global"
        # and Cloud DLP answers INVALID_ARGUMENT -- for every row, on a
        # misconfiguration that has nothing to do with any of them. The
        # classifier below would read that as the sample's fault and the
        # job would write FAILED across the whole backlog, which is
        # terminal. gcp_project_id is only required when env == "gcp"
        # (config.validate_for_production), so a scenario A or B operator
        # who turns DLP_ENABLED on is one env var away from this.
        return DLPScanResult(
            clean=False,
            error="DLP_ENABLED is set but gcp_project_id is not configured",
            scan_time_ms=(time.monotonic() - start) * 1000,
        )

    scannable = get_scannable_fields()
    content, field_offsets = _build_content_item(sample, scannable)

    if not content.strip():
        return DLPScanResult(clean=True, scan_time_ms=0.0)

    try:
        import google.cloud.dlp_v2 as dlp
        from google.api_core import gapic_v1

        client = dlp.DlpServiceClient()
        parent = f"projects/{settings.gcp_project_id}/locations/global"

        inspect_config = dlp.InspectConfig(
            info_types=[dlp.InfoType(name=it) for it in SCAN_INFO_TYPES],
            min_likelihood=dlp.Likelihood[MIN_LIKELIHOOD],
            include_quote=True,
            limits=dlp.InspectConfig.FindingLimits(
                max_findings_per_request=25,
            ),
        )

        item = dlp.ContentItem(value=content)

        response = client.inspect_content(
            request={
                "parent": parent,
                "inspect_config": inspect_config,
                "item": item,
            },
            # DEFAULT rather than None: None means "no deadline at all" to
            # the client library, which is the opposite of what a caller
            # who passed nothing wants.
            timeout=gapic_v1.method.DEFAULT if timeout is None else timeout,
        )

        findings: list[DLPFinding] = []
        for finding in response.result.findings:
            field_name = _offset_to_field(
                finding.location.byte_range.start,
                field_offsets,
            )
            info_type = finding.info_type.name
            likelihood = finding.likelihood.name

            if _is_exception(field_name, info_type):
                continue

            if not _likelihood_meets_threshold(likelihood):
                continue

            findings.append(
                DLPFinding(
                    field_name=field_name,
                    info_type=info_type,
                    likelihood=likelihood,
                    matched_text=_redact_matched_text(finding.quote or ""),
                    quote_offset=finding.location.byte_range.start,
                )
            )

        elapsed = (time.monotonic() - start) * 1000
        return DLPScanResult(
            clean=len(findings) == 0,
            findings=findings,
            scan_time_ms=elapsed,
        )

    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        logger.error("DLP scan failed: %s", e)
        return DLPScanResult(
            clean=False,
            error=str(e),
            permanent=_is_permanent_error(e),
            scan_time_ms=elapsed,
        )


def scan_batch_metadata(
    samples: list[dict[str, Any]],
) -> dict[str, DLPScanResult]:
    """
    Scan multiple samples for PII.
    Returns dict of sample_id -> DLPScanResult.
    """
    from backend.config import get_settings

    settings = get_settings()
    if not settings.dlp_enabled:
        return {
            s.get("sample_id", f"row_{i}"): DLPScanResult(clean=True) for i, s in enumerate(samples)
        }

    results: dict[str, DLPScanResult] = {}
    for sample in samples:
        sid = sample.get("sample_id", "unknown")
        results[sid] = scan_sample_metadata(sample)
    return results
