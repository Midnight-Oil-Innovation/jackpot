"""Pipeline ↔ sample compatibility evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompatibilityReport:
    soft_warnings: list[dict[str, Any]] = field(default_factory=list)
    hard_blocks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_hard_blocked(self) -> bool:
        return bool(self.hard_blocks)

    @property
    def has_warnings(self) -> bool:
        return bool(self.soft_warnings)

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        return {"soft_warnings": self.soft_warnings, "hard_blocks": self.hard_blocks}


def _parse_compatibility_rules(catalog_row: dict[str, Any]) -> dict[str, Any]:
    rules = catalog_row.get("compatibility_rules") or {}
    if isinstance(rules, str):
        # JSONB may round-trip as a string in some drivers; best-effort parse
        try:
            rules = json.loads(rules)
        except (ValueError, TypeError):
            rules = {}
    return rules


def _check_source_type(
    sid: str, source_type: str, allowed_sources: list[str] | None
) -> dict | None:
    if allowed_sources and source_type and source_type not in allowed_sources:
        return {
            "sample_id": sid,
            "reason": (
                f"Pipeline accepts source_type in {allowed_sources}, but sample is {source_type!r}."
            ),
        }
    return None


def _check_scrub_status(sid: str, scrub_status: str, require_scrub: bool) -> dict | None:
    if require_scrub and scrub_status and scrub_status not in ("COMPLETE", "SKIPPED"):
        return {
            "sample_id": sid,
            "reason": (
                f"Pipeline requires scrubbed reads but sample scrub_status is {scrub_status!r}."
            ),
        }
    return None


def _check_pii_scan_status(sid: str, pii_scan_status: str) -> dict | None:
    """Block a flagged sample from pipeline input (Critical Rule 43).

    Unconditional, unlike ``_check_scrub_status`` above: scrubbing is a
    per-pipeline requirement a catalog entry opts into, while PII in the
    metadata is a property of the sample that no pipeline is entitled to
    consume. PENDING is deliberately not blocked -- ``run_pii_scan_job``
    leaves rows there during a Cloud DLP outage, and refusing every launch
    for the duration would make the scanner's availability the platform's
    availability.
    """
    if pii_scan_status == "PII_DETECTED":
        return {
            "sample_id": sid,
            "reason": (
                "Sample metadata was flagged for PII by the DLP scan. Fix the "
                "flagged fields or obtain a Lab Director override before using "
                "it as pipeline input."
            ),
        }
    return None


def _check_quality_tier(
    sid: str, quality_status: str, min_quality: str | None, tier_rank: dict[str, int]
) -> dict | None:
    if (
        min_quality
        and quality_status in tier_rank
        and min_quality in tier_rank
        and tier_rank[quality_status] < tier_rank[min_quality]
    ):
        return {
            "sample_id": sid,
            "reason": (
                f"Sample quality_status {quality_status!r} is below "
                f"pipeline minimum {min_quality!r}."
            ),
        }
    return None


def _check_organism(sid: str, organism: str, allowed_organisms: list[str] | None) -> dict | None:
    if allowed_organisms and organism and organism not in allowed_organisms:
        return {
            "sample_id": sid,
            "reason": f"Pipeline targets {allowed_organisms}, but sample organism is {organism!r}.",
        }
    return None


def _evaluate_sample(
    sample: dict[str, Any],
    *,
    allowed_sources: list[str] | None,
    require_scrub: bool,
    min_quality: str | None,
    allowed_organisms: list[str] | None,
    tier_rank: dict[str, int],
) -> tuple[list[dict], list[dict]]:
    """Run every compatibility rule against one sample.

    Returns (hard_blocks, soft_warnings) — each a list of 0-2 dicts.
    """
    sid = sample.get("sample_id") or str(sample.get("id") or "?")
    source_type = (sample.get("source_type") or "").strip()
    scrub_status = (sample.get("scrub_status") or "").strip()
    pii_scan_status = (sample.get("pii_scan_status") or "").strip()
    quality_status = (sample.get("quality_status") or "").strip()
    organism = (sample.get("organism_name") or "").strip()

    hard_blocks = [
        b
        for b in (
            _check_source_type(sid, source_type, allowed_sources),
            _check_scrub_status(sid, scrub_status, require_scrub),
            _check_pii_scan_status(sid, pii_scan_status),
        )
        if b
    ]
    soft_warnings = [
        w
        for w in (
            _check_quality_tier(sid, quality_status, min_quality, tier_rank),
            _check_organism(sid, organism, allowed_organisms),
        )
        if w
    ]
    return hard_blocks, soft_warnings


def compute_pipeline_compatibility(
    catalog_row: dict[str, Any],
    samples: list[dict[str, Any]],
) -> CompatibilityReport:
    """
    Apply pipeline_catalog.compatibility_rules against supplied samples.

    Supported rule keys (all optional):
      * ``source_types``         → hard-block samples whose source_type is not in the list
      * ``required_scrub``       → hard-block samples with scrub_status != 'COMPLETE'
      * ``min_quality_status``   → soft-warn samples below the listed tier
      * ``organisms``            → soft-warn samples whose organism_name is not in the list

    Unknown keys are ignored. ``rules`` may be missing or an empty dict —
    in that case every sample is compatible with no warnings, except for the
    PII check, which is not rule-driven: a sample flagged by the DLP scan is
    hard-blocked whatever the catalog entry says (Critical Rule 43).
    """
    report = CompatibilityReport()
    rules = _parse_compatibility_rules(catalog_row)
    tier_rank = {"PRELIMINARY": 1, "ANALYZABLE": 2, "SUBMITTABLE": 3}

    for sample in samples:
        hard_blocks, soft_warnings = _evaluate_sample(
            sample,
            allowed_sources=rules.get("source_types"),
            require_scrub=bool(rules.get("required_scrub")),
            min_quality=rules.get("min_quality_status"),
            allowed_organisms=rules.get("organisms"),
            tier_rank=tier_rank,
        )
        report.hard_blocks.extend(hard_blocks)
        report.soft_warnings.extend(soft_warnings)

    return report
