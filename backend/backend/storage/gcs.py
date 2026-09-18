# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Google Cloud Storage backend."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import BinaryIO

from google.api_core.exceptions import Forbidden, GoogleAPIError, NotFound
from google.cloud import storage as gcs_module
from requests.exceptions import RequestException

from backend.storage.base import (
    DownloadResult,
    PresignMethod,
    StorageBackend,
    StorageObject,
    UploadResult,
)
from backend.storage.exceptions import (
    StorageBackendUnavailableError,
    StorageError,
    StorageObjectNotFoundError,
    StoragePermissionError,
)


def _validate_key(key: str) -> None:
    if not key:
        raise StorageError("Storage key must not be empty")
    if "\\" in key:
        raise StorageError(f"Storage key must not contain backslashes: {key}", key=key)
    if any(seg == ".." for seg in key.split("/")):
        raise StorageError(f"Storage key must not contain '..' segments: {key}", key=key)


def _storage_object(blob, key: str) -> StorageObject:
    """Build a StorageObject from a GCS blob.

    One home for the Optional-timestamp question. `blob.updated` is
    Optional — a blob that has not been reloaded carries no timestamp —
    while StorageObject requires one. Epoch is the honest stand-in: it
    reads as "unknown" rather than inventing a plausible recent time.

    Extracted because the two construction sites answered that question
    differently, and pyright only caught one of them: list_blobs() yields
    Any, so it never saw the Optional. Same field, two answers, one file —
    the shape of the bug this change set is named after.
    """
    return StorageObject(
        key=key,
        size=blob.size or 0,
        last_modified=blob.updated or datetime.fromtimestamp(0, tz=UTC),
        content_type=blob.content_type,
        etag=blob.etag,
        metadata=dict(blob.metadata or {}),
    )


class GCSStorageBackend(StorageBackend):
    """Google Cloud Storage backend."""

    backend_name = "gcs"

    def __init__(
        self,
        bucket_name: str,
        project: str,
        location: str | None = None,
        api_endpoint: str | None = None,
    ) -> None:
        self.bucket_name = bucket_name
        self.project = project
        self.location = location
        self.api_endpoint = api_endpoint

        if api_endpoint:
            # Emulator mode: anonymous credentials, point at the emulator
            from google.auth.credentials import AnonymousCredentials

            self._client = gcs_module.Client(
                project=project,
                credentials=AnonymousCredentials(),
                client_options={"api_endpoint": api_endpoint},
            )
        else:
            # Production mode: default credentials
            self._client = gcs_module.Client(project=project)
        self._bucket = self._client.bucket(bucket_name)

    def upload(
        self,
        key: str,
        fileobj: BinaryIO,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        _validate_key(key)
        blob = self._bucket.blob(key)
        if metadata:
            blob.metadata = metadata
        try:
            blob.upload_from_file(fileobj, content_type=content_type, rewind=True)
            blob.reload()
        except Forbidden as e:
            raise StoragePermissionError(str(e), key=key, backend=self.backend_name) from e
        except GoogleAPIError as e:
            raise StorageBackendUnavailableError(str(e), key=key, backend=self.backend_name) from e
        # Not GoogleAPIError: upload_from_file is a resumable transfer, and a
        # checksum mismatch leaves it as google.resumable_media.DataCorruption,
        # which blob.py re-raises bare and which shares no ancestor with
        # GoogleAPIError -- so it escaped every handler here, breaking the
        # StorageError-only contract in exceptions.py. Plain StorageError, not
        # StorageBackendUnavailableError: corrupt bytes arrived, so the backend
        # was reachable, and a caller retrying on "unavailable" would retry the
        # one failure a retry cannot fix.
        except Exception as e:
            raise StorageError(str(e), key=key, backend=self.backend_name) from e

        return UploadResult(
            key=key,
            size=blob.size or 0,
            uri=self.get_uri(key),
            etag=blob.etag,
        )

    def download(self, key: str, fileobj: BinaryIO) -> DownloadResult:
        _validate_key(key)
        blob = self._bucket.blob(key)
        try:
            blob.download_to_file(fileobj)
            blob.reload()
        except NotFound as e:
            raise StorageObjectNotFoundError(str(e), key=key, backend=self.backend_name) from e
        except Forbidden as e:
            raise StoragePermissionError(str(e), key=key, backend=self.backend_name) from e
        except GoogleAPIError as e:
            raise StorageBackendUnavailableError(str(e), key=key, backend=self.backend_name) from e
        # See upload() -- download_to_file is the other resumable transfer, and
        # DataCorruption escapes it the same way.
        except Exception as e:
            raise StorageError(str(e), key=key, backend=self.backend_name) from e

        return DownloadResult(
            key=key,
            size=blob.size or 0,
            content_type=blob.content_type,
        )

    def exists(self, key: str) -> bool:
        _validate_key(key)
        try:
            return self._bucket.blob(key).exists()
        except GoogleAPIError as e:
            raise StorageBackendUnavailableError(str(e), key=key, backend=self.backend_name) from e
        # Positional, as in upload(): a credential that will not refresh raises
        # google.auth.GoogleAuthError, which is neither a GoogleAPIError nor
        # anything DEFAULT_RETRY's predicate will wrap, so it matched nothing
        # above. The try holds one library call, so catching broadly hides no
        # local bug -- and unlike naming GoogleAuthError it also holds for the
        # next alien hierarchy, which is what exceptions.py actually promises.
        except Exception as e:
            raise StorageError(str(e), key=key, backend=self.backend_name) from e

    def delete(self, key: str) -> None:
        _validate_key(key)
        try:
            self._bucket.blob(key).delete()
        except NotFound:
            return
        except Forbidden as e:
            raise StoragePermissionError(str(e), key=key, backend=self.backend_name) from e
        except GoogleAPIError as e:
            raise StorageBackendUnavailableError(str(e), key=key, backend=self.backend_name) from e
        # delete() alone defaults to DEFAULT_RETRY_IF_GENERATION_SPECIFIED and we
        # pass no generation, so retry is off and nothing turns the transport
        # error into a GoogleAPIError -- the raw requests exception escaped.
        # exists/stat/list_objects retry unconditionally and surface RetryError,
        # caught above. Not fixed by passing retry=DEFAULT_RETRY: a DELETE with
        # no generation precondition is not idempotent, so the library gates it.
        except RequestException as e:
            raise StorageBackendUnavailableError(str(e), key=key, backend=self.backend_name) from e
        except Exception as e:
            raise StorageError(str(e), key=key, backend=self.backend_name) from e

    def stat(self, key: str) -> StorageObject:
        _validate_key(key)
        try:
            blob = self._bucket.get_blob(key)
        except GoogleAPIError as e:
            raise StorageBackendUnavailableError(str(e), key=key, backend=self.backend_name) from e
        except Exception as e:
            raise StorageError(str(e), key=key, backend=self.backend_name) from e
        if blob is None:
            raise StorageObjectNotFoundError(
                f"Object not found: {key}", key=key, backend=self.backend_name
            )

        return _storage_object(blob, key)

    def list_objects(self, prefix: str = "") -> Iterable[StorageObject]:
        try:
            for blob in self._client.list_blobs(self._bucket, prefix=prefix):
                yield _storage_object(blob, blob.name)
        except GoogleAPIError as e:
            raise StorageBackendUnavailableError(str(e), backend=self.backend_name) from e
        # See exists(). _storage_object is ours and inside the try, so a bug in it
        # surfaces as StorageError too -- the chained cause still names it.
        except Exception as e:
            raise StorageError(str(e), backend=self.backend_name) from e

    def presign_url(
        self,
        key: str,
        expires_in: timedelta,
        method: PresignMethod = PresignMethod.GET,
        content_type: str | None = None,
    ) -> str:
        _validate_key(key)
        blob = self._bucket.blob(key)
        try:
            return blob.generate_signed_url(
                version="v4",
                expiration=expires_in,
                method=method.value,
                content_type=content_type if method == PresignMethod.PUT else None,
            )
        except GoogleAPIError as e:
            raise StorageBackendUnavailableError(str(e), key=key, backend=self.backend_name) from e
        except Exception as e:
            raise StorageError(str(e), key=key, backend=self.backend_name) from e

    def get_uri(self, key: str) -> str:
        return f"gs://{self.bucket_name}/{key}"

    def health_check(self) -> bool:
        try:
            self._bucket.reload()
            return True
        except Exception:
            return False
