# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Tests for ``jackpot.sdk.files.FilesModule`` (Phase P0f F-9).

The module is a thin HTTP wrapper — the assertions verify that each
public method calls the right URL with the right params/body and
returns the unwrapped data shape.
"""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from jackpot.core.client import JACKPOTClient
from jackpot.sdk.files import FilesModule

API_URL = "http://testserver"
TOKEN = "jk_test_abc123"


@pytest.fixture
def files() -> FilesModule:
    return FilesModule(JACKPOTClient(api_url=API_URL, token=TOKEN))


def test_get_returns_unwrapped_dict(files, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{API_URL}/api/v1/files/9001",
        json={
            "success": True,
            "data": {"id": 9001, "storage_state": "EXTERNAL"},
        },
    )
    out = files.get(9001)
    assert out == {"id": 9001, "storage_state": "EXTERNAL"}


def test_list_passes_filters(files, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=(
            f"{API_URL}/api/v1/files/?page=1&per_page=50&"
            "sort_by=first_seen_at&sort_dir=desc&storage_state=BROKEN&project_id=12"
        ),
        json={
            "success": True,
            "data": [{"id": 1, "storage_state": "BROKEN"}],
            "pagination": {"page": 1, "per_page": 50, "total": 1, "pages": 1},
        },
    )
    out = files.list(storage_state="BROKEN", project_id=12)
    assert isinstance(out, list)
    assert out[0]["id"] == 1


def test_promote_posts_target_and_retention(files, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{API_URL}/api/v1/files/9001/promote",
        method="POST",
        status_code=202,
        json={
            "success": True,
            "data": {
                "file_id": 9001,
                "current_state": "EXTERNAL",
                "target_state": "MANAGED",
                "job_id": "promote_9001_xyz",
                "estimated_seconds": 5,
                "status": "QUEUED",
            },
        },
    )
    out = files.promote(9001, "managed", retention_policy="long_term")
    assert out["job_id"] == "promote_9001_xyz"
    assert out["target_state"] == "MANAGED"
    sent = httpx_mock.get_request().read()
    import json

    body = json.loads(sent.decode())
    assert body == {"to": "MANAGED", "retention_policy": "LONG_TERM"}


def test_get_job_returns_status(files, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{API_URL}/api/v1/files/jobs/promote_9001_xyz",
        json={
            "success": True,
            "data": {
                "job_id": "promote_9001_xyz",
                "status": "COMPLETED",
                "outcome": "SUCCESS",
                "copied_bytes": 4096,
            },
        },
    )
    out = files.get_job("promote_9001_xyz")
    assert out["status"] == "COMPLETED"
    assert out["copied_bytes"] == 4096


def test_verify_returns_post_verify_snapshot(files, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{API_URL}/api/v1/files/9001/verify",
        method="POST",
        json={
            "success": True,
            "data": {
                "file_id": 9001,
                "uri": "file:///srv/r1.fastq.gz",
                "storage_state": "EXTERNAL",
                "last_verification_status": "OK",
                "last_verified_at": "2026-05-03T15:42:01Z",
            },
        },
    )
    out = files.verify(9001)
    assert out["last_verification_status"] == "OK"
    assert out["storage_state"] == "EXTERNAL"


def test_session_exposes_files_module(monkeypatch):
    """``Session.files`` instantiates the module lazily."""
    monkeypatch.setenv("JACKPOT_API_URL", "http://x")
    monkeypatch.setenv("JACKPOT_API_TOKEN", "tok")
    from jackpot.sdk.session import Session

    session = Session(api_url="http://x", token="tok")
    assert isinstance(session.files, FilesModule)
    # Cached on the second access
    assert session.files is session.files
