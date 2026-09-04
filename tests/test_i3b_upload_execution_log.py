"""I-3b: ``_upload_execution_log`` storage helper.

A unit test for the helper that writes the assembled log content to
managed storage and returns the canonical URI. The full
``execute_submission`` tests stub this helper so we don't pin the
storage abstraction inside their mocks; this file exercises the helper
directly with a fake backend.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from backend.jobs import _upload_execution_log


@pytest.mark.asyncio
async def test_upload_returns_canonical_uri():
    fake_backend = MagicMock()
    # The helper returns backend.get_uri(key) rather than assembling
    # "{prefix}://{bucket}/{key}" itself — one URI answer per backend,
    # instead of a second copy that has to agree (B-STORAGE-LOCAL-FALLTHROUGH).
    fake_backend.get_uri.side_effect = lambda key: f"s3://jackpot-submissions/{key}"
    # Patch on the `backend.storage` namespace because the helper does
    # `from backend.storage import ...` at call time; the name is
    # resolved against `backend.storage.__init__`'s re-exports.
    with (
        patch("backend.storage.get_storage_backend", return_value=fake_backend),
    ):
        uri = await _upload_execution_log(
            submission_id=42,
            attempt=1,
            content=b"log content",
            completed_at=datetime(2026, 5, 4, 12, 30, 45, tzinfo=UTC),
        )
    assert uri == ("s3://jackpot-submissions/executions/42/execution_20260504T123045Z_attempt1.log")
    fake_backend.upload.assert_called_once()
    args, kwargs = fake_backend.upload.call_args
    # Positional: key, fileobj. Kwargs include content_type and metadata.
    assert args[0] == ("executions/42/execution_20260504T123045Z_attempt1.log")
    assert kwargs.get("content_type") == "text/plain; charset=utf-8"
    md = kwargs.get("metadata") or {}
    assert md["jackpot_submission_id"] == "42"
    assert md["jackpot_attempt"] == "1"
    assert md["jackpot_artifact_kind"] == "execution_log"
    # The fileobj's content matches what we passed in.
    fileobj = args[1]
    fileobj.seek(0)
    assert fileobj.read() == b"log content"


@pytest.mark.asyncio
async def test_upload_object_key_segments_by_submission_id():
    """Different submission IDs land under their own subkey for diagnostic
    discoverability via S3 list_objects."""
    fake_backend = MagicMock()
    # The helper returns backend.get_uri(key) rather than assembling
    # "{prefix}://{bucket}/{key}" itself — one URI answer per backend,
    # instead of a second copy that has to agree (B-STORAGE-LOCAL-FALLTHROUGH).
    fake_backend.get_uri.side_effect = lambda key: f"s3://jackpot-submissions/{key}"
    with (
        patch("backend.storage.get_storage_backend", return_value=fake_backend),
    ):
        uri_a = await _upload_execution_log(
            submission_id=1,
            attempt=1,
            content=b"a",
            completed_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        uri_b = await _upload_execution_log(
            submission_id=2,
            attempt=3,
            content=b"b",
            completed_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    assert "executions/1/" in uri_a
    assert "executions/2/" in uri_b
    assert "_attempt1." in uri_a
    assert "_attempt3." in uri_b
