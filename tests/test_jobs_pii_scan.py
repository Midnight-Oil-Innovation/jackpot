# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Unit tests for backend.jobs.run_pii_scan_job (Critical Rule 43).

The job is the missing production call site for ``backend/dlp_scanner.py``
(issue #261): ingest sets ``pii_scan_status = 'PENDING'`` and, before this,
nothing moved a row off it.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.dlp_scanner import DLPFinding, DLPScanResult
from backend.jobs import run_pii_scan_job

ROW = {"id": 7, "sample_id": "EXAMPLE-2026-001", "comments": "call Jane Roe"}


def _settings(dlp_enabled: bool = True, budget_seconds: int = 600):
    # Only the two fields the job itself reads. ``pii_scan_interval_seconds``
    # is main.py's business.
    return SimpleNamespace(
        dlp_enabled=dlp_enabled,
        pii_scan_max_seconds_per_tick=budget_seconds,
    )


def _counters(**overrides):
    base = {"scanned": 0, "flagged": 0, "errors": 0, "skipped": 0, "raced": 0}
    base.update(overrides)
    return base


@contextmanager
def _patches(*, scan_result, dlp_enabled=True, budget_seconds=600, updated_rows=None):
    """Patch the job's module-level collaborators, yielding them by name.

    ``patch.multiple`` only hands back the mocks it created itself, so the
    stubs are built here and yielded explicitly.
    """
    mocks = {
        "get_settings": MagicMock(return_value=_settings(dlp_enabled, budget_seconds)),
        "execute_query": MagicMock(return_value=[ROW]),
        # The UPDATE carries RETURNING id; an empty list is the "some
        # other tick already decided this row" case.
        "execute_write": MagicMock(
            return_value=[{"id": ROW["id"]}] if updated_rows is None else updated_rows
        ),
        # A bare MagicMock already implements the context-manager protocol,
        # which is all ``with get_db() as db:`` needs here.
        "get_db": MagicMock(),
        "log_audit": MagicMock(),
        "scan_sample_metadata": MagicMock(return_value=scan_result),
    }
    with patch.multiple("backend.jobs", **mocks):
        yield mocks


def test_a_dlp_outage_leaves_the_row_pending() -> None:
    """An API failure must not be read as "PII found".

    ``scan_sample_metadata`` reports its own exceptions as
    ``DLPScanResult(clean=False, error=...)``. A job that branches on
    ``clean`` alone marks every sample PII_DETECTED for the duration of a
    Cloud DLP outage -- the state Rule 43 wants queries, pipelines and
    export blocked on, once something enforces it. The row has to stay
    PENDING and be retried.
    """
    outage = DLPScanResult(clean=False, error="503 Service Unavailable")
    with _patches(scan_result=outage) as mocks:
        counters = asyncio.run(run_pii_scan_job())

    # Load-bearing, and the anti-vacuity guard: the stub is reachable only
    # through the patch, so a scan that never ran would give errors=0 here
    # and pass every "no write happened" assertion below for the wrong
    # reason.
    mocks["scan_sample_metadata"].assert_called_once_with(ROW)
    assert counters == _counters(errors=1)
    mocks["execute_write"].assert_not_called()
    mocks["log_audit"].assert_not_called()


def test_findings_flag_the_sample_and_write_an_audit_row() -> None:
    """A real finding writes PII_DETECTED and records which field tripped."""
    finding = DLPFinding(
        field_name="comments",
        info_type="PERSON_NAME",
        likelihood="VERY_LIKELY",
        matched_text="J******e",
        quote_offset=5,
    )
    with _patches(scan_result=DLPScanResult(clean=False, findings=[finding])) as mocks:
        counters = asyncio.run(run_pii_scan_job())

    assert counters == _counters(scanned=1, flagged=1)
    sql, params = mocks["execute_write"].call_args.args[:2]
    assert params == {"status": "PII_DETECTED", "id": 7}
    # The docstring's idempotency claim rests on this clause and nothing
    # else asserts it: a row that has already left PENDING must not be
    # overwritten by a tick that raced it.
    assert "pii_scan_status = 'PENDING'" in sql
    # Same shape, and the only thing that can pin RETURNING at this seam:
    # execute_write is a stub, so a dropped RETURNING still hands back the
    # stubbed rows and every behavioural assertion keeps passing.
    assert "RETURNING id" in sql

    audit_kwargs = mocks["log_audit"].call_args.kwargs
    assert audit_kwargs["action"] == "PII_SCAN_FLAGGED"
    assert audit_kwargs["resource_id"] == "7"
    assert audit_kwargs["metadata"]["findings"] == [
        {"field_name": "comments", "info_type": "PERSON_NAME", "likelihood": "VERY_LIKELY"}
    ]
    # The redacted quote is still derived from the PII and is not needed to
    # act on the finding, so it must not reach the audit log.
    assert "J******e" not in str(audit_kwargs["metadata"])


def test_a_clean_scan_completes_the_row() -> None:
    with _patches(scan_result=DLPScanResult(clean=True)) as mocks:
        counters = asyncio.run(run_pii_scan_job())

    assert counters == _counters(scanned=1)
    params = mocks["execute_write"].call_args.args[1]
    assert params == {"status": "COMPLETE", "id": 7}
    mocks["log_audit"].assert_not_called()


def test_the_job_is_a_no_op_while_dlp_is_disabled() -> None:
    """DLP_ENABLED=false must leave rows PENDING, not mark them COMPLETE.

    The scanner short-circuits to ``clean=True`` when DLP is off. Running
    the loop anyway would durably record "scanned, no PII" for samples
    nothing looked at, and they would never be re-selected once an operator
    enabled DLP.
    """
    with _patches(scan_result=DLPScanResult(clean=True), dlp_enabled=False) as mocks:
        counters = asyncio.run(run_pii_scan_job())

    assert counters == _counters()
    mocks["execute_query"].assert_not_called()
    mocks["scan_sample_metadata"].assert_not_called()
    mocks["execute_write"].assert_not_called()


def test_rows_past_the_wall_clock_budget_are_left_for_the_next_tick() -> None:
    """The budget bounds the tick; unscanned rows stay PENDING, not COMPLETE."""
    with _patches(scan_result=DLPScanResult(clean=True), budget_seconds=0) as mocks:
        counters = asyncio.run(run_pii_scan_job())

    assert counters == _counters(skipped=1)
    mocks["scan_sample_metadata"].assert_not_called()
    mocks["execute_write"].assert_not_called()


def test_a_row_decided_by_another_tick_is_not_audited_again() -> None:
    """No UPDATE, no audit row.

    The UPDATE is conditional on the row still being PENDING, so a racing
    scheduler tick or a manual trigger makes it a no-op. Writing
    "PENDING -> PII_DETECTED" to the audit log for a write that did not
    happen would record something that never occurred.
    """
    finding = DLPFinding(
        field_name="comments",
        info_type="PERSON_NAME",
        likelihood="VERY_LIKELY",
        matched_text="J******e",
        quote_offset=5,
    )
    with _patches(
        scan_result=DLPScanResult(clean=False, findings=[finding]),
        updated_rows=[],
    ) as mocks:
        counters = asyncio.run(run_pii_scan_job())

    assert counters == _counters(raced=1)
    mocks["execute_write"].assert_called_once()
    mocks["log_audit"].assert_not_called()
