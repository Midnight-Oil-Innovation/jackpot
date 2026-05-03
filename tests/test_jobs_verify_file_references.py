# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Unit tests for backend.jobs.verify_file_references (Phase P0f F-5).

The job is the safety net for the no-copy ingest model: re-stat
EXTERNAL/MIRRORED files, transition to BROKEN after three consecutive
failures, audit + notify lab directors on transition. Tests run against
mocked DB / storage helpers so the suite stays fast (no testcontainer)
and the failure-counting state machine is exercised in isolation.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.jobs import (
    _lab_directors_for_sample_file,
    _next_failure_status,
    _parse_failure_count,
    verify_file_references,
)


def _settings(**overrides):
    base = {
        "verification_interval_seconds": 86400,
        "verification_files_per_tick": 100,
        "verification_consecutive_failures_to_break": 3,
        "verification_re_fingerprint": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@contextmanager
def _fake_db():
    """get_db() context manager stand-in."""
    yield MagicMock(name="db")


def _patches(
    *,
    rows: list[dict],
    settings,
    audit=None,
    notify=None,
    extra_query_returns: list | None = None,
):
    """Common patch stack. ``extra_query_returns`` lets a test drive
    the secondary execute_query calls used by the lab-director lookup;
    each entry is the return value for one *additional* call after the
    initial row-selection query."""

    extra_iter = iter(extra_query_returns or [])
    select_calls = {"n": 0}

    def execute_query_side_effect(sql, params=None, conn=None):
        select_calls["n"] += 1
        if select_calls["n"] == 1:
            return rows
        try:
            return next(extra_iter)
        except StopIteration:
            return []

    return patch.multiple(
        "backend.jobs",
        get_settings=MagicMock(return_value=settings),
        execute_query=MagicMock(side_effect=execute_query_side_effect),
        execute_write=MagicMock(return_value=[]),
        get_db=MagicMock(side_effect=_fake_db),
        log_audit=audit if audit is not None else MagicMock(),
        create_notification=notify if notify is not None else MagicMock(),
    )


def _row(
    file_id: int,
    uri: str,
    *,
    size: int | None = None,
    head: str | None = None,
    tail: str | None = None,
    status: str | None = None,
    state: str = "EXTERNAL",
) -> dict:
    return {
        "id": file_id,
        "uri": uri,
        "file_size_bytes": size,
        "head64k_hash": head,
        "tail64k_hash": tail,
        "last_verification_status": status,
        "storage_state": state,
    }


# ─── Helpers ───────────────────────────────────────────────────────────────


def test_parse_failure_count_handles_all_shapes():
    assert _parse_failure_count(None) == 0
    assert _parse_failure_count("OK") == 0
    assert _parse_failure_count("MISSING") == 1
    assert _parse_failure_count("READ_ERROR") == 1
    assert _parse_failure_count("MISSING_2") == 2
    assert _parse_failure_count("READ_ERROR_3") == 3


def test_next_failure_status_first_failure():
    assert _next_failure_status(None, "MISSING") == ("MISSING", 1)
    assert _next_failure_status("OK", "READ_ERROR") == ("READ_ERROR", 1)


def test_next_failure_status_increments_kind_can_change():
    """Consecutive non-OK statuses count up regardless of kind change.

    The reported kind is always the most recent: a row that read-errored
    twice and then went MISSING reports MISSING_3 — operators see the
    fresh failure mode, not the historical one.
    """
    assert _next_failure_status("MISSING", "MISSING") == ("MISSING_2", 2)
    assert _next_failure_status("MISSING", "READ_ERROR") == ("READ_ERROR_2", 2)
    assert _next_failure_status("READ_ERROR_2", "MISSING") == ("MISSING_3", 3)


def test_next_failure_status_caps_at_three():
    assert _next_failure_status("MISSING_3", "MISSING") == ("MISSING_3", 3)


def test_next_failure_status_rejects_unknown_kind():
    with pytest.raises(ValueError):
        _next_failure_status(None, "BOGUS")


# ─── OK path ───────────────────────────────────────────────────────────────


def test_verify_local_file_ok(tmp_path):
    """Existing file with matching size becomes OK; state unchanged."""
    f = tmp_path / "ok.fastq"
    f.write_bytes(b"x" * 256)
    rows = [_row(1, str(f), size=256)]

    write_mock = MagicMock(return_value=[])
    audit = MagicMock()
    notify = MagicMock()

    with (
        _patches(rows=rows, settings=_settings(), audit=audit, notify=notify),
        patch("backend.jobs.execute_write", write_mock),
    ):
        counters = asyncio.run(verify_file_references())

    assert counters == {
        "verified_ok": 1,
        "verification_failed": 0,
        "transitioned_to_broken": 0,
        "skipped": 0,
    }
    sql, params = write_mock.call_args_list[0].args
    assert "last_verification_status = 'OK'" in sql
    assert params == {"id": 1}
    audit.assert_not_called()
    notify.assert_not_called()


# ─── First-strike failure ──────────────────────────────────────────────────


def test_verify_local_file_missing_first_time(tmp_path):
    """Missing file on first verification: status MISSING, state stays EXTERNAL."""
    rows = [_row(1, str(tmp_path / "gone.fastq"), size=10, status=None)]

    write_mock = MagicMock(return_value=[])
    audit = MagicMock()
    notify = MagicMock()

    with (
        _patches(rows=rows, settings=_settings(), audit=audit, notify=notify),
        patch("backend.jobs.execute_write", write_mock),
    ):
        counters = asyncio.run(verify_file_references())

    assert counters["verification_failed"] == 1
    assert counters["transitioned_to_broken"] == 0
    sql, params = write_mock.call_args_list[0].args
    assert "storage_state" not in sql  # no state change yet
    assert params["status"] == "MISSING"

    # Per-failure audit, no transition audit.
    actions = [c.kwargs.get("action") for c in audit.call_args_list]
    assert actions == ["VERIFY_FILE_FAILED"]
    notify.assert_not_called()


# ─── Three-strike transition ───────────────────────────────────────────────


def test_verify_local_file_missing_three_times_transitions_to_broken(tmp_path):
    """A row that already failed twice: third tick transitions to BROKEN."""
    rows = [_row(7, str(tmp_path / "gone.fastq"), size=10, status="MISSING_2")]

    write_mock = MagicMock(return_value=[])
    audit = MagicMock()
    notify = MagicMock()
    # Lab directors lookup returns one user.
    extra = [[{"user_id": 42}]]

    with (
        _patches(
            rows=rows,
            settings=_settings(),
            audit=audit,
            notify=notify,
            extra_query_returns=extra,
        ),
        patch("backend.jobs.execute_write", write_mock),
    ):
        counters = asyncio.run(verify_file_references())

    assert counters["transitioned_to_broken"] == 1
    sql, params = write_mock.call_args_list[0].args
    assert "storage_state = 'BROKEN'" in sql
    assert params["status"] == "MISSING_3"

    actions = [c.kwargs.get("action") for c in audit.call_args_list]
    assert "VERIFY_FILE_FAILED" in actions
    assert "MARK_FILE_BROKEN" in actions

    # Lab director was notified.
    notify.assert_called_once()
    assert notify.call_args.kwargs["recipient_id"] == 42
    assert notify.call_args.kwargs["event_type"] == "FILE_REFERENCE_BROKEN"


# ─── SIZE_CHANGED ──────────────────────────────────────────────────────────


def test_verify_local_file_size_changed(tmp_path):
    """File's size differs from recorded → status SIZE_CHANGED."""
    f = tmp_path / "shrunk.fastq"
    f.write_bytes(b"x" * 100)  # actual = 100
    rows = [_row(1, str(f), size=500, status=None)]  # recorded = 500

    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
    ):
        counters = asyncio.run(verify_file_references())

    assert counters["verification_failed"] == 1
    assert write_mock.call_args_list[0].args[1]["status"] == "SIZE_CHANGED"


# ─── Recovery resets the counter ───────────────────────────────────────────


def test_verify_recovery_resets_failure_count(tmp_path):
    """Previously MISSING_2 row whose URI now resolves cleanly resets to OK."""
    f = tmp_path / "back.fastq"
    f.write_bytes(b"y" * 50)
    rows = [_row(1, str(f), size=50, status="MISSING_2")]

    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
    ):
        counters = asyncio.run(verify_file_references())

    assert counters == {
        "verified_ok": 1,
        "verification_failed": 0,
        "transitioned_to_broken": 0,
        "skipped": 0,
    }
    sql = write_mock.call_args_list[0].args[0]
    assert "last_verification_status = 'OK'" in sql


# ─── State filtering ───────────────────────────────────────────────────────


def test_verify_skips_managed_and_broken_via_where_clause():
    """The SQL row-selector restricts to EXTERNAL/MIRRORED only — MANAGED,
    STAGED, and BROKEN rows are never selected. Verifies the WHERE clause
    rather than testing each excluded state separately."""
    captured: list[str] = []

    def execute_query_capture(sql, params=None, conn=None):
        captured.append(sql)
        return []

    with patch.multiple(
        "backend.jobs",
        get_settings=MagicMock(return_value=_settings()),
        execute_query=MagicMock(side_effect=execute_query_capture),
        execute_write=MagicMock(return_value=[]),
        get_db=MagicMock(side_effect=_fake_db),
    ):
        asyncio.run(verify_file_references())

    assert "storage_state IN ('EXTERNAL', 'MIRRORED')" in captured[0]
    assert "is_deleted" in captured[0]


# ─── Per-tick limit ────────────────────────────────────────────────────────


def test_verify_respects_files_per_tick():
    """The LIMIT placeholder gets the configured per-tick value."""
    captured_params: list[dict] = []

    def execute_query_capture(sql, params=None, conn=None):
        captured_params.append(params or {})
        return []

    with patch.multiple(
        "backend.jobs",
        get_settings=MagicMock(return_value=_settings(verification_files_per_tick=7)),
        execute_query=MagicMock(side_effect=execute_query_capture),
        execute_write=MagicMock(return_value=[]),
        get_db=MagicMock(side_effect=_fake_db),
    ):
        asyncio.run(verify_file_references())

    assert captured_params[0]["limit"] == 7


# ─── Ordering ──────────────────────────────────────────────────────────────


def test_verify_orders_by_last_verified_at_nulls_first():
    captured_sql: list[str] = []

    def execute_query_capture(sql, params=None, conn=None):
        captured_sql.append(sql)
        return []

    with patch.multiple(
        "backend.jobs",
        get_settings=MagicMock(return_value=_settings()),
        execute_query=MagicMock(side_effect=execute_query_capture),
        execute_write=MagicMock(return_value=[]),
        get_db=MagicMock(side_effect=_fake_db),
    ):
        asyncio.run(verify_file_references())

    assert "ORDER BY last_verified_at ASC NULLS FIRST" in captured_sql[0]


# ─── Re-fingerprint catches content drift ──────────────────────────────────


def test_verify_re_fingerprint_detects_content_drift(tmp_path):
    """Same file size, but cheap fingerprint differs from recorded values."""
    f = tmp_path / "drifted.fastq"
    payload = b"different content but same length" * 40  # fixed length
    f.write_bytes(payload)
    rows = [
        _row(
            1,
            str(f),
            size=len(payload),
            head="stale_head_hash",
            tail="stale_tail_hash",
            status=None,
        )
    ]

    write_mock = MagicMock(return_value=[])

    with (
        _patches(
            rows=rows,
            settings=_settings(verification_re_fingerprint=True),
        ),
        patch("backend.jobs.execute_write", write_mock),
    ):
        counters = asyncio.run(verify_file_references())

    assert counters["verification_failed"] == 1
    assert write_mock.call_args_list[0].args[1]["status"] == "SIZE_CHANGED"


def test_verify_re_fingerprint_off_by_default(tmp_path):
    """With verification_re_fingerprint=False (default), drift is invisible."""
    f = tmp_path / "drifted.fastq"
    payload = b"some content" * 40
    f.write_bytes(payload)
    rows = [
        _row(
            1,
            str(f),
            size=len(payload),
            head="stale_head_hash",
            tail="stale_tail_hash",
        )
    ]

    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
    ):
        counters = asyncio.run(verify_file_references())

    # Default skips re-fingerprinting; size matches → OK.
    assert counters["verified_ok"] == 1


# ─── Audit + notification on break ─────────────────────────────────────────


def test_verify_creates_audit_log_on_break(tmp_path):
    """MARK_FILE_BROKEN audit row written when a row transitions."""
    rows = [_row(99, str(tmp_path / "gone.fq"), size=10, status="READ_ERROR_2")]
    audit = MagicMock()
    extra = [[{"user_id": 1}]]

    with _patches(
        rows=rows,
        settings=_settings(),
        audit=audit,
        extra_query_returns=extra,
    ):
        asyncio.run(verify_file_references())

    actions = [c.kwargs.get("action") for c in audit.call_args_list]
    assert "MARK_FILE_BROKEN" in actions
    mark_call = next(
        c for c in audit.call_args_list if c.kwargs.get("action") == "MARK_FILE_BROKEN"
    )
    assert mark_call.kwargs["after"] == {"storage_state": "BROKEN"}
    assert mark_call.kwargs["resource_id"] == "99"


def test_verify_notifies_all_lab_directors_on_break(tmp_path):
    """Every distinct lab-director user_id returned by the lookup gets one notification."""
    rows = [_row(50, str(tmp_path / "gone.fq"), size=20, status="MISSING_2")]
    notify = MagicMock()
    extra = [[{"user_id": 11}, {"user_id": 22}, {"user_id": 33}]]

    with _patches(
        rows=rows,
        settings=_settings(),
        notify=notify,
        extra_query_returns=extra,
    ):
        asyncio.run(verify_file_references())

    recipients = sorted(c.kwargs["recipient_id"] for c in notify.call_args_list)
    assert recipients == [11, 22, 33]
    assert all(c.kwargs["event_type"] == "FILE_REFERENCE_BROKEN" for c in notify.call_args_list)
    # URI is included in the notification body so the operator can identify the file.
    body = notify.call_args_list[0].kwargs["body"]
    assert "gone.fq" in body or str(rows[0]["uri"]) in body


# ─── Orphan rows ───────────────────────────────────────────────────────────


def test_verify_handles_orphan_sample_files_row(tmp_path, caplog):
    """No live samples reference the row → BROKEN transition still happens,
    no notifications, WARNING logged."""
    rows = [_row(7, str(tmp_path / "x.fq"), size=100, status="MISSING_2")]
    audit = MagicMock()
    notify = MagicMock()
    extra = [[]]  # no lab directors

    with (
        caplog.at_level("WARNING", logger="backend.jobs"),
        _patches(
            rows=rows,
            settings=_settings(),
            audit=audit,
            notify=notify,
            extra_query_returns=extra,
        ),
    ):
        counters = asyncio.run(verify_file_references())

    assert counters["transitioned_to_broken"] == 1
    notify.assert_not_called()
    actions = [c.kwargs.get("action") for c in audit.call_args_list]
    assert "MARK_FILE_BROKEN" in actions
    assert any("orphan" in r.message.lower() for r in caplog.records)


# ─── Remote URI ────────────────────────────────────────────────────────────


def test_verify_handles_remote_gs_uri():
    """gs:// rows route through backend.storage._get_client.head_object."""
    rows = [_row(1, "gs://bkt/key.fq", size=2048)]

    head_mock = MagicMock(return_value={"ContentLength": 2048})
    client = MagicMock(head_object=head_mock)

    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
        patch("backend.storage._get_client", return_value=client),
    ):
        counters = asyncio.run(verify_file_references())

    assert counters == {
        "verified_ok": 1,
        "verification_failed": 0,
        "transitioned_to_broken": 0,
        "skipped": 0,
    }
    head_mock.assert_called_once_with(Bucket="bkt", Key="key.fq")


def test_verify_remote_size_mismatch_triggers_size_changed():
    rows = [_row(1, "gs://bkt/key.fq", size=999)]
    head_mock = MagicMock(return_value={"ContentLength": 1000})
    client = MagicMock(head_object=head_mock)
    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
        patch("backend.storage._get_client", return_value=client),
    ):
        asyncio.run(verify_file_references())

    assert write_mock.call_args_list[0].args[1]["status"] == "SIZE_CHANGED"


def test_verify_remote_404_maps_to_missing():
    """boto3 ClientError with NoSuchKey/404 → FileNotFoundError → MISSING."""
    from botocore.exceptions import ClientError

    rows = [_row(1, "s3://bkt/missing.fq", size=100)]
    err = ClientError(
        {
            "Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."},
            "ResponseMetadata": {"HTTPStatusCode": 404},
        },
        "HeadObject",
    )
    client = MagicMock()
    client.head_object.side_effect = err
    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
        patch("backend.storage._get_client", return_value=client),
    ):
        counters = asyncio.run(verify_file_references())

    assert counters["verification_failed"] == 1
    assert write_mock.call_args_list[0].args[1]["status"] == "MISSING"


def test_verify_remote_other_client_error_is_read_error():
    """Non-404 ClientError → categorized as READ_ERROR, not MISSING."""
    from botocore.exceptions import ClientError

    rows = [_row(1, "gs://bkt/x.fq", size=100)]
    err = ClientError(
        {
            "Error": {"Code": "AccessDenied", "Message": "Access denied"},
            "ResponseMetadata": {"HTTPStatusCode": 403},
        },
        "HeadObject",
    )
    client = MagicMock()
    client.head_object.side_effect = err
    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
        patch("backend.storage._get_client", return_value=client),
    ):
        asyncio.run(verify_file_references())

    assert write_mock.call_args_list[0].args[1]["status"] == "READ_ERROR"


def test_verify_http_uri_via_httpx():
    """http(s):// rows route through httpx HEAD; Content-Length used as size."""

    class _Resp:
        status_code = 200
        headers = {"Content-Length": "1024"}

        def raise_for_status(self):
            return None

    class _ClientCtx:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def head(self, uri):
            return _Resp()

    rows = [_row(1, "https://example.com/data.fastq", size=1024)]
    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
        patch("httpx.Client", return_value=_ClientCtx()),
    ):
        counters = asyncio.run(verify_file_references())

    assert counters["verified_ok"] == 1


def test_verify_http_404_maps_to_missing():
    class _Resp:
        status_code = 404
        headers: dict = {}

        def raise_for_status(self):
            raise AssertionError("should not be called when 404 short-circuits")

    class _ClientCtx:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def head(self, uri):
            return _Resp()

    rows = [_row(1, "https://example.com/gone.fastq", size=10)]
    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
        patch("httpx.Client", return_value=_ClientCtx()),
    ):
        asyncio.run(verify_file_references())

    assert write_mock.call_args_list[0].args[1]["status"] == "MISSING"


def test_verify_re_fingerprint_raises_is_read_error(tmp_path):
    """re_fingerprint=True; cheap_fingerprint blows up → READ_ERROR."""
    f = tmp_path / "x.fq"
    f.write_bytes(b"a" * 100)
    rows = [_row(1, str(f), size=100, head="h", tail="t")]
    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings(verification_re_fingerprint=True)),
        patch("backend.jobs.execute_write", write_mock),
        patch(
            "backend.jobs.cheap_fingerprint",
            side_effect=RuntimeError("range request failed"),
        ),
    ):
        asyncio.run(verify_file_references())

    assert write_mock.call_args_list[0].args[1]["status"] == "READ_ERROR"


def test_verify_sra_uri_treated_as_size_unknown():
    """sra:// URIs return None for size → no SIZE_CHANGED, status=OK."""
    rows = [_row(1, "sra://SRR12345", size=None)]
    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
    ):
        counters = asyncio.run(verify_file_references())

    assert counters["verified_ok"] == 1


def test_verify_unsupported_scheme_is_read_error():
    """ftp:// or similar → ValueError → READ_ERROR (categorized as transient)."""
    rows = [_row(1, "ftp://example.com/foo.fq", size=10)]
    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
    ):
        asyncio.run(verify_file_references())

    assert write_mock.call_args_list[0].args[1]["status"] == "READ_ERROR"


# ─── Permission denied counts as READ_ERROR ────────────────────────────────


def test_verify_permission_denied_is_read_error(tmp_path):
    """Locked file → PermissionError → READ_ERROR (not MISSING)."""
    f = tmp_path / "locked.fq"
    f.write_bytes(b"secret")
    f.chmod(0o000)
    rows = [_row(1, str(f), size=6)]
    write_mock = MagicMock(return_value=[])

    try:
        with (
            _patches(rows=rows, settings=_settings()),
            patch("backend.jobs.execute_write", write_mock),
        ):
            counters = asyncio.run(verify_file_references())
    finally:
        f.chmod(0o600)

    # On macOS/Linux the permission-locked stat may still succeed (stat()
    # only needs +x on the parent dir). Either outcome is fine — we just
    # verify the failure code, when present, is READ_ERROR rather than
    # MISSING.
    if counters["verified_ok"] == 0:
        assert counters["verification_failed"] == 1
        status = write_mock.call_args_list[0].args[1]["status"]
        assert status.startswith("READ_ERROR") or status == "READ_ERROR"


# ─── Empty-table no-op ─────────────────────────────────────────────────────


def test_verify_returns_zero_counters_when_no_rows():
    with _patches(rows=[], settings=_settings()):
        counters = asyncio.run(verify_file_references())
    assert counters == {
        "verified_ok": 0,
        "verification_failed": 0,
        "transitioned_to_broken": 0,
        "skipped": 0,
    }


# ─── Lab director lookup ───────────────────────────────────────────────────


def test_lab_directors_for_sample_file_query_shape():
    """The lookup joins sample_files → samples → lab_membership and
    filters by is_lab_director, deleting soft-deleted samples."""
    captured_sql: list[str] = []
    captured_params: list[dict] = []

    def execute_query_capture(sql, params=None, conn=None):
        captured_sql.append(sql)
        captured_params.append(params or {})
        return [{"user_id": 5}, {"user_id": 7}]

    db = MagicMock(name="db")
    with patch("backend.jobs.execute_query", side_effect=execute_query_capture):
        ids = _lab_directors_for_sample_file(123, db)

    assert ids == [5, 7]
    assert "JOIN samples s" in captured_sql[0]
    assert "is_deleted = FALSE" in captured_sql[0]
    assert "is_lab_director = TRUE" in captured_sql[0]
    assert captured_params[0] == {"sfid": 123}


# ─── Module sanity ─────────────────────────────────────────────────────────


def test_verify_file_references_is_async():
    import asyncio as _asyncio

    assert _asyncio.iscoroutinefunction(verify_file_references)
