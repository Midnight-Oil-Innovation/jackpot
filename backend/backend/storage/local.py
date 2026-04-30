# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-present Glen Otero
"""Local filesystem storage backend.

This backend stores objects as files under a configured root directory.
Presigned URLs are HMAC-SHA256-signed with an expiry timestamp; a separate
HTTP server (e.g., FastAPI route) is responsible for verifying signatures
and serving file content.

Suitable for single-node deployments where no object storage is available.
Not suitable for multi-replica deployments unless the root directory is on
a shared filesystem.
"""

from __future__ import annotations

import hashlib
import hmac
import shutil
import time
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote, urlencode

from backend.storage.base import (
    DownloadResult,
    PresignMethod,
    StorageBackend,
    StorageObject,
    UploadResult,
)
from backend.storage.exceptions import (
    StorageError,
    StorageObjectNotFoundError,
    StoragePermissionError,
)


class LocalFSStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    backend_name = "local"

    def __init__(
        self,
        root_path: str,
        presign_secret: str,
        public_url_base: str,
    ) -> None:
        self.root_path = Path(root_path).resolve()
        self.root_path.mkdir(parents=True, exist_ok=True)
        if len(presign_secret) < 32:
            raise StorageError(
                "presign_secret must be at least 32 characters", backend=self.backend_name
            )
        self._presign_secret = presign_secret.encode("utf-8")
        self._public_url_base = public_url_base.rstrip("/")

    def _resolve_key(self, key: str) -> Path:
        if not key:
            raise StorageError("Storage key must not be empty", backend=self.backend_name)
        if "\\" in key:
            raise StorageError(
                f"Storage key must not contain backslashes: {key}",
                key=key,
                backend=self.backend_name,
            )
        if any(seg == ".." for seg in key.split("/")):
            raise StorageError(
                f"Storage key must not contain '..' segments: {key}",
                key=key,
                backend=self.backend_name,
            )

        candidate = (self.root_path / key).resolve()
        try:
            candidate.relative_to(self.root_path)
        except ValueError as e:
            raise StoragePermissionError(
                f"Resolved path escapes storage root: {key}",
                key=key,
                backend=self.backend_name,
            ) from e
        return candidate

    def upload(
        self,
        key: str,
        fileobj: BinaryIO,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        path = self._resolve_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            shutil.copyfileobj(fileobj, f)

        size = path.stat().st_size

        if metadata or content_type:
            self._write_sidecar(path, content_type=content_type, metadata=metadata or {})

        return UploadResult(
            key=key,
            size=size,
            uri=self.get_uri(key),
        )

    def download(self, key: str, fileobj: BinaryIO) -> DownloadResult:
        path = self._resolve_key(key)
        if not path.is_file():
            raise StorageObjectNotFoundError(
                f"Object not found: {key}", key=key, backend=self.backend_name
            )

        with open(path, "rb") as f:
            shutil.copyfileobj(f, fileobj)
        ct, _ = self._read_sidecar(path)
        return DownloadResult(
            key=key,
            size=path.stat().st_size,
            content_type=ct,
        )

    def exists(self, key: str) -> bool:
        path = self._resolve_key(key)
        return path.is_file()

    def delete(self, key: str) -> None:
        path = self._resolve_key(key)
        if path.is_file():
            path.unlink()
        sidecar = self._sidecar_path(path)
        if sidecar.is_file():
            sidecar.unlink()

    def stat(self, key: str) -> StorageObject:
        path = self._resolve_key(key)
        if not path.is_file():
            raise StorageObjectNotFoundError(
                f"Object not found: {key}", key=key, backend=self.backend_name
            )
        st = path.stat()
        ct, meta = self._read_sidecar(path)
        return StorageObject(
            key=key,
            size=st.st_size,
            last_modified=datetime.fromtimestamp(st.st_mtime, tz=UTC),
            content_type=ct,
            metadata=meta,
        )

    def list_objects(self, prefix: str = "") -> Iterable[StorageObject]:
        prefix_path = self._resolve_key(prefix) if prefix else self.root_path
        if not prefix_path.exists():
            return
        if prefix_path.is_file():
            yield self.stat(prefix)
            return

        for path in sorted(prefix_path.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix == ".jackpot-meta":
                continue
            try:
                rel = path.relative_to(self.root_path).as_posix()
            except ValueError:
                continue
            try:
                yield self.stat(rel)
            except StorageObjectNotFoundError:
                continue

    def presign_url(
        self,
        key: str,
        expires_in: timedelta,
        method: PresignMethod = PresignMethod.GET,
        content_type: str | None = None,
    ) -> str:
        self._resolve_key(key)
        expires_at = int(time.time() + expires_in.total_seconds())
        signature = self._sign(method.value, key, expires_at)
        params = {"expires": expires_at, "sig": signature, "method": method.value}
        return f"{self._public_url_base}/{quote(key)}?{urlencode(params)}"

    def verify_presigned(
        self,
        method: str,
        key: str,
        expires_at: int,
        signature: str,
    ) -> bool:
        """Verify a presigned URL signature.

        Used by the HTTP route that serves local files. Not part of the
        StorageBackend interface, but exposed here so the route does not
        need to know about the HMAC secret.
        """
        if expires_at < int(time.time()):
            return False
        expected = self._sign(method, key, expires_at)
        return hmac.compare_digest(expected, signature)

    def get_uri(self, key: str) -> str:
        return f"file://{self._resolve_key(key)}"

    def health_check(self) -> bool:
        try:
            probe = self.root_path / ".jackpot-health-check"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True
        except OSError:
            return False

    # Internals

    def _sign(self, method: str, key: str, expires_at: int) -> str:
        msg = f"{method}:{key}:{expires_at}".encode()
        return hmac.new(self._presign_secret, msg, hashlib.sha256).hexdigest()

    def _sidecar_path(self, path: Path) -> Path:
        return path.with_suffix(path.suffix + ".jackpot-meta")

    def _write_sidecar(
        self, path: Path, content_type: str | None, metadata: dict[str, str]
    ) -> None:
        sidecar = self._sidecar_path(path)
        lines: list[str] = []
        if content_type:
            lines.append(f"content_type={content_type}")
        for k, v in metadata.items():
            if "\n" in k or "\n" in v or "=" in k:
                continue
            lines.append(f"meta:{k}={v}")
        sidecar.write_text("\n".join(lines), encoding="utf-8")

    def _read_sidecar(self, path: Path) -> tuple[str | None, dict[str, str]]:
        sidecar = self._sidecar_path(path)
        if not sidecar.is_file():
            return None, {}
        ct: str | None = None
        meta: dict[str, str] = {}
        for line in sidecar.read_text(encoding="utf-8").splitlines():
            if line.startswith("content_type="):
                ct = line[len("content_type=") :]
            elif line.startswith("meta:"):
                rest = line[len("meta:") :]
                if "=" in rest:
                    k, v = rest.split("=", 1)
                    meta[k] = v
        return ct, meta
