# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""GCS-specific tests."""

from __future__ import annotations

import io
from unittest.mock import Mock

import pytest
from google.resumable_media import DataCorruption

from backend.storage.exceptions import StorageError
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
