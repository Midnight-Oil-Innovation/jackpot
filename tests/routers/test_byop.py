# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Tests for the P0f B-BYOP-4 BYOP pipeline CRUD + lifecycle router.

Uses ``TestClient`` against a minimal FastAPI app mounting only
``backend.routers.byop.router`` with an in-memory SQLite engine
(mirrors ``test_profiles.py``). Stage 1 / Stage 2 gates
(``validate_manifest`` / ``run_sandbox``) are monkeypatched so no
Docker, no network, no schema file reads.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.auth.guards import get_current_user
from backend.database import get_db_dep
from backend.routers import byop
from backend.routers.byop import Base, router
from backend.services.byop_sandbox import SandboxResult, StepResult
from backend.services.byop_validator import CheckResult, ValidationReport

USER = {"id": 1, "email": "bioinfo@example.org", "is_platform_admin": False}

VALID_MANIFEST = """\
api_version: v1
kind: pipeline
metadata:
  name: tb-typer
  display_name: TB Typer
  version: 1.2.3
  description: TB lineage typing
  license: MIT
  citation: doi:10.0/example
engine:
  type: nextflow
  version: "23.10"
  entrypoint: main.nf
containers:
  - image: quay.io/tb/typer:1.2.3
cost:
  estimated_total_per_sample_usd: 0.42
"""

CREATE_PAYLOAD = {
    "source_type": "git",
    "source_url": "https://github.com/example/tb-typer",
    "source_ref": "v1.2.3",
    "manifest_yaml": VALID_MANIFEST,
}


def _stage1_pass(manifest, schema, refs, licenses, perms):
    return ValidationReport(
        manifest_id="tb-typer-1.2.3",
        passed=True,
        checks=[CheckResult(check_name="schema_conformance", passed=True, message="ok")],
    )


def _stage1_fail(manifest, schema, refs, licenses, perms):
    return ValidationReport(
        manifest_id="tb-typer-1.2.3",
        passed=False,
        checks=[CheckResult(check_name="license", passed=False, message="license rejected")],
    )


def _stage2_pass(pipeline_id, image, engine_type, entrypoint, sandbox_dir, isolation="docker"):
    return SandboxResult(
        pipeline_id=pipeline_id,
        outcome="SANDBOX_PASSED",
        steps=[StepResult(step_name="container_pull", passed=True, message="ok")],
        sandbox_log="pull ok",
    )


def _stage2_fail(pipeline_id, image, engine_type, entrypoint, sandbox_dir, isolation="docker"):
    return SandboxResult(
        pipeline_id=pipeline_id,
        outcome="SANDBOX_FAILED",
        steps=[StepResult(step_name="container_pull", passed=False, message="pull failed")],
        sandbox_log="pull failed",
    )


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    monkeypatch.setattr(byop, "validate_manifest", _stage1_pass)
    monkeypatch.setattr(byop, "run_sandbox", _stage2_pass)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_get_db() -> Iterator:
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    fresh = FastAPI()
    fresh.include_router(router)
    fresh.dependency_overrides[get_db_dep] = override_get_db
    fresh.dependency_overrides[get_current_user] = lambda: USER
    try:
        yield fresh
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _create(client: TestClient) -> dict:
    response = client.post("/api/v1/byop/pipelines", json=CREATE_PAYLOAD)
    assert response.status_code == 201, response.text
    return response.json()


# --- CRUD happy paths -----------------------------------------------------


@pytest.fixture(autouse=True)
def _byop_author(authz_grants):
    """These are CRUD tests, not authorization tests — the caller holds the
    register verb instance-wide so each case exercises the route rather than
    the guard. The authorization boundaries themselves are pinned in
    test_tenancy.py and tests/authz/.

    MOCK_USER_ID mirrors whatever user the module's client fixture presents.
    """
    from backend.authz import ROOT

    for uid in (1, 2, 3):
        authz_grants(uid, [("pipeline:register_custom", ROOT)])


def test_create_pipeline(client: TestClient) -> None:
    body = _create(client)
    assert body["name"] == "tb-typer"
    assert body["display_name"] == "TB Typer"
    assert body["version"] == "1.2.3"
    assert body["engine_type"] == "nextflow"
    assert body["engine_version"] == "23.10"
    assert body["source_type"] == "git"
    assert body["license_spdx"] == "MIT"
    assert body["cost_estimate_usd"] == 0.42
    assert body["pipeline_status"] == "ACTIVE"
    assert body["registered_by_user_id"] == "1"
    assert body["activated_at"] is not None
    assert body["last_validated_at"] is not None


def test_get_pipeline(client: TestClient) -> None:
    created = _create(client)
    response = client.get(f"/api/v1/byop/pipelines/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["name"] == "tb-typer"


def test_list_pipelines(client: TestClient) -> None:
    _create(client)
    response = client.get("/api/v1/byop/pipelines")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1


def test_list_pipelines_filters(client: TestClient) -> None:
    created = _create(client)
    client.post(f"/api/v1/byop/pipelines/{created['id']}/deactivate")
    assert client.get("/api/v1/byop/pipelines", params={"pipeline_status": "ACTIVE"}).json() == []
    assert (
        len(client.get("/api/v1/byop/pipelines", params={"pipeline_status": "DEACTIVATED"}).json())
        == 1
    )
    assert len(client.get("/api/v1/byop/pipelines", params={"engine_type": "nextflow"}).json()) == 1


def test_update_pipeline_metadata_only(client: TestClient) -> None:
    created = _create(client)
    response = client.put(
        f"/api/v1/byop/pipelines/{created['id']}",
        json={"display_name": "TB Typer Pro", "description": "renamed"},
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "TB Typer Pro"
    assert response.json()["description"] == "renamed"


def test_patch_pipeline_also_works(client: TestClient) -> None:
    created = _create(client)
    response = client.patch(
        f"/api/v1/byop/pipelines/{created['id']}", json={"description": "patched"}
    )
    assert response.status_code == 200
    assert response.json()["description"] == "patched"


def test_delete_pipeline_archives(client: TestClient) -> None:
    created = _create(client)
    response = client.delete(f"/api/v1/byop/pipelines/{created['id']}")
    assert response.status_code == 200
    assert response.json()["pipeline_status"] == "ARCHIVED"
    # Row still readable — no hard delete.
    assert client.get(f"/api/v1/byop/pipelines/{created['id']}").status_code == 200


# --- Lifecycle happy paths ------------------------------------------------


def test_revalidate_pass_keeps_active(client: TestClient) -> None:
    created = _create(client)
    response = client.post(f"/api/v1/byop/pipelines/{created['id']}/revalidate")
    assert response.status_code == 200
    body = response.json()
    assert body["pipeline_status"] == "ACTIVE"
    assert body["last_validated_at"] is not None


def test_revalidate_failure_deactivates(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create(client)
    monkeypatch.setattr(byop, "validate_manifest", _stage1_fail)
    response = client.post(f"/api/v1/byop/pipelines/{created['id']}/revalidate")
    assert response.status_code == 200
    body = response.json()
    assert body["pipeline_status"] == "DEACTIVATED"
    assert body["deactivated_at"] is not None
    assert "license rejected" in body["validation_log"]


def test_revalidate_sandbox_failure_deactivates(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create(client)
    monkeypatch.setattr(byop, "run_sandbox", _stage2_fail)
    response = client.post(f"/api/v1/byop/pipelines/{created['id']}/revalidate")
    assert response.status_code == 200
    assert response.json()["pipeline_status"] == "DEACTIVATED"


def test_deactivate(client: TestClient) -> None:
    created = _create(client)
    response = client.post(f"/api/v1/byop/pipelines/{created['id']}/deactivate")
    assert response.status_code == 200
    body = response.json()
    assert body["pipeline_status"] == "DEACTIVATED"
    assert body["deactivated_at"] is not None


def test_archive_from_deactivated(client: TestClient) -> None:
    created = _create(client)
    client.post(f"/api/v1/byop/pipelines/{created['id']}/deactivate")
    response = client.post(f"/api/v1/byop/pipelines/{created['id']}/archive")
    assert response.status_code == 200
    assert response.json()["pipeline_status"] == "ARCHIVED"


# --- Failure paths --------------------------------------------------------


def test_not_found_everywhere(client: TestClient) -> None:
    assert client.get("/api/v1/byop/pipelines/999").status_code == 404
    assert client.put("/api/v1/byop/pipelines/999", json={"description": "x"}).status_code == 404
    assert client.delete("/api/v1/byop/pipelines/999").status_code == 404
    assert client.post("/api/v1/byop/pipelines/999/revalidate").status_code == 404
    assert client.post("/api/v1/byop/pipelines/999/deactivate").status_code == 404
    assert client.post("/api/v1/byop/pipelines/999/archive").status_code == 404


def test_create_stage1_failure_is_422_and_no_write(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(byop, "validate_manifest", _stage1_fail)
    response = client.post("/api/v1/byop/pipelines", json=CREATE_PAYLOAD)
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "VALIDATION_FAILED"
    assert client.get("/api/v1/byop/pipelines").json() == []


def test_create_stage2_failure_is_422_and_no_write(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(byop, "run_sandbox", _stage2_fail)
    response = client.post("/api/v1/byop/pipelines", json=CREATE_PAYLOAD)
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "SANDBOX_FAILED"
    assert client.get("/api/v1/byop/pipelines").json() == []


def test_create_bad_yaml_is_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/byop/pipelines",
        json={"source_type": "git", "manifest_yaml": "a: [unclosed"},
    )
    assert response.status_code == 422


def test_create_bad_source_type_is_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/byop/pipelines",
        json={"source_type": "ftp", "manifest_yaml": VALID_MANIFEST},
    )
    assert response.status_code == 422


def test_update_validation_failure_is_422_and_no_write(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create(client)
    monkeypatch.setattr(byop, "validate_manifest", _stage1_fail)
    response = client.put(
        f"/api/v1/byop/pipelines/{created['id']}",
        json={"manifest_yaml": VALID_MANIFEST.replace("MIT", "SSPL-1.0")},
    )
    assert response.status_code == 422
    unchanged = client.get(f"/api/v1/byop/pipelines/{created['id']}").json()
    assert unchanged["license_spdx"] == "MIT"


def test_update_with_manifest_revalidates(client: TestClient) -> None:
    created = _create(client)
    response = client.put(
        f"/api/v1/byop/pipelines/{created['id']}",
        json={"manifest_yaml": VALID_MANIFEST.replace("1.2.3", "1.3.0")},
    )
    assert response.status_code == 200
    assert response.json()["version"] == "1.3.0"


def test_update_empty_payload_is_400(client: TestClient) -> None:
    created = _create(client)
    response = client.put(f"/api/v1/byop/pipelines/{created['id']}", json={})
    assert response.status_code == 400


def test_illegal_transitions_are_409(client: TestClient) -> None:
    created = _create(client)
    pid = created["id"]
    # ACTIVE -> deactivate -> second deactivate is illegal.
    client.post(f"/api/v1/byop/pipelines/{pid}/deactivate")
    assert client.post(f"/api/v1/byop/pipelines/{pid}/deactivate").status_code == 409
    # Archive, then everything mutating is illegal.
    client.post(f"/api/v1/byop/pipelines/{pid}/archive")
    assert client.post(f"/api/v1/byop/pipelines/{pid}/archive").status_code == 409
    assert client.post(f"/api/v1/byop/pipelines/{pid}/deactivate").status_code == 409
    assert client.post(f"/api/v1/byop/pipelines/{pid}/revalidate").status_code == 409
    assert client.delete(f"/api/v1/byop/pipelines/{pid}").status_code == 409
    assert client.put(f"/api/v1/byop/pipelines/{pid}", json={"description": "x"}).status_code == 409


# --- M2-DROP-PRE slice 6: per-row manage authority on the read model -------


def test_can_manage_is_true_for_the_registrant_holding_no_grant(
    client: TestClient, authz_grants
) -> None:
    """The registrant may manage their own pipeline with zero grants.

    This is the case the UI used to hide. It gated the deactivate/archive
    controls on ``is_platform_admin``, so the person who registered the
    pipeline — whom ``_may_manage``'s registrant rung admits — saw no
    controls for a row the server would have let them mutate.
    """
    _create(client)
    authz_grants(1, [])  # strip the autouse ROOT grant; registrant rung only

    body = client.get("/api/v1/byop/pipelines").json()

    assert [p["can_manage"] for p in body] == [True]


def test_can_manage_is_false_for_a_stranger_to_the_row(
    app: FastAPI, client: TestClient, authz_grants
) -> None:
    """Neither registrant nor grant-holder gets no manage affordance.

    The catalog list is intentionally unscoped (design §9 — bioinformaticians
    browse everything), so the row is visible. ``can_manage`` is what keeps
    the mutate controls off it, and the mutating routes still answer 404
    independently — this flag is an affordance, never the enforcement.
    """
    _create(client)

    stranger = {"id": 99, "email": "stranger@example.org"}
    app.dependency_overrides[get_current_user] = lambda: stranger
    authz_grants(99, [])

    body = client.get("/api/v1/byop/pipelines").json()

    assert [p["can_manage"] for p in body] == [False]
    assert client.post("/api/v1/byop/pipelines/1/deactivate").status_code == 404
