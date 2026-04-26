# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-present Glen Otero
"""Abstract storage backend interface and shared data types.

All concrete storage backends must implement the StorageBackend protocol.
Callers should depend only on the StorageBackend interface, never on a
concrete backend class.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import BinaryIO


class PresignMethod(str, enum.Enum):
    """HTTP method for which a presigned URL is being generated."""

    GET = "GET"
    PUT = "PUT"


@dataclass(frozen=True)
class StorageObject:
    """Metadata describing a stored object.

    All backends populate at least key, size, and last_modified. Other fields
    may be None depending on backend capability.
    """

    key: str
    size: int
    last_modified: datetime
    content_type: str | None = None
    etag: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class UploadResult:
    """Result returned from an upload operation."""

    key: str
    size: int
    uri: str
    etag: str | None = None


@dataclass(frozen=True)
class DownloadResult:
    """Result returned from a download operation."""

    key: str
    size: int
    content_type: str | None = None


class StorageBackend(ABC):
    """Abstract interface for object storage.

    Implementations must be safe to use from multiple threads, but not
    necessarily from multiple processes - process-level safety is the
    responsibility of the underlying service (GCS, S3, etc.).

    Keys are forward-slash-delimited paths within a logical bucket or root.
    Implementations should reject keys containing backslashes or path
    traversal segments ('..').
    """

    backend_name: str = "abstract"

    @abstractmethod
    def upload(
        self,
        key: str,
        fileobj: BinaryIO,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        """Upload an object from a file-like reader.

        Args:
            key: Object key (forward-slash path within the storage root).
            fileobj: Readable binary file-like object.
            content_type: Optional MIME type to record on the object.
            metadata: Optional key-value metadata to record on the object.

        Returns:
            UploadResult describing the uploaded object.

        Raises:
            StoragePermissionError: If the backend rejects the upload.
            StorageBackendUnavailableError: If the backend is unreachable.
            StorageError: For other backend-specific failures.
        """
        raise NotImplementedError

    @abstractmethod
    def download(self, key: str, fileobj: BinaryIO) -> DownloadResult:
        """Download an object into a file-like writer.

        Args:
            key: Object key.
            fileobj: Writable binary file-like object.

        Returns:
            DownloadResult describing the downloaded object.

        Raises:
            StorageObjectNotFoundError: If the object does not exist.
            StoragePermissionError: If the backend rejects the download.
            StorageBackendUnavailableError: If the backend is unreachable.
        """
        raise NotImplementedError

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if the object exists.

        Should not raise StorageObjectNotFoundError - use this to check.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete an object.

        Idempotent: deleting a nonexistent object is not an error.

        Raises:
            StoragePermissionError: If the backend rejects the delete.
            StorageBackendUnavailableError: If the backend is unreachable.
        """
        raise NotImplementedError

    @abstractmethod
    def stat(self, key: str) -> StorageObject:
        """Return metadata for an object.

        Raises:
            StorageObjectNotFoundError: If the object does not exist.
        """
        raise NotImplementedError

    @abstractmethod
    def list_objects(self, prefix: str = "") -> Iterable[StorageObject]:
        """Iterate over objects whose keys begin with the given prefix.

        The iterator should be lazy: backends should paginate transparently
        rather than loading all results into memory.
        """
        raise NotImplementedError

    @abstractmethod
    def presign_url(
        self,
        key: str,
        expires_in: timedelta,
        method: PresignMethod = PresignMethod.GET,
        content_type: str | None = None,
    ) -> str:
        """Generate a presigned URL for direct client access to an object.

        Args:
            key: Object key.
            expires_in: How long the URL should remain valid.
            method: HTTP method the URL grants.
            content_type: For PUT URLs, the expected Content-Type.

        Returns:
            A URL that grants the requested access for the requested duration.
        """
        raise NotImplementedError

    @abstractmethod
    def get_uri(self, key: str) -> str:
        """Return the canonical backend-native URI for an object.

        Examples:
            gs://my-bucket/path/to/object
            s3://my-bucket/path/to/object
            file:///var/jackpot/data/path/to/object
        """
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if the backend is reachable and writable."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} backend={self.backend_name}>"
