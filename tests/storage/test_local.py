# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-present Glen Otero
"""Local filesystem backend-specific tests."""

from __future__ import annotations

import io
import secrets
import time
from datetime import timedelta

import pytest

from backend.storage.base import PresignMethod
from backend.storage.exceptions import StorageError
from backend.storage.local import LocalFSStorageBackend


def _make_backend(tmp_path) -> LocalFSStorageBackend:
    return LocalFSStorageBackend(
        root_path=str(tmp_path),
        presign_secret=secrets.token_hex(32),
        public_url_base="https://example.org/files",
    )


def test_rejects_path_traversal(tmp_path) -> None:
    backend = _make_backend(tmp_path)
    with pytest.raises(StorageError):
        backend.upload("../escape.txt", io.BytesIO(b"x"))


def test_rejects_backslash(tmp_path) -> None:
    backend = _make_backend(tmp_path)
    with pytest.raises(StorageError):
        backend.upload("dir\\file.txt", io.BytesIO(b"x"))


def test_rejects_short_presign_secret(tmp_path) -> None:
    with pytest.raises(StorageError):
        LocalFSStorageBackend(
            root_path=str(tmp_path),
            presign_secret="too-short",
            public_url_base="https://example.org/files",
        )


def test_presign_signature_verifies(tmp_path) -> None:
    backend = _make_backend(tmp_path)
    backend.upload("a.txt", io.BytesIO(b"x"))
    url = backend.presign_url("a.txt", timedelta(minutes=5), PresignMethod.GET)

    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    expires_at = int(params["expires"][0])
    signature = params["sig"][0]
    assert backend.verify_presigned("GET", "a.txt", expires_at, signature) is True


def test_presign_expired_signature_rejected(tmp_path) -> None:
    backend = _make_backend(tmp_path)
    backend.upload("a.txt", io.BytesIO(b"x"))
    expires_at = int(time.time()) - 10
    sig = backend._sign("GET", "a.txt", expires_at)
    assert backend.verify_presigned("GET", "a.txt", expires_at, sig) is False


def test_presign_tampered_signature_rejected(tmp_path) -> None:
    backend = _make_backend(tmp_path)
    backend.upload("a.txt", io.BytesIO(b"x"))
    expires_at = int(time.time()) + 300
    bad_sig = "0" * 64
    assert backend.verify_presigned("GET", "a.txt", expires_at, bad_sig) is False


def test_metadata_roundtrip(tmp_path) -> None:
    backend = _make_backend(tmp_path)
    backend.upload(
        "meta.txt",
        io.BytesIO(b"x"),
        content_type="text/plain",
        metadata={"source": "test", "tier": "ANALYZABLE"},
    )
    obj = backend.stat("meta.txt")
    assert obj.content_type == "text/plain"
    assert obj.metadata == {"source": "test", "tier": "ANALYZABLE"}
