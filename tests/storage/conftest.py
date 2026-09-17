# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Pytest fixtures for storage backend tests.

Spins up real services in containers using testcontainers:
- MinIO for S3 / MinIO tests (dynamic port mapping)
- fake-gcs-server for GCS tests (host port chosen up front — see notes)

Local filesystem tests use pytest's tmp_path fixture (no container needed).

Why fake-gcs-server needs its host port decided before the container starts:
fake-gcs-server generates resumable-upload continuation URLs server-side and
returns them to the client. The -external-url flag tells it what URL to put in
those responses, so we must know the host port before starting the container
and cannot use testcontainers' usual after-the-fact port mapping. We ask the
OS for a free port rather than pinning one, which keeps the suite off whatever
already owns 4443 and lets pytest-xdist workers run in parallel.
"""

from __future__ import annotations

import contextlib
import secrets
import socket
import time
from collections.abc import Generator

import boto3
import container_images
import pytest
import requests
from botocore.client import Config as BotoConfig
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

# ---------- MinIO (dynamic port) ----------


@pytest.fixture(scope="session")
def minio_container() -> Generator[DockerContainer, None, None]:
    """Run a MinIO container for the test session."""
    container = (
        DockerContainer(container_images.MINIO)
        .with_command("server /data --console-address :9001")
        .with_env("MINIO_ROOT_USER", "minioadmin")
        .with_env("MINIO_ROOT_PASSWORD", "minioadmin")
        .with_exposed_ports(9000, 9001)
    )
    container.start()
    try:
        wait_for_logs(container, "API:", timeout=30)
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def minio_endpoint(minio_container: DockerContainer) -> str:
    host = minio_container.get_container_host_ip()
    port = minio_container.get_exposed_port(9000)
    return f"http://{host}:{port}"


@pytest.fixture
def minio_bucket(minio_endpoint: str) -> Generator[str, None, None]:
    bucket = f"jackpot-test-{secrets.token_hex(4)}"
    client = boto3.client(
        "s3",
        endpoint_url=minio_endpoint,
        aws_access_key_id="minioadmin",
        aws_secret_access_key="minioadmin",
        region_name="us-east-1",
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    client.create_bucket(Bucket=bucket)
    try:
        yield bucket
    finally:
        try:
            objects = client.list_objects_v2(Bucket=bucket).get("Contents", []) or []
            for obj in objects:
                client.delete_object(Bucket=bucket, Key=obj["Key"])
            client.delete_bucket(Bucket=bucket)
        except Exception:
            pass


# ---------- fake-gcs-server (host port chosen before start) ----------

# How long one port attempt waits for the server to answer before the
# fixture assumes the port was lost and tries another. Named so the
# retry canary can shrink it instead of paying 10s per deliberate miss.
_PROBE_TIMEOUT_SECONDS = 10.0


def _free_host_port() -> int:
    """Ask the OS for a free host port and release it immediately."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def fake_gcs_container() -> Generator[tuple[DockerContainer, int], None, None]:
    """Run fake-gcs-server on a host port chosen before the container starts.

    -external-url tells fake-gcs-server what URL to advertise in upload
    continuation responses, which is critical for resumable uploads to work.
    So the port must be known up front, and that leaves a window between
    releasing the probe socket and docker binding the port. Retry rather
    than fail: under `pytest -n auto` several workers probe at the same
    moment and the OS can hand the same just-freed port to two of them,
    which is the flake this whole fixture exists to avoid.
    """
    last_err: Exception | None = None
    for _ in range(5):
        port = _free_host_port()
        container = (
            DockerContainer(container_images.FAKE_GCS)
            .with_command(
                f"-scheme http -port 4443 -backend memory -external-url http://127.0.0.1:{port}"
            )
            .with_bind_ports(4443, port)
        )
        try:
            container.start()
            wait_for_logs(container, "server started", timeout=30)
            _wait_until_fake_gcs_ready(f"http://127.0.0.1:{port}", _PROBE_TIMEOUT_SECONDS)
        except Exception as e:
            # A lost-port collision does NOT surface as a start() failure under
            # every docker backend — colima happily starts the container and
            # the symptom is a server nothing can reach. So the reachability
            # probe is what the retry keys on, not the start call.
            last_err = e
            with contextlib.suppress(Exception):
                container.stop()
            continue
        try:
            yield container, port
        finally:
            container.stop()
        return
    raise RuntimeError(f"fake-gcs-server could not bind a usable host port in 5 tries: {last_err}")


def _wait_until_fake_gcs_ready(endpoint: str, timeout: float) -> None:
    """Block until FAKE-GCS-SERVER — not merely something — answers on `endpoint`.

    The identity check is the point. This probe is what the retry loop keys on,
    so anything it accepts is treated as "the port is ours". An earlier version
    accepted any 200 *or 404*, which means an unrelated service holding the port
    and returning a 404 would have been read as success: the retry would not
    fire and every storage test would run against a stranger.

    The pinned image answers /storage/v1/b with 200 and {"kind": "storage#buckets"}.
    """
    deadline = time.time() + timeout
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            r = requests.get(f"{endpoint}/storage/v1/b", timeout=2)
            if r.status_code == 200 and r.json().get("kind") == "storage#buckets":
                return
            last_err = RuntimeError(
                f"port answered, but not as fake-gcs-server: HTTP {r.status_code} {r.text[:80]!r}"
            )
        except (requests.RequestException, ValueError) as e:
            last_err = e
        time.sleep(0.5)
    raise RuntimeError(f"fake-gcs-server did not become ready on {endpoint}: {last_err}")


@pytest.fixture(scope="session")
def fake_gcs_endpoint(fake_gcs_container: tuple[DockerContainer, int]) -> str:
    """The URL clients should use to reach fake-gcs-server."""
    _container, port = fake_gcs_container
    return f"http://127.0.0.1:{port}"


@pytest.fixture
def gcs_bucket(fake_gcs_endpoint: str) -> Generator[tuple[str, str, str], None, None]:
    """Create a bucket on fake-gcs-server. Returns (bucket_name, project, endpoint)."""
    project = "jackpot-test-project"
    bucket_name = f"jackpot-test-{secrets.token_hex(4)}"
    create_url = f"{fake_gcs_endpoint}/storage/v1/b?project={project}"

    resp = requests.post(create_url, json={"name": bucket_name}, timeout=5)
    assert resp.status_code in (
        200,
        409,
    ), f"Could not create bucket: {resp.status_code} {resp.text}"

    try:
        yield bucket_name, project, fake_gcs_endpoint
    finally:
        try:
            list_url = f"{fake_gcs_endpoint}/storage/v1/b/{bucket_name}/o"
            r = requests.get(list_url, timeout=5)
            if r.status_code == 200:
                for item in r.json().get("items", []):
                    obj_name = item["name"]
                    requests.delete(
                        f"{fake_gcs_endpoint}/storage/v1/b/{bucket_name}/o/{obj_name}",
                        timeout=5,
                    )
            requests.delete(
                f"{fake_gcs_endpoint}/storage/v1/b/{bucket_name}",
                timeout=5,
            )
        except Exception:
            pass
