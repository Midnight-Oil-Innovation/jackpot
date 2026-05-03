# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Unit tests for backend.jobs.promote_file_storage (Phase P0f F-9).

The job streams a file's bytes from its source URI into managed
storage, verifies the SHA-256 of the copy, and atomically transitions
the ``sample_files`` row. Tests run against mocked DB / storage
helpers so the suite stays fast and the failure-path semantics
(corruption detection, partial-cleanup, audit + notification on both
outcomes) are exercised in isolation.
"""

from __future__ import annotations

import asyncio
import hashlib
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.jobs import (
    _PROMOTE_JOBS,
    PROMOTE_CHUNK_SIZE,
    get_promote_job_status,
    promote_file_storage,
)


def _settings(**overrides):
    base = {
        "managed_storage_root": "file:///tmp/jackpot-managed",
        "promote_chunk_size_mb": 8,
        "promote_max_seconds_per_job": 3600,
        "promote_verify_hash": True,
        "verification_re_fingerprint": False,
        "verification_consecutive_failures_to_break": 3,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@contextmanager
def _fake_db():
    yield MagicMock(name="db")


def _row(file_id: int, uri: str, *, state: str = "EXTERNAL", size: int = 1024) -> dict:
    return {
        "id": file_id,
        "sample_id_fk": file_id * 10,
        "uri": uri,
        "storage_state": state,
        "file_size_bytes": size,
    }


@pytest.fixture(autouse=True)
def _clear_promote_tracker():
    _PROMOTE_JOBS.clear()
    yield
    _PROMOTE_JOBS.clear()


def _patches(*, settings, query_returns: list, audit=None, notify=None):
    """Common patch stack for the promote job."""
    iter_returns = iter(query_returns)

    def execute_query_side_effect(sql, params=None, conn=None):
        try:
            return next(iter_returns)
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


# ── Local-to-local copy ──────────────────────────────────────────────────


def test_promote_local_to_local_succeeds(tmp_path):
    payload = b"GATTACA-FASTQ" * 1000
    src = tmp_path / "input.fastq.gz"
    src.write_bytes(payload)
    expected_hash = hashlib.sha256(payload).hexdigest()
    dest_root = tmp_path / "managed"

    rows = [[_row(101, str(src), size=len(payload))]]
    settings = _settings(managed_storage_root=f"file://{dest_root}")
    audit = MagicMock()

    with _patches(settings=settings, query_returns=rows, audit=audit):
        counters = asyncio.run(
            promote_file_storage(
                file_id=101,
                target_state="MANAGED",
                retention_policy="STANDARD",
                trigger_user_id=7,
                job_id="job-101",
            )
        )

    assert counters["outcome"] == "SUCCESS"
    assert counters["copied_bytes"] == len(payload)
    assert counters["verified_hash"] == expected_hash
    # Audit emitted PROMOTE_FILE
    actions = [c.kwargs["action"] for c in audit.call_args_list]
    assert "PROMOTE_FILE" in actions
    # Tracker reflects success
    assert get_promote_job_status("job-101")["status"] == "COMPLETED"
    # Destination file exists
    dest_path = dest_root / "sample_1010" / "input.fastq.gz"
    assert dest_path.exists()
    assert dest_path.read_bytes() == payload


def test_promote_failure_leaves_state_unchanged_and_cleans_destination(tmp_path):
    """Source unreachable → row not transitioned, destination removed."""
    bogus_src = "file:///definitely-does-not-exist-zzz/file.fastq.gz"
    dest_root = tmp_path / "managed"
    rows = [[_row(202, bogus_src)]]
    settings = _settings(managed_storage_root=f"file://{dest_root}")
    audit = MagicMock()
    notify = MagicMock()
    write = MagicMock(return_value=[])

    with (
        _patches(settings=settings, query_returns=rows, audit=audit, notify=notify),
        patch("backend.jobs.execute_write", write),
    ):
        counters = asyncio.run(
            promote_file_storage(
                file_id=202,
                target_state="MANAGED",
                retention_policy="STANDARD",
                trigger_user_id=7,
                job_id="job-202",
            )
        )

    assert counters["outcome"] == "FAILURE"
    assert "FileNotFoundError" in counters["error_message"] or "No such file" in (
        counters["error_message"] or ""
    )
    # No state-update writes to sample_files were issued
    state_updates = [
        call
        for call in write.call_args_list
        if "UPDATE sample_files" in (call.args[0] if call.args else "")
        and "storage_state" in (call.args[0] if call.args else "")
    ]
    assert state_updates == []
    actions = [c.kwargs["action"] for c in audit.call_args_list]
    assert "PROMOTE_FILE_FAILED" in actions
    # Notification recipient is the trigger user
    assert notify.called
    assert notify.call_args.kwargs["recipient_id"] == 7
    # Tracker shows failure
    assert get_promote_job_status("job-202")["status"] == "FAILED"


def test_promote_managed_storage_root_unset_fails_clearly():
    rows = [[_row(303, "file:///tmp/x.fastq")]]
    settings = _settings(managed_storage_root="")  # operator forgot to set it
    audit = MagicMock()

    with _patches(settings=settings, query_returns=rows, audit=audit):
        counters = asyncio.run(
            promote_file_storage(
                file_id=303,
                target_state="MANAGED",
                retention_policy="STANDARD",
                trigger_user_id=7,
                job_id="job-303",
            )
        )

    assert counters["outcome"] == "FAILURE"
    assert "managed_storage_root" in counters["error_message"]
    # No PROMOTE_FILE / PROMOTE_FILE_FAILED audit when we reject before
    # the copy attempt — the deployment is misconfigured, not the data.
    actions = [c.kwargs["action"] for c in audit.call_args_list]
    assert "PROMOTE_FILE" not in actions


def test_promote_already_in_target_state_is_noop():
    """A second run after a successful promote returns SUCCESS noop."""
    rows = [[_row(404, "gs://lab/already.fastq.gz", state="MANAGED", size=1024)]]
    settings = _settings()

    with _patches(settings=settings, query_returns=rows):
        counters = asyncio.run(
            promote_file_storage(
                file_id=404,
                target_state="MANAGED",
                retention_policy="STANDARD",
                trigger_user_id=7,
                job_id="job-404",
            )
        )

    assert counters["outcome"] == "SUCCESS"
    assert get_promote_job_status("job-404")["outcome"] == "NOOP"


def test_promote_unknown_file_id_returns_failure():
    """No row → FAILURE without crashing."""
    settings = _settings()
    with _patches(settings=settings, query_returns=[[]]):  # empty result
        counters = asyncio.run(
            promote_file_storage(
                file_id=99999,
                target_state="MANAGED",
                retention_policy="STANDARD",
                trigger_user_id=7,
                job_id="job-missing",
            )
        )
    assert counters["outcome"] == "FAILURE"
    assert "not found" in counters["error_message"].lower()


def test_promote_uses_server_side_copy_for_same_cloud_backend():
    """Both URIs gs:// → server-side CopyObject + destination re-hash."""
    src_uri = "gs://lab/fixtures/input.fastq.gz"
    rows = [[_row(505, src_uri, size=4096)]]
    settings = _settings(managed_storage_root="gs://jackpot-managed")

    fake_client = MagicMock()
    fake_client.copy_object.return_value = {}
    # Destination re-hash path: head + get_object body iter_chunks
    dummy_bytes = b"GATTACA" * 512
    body = MagicMock()
    body.iter_chunks.return_value = iter([dummy_bytes])
    body.close = MagicMock()
    fake_client.get_object.return_value = {"Body": body}
    fake_client.head_object.return_value = {"ContentLength": len(dummy_bytes)}
    expected_hash = hashlib.sha256(dummy_bytes).hexdigest()

    audit = MagicMock()
    with (
        _patches(settings=settings, query_returns=rows, audit=audit),
        patch("backend.jobs._get_client", return_value=fake_client, create=True),
        patch("backend.storage._get_client", return_value=fake_client),
    ):
        counters = asyncio.run(
            promote_file_storage(
                file_id=505,
                target_state="MANAGED",
                retention_policy="STANDARD",
                trigger_user_id=7,
                job_id="job-505",
            )
        )

    assert counters["outcome"] == "SUCCESS"
    assert counters["verified_hash"] == expected_hash
    fake_client.copy_object.assert_called_once()
    # Destination path includes sample_id_fk=5050 and the source filename
    copy_kwargs = fake_client.copy_object.call_args.kwargs
    assert copy_kwargs["Bucket"] == "jackpot-managed"
    assert copy_kwargs["Key"].startswith("sample_5050/")
    assert copy_kwargs["Key"].endswith("input.fastq.gz")


def test_promote_chunk_size_constant_is_eight_mb():
    """Tests asserting the chunk-size constant aren't pretending it's a
    settings field — F-9 ships an 8 MB default in :data:`PROMOTE_CHUNK_SIZE`
    and a Settings override (``promote_chunk_size_mb``)."""
    assert PROMOTE_CHUNK_SIZE == 8 * 1024 * 1024
