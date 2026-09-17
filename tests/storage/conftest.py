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


@pytest.fixture(scope="session")
def fake_gcs_port() -> int:
    """A free host port to bind fake-gcs-server to, picked before it starts."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def fake_gcs_container(fake_gcs_port: int) -> Generator[DockerContainer, None, None]:
    """Run a fake-gcs-server container, bound to the chosen host port.

    -external-url tells fake-gcs-server what URL to advertise in upload
    continuation responses, which is critical for resumable uploads to work.
    """
    external_url = f"http://127.0.0.1:{fake_gcs_port}"

    container = (
        DockerContainer(container_images.FAKE_GCS)
        .with_command(f"-scheme http -port 4443 -backend memory -external-url {external_url}")
        .with_bind_ports(4443, fake_gcs_port)
    )
    container.start()
    try:
        wait_for_logs(container, "server started", timeout=30)
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def fake_gcs_endpoint(fake_gcs_container: DockerContainer, fake_gcs_port: int) -> str:
    """The URL clients should use to reach fake-gcs-server."""
    endpoint = f"http://127.0.0.1:{fake_gcs_port}"

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
