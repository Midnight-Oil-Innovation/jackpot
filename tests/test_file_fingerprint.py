# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Unit tests for backend.file_fingerprint.cheap_fingerprint."""

from __future__ import annotations

import gzip
import hashlib
import io
import os
from unittest.mock import MagicMock, patch

import pytest

from backend.file_fingerprint import (
    FINGERPRINT_CHUNK_SIZE,
    cheap_fingerprint,
)

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


# ─── Local files ───────────────────────────────────────────────────────────


def test_local_file_under_128kb_head_and_tail_equal(tmp_path):
    payload = b"x" * (FINGERPRINT_CHUNK_SIZE + 1024)  # 65 KB — single block
    f = tmp_path / "small.fastq"
    f.write_bytes(payload)

    size, head, tail = cheap_fingerprint(str(f))

    assert size == len(payload)
    assert head == tail
    assert head == hashlib.sha256(payload).hexdigest()


def test_local_file_exactly_128kb_head_and_tail_differ(tmp_path):
    head_block = b"H" * FINGERPRINT_CHUNK_SIZE
    tail_block = b"T" * FINGERPRINT_CHUNK_SIZE
    payload = head_block + tail_block
    f = tmp_path / "edge.fastq"
    f.write_bytes(payload)

    size, head, tail = cheap_fingerprint(str(f))

    assert size == 2 * FINGERPRINT_CHUNK_SIZE
    assert head == hashlib.sha256(head_block).hexdigest()
    assert tail == hashlib.sha256(tail_block).hexdigest()
    assert head != tail


def test_local_file_over_128kb_head_and_tail_differ(tmp_path):
    head_block = b"A" * FINGERPRINT_CHUNK_SIZE
    middle = b"M" * (10 * 1024)
    tail_block = b"Z" * FINGERPRINT_CHUNK_SIZE
    payload = head_block + middle + tail_block
    f = tmp_path / "big.fastq"
    f.write_bytes(payload)

    size, head, tail = cheap_fingerprint(str(f))

    assert size == len(payload)
    assert head == hashlib.sha256(head_block).hexdigest()
    assert tail == hashlib.sha256(tail_block).hexdigest()
    assert head != tail


def test_local_file_empty(tmp_path):
    f = tmp_path / "empty.fastq"
    f.write_bytes(b"")

    size, head, tail = cheap_fingerprint(str(f))

    assert size == 0
    assert head == EMPTY_SHA256
    assert tail == EMPTY_SHA256


def test_local_file_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        cheap_fingerprint(str(tmp_path / "does-not-exist.fastq"))


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")
def test_local_file_permission_denied(tmp_path):
    f = tmp_path / "locked.fastq"
    f.write_bytes(b"secret")
    f.chmod(0o000)
    try:
        with pytest.raises(PermissionError):
            cheap_fingerprint(str(f))
    finally:
        f.chmod(0o600)


def test_local_file_with_file_uri_prefix_matches_bare_path(tmp_path):
    payload = b"identical content"
    f = tmp_path / "uri.fastq"
    f.write_bytes(payload)

    via_path = cheap_fingerprint(str(f))
    via_uri = cheap_fingerprint(f"file://{f}")

    assert via_path == via_uri


# ─── Compression handling ──────────────────────────────────────────────────


def test_gzip_files_with_different_compression_levels_have_different_fingerprints(
    tmp_path,
):
    """F-3 fingerprints compressed bytes; identical decompressed content
    compressed with different levels produces different cheap fingerprints,
    which is correct (they are different files at the byte level)."""
    raw = b"GATTACA\n" * 50_000  # ~400 KB — guarantees distinct head/tail
    f1 = tmp_path / "level1.fastq.gz"
    f9 = tmp_path / "level9.fastq.gz"
    f1.write_bytes(gzip.compress(raw, compresslevel=1))
    f9.write_bytes(gzip.compress(raw, compresslevel=9))

    fp1 = cheap_fingerprint(str(f1))
    fp9 = cheap_fingerprint(str(f9))

    assert fp1 != fp9
    # Sanity: same file fingerprints stably.
    assert cheap_fingerprint(str(f1)) == fp1


# ─── SRA ────────────────────────────────────────────────────────────────────


def test_sra_uri_returns_deterministic_accession_hash():
    fp_a = cheap_fingerprint("sra://SRR12345")
    fp_b = cheap_fingerprint("sra://SRR12345")
    fp_other = cheap_fingerprint("sra://SRR99999")

    assert fp_a == fp_b
    assert fp_a != fp_other
    size, head, tail = fp_a
    assert size == 0
    assert head == tail  # synthetic — both derived from same accession string


# ─── Unsupported schemes ───────────────────────────────────────────────────


def test_unsupported_scheme_raises_value_error():
    with pytest.raises(ValueError, match="Unsupported URI scheme"):
        cheap_fingerprint("ftp://example.com/foo.fastq")


# ─── Object storage (mocked) ───────────────────────────────────────────────


def _make_mock_s3_client(payload: bytes):
    client = MagicMock()
    client.head_object.return_value = {"ContentLength": len(payload)}

    def get_object(Bucket, Key, Range):  # noqa: N803 — boto3 kwargs
        prefix, byte_range = Range.split("=")
        assert prefix == "bytes"
        start_s, end_s = byte_range.split("-")
        start, end = int(start_s), int(end_s)
        return {"Body": io.BytesIO(payload[start : end + 1])}

    client.get_object.side_effect = get_object
    return client


def test_gcs_fingerprint_uses_storage_module():
    payload = (b"H" * FINGERPRINT_CHUNK_SIZE) + (b"M" * 1000) + (b"T" * FINGERPRINT_CHUNK_SIZE)
    mock_client = _make_mock_s3_client(payload)

    with patch("backend.storage._get_client", return_value=mock_client):
        size, head, tail = cheap_fingerprint("gs://example-bucket/path/file.fastq.gz")

    assert size == len(payload)
    assert head == hashlib.sha256(b"H" * FINGERPRINT_CHUNK_SIZE).hexdigest()
    assert tail == hashlib.sha256(b"T" * FINGERPRINT_CHUNK_SIZE).hexdigest()
    mock_client.head_object.assert_called_once_with(
        Bucket="example-bucket", Key="path/file.fastq.gz"
    )
    # Two ranged GETs: head + tail.
    assert mock_client.get_object.call_count == 2


def test_s3_fingerprint_uses_storage_module():
    payload = b"D" * 200  # < 128 KB — single ranged GET path
    mock_client = _make_mock_s3_client(payload)

    with patch("backend.storage._get_client", return_value=mock_client):
        size, head, tail = cheap_fingerprint("s3://my-bucket/foo/bar.fasta")

    assert size == 200
    assert head == tail
    assert head == hashlib.sha256(payload).hexdigest()
    mock_client.head_object.assert_called_once_with(Bucket="my-bucket", Key="foo/bar.fasta")
    assert mock_client.get_object.call_count == 1


def test_object_storage_empty_object_short_circuits():
    mock_client = _make_mock_s3_client(b"")

    with patch("backend.storage._get_client", return_value=mock_client):
        size, head, tail = cheap_fingerprint("gs://b/empty")

    assert (size, head, tail) == (0, EMPTY_SHA256, EMPTY_SHA256)
    # No bytes need to be fetched for an empty object.
    mock_client.get_object.assert_not_called()


# ─── HTTP/HTTPS (mocked) ───────────────────────────────────────────────────


class _FakeHttpResponse:
    def __init__(self, body: bytes, headers: dict | None = None):
        self.content = body
        self.headers = headers or {}

    def raise_for_status(self):  # noqa: D401 — mimic httpx
        return None


class _FakeHttpClient:
    def __init__(self, payload: bytes):
        self._payload = payload
        self.head_calls = 0
        self.get_calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def head(self, uri):
        self.head_calls += 1
        return _FakeHttpResponse(b"", {"Content-Length": str(len(self._payload))})

    def get(self, uri, headers):
        self.get_calls.append(headers["Range"])
        prefix, byte_range = headers["Range"].split("=")
        assert prefix == "bytes"
        start, end = (int(x) for x in byte_range.split("-"))
        return _FakeHttpResponse(self._payload[start : end + 1])


def test_http_fingerprint_uses_range_requests():
    payload = (b"H" * FINGERPRINT_CHUNK_SIZE) + (b"x" * 100) + (b"T" * FINGERPRINT_CHUNK_SIZE)
    fake = _FakeHttpClient(payload)

    with patch("httpx.Client", return_value=fake):
        size, head, tail = cheap_fingerprint("https://example.com/big.fastq.gz")

    assert size == len(payload)
    assert head == hashlib.sha256(b"H" * FINGERPRINT_CHUNK_SIZE).hexdigest()
    assert tail == hashlib.sha256(b"T" * FINGERPRINT_CHUNK_SIZE).hexdigest()
    assert fake.head_calls == 1
    assert len(fake.get_calls) == 2


def test_http_fingerprint_small_file_single_get():
    payload = b"D" * 4096  # < 128 KB — single ranged GET
    fake = _FakeHttpClient(payload)

    with patch("httpx.Client", return_value=fake):
        size, head, tail = cheap_fingerprint("http://example.com/small.fastq")

    assert size == 4096
    assert head == tail == hashlib.sha256(payload).hexdigest()
    assert len(fake.get_calls) == 1


def test_http_fingerprint_empty_file_skips_gets():
    fake = _FakeHttpClient(b"")

    with patch("httpx.Client", return_value=fake):
        size, head, tail = cheap_fingerprint("https://example.com/empty.fastq")

    assert (size, head, tail) == (0, EMPTY_SHA256, EMPTY_SHA256)
    assert fake.head_calls == 1
    assert fake.get_calls == []
