"""
Tests for POST /api/v1/pipelines/{run_id}/results/{result_type}.

Covers: happy-path 201, unknown result_type 422, invalid payload 422,
duplicate 409, unknown run_id 404, missing or wrong X-Pipeline-Token 401,
pipeline_results metrics merge within the same transaction.
"""

from __future__ import annotations

import uuid

import pytest

from backend.database import execute_query, execute_write


def _seed_pipeline_run(token: str) -> str:
    """Seed a pipeline_runs row and return its run_id."""
    run_id = f"test-run-{uuid.uuid4().hex[:8]}"
    execute_write(
        """
        INSERT INTO pipeline_runs
            (lab_id, project_id, launched_by_id, pipeline_name, pipeline_version,
             run_id, pipeline_token, status)
        VALUES (1, 1, 1, 'jackpot-sc2', 'v1.0.0', :run_id, :token, 'running')
        """,
        {"run_id": run_id, "token": token},
    )
    return run_id


def _cleanup(run_id: str) -> None:
    execute_write("DELETE FROM pangolin_results WHERE run_id = :r", {"r": run_id})
    execute_write("DELETE FROM amr_results WHERE run_id = :r", {"r": run_id})
    execute_write("DELETE FROM nextclade_results WHERE run_id = :r", {"r": run_id})
    execute_write("DELETE FROM pipeline_results WHERE run_id = :r", {"r": run_id})
    execute_write("DELETE FROM pipeline_runs WHERE run_id = :r", {"r": run_id})
    execute_write(
        "DELETE FROM audit_log WHERE resource_id LIKE :r",
        {"r": f"{run_id}:%"},
    )


@pytest.mark.asyncio
async def test_register_pangolin_result_201(client):
    token = "tok-" + uuid.uuid4().hex
    run_id = _seed_pipeline_run(token)
    payload = {
        "sample_id": "AZ-1",
        "lineage": "BA.2.86",
        "pangolin_version": "4.3.1",
        "conflict": 0.0,
    }
    resp = await client.post(
        f"/api/v1/pipelines/{run_id}/results/pangolin_results",
        json=payload,
        headers={"X-Pipeline-Token": token},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "registered"
    assert isinstance(body["data"]["result_id"], int)

    rows = execute_query(
        "SELECT lineage, pangolin_version FROM pangolin_results "
        "WHERE run_id = :r AND sample_id = :s",
        {"r": run_id, "s": "AZ-1"},
    )
    assert len(rows) == 1
    assert rows[0]["lineage"] == "BA.2.86"

    summary = execute_query(
        "SELECT metrics FROM pipeline_results WHERE run_id = :r AND sample_id = :s",
        {"r": run_id, "s": "AZ-1"},
    )
    assert len(summary) == 1
    assert summary[0]["metrics"]["pangolin_results"]["registered"] is True

    audits = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'pipeline_result' "
        "AND resource_id LIKE :p",
        {"p": f"{run_id}:%"},
    )
    assert any(a["action"] == "REGISTER_PIPELINE_RESULT" for a in audits)

    _cleanup(run_id)


@pytest.mark.asyncio
async def test_wrong_token_returns_401(client):
    token = "tok-" + uuid.uuid4().hex
    run_id = _seed_pipeline_run(token)

    resp = await client.post(
        f"/api/v1/pipelines/{run_id}/results/pangolin_results",
        json={"sample_id": "AZ-1", "lineage": "BA.2.86", "pangolin_version": "4.3.1"},
        headers={"X-Pipeline-Token": "wrong-token"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_TOKEN"

    rows = execute_query("SELECT id FROM pangolin_results WHERE run_id = :r", {"r": run_id})
    assert rows == []

    _cleanup(run_id)


@pytest.mark.asyncio
async def test_missing_token_returns_401(client):
    token = "tok-" + uuid.uuid4().hex
    run_id = _seed_pipeline_run(token)

    resp = await client.post(
        f"/api/v1/pipelines/{run_id}/results/pangolin_results",
        json={"sample_id": "AZ-1", "lineage": "BA.2.86", "pangolin_version": "4.3.1"},
    )
    assert resp.status_code == 401
    _cleanup(run_id)


@pytest.mark.asyncio
async def test_unknown_run_id_returns_404(client):
    resp = await client.post(
        "/api/v1/pipelines/does-not-exist/results/pangolin_results",
        json={"sample_id": "AZ-1", "lineage": "BA.2.86", "pangolin_version": "4.3.1"},
        headers={"X-Pipeline-Token": "anything"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RUN_NOT_FOUND"


@pytest.mark.asyncio
async def test_unknown_result_type_returns_422(client):
    token = "tok-" + uuid.uuid4().hex
    run_id = _seed_pipeline_run(token)
    resp = await client.post(
        f"/api/v1/pipelines/{run_id}/results/gobbledygook",
        json={"sample_id": "AZ-1"},
        headers={"X-Pipeline-Token": token},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "UNKNOWN_RESULT_TYPE"
    _cleanup(run_id)


@pytest.mark.asyncio
async def test_invalid_payload_returns_422(client):
    token = "tok-" + uuid.uuid4().hex
    run_id = _seed_pipeline_run(token)

    # identity_percent > 100 violates AMRResult bounds
    resp = await client.post(
        f"/api/v1/pipelines/{run_id}/results/amr_results",
        json={
            "sample_id": "AZ-1",
            "gene_symbol": "mcr-1",
            "tool_name": "amrfinderplus",
            "identity_percent": 120,
        },
        headers={"X-Pipeline-Token": token},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_PAYLOAD"
    _cleanup(run_id)


@pytest.mark.asyncio
async def test_duplicate_returns_409(client):
    token = "tok-" + uuid.uuid4().hex
    run_id = _seed_pipeline_run(token)
    payload = {
        "sample_id": "AZ-1",
        "lineage": "BA.2.86",
        "pangolin_version": "4.3.1",
    }
    first = await client.post(
        f"/api/v1/pipelines/{run_id}/results/pangolin_results",
        json=payload,
        headers={"X-Pipeline-Token": token},
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/pipelines/{run_id}/results/pangolin_results",
        json=payload,
        headers={"X-Pipeline-Token": token},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DUPLICATE_RESULT"
    _cleanup(run_id)


@pytest.mark.asyncio
async def test_jsonb_field_persisted(client):
    """NextcladeResult.substitutions is JSONB — make sure the list round-trips."""
    token = "tok-" + uuid.uuid4().hex
    run_id = _seed_pipeline_run(token)
    subs = ["A23403G", "C14408T"]
    payload = {
        "sample_id": "AZ-1",
        "nextclade_version": "3.4.1",
        "clade": "24A",
        "substitutions": subs,
        "total_substitutions": 2,
    }
    resp = await client.post(
        f"/api/v1/pipelines/{run_id}/results/nextclade_results",
        json=payload,
        headers={"X-Pipeline-Token": token},
    )
    assert resp.status_code == 201, resp.text

    rows = execute_query(
        "SELECT substitutions, total_substitutions FROM nextclade_results "
        "WHERE run_id = :r AND sample_id = :s",
        {"r": run_id, "s": "AZ-1"},
    )
    assert rows[0]["substitutions"] == subs
    assert rows[0]["total_substitutions"] == 2
    _cleanup(run_id)


@pytest.mark.asyncio
async def test_metrics_merges_across_result_types(client):
    """Two different result_types for the same sample merge into one metrics blob."""
    token = "tok-" + uuid.uuid4().hex
    run_id = _seed_pipeline_run(token)

    r1 = await client.post(
        f"/api/v1/pipelines/{run_id}/results/pangolin_results",
        json={"sample_id": "AZ-1", "lineage": "BA.2.86", "pangolin_version": "4.3.1"},
        headers={"X-Pipeline-Token": token},
    )
    assert r1.status_code == 201

    r2 = await client.post(
        f"/api/v1/pipelines/{run_id}/results/amr_results",
        json={"sample_id": "AZ-1", "gene_symbol": "mcr-1", "tool_name": "amrfinderplus"},
        headers={"X-Pipeline-Token": token},
    )
    assert r2.status_code == 201

    summary = execute_query(
        "SELECT metrics FROM pipeline_results WHERE run_id = :r AND sample_id = :s",
        {"r": run_id, "s": "AZ-1"},
    )
    assert len(summary) == 1
    metrics = summary[0]["metrics"]
    assert metrics["pangolin_results"]["registered"] is True
    assert metrics["amr_results"]["registered"] is True
    _cleanup(run_id)
