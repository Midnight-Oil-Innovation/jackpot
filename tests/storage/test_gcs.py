# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""GCS-specific tests."""

from __future__ import annotations

import io
from unittest.mock import Mock

import pytest
import requests
from google.resumable_media import DataCorruption

from backend.storage.exceptions import StorageBackendUnavailableError, StorageError
from backend.storage.gcs import GCSStorageBackend


def test_gcs_uri_format(gcs_bucket: tuple[str, str, str]) -> None:
    bucket_name, project, endpoint = gcs_bucket
    backend = GCSStorageBackend(
        bucket_name=bucket_name,
        project=project,
        api_endpoint=endpoint,
    )
    assert backend.get_uri("a/b.txt") == f"gs://{bucket_name}/a/b.txt"


def _offline_backend() -> GCSStorageBackend:
    """A backend pointed at a dead port, so a lapsed stub fails loudly, not silently."""
    return GCSStorageBackend(
        bucket_name="jackpot-test",
        project="jackpot-test-project",
        api_endpoint="http://127.0.0.1:1",
    )


@pytest.mark.parametrize("transfer", ["upload_from_file", "download_to_file"])
def test_checksum_mismatch_surfaces_as_storage_error(
    transfer: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A corrupt transfer must still surface as StorageError, not a raw library error.

    DataCorruption descends from Exception, not GoogleAPIError, and comes out
    of both resumable transfers uncaught — so it matched none of the handlers
    in upload()/download().
    """
    backend = _offline_backend()
    blob = Mock()
    getattr(blob, transfer).side_effect = DataCorruption(None, "checksum mismatch")
    monkeypatch.setattr(backend._bucket, "blob", lambda _key: blob)

    with pytest.raises(StorageError) as excinfo:
        if transfer == "upload_from_file":
            backend.upload("a/b.txt", io.BytesIO(b"payload"))
        else:
            backend.download("a/b.txt", io.BytesIO())

    # The cause assert is the anti-vacuity guard, and the only one. If the
    # monkeypatch ever stops taking effect, the real blob reaches the dead
    # endpoint and the new handler turns that ConnectionError into a plain
    # StorageError as well — so pytest.raises and the type check below would
    # both pass on nothing. Only the cause tells the two apart.
    assert isinstance(excinfo.value.__cause__, DataCorruption)
    # Corrupt bytes mean the backend answered, so this must NOT be the
    # unavailable variant — a caller retrying on that would retry forever.
    assert type(excinfo.value) is StorageError


def test_delete_transport_failure_surfaces_as_backend_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transport failure on delete() must surface as StorageBackendUnavailableError.

    delete() is the one method here with retry off by default -- it is
    conditional on a generation, and JACKPOT passes none -- so nothing
    translated the transport error into google.api_core's hierarchy and the raw
    requests exception reached the caller. See the handler in gcs.py.
    """
    backend = _offline_backend()
    blob = Mock()
    exc = requests.exceptions.ConnectionError("connection refused")
    blob.delete.side_effect = exc
    monkeypatch.setattr(backend._bucket, "blob", lambda _key: blob)

    with pytest.raises(StorageBackendUnavailableError) as excinfo:
        backend.delete("a/b.txt")

    # Identity, not isinstance, and it is the anti-vacuity guard. If the
    # monkeypatch ever lapses, the real blob hits the dead port and raises its
    # own ConnectionError, which the fix maps to this same type -- so every
    # other assertion here would pass on nothing.
    assert excinfo.value.__cause__ is exc
