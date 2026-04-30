# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-present Glen Otero
"""AWS S3 / MinIO storage backend.

Both AWS S3 and MinIO speak the same API, so they share an implementation.
The difference is whether endpoint_url is set (MinIO) or omitted (AWS).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from typing import BinaryIO

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError

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


class S3StorageBackend(StorageBackend):
    """S3-compatible storage backend (AWS S3 or MinIO)."""

    def __init__(
        self,
        bucket_name: str,
        region: str,
        access_key: str,
        secret_key: str,
        endpoint_url: str | None = None,
        use_path_style: bool = False,
        backend_name: str = "s3",
    ) -> None:
        self.backend_name = backend_name
        self.bucket_name = bucket_name
        self.region = region
        self.endpoint_url = endpoint_url

        config_kwargs: dict = {"signature_version": "s3v4"}
        if use_path_style:
            config_kwargs["s3"] = {"addressing_style": "path"}
        boto_config = BotoConfig(**config_kwargs)

        self._client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            endpoint_url=endpoint_url,
            config=boto_config,
        )

    def _classify_client_error(self, e: ClientError, key: str | None) -> StorageError:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchKey", "404", "NotFound"):
            return StorageObjectNotFoundError(str(e), key=key, backend=self.backend_name)
        if code in ("AccessDenied", "403", "Forbidden"):
            return StoragePermissionError(str(e), key=key, backend=self.backend_name)
        return StorageError(str(e), key=key, backend=self.backend_name)

    def upload(
        self,
        key: str,
        fileobj: BinaryIO,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        _validate_key(key)
        extra_args: dict = {}
        if content_type:
            extra_args["ContentType"] = content_type
        if metadata:
            extra_args["Metadata"] = metadata

        try:
            self._client.upload_fileobj(fileobj, self.bucket_name, key, ExtraArgs=extra_args)
            head = self._client.head_object(Bucket=self.bucket_name, Key=key)
        except EndpointConnectionError as e:
            raise StorageBackendUnavailableError(str(e), key=key, backend=self.backend_name) from e
        except ClientError as e:
            raise self._classify_client_error(e, key) from e
        except BotoCoreError as e:
            raise StorageError(str(e), key=key, backend=self.backend_name) from e

        return UploadResult(
            key=key,
            size=head.get("ContentLength", 0),
            uri=self.get_uri(key),
            etag=head.get("ETag", "").strip('"') or None,
        )

    def download(self, key: str, fileobj: BinaryIO) -> DownloadResult:
        _validate_key(key)
        try:
            self._client.download_fileobj(self.bucket_name, key, fileobj)
            head = self._client.head_object(Bucket=self.bucket_name, Key=key)
        except EndpointConnectionError as e:
            raise StorageBackendUnavailableError(str(e), key=key, backend=self.backend_name) from e
        except ClientError as e:
            raise self._classify_client_error(e, key) from e
        except BotoCoreError as e:
            raise StorageError(str(e), key=key, backend=self.backend_name) from e

        return DownloadResult(
            key=key,
            size=head.get("ContentLength", 0),
            content_type=head.get("ContentType"),
        )

    def exists(self, key: str) -> bool:
        _validate_key(key)
        try:
            self._client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404", "NotFound"):
                return False
            raise self._classify_client_error(e, key) from e
        except EndpointConnectionError as e:
            raise StorageBackendUnavailableError(str(e), key=key, backend=self.backend_name) from e

    def delete(self, key: str) -> None:
        _validate_key(key)
        try:
            self._client.delete_object(Bucket=self.bucket_name, Key=key)
        except EndpointConnectionError as e:
            raise StorageBackendUnavailableError(str(e), key=key, backend=self.backend_name) from e
        except ClientError as e:
            err = self._classify_client_error(e, key)
            if isinstance(err, StorageObjectNotFoundError):
                return
            raise err from e

    def stat(self, key: str) -> StorageObject:
        _validate_key(key)
        try:
            head = self._client.head_object(Bucket=self.bucket_name, Key=key)
        except ClientError as e:
            raise self._classify_client_error(e, key) from e
        except EndpointConnectionError as e:
            raise StorageBackendUnavailableError(str(e), key=key, backend=self.backend_name) from e

        return StorageObject(
            key=key,
            size=head.get("ContentLength", 0),
            last_modified=head["LastModified"],
            content_type=head.get("ContentType"),
            etag=(head.get("ETag") or "").strip('"') or None,
            metadata=dict(head.get("Metadata") or {}),
        )

    def list_objects(self, prefix: str = "") -> Iterable[StorageObject]:
        paginator = self._client.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                for obj in page.get("Contents", []) or []:
                    yield StorageObject(
                        key=obj["Key"],
                        size=obj.get("Size", 0),
                        last_modified=obj["LastModified"],
                        etag=(obj.get("ETag") or "").strip('"') or None,
                    )
        except EndpointConnectionError as e:
            raise StorageBackendUnavailableError(str(e), backend=self.backend_name) from e
        except ClientError as e:
            raise self._classify_client_error(e, None) from e

    def presign_url(
        self,
        key: str,
        expires_in: timedelta,
        method: PresignMethod = PresignMethod.GET,
        content_type: str | None = None,
    ) -> str:
        _validate_key(key)
        params: dict = {"Bucket": self.bucket_name, "Key": key}
        if method == PresignMethod.GET:
            client_method = "get_object"
        else:
            client_method = "put_object"
            if content_type:
                params["ContentType"] = content_type

        try:
            return self._client.generate_presigned_url(
                client_method,
                Params=params,
                ExpiresIn=int(expires_in.total_seconds()),
            )
        except (BotoCoreError, ClientError) as e:
            raise StorageError(str(e), key=key, backend=self.backend_name) from e

    def get_uri(self, key: str) -> str:
        return f"s3://{self.bucket_name}/{key}"

    def health_check(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self.bucket_name)
            return True
        except (ClientError, EndpointConnectionError, BotoCoreError):
            return False
