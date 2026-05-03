# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Unit tests for backend.jobs.compute_full_content_hash (Phase P0f F-4)."""

from __future__ import annotations

import asyncio
import hashlib
import io
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.jobs import FULL_HASH_CHUNK_SIZE, compute_full_content_hash


def _settings(**overrides):
    base = {
        "full_hash_interval_seconds": 300,
        "full_hash_max_seconds_per_tick": 1800,
        "compute_sra_full_hash": False,
        "skip_remote_full_hash": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@contextmanager
def _fake_db():
    """get_db() context manager stand-in. The body just needs an object."""
    yield MagicMock(name="db")


def _patches(
    *,
    rows: list[dict],
    settings,
    execute_query_extra=None,
    audit=None,
):
    """Common patch stack for the F-4 job.

    ``execute_query_extra`` is a callable returning the next collision-lookup
    result list per call (for tests that need to drive the second
    ``execute_query`` call — the inner collision lookup).
    """
    select_calls = {"n": 0}

    def execute_query_side_effect(sql, params=None, conn=None):
        select_calls["n"] += 1
        # First call is always the row-selection query; subsequent calls
        # are collision lookups inside the per-row loop.
        if select_calls["n"] == 1:
            return rows
        if execute_query_extra is None:
            return []
        return execute_query_extra(select_calls["n"] - 1)

    return patch.multiple(
        "backend.jobs",
        get_settings=MagicMock(return_value=settings),
        execute_query=MagicMock(side_effect=execute_query_side_effect),
        execute_write=MagicMock(return_value=[]),
        get_db=MagicMock(side_effect=_fake_db),
        log_audit=audit if audit is not None else MagicMock(),
    )


# ─── Local file streaming ──────────────────────────────────────────────────


def test_full_hash_local_file_populates_content_hash(tmp_path):
    payload = b"GATTACA\n" * 200_000  # ~1.6 MB — single 8 MB chunk
    f = tmp_path / "sample.fastq"
    f.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()

    rows = [{"id": 1, "uri": str(f), "alternate_uris": []}]
    settings = _settings()
    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=settings),
        patch("backend.jobs.execute_write", write_mock),
    ):
        counters = asyncio.run(compute_full_content_hash())

    assert counters == {"hashed": 1, "reconciled": 0, "skipped": 0, "errors": 0}
    sql, params = write_mock.call_args_list[0].args
    assert "UPDATE sample_files SET content_hash" in sql
    assert params == {"h": expected, "id": 1}


def test_full_hash_streams_in_chunks_for_large_file(tmp_path):
    """File larger than one 8 MB chunk is hashed correctly via streaming."""
    block = b"X" * (3 * FULL_HASH_CHUNK_SIZE + 4096)  # ~24 MB + tail
    f = tmp_path / "big.fastq.gz"
    f.write_bytes(block)
    expected = hashlib.sha256(block).hexdigest()

    rows = [{"id": 7, "uri": str(f), "alternate_uris": []}]
    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
    ):
        counters = asyncio.run(compute_full_content_hash())

    assert counters["hashed"] == 1
    assert write_mock.call_args_list[0].args[1]["h"] == expected


def test_full_hash_no_audit_on_routine_success(tmp_path):
    f = tmp_path / "small.fastq"
    f.write_bytes(b"hello")
    rows = [{"id": 2, "uri": str(f), "alternate_uris": []}]
    audit_mock = MagicMock()

    with _patches(rows=rows, settings=_settings(), audit=audit_mock):
        counters = asyncio.run(compute_full_content_hash())

    assert counters["hashed"] == 1
    audit_mock.assert_not_called()


# ─── Idempotency ───────────────────────────────────────────────────────────


def test_full_hash_skips_already_hashed_rows():
    """Already-hashed rows are filtered by the SQL WHERE clause; the function
    only sees rows the row-selector returned. With no rows returned, the
    job is a no-op (hashed=0).
    """
    rows: list[dict] = []
    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
    ):
        counters = asyncio.run(compute_full_content_hash())

    assert counters == {"hashed": 0, "reconciled": 0, "skipped": 0, "errors": 0}
    write_mock.assert_not_called()


# ─── SRA opt-in ─────────────────────────────────────────────────────────────


def test_full_hash_skips_sra_rows_when_setting_disabled(tmp_path):
    """When compute_sra_full_hash is False, the row-selector excludes
    sra:// URIs. Verified via the WHERE clause built by _select_rows_to_hash.
    """
    captured_sql: list[str] = []
    captured_params: list[dict] = []

    def execute_query_capture(sql, params=None, conn=None):
        captured_sql.append(sql)
        captured_params.append(params or {})
        return []  # simulate no eligible rows

    with patch.multiple(
        "backend.jobs",
        get_settings=MagicMock(return_value=_settings(compute_sra_full_hash=False)),
        execute_query=MagicMock(side_effect=execute_query_capture),
        execute_write=MagicMock(return_value=[]),
        get_db=MagicMock(side_effect=_fake_db),
    ):
        asyncio.run(compute_full_content_hash())

    assert "sra://" in str(captured_params[0].values())
    assert "uri NOT LIKE :prefix_" in captured_sql[0]


def test_full_hash_includes_sra_rows_when_setting_enabled():
    """When compute_sra_full_hash is True, no sra:// exclusion is added."""
    captured_params: list[dict] = []

    def execute_query_capture(sql, params=None, conn=None):
        captured_params.append(params or {})
        return []

    with patch.multiple(
        "backend.jobs",
        get_settings=MagicMock(return_value=_settings(compute_sra_full_hash=True)),
        execute_query=MagicMock(side_effect=execute_query_capture),
        execute_write=MagicMock(return_value=[]),
        get_db=MagicMock(side_effect=_fake_db),
    ):
        asyncio.run(compute_full_content_hash())

    # No NOT-LIKE-prefix params: nothing excluded.
    assert all("sra" not in str(v) for v in captured_params[0].values())


# ─── Remote-skip setting ───────────────────────────────────────────────────


def test_full_hash_skips_remote_when_setting_enabled():
    captured_params: list[dict] = []

    def execute_query_capture(sql, params=None, conn=None):
        captured_params.append(params or {})
        return []

    with patch.multiple(
        "backend.jobs",
        get_settings=MagicMock(return_value=_settings(skip_remote_full_hash=True)),
        execute_query=MagicMock(side_effect=execute_query_capture),
        execute_write=MagicMock(return_value=[]),
        get_db=MagicMock(side_effect=_fake_db),
    ):
        asyncio.run(compute_full_content_hash())

    values = list(captured_params[0].values())
    assert any(v.startswith("gs://") for v in values)
    assert any(v.startswith("s3://") for v in values)
    assert any(v.startswith("http://") for v in values)
    assert any(v.startswith("https://") for v in values)


# ─── Collision reconciliation ──────────────────────────────────────────────


def test_full_hash_reconciles_collision(tmp_path):
    """Two rows with same content but different cheap fingerprints; after
    F-4 hashes the second, it finds the first row already has the same
    content_hash and merges into it: appends URI to alternate_uris,
    redirects paired_file_id, deletes the duplicate, audits the merge.
    """
    payload = b"identical bytes" * 1000
    f = tmp_path / "dup.fastq"
    f.write_bytes(payload)
    expected_hash = hashlib.sha256(payload).hexdigest()

    rows = [{"id": 42, "uri": str(f), "alternate_uris": []}]
    survivor = {"id": 17, "alternate_uris": ["gs://other/loc"]}
    audit_mock = MagicMock()
    write_mock = MagicMock(return_value=[])

    def collision_after_first(_call_idx):
        return [survivor]

    with patch.multiple(
        "backend.jobs",
        get_settings=MagicMock(return_value=_settings()),
        execute_query=MagicMock(
            side_effect=[rows, [survivor]],  # 1st: row selection, 2nd: collision lookup
        ),
        execute_write=write_mock,
        get_db=MagicMock(side_effect=_fake_db),
        log_audit=audit_mock,
    ):
        counters = asyncio.run(compute_full_content_hash())

    assert counters == {"hashed": 0, "reconciled": 1, "skipped": 0, "errors": 0}

    issued_sql = [c.args[0] for c in write_mock.call_args_list]
    assert any("array_append(alternate_uris" in s for s in issued_sql)
    assert any("paired_file_id = :sid" in s for s in issued_sql)
    assert any("DELETE FROM sample_files" in s for s in issued_sql)

    audit_mock.assert_called_once()
    audit_kwargs = audit_mock.call_args.kwargs
    assert audit_kwargs["action"] == "RECONCILE_SAMPLE_FILES_HASH_COLLISION"
    assert audit_kwargs["resource_id"] == "17"
    assert audit_kwargs["metadata"]["merged_id"] == 42
    assert audit_kwargs["metadata"]["content_hash"] == expected_hash


def test_full_hash_reconciliation_skips_alternate_uri_append_when_already_present(
    tmp_path,
):
    """If the surviving row already lists our URI in alternate_uris, the
    append step is skipped (the redirect + delete + audit still run)."""
    payload = b"same"
    f = tmp_path / "x.fastq"
    f.write_bytes(payload)

    rows = [{"id": 5, "uri": str(f), "alternate_uris": []}]
    survivor = {"id": 9, "alternate_uris": [str(f)]}
    write_mock = MagicMock(return_value=[])

    with patch.multiple(
        "backend.jobs",
        get_settings=MagicMock(return_value=_settings()),
        execute_query=MagicMock(side_effect=[rows, [survivor]]),
        execute_write=write_mock,
        get_db=MagicMock(side_effect=_fake_db),
        log_audit=MagicMock(),
    ):
        asyncio.run(compute_full_content_hash())

    issued_sql = [c.args[0] for c in write_mock.call_args_list]
    # No array_append issued — URI was already in alternate_uris.
    assert not any("array_append" in s for s in issued_sql)
    # Still does the redirect + delete.
    assert any("paired_file_id = :sid" in s for s in issued_sql)
    assert any("DELETE FROM sample_files" in s for s in issued_sql)


# ─── Error paths ───────────────────────────────────────────────────────────


def test_full_hash_handles_missing_file(tmp_path):
    rows = [
        {"id": 1, "uri": str(tmp_path / "nope.fastq"), "alternate_uris": []},
    ]
    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
    ):
        counters = asyncio.run(compute_full_content_hash())

    assert counters == {"hashed": 0, "reconciled": 0, "skipped": 0, "errors": 1}
    write_mock.assert_not_called()


def test_full_hash_handles_permission_denied(tmp_path):
    f = tmp_path / "locked.fastq"
    f.write_bytes(b"secret")
    f.chmod(0o000)
    rows = [{"id": 3, "uri": str(f), "alternate_uris": []}]
    write_mock = MagicMock(return_value=[])

    try:
        with (
            _patches(rows=rows, settings=_settings()),
            patch("backend.jobs.execute_write", write_mock),
        ):
            counters = asyncio.run(compute_full_content_hash())
    finally:
        f.chmod(0o600)

    assert counters["errors"] == 1
    assert counters["hashed"] == 0


# ─── Wall-clock budget ─────────────────────────────────────────────────────


def test_full_hash_respects_wall_clock_budget(tmp_path):
    """Three rows, but ``time.monotonic`` advances past the budget after
    the first hash — the remaining rows are reported as ``skipped``."""
    payload = b"abc"
    f = tmp_path / "tiny.fastq"
    f.write_bytes(payload)
    rows = [{"id": i, "uri": str(f), "alternate_uris": []} for i in (1, 2, 3)]
    write_mock = MagicMock(return_value=[])

    # Call 1: deadline = 0 + 10 = 10. Call 2: under budget, row 1 hashes.
    # Call 3 onwards: past deadline → row 2 + row 3 skipped.
    monotonic_values = iter([0.0, 0.0, 9999.0, 9999.0])

    with (
        _patches(rows=rows, settings=_settings(full_hash_max_seconds_per_tick=10)),
        patch("backend.jobs.execute_write", write_mock),
        patch("backend.jobs.monotonic", side_effect=lambda: next(monotonic_values)),
    ):
        counters = asyncio.run(compute_full_content_hash())

    assert counters["hashed"] == 1
    assert counters["skipped"] == 2


# ─── Object-storage and HTTP streaming (mocked) ────────────────────────────


def test_full_hash_streams_gs_via_storage_client():
    """When the row's URI is gs://, the streaming path goes through
    ``backend.storage._get_client`` and uses ``iter_chunks`` for SHA-256."""
    payload = b"cloud-bytes" * 100
    expected = hashlib.sha256(payload).hexdigest()

    body = MagicMock()
    body.iter_chunks.return_value = iter([payload])
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": body}

    rows = [{"id": 1, "uri": "gs://bkt/key.fq", "alternate_uris": []}]
    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
        patch("backend.storage._get_client", return_value=mock_client),
    ):
        counters = asyncio.run(compute_full_content_hash())

    assert counters["hashed"] == 1
    assert write_mock.call_args_list[0].args[1]["h"] == expected
    body.close.assert_called_once()


def test_full_hash_streams_http_via_httpx():
    payload = b"http-bytes" * 50
    expected = hashlib.sha256(payload).hexdigest()

    class _Resp:
        def raise_for_status(self):
            return None

        def iter_bytes(self, chunk_size):
            yield payload

    class _StreamCtx:
        def __enter__(self):
            return _Resp()

        def __exit__(self, *_):
            return False

    class _ClientCtx:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def stream(self, method, uri):
            return _StreamCtx()

    rows = [{"id": 1, "uri": "https://example.com/a.fastq", "alternate_uris": []}]
    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
        patch("httpx.Client", return_value=_ClientCtx()),
    ):
        counters = asyncio.run(compute_full_content_hash())

    assert counters["hashed"] == 1
    assert write_mock.call_args_list[0].args[1]["h"] == expected


def test_full_hash_unsupported_scheme_counts_as_error():
    """Direct call with an unsupported scheme bypasses the row-selector
    filter (row-selector would normally exclude it). The exception is
    caught and counted as an error."""
    rows = [{"id": 99, "uri": "ftp://nope/foo.fastq", "alternate_uris": []}]
    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=_settings()),
        patch("backend.jobs.execute_write", write_mock),
    ):
        counters = asyncio.run(compute_full_content_hash())

    assert counters["errors"] == 1
    assert counters["hashed"] == 0


def test_full_hash_sra_direct_call_raises_caught_as_error():
    """If somehow an sra:// row sneaks past the filter, the streaming
    helper raises and the row gets counted as an error rather than
    crashing the job."""
    rows = [{"id": 50, "uri": "sra://SRR123", "alternate_uris": []}]

    # Force compute_sra_full_hash=True so the selector doesn't exclude it,
    # then verify it still errors at the streaming layer.
    settings = _settings(compute_sra_full_hash=True)
    write_mock = MagicMock(return_value=[])

    with (
        _patches(rows=rows, settings=settings),
        patch("backend.jobs.execute_write", write_mock),
    ):
        counters = asyncio.run(compute_full_content_hash())

    assert counters["errors"] == 1


# ─── Empty-table no-op ─────────────────────────────────────────────────────


def test_full_hash_returns_zero_counters_when_no_rows():
    with _patches(rows=[], settings=_settings()):
        counters = asyncio.run(compute_full_content_hash())
    assert counters == {"hashed": 0, "reconciled": 0, "skipped": 0, "errors": 0}


# Module sanity checks — guard against accidental refactors.
def test_full_hash_chunk_size_is_8mb():
    assert FULL_HASH_CHUNK_SIZE == 8 * 1024 * 1024


def test_compute_full_content_hash_is_async():
    import asyncio as _asyncio

    assert _asyncio.iscoroutinefunction(compute_full_content_hash)


# Guard against unused-import lint while still using the names this
# module touches indirectly via patches.
_ = io  # noqa: F841 — used by the mock harness's StreamingBody analog
