# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Pytest fixtures for storage backend tests.

Spins up real services in containers using testcontainers:
- MinIO for S3 / MinIO tests (dynamic port mapping)
- fake-gcs-server for GCS tests (FIXED host port 4443 — see notes)

Local filesystem tests use pytest's tmp_path fixture (no container needed).

Why fake-gcs-server uses a fixed host port:
fake-gcs-server generates resumable-upload continuation URLs server-side and
returns them to the client. Those URLs need to be reachable from the client.
The -external-url flag tells fake-gcs-server what URL to put in those
responses. We need to know the URL before starting the container, which means
we need to know the host port before starting the container, which means we
have to bind to a fixed port. Default: 4443 (matching the in-container port).
If port 4443 is already in use on your machine, the test will fail with a
port-binding error and you'll need to free the port (or override via the
JACKPOT_TEST_FAKE_GCS_PORT env var).
"""

from __future__ import annotations

import os
import secrets
import socket
import time
from collections.abc import Generator

import boto3
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
        DockerContainer("quay.io/minio/minio:RELEASE.2024-09-13T20-26-02Z")
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


# ---------- fake-gcs-server (fixed host port) ----------


def _get_fake_gcs_port() -> int:
    """The fixed host port for fake-gcs-server.

    Override with JACKPOT_TEST_FAKE_GCS_PORT env var if 4443 is taken.
    """
    return int(os.environ.get("JACKPOT_TEST_FAKE_GCS_PORT", "4443"))


def _check_port_available(port: int) -> None:
    """Raise a clear error if the host port is already in use."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError as e:
        raise RuntimeError(
            f"Host port {port} is in use; fake-gcs-server cannot bind to it. "
            f"Free the port, or set JACKPOT_TEST_FAKE_GCS_PORT to a free port. "
            f"Underlying error: {e}"
        ) from e
    finally:
        sock.close()


@pytest.fixture(scope="session")
def fake_gcs_container() -> Generator[DockerContainer, None, None]:
    """Run a fake-gcs-server container, bound to a fixed host port.

    -external-url tells fake-gcs-server what URL to advertise in upload
    continuation responses, which is critical for resumable uploads to work.
    """
    port = _get_fake_gcs_port()
    _check_port_available(port)

    external_url = f"http://127.0.0.1:{port}"

    container = (
        DockerContainer("fsouza/fake-gcs-server:1.49.2")
        .with_command(f"-scheme http -port 4443 -backend memory -external-url {external_url}")
        .with_bind_ports(4443, port)
    )
    container.start()
    try:
        wait_for_logs(container, "server started", timeout=30)
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def fake_gcs_endpoint(fake_gcs_container: DockerContainer) -> str:
    """The URL clients should use to reach fake-gcs-server."""
    port = _get_fake_gcs_port()
    endpoint = f"http://127.0.0.1:{port}"

    deadline = time.time() + 30
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            r = requests.get(f"{endpoint}/storage/v1/b", timeout=2)
            if r.status_code in (200, 404):
                return endpoint
        except requests.RequestException as e:
            last_err = e
            time.sleep(0.5)
    raise RuntimeError(f"fake-gcs-server did not become ready: {last_err}")


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
