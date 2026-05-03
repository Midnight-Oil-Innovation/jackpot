# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Cheap file fingerprinting for content-hash-keyed deduplication.

Phase P0f F-3. See spec.md Phase P0f Specification (the "New modules"
subsection) and Critical Rules 57 (no copy on ingest) and 58
(content_hash is the dedup primitive).

The cheap fingerprint reads only the first 64 KB and last 64 KB of a
file, producing (size_bytes, head_sha256_hex, tail_sha256_hex). This
indexes ``sample_files`` for dedup-during-ingest before the full
``content_hash`` is populated. The ``compute_full_content_hash``
background job (F-4) computes proper SHA-256 lazily and reconciles any
fingerprint collisions cheap fingerprinting missed.

Per Critical Rule 20, this module does not duplicate file-type or
naming logic — it fingerprints raw bytes regardless of file type.
gzip and BGZF content is fingerprinted as compressed bytes (not
decompressed), which is correct: two files identical at the byte level
dedup; two files identical only after decompression do not (until F-4
reconciles them).
"""

from __future__ import annotations

import hashlib
import os
from typing import Final
from urllib.parse import urlparse

FINGERPRINT_CHUNK_SIZE: Final[int] = 64 * 1024


def cheap_fingerprint(uri: str) -> tuple[int, str, str]:
    """Return (size_bytes, head64k_sha256_hex, tail64k_sha256_hex) for ``uri``.

    Reads only the first 64 KB and last 64 KB of the file rather than
    streaming the whole thing. Suitable for dedup-during-ingest checks
    where a full SHA-256 would be too slow on multi-gigabyte FASTQ files.

    Supported schemes:

    - ``file://`` and bare paths — ``os.open`` + ``os.pread``
    - ``gs://bucket/key`` — Range request via ``backend.storage._get_client``
    - ``s3://bucket/key`` — Range request via ``backend.storage._get_client``
    - ``sra://ACCESSION`` — synthetic hash derived from accession
      (SRA archives don't yield to byte-range reads; F-4 handles the
      real content via ``fasterq-dump``)
    - ``http://`` / ``https://`` — Range request via ``httpx``

    Edge cases:

    - File smaller than 128 KB: head and tail overlap; both hashes
      cover the whole file and are equal.
    - Empty file: returns ``(0, sha256(""), sha256(""))``.
    - Missing or unreadable: raises ``FileNotFoundError`` /
      ``PermissionError`` (caller decides whether to mark ``BROKEN``).
    """
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    if scheme in ("", "file"):
        return _fingerprint_local(parsed.path if scheme == "file" else uri)
    if scheme == "gs":
        return _fingerprint_object_storage(parsed.netloc, parsed.path.lstrip("/"))
    if scheme == "s3":
        return _fingerprint_object_storage(parsed.netloc, parsed.path.lstrip("/"))
    if scheme == "sra":
        accession = parsed.netloc or parsed.path.lstrip("/")
        return _fingerprint_sra(accession)
    if scheme in ("http", "https"):
        return _fingerprint_http(uri)
    raise ValueError(f"Unsupported URI scheme: {scheme!r}")


def _fingerprint_local(path: str) -> tuple[int, str, str]:
    """Fingerprint a local file using ``os.open`` + ``os.pread``."""
    fd = os.open(path, os.O_RDONLY)
    try:
        size = os.fstat(fd).st_size
        if size == 0:
            empty = hashlib.sha256(b"").hexdigest()
            return (0, empty, empty)
        if size < 2 * FINGERPRINT_CHUNK_SIZE:
            data = os.pread(fd, size, 0)
            digest = hashlib.sha256(data).hexdigest()
            return (size, digest, digest)
        head = os.pread(fd, FINGERPRINT_CHUNK_SIZE, 0)
        tail = os.pread(fd, FINGERPRINT_CHUNK_SIZE, size - FINGERPRINT_CHUNK_SIZE)
        return (
            size,
            hashlib.sha256(head).hexdigest(),
            hashlib.sha256(tail).hexdigest(),
        )
    finally:
        os.close(fd)


def _fingerprint_object_storage(bucket: str, key: str) -> tuple[int, str, str]:
    """Fingerprint a ``gs://`` or ``s3://`` object via Range requests.

    Uses ``backend.storage._get_client`` so credentials and endpoint
    follow the same configuration as the rest of the storage layer.
    """
    from backend.storage import _get_client

    client = _get_client()
    head = client.head_object(Bucket=bucket, Key=key)
    size = int(head["ContentLength"])

    if size == 0:
        empty = hashlib.sha256(b"").hexdigest()
        return (0, empty, empty)

    if size <= 2 * FINGERPRINT_CHUNK_SIZE:
        body = client.get_object(
            Bucket=bucket,
            Key=key,
            Range=f"bytes=0-{size - 1}",
        )["Body"].read()
        digest = hashlib.sha256(body).hexdigest()
        return (size, digest, digest)

    head_bytes = client.get_object(
        Bucket=bucket,
        Key=key,
        Range=f"bytes=0-{FINGERPRINT_CHUNK_SIZE - 1}",
    )["Body"].read()
    tail_bytes = client.get_object(
        Bucket=bucket,
        Key=key,
        Range=f"bytes={size - FINGERPRINT_CHUNK_SIZE}-{size - 1}",
    )["Body"].read()
    return (
        size,
        hashlib.sha256(head_bytes).hexdigest(),
        hashlib.sha256(tail_bytes).hexdigest(),
    )


def _fingerprint_sra(accession: str) -> tuple[int, str, str]:
    """Synthetic fingerprint for an ``sra://`` URI.

    SRA accessions are multi-file archives that don't support byte-range
    reads in any practical sense. We return a deterministic hash of the
    accession so two registrations of the same accession dedup, and
    leave full-content-hashing to F-4 (which triggers ``fasterq-dump``
    on a compute node).

    Size is reported as ``0`` because the on-disk size after extraction
    is unknown until the dump runs.
    """
    digest = hashlib.sha256(f"sra://{accession}".encode()).hexdigest()
    return (0, digest, digest)


def _fingerprint_http(uri: str) -> tuple[int, str, str]:
    """Fingerprint an ``http(s)://`` URI via Range requests.

    Last-resort path. Uses HEAD for size, then two ranged GETs.
    """
    import httpx

    with httpx.Client(follow_redirects=True) as client:
        head_resp = client.head(uri)
        head_resp.raise_for_status()
        size = int(head_resp.headers["Content-Length"])

        if size == 0:
            empty = hashlib.sha256(b"").hexdigest()
            return (0, empty, empty)

        if size < 2 * FINGERPRINT_CHUNK_SIZE:
            full = client.get(uri, headers={"Range": f"bytes=0-{size - 1}"})
            full.raise_for_status()
            digest = hashlib.sha256(full.content).hexdigest()
            return (size, digest, digest)

        head_bytes = client.get(uri, headers={"Range": f"bytes=0-{FINGERPRINT_CHUNK_SIZE - 1}"})
        head_bytes.raise_for_status()
        tail_bytes = client.get(
            uri,
            headers={"Range": f"bytes={size - FINGERPRINT_CHUNK_SIZE}-{size - 1}"},
        )
        tail_bytes.raise_for_status()
        return (
            size,
            hashlib.sha256(head_bytes.content).hexdigest(),
            hashlib.sha256(tail_bytes.content).hexdigest(),
        )


__all__ = [
    "FINGERPRINT_CHUNK_SIZE",
    "cheap_fingerprint",
]
