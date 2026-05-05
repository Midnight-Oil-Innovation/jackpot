# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""I-3c: ``SubmissionsModule`` SDK tests.

The module is a wrapper around the JACKPOT HTTP client. We mock the
client's HTTP methods and assert (a) the right URL/method is hit,
(b) the right body is sent, (c) the response is unwrapped correctly.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from jackpot.core.exceptions import ConflictError, JACKPOTError
from jackpot.sdk.submissions import SubmissionsModule


@pytest.fixture
def fake_client() -> MagicMock:
    client = MagicMock()
    # Mirror JACKPOTClient's interface — the SDK uses .post, .get, .patch,
    # .delete.
    client.api_url = "http://test"
    client._headers = {"Authorization": "Bearer tok"}
    client.post.return_value = {"ok": True}
    client.get.return_value = {"ok": True}
    client.patch.return_value = {"ok": True}
    client.delete.return_value = {"ok": True}
    return client


@pytest.fixture
def sdk(fake_client) -> SubmissionsModule:
    return SubmissionsModule(fake_client)


# ── create / list / get / update / delete ──────────────────────────


def test_create_posts_to_root(sdk, fake_client):
    sdk.create(title="T", target_repository="NCBI", lab_id=1, sample_ids=[1, 2])
    fake_client.post.assert_called_once()
    args, kwargs = fake_client.post.call_args
    assert args[0] == "/api/v1/submissions/"
    body = kwargs["json"]
    assert body["title"] == "T"
    assert body["target_repository"] == "NCBI"
    assert body["sample_ids"] == [1, 2]
    # Optional fields are omitted when None
    assert "description" not in body
    assert "release_date" not in body


def test_create_includes_optional_fields(sdk, fake_client):
    sdk.create(
        title="T",
        target_repository="NCBI",
        lab_id=1,
        sample_ids=[1],
        description="d",
        bioproject_accession="PRJNA1",
        release_date="2030-01-01",
    )
    body = fake_client.post.call_args.kwargs["json"]
    assert body["description"] == "d"
    assert body["bioproject_accession"] == "PRJNA1"
    assert body["release_date"] == "2030-01-01"


def test_list_returns_data_array(sdk, fake_client):
    fake_client.get.return_value = {"data": [{"id": 1}, {"id": 2}]}
    result = sdk.list(lab_id=1, status="DRAFT")
    assert result == [{"id": 1}, {"id": 2}]
    assert fake_client.get.call_args.args[0] == "/api/v1/submissions/"
    params = fake_client.get.call_args.kwargs["params"]
    assert params["lab_id"] == 1
    assert params["status"] == "DRAFT"


def test_list_handles_bare_list_response(sdk, fake_client):
    fake_client.get.return_value = [{"id": 1}]
    result = sdk.list()
    assert result == [{"id": 1}]


def test_get_calls_id_endpoint(sdk, fake_client):
    fake_client.get.return_value = {"id": 42, "title": "T"}
    result = sdk.get(42)
    fake_client.get.assert_called_once_with("/api/v1/submissions/42")
    assert result["id"] == 42


def test_update_patches_specific_path(sdk, fake_client):
    sdk.update(42, title="new title", description="d")
    args, kwargs = fake_client.patch.call_args
    assert args[0] == "/api/v1/submissions/42"
    assert kwargs["json"] == {"title": "new title", "description": "d"}


def test_delete_calls_delete(sdk, fake_client):
    sdk.delete(42)
    fake_client.delete.assert_called_once_with("/api/v1/submissions/42")


# ── samples / validation / generate ────────────────────────────────


def test_add_samples(sdk, fake_client):
    sdk.add_samples(42, [1, 2, 3])
    args, kwargs = fake_client.post.call_args
    assert args[0] == "/api/v1/submissions/42/samples"
    assert kwargs["json"] == {"sample_ids": [1, 2, 3]}


def test_validate(sdk, fake_client):
    sdk.validate(42)
    fake_client.post.assert_called_once_with("/api/v1/submissions/42/validate")


def test_generate_default_link(sdk, fake_client):
    sdk.generate(42)
    args, kwargs = fake_client.post.call_args
    assert args[0] == "/api/v1/submissions/42/generate"
    assert kwargs["json"] == {"copy_files": False}


def test_generate_copy_files(sdk, fake_client):
    sdk.generate(42, copy_files=True)
    assert fake_client.post.call_args.kwargs["json"] == {"copy_files": True}


def test_mark_submitted(sdk, fake_client):
    sdk.mark_submitted(42)
    fake_client.post.assert_called_once_with("/api/v1/submissions/42/mark-submitted")


def test_register_accessions_inline(sdk, fake_client):
    accs = [{"sample_id": "S1", "biosample": "SAMN1"}]
    sdk.register_accessions(42, accs)
    args, kwargs = fake_client.post.call_args
    assert args[0] == "/api/v1/submissions/42/register-accessions"
    assert kwargs["json"] == {"accessions": accs}


def test_mark_rejected_carries_reason(sdk, fake_client):
    sdk.mark_rejected(42, "duplicate")
    assert fake_client.post.call_args.kwargs["json"] == {"reason": "duplicate"}


def test_withdraw_carries_reason(sdk, fake_client):
    sdk.withdraw(42, "operator request")
    assert fake_client.post.call_args.kwargs["json"] == {"reason": "operator request"}


# ── I-3c: backend execution ────────────────────────────────────────


def test_execute_calls_execute_endpoint(sdk, fake_client):
    fake_client.post.return_value = {"id": 42, "status": "EXECUTING"}
    result = sdk.execute(42)
    fake_client.post.assert_called_once_with("/api/v1/submissions/42/execute")
    assert result["status"] == "EXECUTING"


def test_execute_propagates_conflict(sdk, fake_client):
    fake_client.post.side_effect = ConflictError(
        "Backend execution is disabled in this deployment.", status_code=409
    )
    with pytest.raises(ConflictError):
        sdk.execute(42)


def test_execute_propagates_missing_credentials_400(sdk, fake_client):
    fake_client.post.side_effect = JACKPOTError(
        "Backend execution requires credentials for repo 'ncbi'.",
        status_code=400,
    )
    with pytest.raises(JACKPOTError):
        sdk.execute(42)


def test_retry_execution_calls_retry_endpoint(sdk, fake_client):
    sdk.retry_execution(42)
    fake_client.post.assert_called_once_with("/api/v1/submissions/42/retry-execution")


def test_execution_logs_returns_entries_array(sdk, fake_client):
    fake_client.get.return_value = {
        "submission_id": 42,
        "entries": [{"attempt": 1}, {"attempt": 2}],
    }
    result = sdk.execution_logs(42)
    assert result == [{"attempt": 1}, {"attempt": 2}]
    fake_client.get.assert_called_once_with("/api/v1/submissions/42/execution-logs")


def test_execution_logs_empty_response(sdk, fake_client):
    fake_client.get.return_value = {"submission_id": 42, "entries": []}
    assert sdk.execution_logs(42) == []
