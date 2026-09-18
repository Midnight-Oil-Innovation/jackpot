# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""GCS-specific tests."""

from __future__ import annotations

import io
from datetime import timedelta
from unittest.mock import Mock

import pytest
import requests
from google.auth.exceptions import RefreshError
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


@pytest.mark.parametrize("method", ["exists", "delete", "stat", "list_objects", "presign_url"])
def test_credential_failure_surfaces_as_storage_error(
    method: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A credential that will not refresh must still surface as StorageError.

    google.auth.exceptions.RefreshError descends from GoogleAuthError, which
    shares no ancestor with GoogleAPIError and which DEFAULT_RETRY's predicate
    declines -- so no retry wraps it either. It escaped every handler in these
    five methods. upload/download were already covered by their positional
    catch.
    """
    backend = _offline_backend()
    exc = RefreshError("could not refresh the access token")
    blob = Mock()
    monkeypatch.setattr(backend._bucket, "blob", lambda _key: blob)

    if method == "exists":
        blob.exists.side_effect = exc
    elif method == "delete":
        blob.delete.side_effect = exc
    elif method == "stat":
        monkeypatch.setattr(backend._bucket, "get_blob", Mock(side_effect=exc))
    elif method == "list_objects":
        monkeypatch.setattr(backend._client, "list_blobs", Mock(side_effect=exc))
    else:
        blob.generate_signed_url.side_effect = exc

    with pytest.raises(StorageError) as excinfo:
        if method == "exists":
            backend.exists("a/b.txt")
        elif method == "delete":
            backend.delete("a/b.txt")
        elif method == "stat":
            backend.stat("a/b.txt")
        elif method == "list_objects":
            list(backend.list_objects())
        else:
            backend.presign_url("a/b.txt", timedelta(minutes=5))

    # Identity, and it is the anti-vacuity guard. Every one of these methods
    # fails on its own against the dead port -- delete and presign_url at once,
    # exists/stat/list_objects after a ~70s retry -- and each of those failures
    # is already a StorageError, so pytest.raises alone would pass on the wrong
    # one. `exc` is reachable only through the stub, so `is exc` holds only if
    # the stub fired.
    assert excinfo.value.__cause__ is exc
