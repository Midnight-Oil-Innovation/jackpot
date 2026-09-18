# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Critical Rule 43: a PII-flagged sample is not pipeline input.

The scan half shipped in #262 and sets ``pii_scan_status``; these cover
what the flag now costs a sample at the pipeline boundary.
"""

from __future__ import annotations

from backend.pipeline_config import compute_pipeline_compatibility

_CATALOG: dict = {"compatibility_rules": {}}


def _sample(pii_scan_status: str, sample_id: str = "EXAMPLE-2026-001") -> dict:
    return {
        "sample_id": sample_id,
        "source_type": "Human",
        "scrub_status": "COMPLETE",
        "quality_status": "SUBMITTABLE",
        "organism_name": "Severe acute respiratory syndrome coronavirus 2",
        "pii_scan_status": pii_scan_status,
    }


def test_a_flagged_sample_is_hard_blocked_by_an_empty_rule_set() -> None:
    """The catalog entry opts into nothing; the block lands anyway.

    Unlike ``required_scrub``, this is not a per-pipeline preference. A
    catalog with no compatibility_rules at all is the case that proves it
    — every other check in this module is inert for that input.
    """
    report = compute_pipeline_compatibility(_CATALOG, [_sample("PII_DETECTED")])

    assert report.is_hard_blocked
    assert [b["sample_id"] for b in report.hard_blocks] == ["EXAMPLE-2026-001"]
    assert "PII" in report.hard_blocks[0]["reason"]
    assert not report.soft_warnings


def test_a_scanned_clean_sample_is_not_blocked() -> None:
    report = compute_pipeline_compatibility(_CATALOG, [_sample("COMPLETE")])

    assert not report.is_hard_blocked


def test_an_unscanned_sample_is_not_blocked() -> None:
    """PENDING must not block, and the reason is availability.

    ``run_pii_scan_job`` leaves rows PENDING for the duration of a Cloud
    DLP outage. Blocking on PENDING would make every launch in the
    platform contingent on a Google API being up.
    """
    report = compute_pipeline_compatibility(_CATALOG, [_sample("PENDING")])

    assert not report.is_hard_blocked


def test_only_the_flagged_sample_of_a_batch_is_blocked() -> None:
    report = compute_pipeline_compatibility(
        _CATALOG,
        [_sample("COMPLETE", "CLEAN-1"), _sample("PII_DETECTED", "FLAGGED-1")],
    )

    assert [b["sample_id"] for b in report.hard_blocks] == ["FLAGGED-1"]


def test_an_overridden_sample_is_not_blocked() -> None:
    """The payoff half of the Lab Director override (cab9f75533cb).

    ``POST /api/v1/samples/{id}/pii-override`` writes ``OVERRIDDEN`` rather
    than ``COMPLETE`` so the audit trail can distinguish "the scanner found
    nothing" from "a person decided what it found is releasable". That only
    unblocks anything because every Rule 43 gate tests ``== 'PII_DETECTED'``
    — a claim about the other end of the contract, so it is asserted here
    rather than inferred from the route's 200.
    """
    report = compute_pipeline_compatibility(_CATALOG, [_sample("OVERRIDDEN")])

    assert not report.is_hard_blocked
