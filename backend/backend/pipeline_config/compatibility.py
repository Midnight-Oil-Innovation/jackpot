"""Pipeline ↔ sample compatibility evaluation."""

from __future__ import annotations

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
    in that case every sample is compatible with no warnings.
    """
    report = CompatibilityReport()
    rules = catalog_row.get("compatibility_rules") or {}
    if isinstance(rules, str):
        # JSONB may round-trip as a string in some drivers; best-effort parse
        import json

        try:
            rules = json.loads(rules)
        except (ValueError, TypeError):
            rules = {}

    allowed_sources: list[str] | None = rules.get("source_types")
    require_scrub: bool = bool(rules.get("required_scrub"))
    min_quality: str | None = rules.get("min_quality_status")
    allowed_organisms: list[str] | None = rules.get("organisms")

    tier_rank = {"PRELIMINARY": 1, "ANALYZABLE": 2, "SUBMITTABLE": 3}

    for sample in samples:
        sid = sample.get("sample_id") or str(sample.get("id") or "?")
        source_type = (sample.get("source_type") or "").strip()
        scrub_status = (sample.get("scrub_status") or "").strip()
        quality_status = (sample.get("quality_status") or "").strip()
        organism = (sample.get("organism_name") or "").strip()

        if allowed_sources and source_type and source_type not in allowed_sources:
            report.hard_blocks.append(
                {
                    "sample_id": sid,
                    "reason": (
                        f"Pipeline accepts source_type in {allowed_sources}, "
                        f"but sample is {source_type!r}."
                    ),
                }
            )

        if require_scrub and scrub_status and scrub_status not in ("COMPLETE", "SKIPPED"):
            report.hard_blocks.append(
                {
                    "sample_id": sid,
                    "reason": (
                        "Pipeline requires scrubbed reads "
                        f"but sample scrub_status is {scrub_status!r}."
                    ),
                }
            )

        if (
            min_quality
            and quality_status in tier_rank
            and min_quality in tier_rank
            and tier_rank[quality_status] < tier_rank[min_quality]
        ):
            report.soft_warnings.append(
                {
                    "sample_id": sid,
                    "reason": (
                        f"Sample quality_status {quality_status!r} is below "
                        f"pipeline minimum {min_quality!r}."
                    ),
                }
            )

        if allowed_organisms and organism and organism not in allowed_organisms:
            report.soft_warnings.append(
                {
                    "sample_id": sid,
                    "reason": (
                        f"Pipeline targets {allowed_organisms}, "
                        f"but sample organism is {organism!r}."
                    ),
                }
            )

    return report
