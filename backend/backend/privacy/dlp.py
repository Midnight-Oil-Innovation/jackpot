"""GCP Cloud DLP scanner - metadata PII gate.

Wraps and consolidates the existing dlp_scanner.py. Track 1 - call-through
to existing prod code; Track 2 hook seam for DP-noise overlay on findings
counts (so audit logs leak less information about scanned content volume).

The DLP gate runs at metadata write time on free-text fields not in
FIELD_EXCEPTIONS, with LIKELY threshold on Cloud DLP findings. The
DLP_ENABLED=false bypass is preserved for local dev and laptop deployment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from backend.privacy._ais_hooks import AISPrivacyHooks, NullAISPrivacyHooks


@dataclass
class DLPFinding:
    """One PII detection in a scanned field.

    Note: `quote` is the offending substring at scan time but should be
    redacted before persisting to audit logs (full content includes the
    PII we're trying to keep out of the database).
    """

    field_path: str
    info_type: str  # GCP DLP info type identifier (EMAIL_ADDRESS, etc.)
    likelihood: str  # POSSIBLE, LIKELY, VERY_LIKELY
    quote: str
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class DLPScanner:
    """Wraps GCP Cloud DLP for metadata-PII scanning.

    Track 1 - wraps existing backend.helpers.dlp_scanner functions; the
    existing field exception list and LIKELY threshold are preserved.

    Track 2 hook seam: future overlays can use the configured hooks to
    apply DP noise to aggregate finding counts before audit logging
    (preserves utility of "we scanned N records, M had findings"-style
    metrics without leaking exact counts that could enable tracing).
    """

    def __init__(
        self,
        enabled: bool | None = None,
        field_exceptions: list[str] | None = None,
        likelihood_threshold: str = "LIKELY",
        hooks: AISPrivacyHooks | None = None,
    ) -> None:
        if enabled is None:
            enabled = os.getenv("DLP_ENABLED", "false").lower() == "true"
        self.enabled = enabled
        self.field_exceptions = field_exceptions or self._default_exceptions()
        self.likelihood_threshold = likelihood_threshold
        self.hooks: AISPrivacyHooks = hooks or NullAISPrivacyHooks()

    @staticmethod
    def _default_exceptions() -> list[str]:
        """Fields where PII is expected by schema design.

        TODO(privacy-scaffold): import the canonical list from
        backend.helpers.dlp_scanner.FIELD_EXCEPTIONS rather than duplicating.
        """
        return [
            "submitter_email",
            "originating_lab_contact",
            "uploader_name",
        ]

    def scan_metadata(
        self,
        record: dict[str, Any],
    ) -> list[DLPFinding]:
        """Scan all free-text fields in `record`, return findings.

        Skips fields in self.field_exceptions. Returns empty list when
        self.enabled is False (laptop / local dev path).

        TODO(privacy-scaffold): delegate to existing scan_metadata() in
        backend.helpers.dlp_scanner once aligned.
        """
        if not self.enabled:
            return []
        findings: list[DLPFinding] = []
        # Delegated implementation calls existing scanner; placeholder body:
        for field_path, value in record.items():
            if field_path in self.field_exceptions:
                continue
            if not isinstance(value, str):
                continue
            # Real impl: cloud DLP API call here, via existing helper.
        return findings

    def scan_text_field(
        self,
        field_path: str,
        text: str,
    ) -> list[DLPFinding]:
        """Scan a single free-text field. Used by per-field validators.

        TODO(privacy-scaffold): delegate to existing per-field scanner.
        """
        if not self.enabled:
            return []
        if field_path in self.field_exceptions:
            return []
        return []

    def register_field_exception(self, field_path: str) -> None:
        """Add a runtime exception for a field that legitimately contains PII.

        TODO(privacy-scaffold): persist via backend.helpers.dlp_scanner if
        runtime registration is supported there; otherwise document as
        configure-time only and remove this method.
        """
        if field_path not in self.field_exceptions:
            self.field_exceptions.append(field_path)
