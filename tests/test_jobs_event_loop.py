"""R-1 #3 — async jobs must not block the event loop.

The three patched call sites in :mod:`backend.jobs` previously called
synchronous I/O directly from ``async def`` job functions, blocking
the entire event loop for the duration of every copy / hash /
verification. Under any concurrent load this stalled the API.

These tests confirm a fast async task can interleave while the slow
sync work executes — i.e. the sync work runs in a worker thread, not
on the event loop. We don't assert exact wall-clock; we assert
relative ordering / progress, which is robust to CI timing variance.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from backend.jobs import (
    compute_full_content_hash,
    promote_file_storage,
    verify_file_references,
)


async def _fast_marker(elapsed_at_done: list[float], started: float) -> None:
    """Tiny async task that should complete well before the slow
    blocking work would, if the slow work weren't offloaded."""
    await asyncio.sleep(0.0)
    elapsed_at_done.append(time.monotonic() - started)


@pytest.mark.asyncio
async def test_promote_file_storage_does_not_block_event_loop(monkeypatch):
    """Location 1: promote_file_storage's _stream_copy_with_hash and
    _server_side_copy_if_supported must run in a worker thread."""

    def slow_stream_copy(source_uri, dest_uri, *, chunk_size):
        time.sleep(0.5)
        return (1024, "deadbeef" * 8)

    monkeypatch.setattr("backend.jobs._stream_copy_with_hash", slow_stream_copy)
    monkeypatch.setattr("backend.jobs._server_side_copy_if_supported", lambda src, dst: False)
    # Skip the DB fetch — make the function fail fast with a clear
    # outcome before the copy. Returning [] means "row not found"
    # which exits before the copy. We instead want the copy path
    # exercised; substitute a stub that returns a valid row.
    monkeypatch.setattr(
        "backend.jobs.execute_query",
        lambda *_a, **_kw: [
            {
                "id": 1,
                "sample_id_fk": 42,
                "uri": "gs://src/x",
                "storage_state": "EXTERNAL",
                "file_size_bytes": 1024,
            }
        ],
    )
    monkeypatch.setattr(
        "backend.jobs._promote_destination_uri",
        lambda *_a, **_kw: "gs://dest/x",
    )
    # Short-circuit the post-copy DB writes and notifications.
    monkeypatch.setattr("backend.jobs._promote_finalize", lambda **_kw: None)
    monkeypatch.setattr("backend.jobs.log_audit", lambda *a, **kw: None)
    monkeypatch.setattr("backend.jobs.create_notification", lambda *a, **kw: None)
    monkeypatch.setattr("backend.jobs._record_promote_job", lambda *a, **kw: None)

    started = time.monotonic()
    elapsed_at_done: list[float] = []
    promote_task = asyncio.create_task(
        promote_file_storage(
            file_id=1,
            target_state="MANAGED",
            retention_policy="default",
            trigger_user_id=1,
            job_id="test-job",
        )
    )
    fast_task = asyncio.create_task(_fast_marker(elapsed_at_done, started))
    await asyncio.gather(promote_task, fast_task)
    fast_elapsed = elapsed_at_done[0]
    # The fast task should have completed essentially immediately,
    # well before the 0.5s sync sleep. <350ms is the loose bound (a
    # blocked loop waits the full 0.5s; loaded CI runners have hit 0.18s);
    # the actual interleave runs in microseconds when offloaded.
    assert fast_elapsed < 0.35, (
        f"Fast task waited {fast_elapsed:.3f}s — sync I/O is blocking the event loop."
    )


@pytest.mark.asyncio
async def test_compute_full_content_hash_does_not_block_event_loop(monkeypatch):
    """Location 2: _stream_full_sha256 (sync, uses httpx.Client for
    http URIs) must run in a worker thread."""

    def slow_hash(uri):
        time.sleep(0.5)
        return "deadbeef" * 8

    monkeypatch.setattr("backend.jobs._stream_full_sha256", slow_hash)
    monkeypatch.setattr(
        "backend.jobs._select_rows_to_hash",
        lambda **_kw: [{"id": 1, "uri": "https://example/x", "alternate_uris": []}],
    )

    # Replace the get_db ContextManager with a no-op so we can route
    # the rest of the job harmlessly.
    class _NullDB:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("backend.jobs.get_db", lambda: _NullDB())
    monkeypatch.setattr("backend.jobs.execute_query", lambda *a, **kw: [])
    monkeypatch.setattr("backend.jobs.execute_write", lambda *a, **kw: None)

    started = time.monotonic()
    elapsed_at_done: list[float] = []
    hash_task = asyncio.create_task(compute_full_content_hash())
    fast_task = asyncio.create_task(_fast_marker(elapsed_at_done, started))
    await asyncio.gather(hash_task, fast_task)
    fast_elapsed = elapsed_at_done[0]
    assert fast_elapsed < 0.35, (
        f"Fast task waited {fast_elapsed:.3f}s — sync I/O is blocking the event loop."
    )


@pytest.mark.asyncio
async def test_verify_file_references_does_not_block_event_loop(monkeypatch):
    """Location 3: _verify_one calls _stat_uri which uses sync
    httpx.Client for http(s) URIs. Must run in a worker thread."""

    def slow_verify(row, *, re_fingerprint):
        time.sleep(0.5)
        return None  # OK

    monkeypatch.setattr("backend.jobs._verify_one", slow_verify)
    monkeypatch.setattr(
        "backend.jobs.execute_query",
        lambda *_a, **_kw: [
            {
                "id": 1,
                "uri": "https://example/x",
                "file_size_bytes": 100,
                "head64k_hash": "h",
                "tail64k_hash": "t",
                "last_verification_status": "OK",
                "storage_state": "EXTERNAL",
            }
        ],
    )

    class _NullDB:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("backend.jobs.get_db", lambda: _NullDB())
    monkeypatch.setattr("backend.jobs.execute_write", lambda *a, **kw: None)
    monkeypatch.setattr("backend.jobs.log_audit", lambda *a, **kw: None)

    started = time.monotonic()
    elapsed_at_done: list[float] = []
    verify_task = asyncio.create_task(verify_file_references())
    fast_task = asyncio.create_task(_fast_marker(elapsed_at_done, started))
    await asyncio.gather(verify_task, fast_task)
    fast_elapsed = elapsed_at_done[0]
    assert fast_elapsed < 0.35, (
        f"Fast task waited {fast_elapsed:.3f}s — sync I/O is blocking the event loop."
    )
