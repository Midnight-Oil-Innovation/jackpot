# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Tests for the P0c multi-tenancy middleware and BYOP IDOR guard.

Middleware/dependency tests run against a minimal FastAPI app mounting
only ``TenancyMiddleware`` with the principal resolver monkeypatched —
no database. BYOP tenancy tests reuse the ``test_byop.py`` SQLite
harness pattern with the lab-membership lookup monkeypatched.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import tenancy
from backend.auth.guards import get_current_user
from backend.authz import ROOT, scope_uri
from backend.database import get_db_dep
from backend.routers import byop
from backend.routers.byop import Base, router
from backend.services.byop_sandbox import SandboxResult, StepResult
from backend.services.byop_validator import CheckResult, ValidationReport
from backend.tenancy import (
    OrgContext,
    TenancyMiddleware,
    get_org_context,
    require_org_access,
)

# ---------------------------------------------------------------------------
# Middleware + dependency
# ---------------------------------------------------------------------------

ORG1_USER = {"id": 10, "email": "a@org1.example", "is_platform_admin": False, "organization_id": 1}


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(TenancyMiddleware)

    @app.get("/api/v1/whoami")
    def whoami(ctx: Annotated[OrgContext, Depends(get_org_context)]) -> dict:
        return {"user_id": ctx.user_id, "org_id": ctx.org_id}

    @app.get("/api/v1/orgs/{org_id}/thing")
    def org_thing(org_id: int, ctx: Annotated[OrgContext, Depends(get_org_context)]) -> dict:
        require_org_access(ctx, org_id)
        return {"ok": True}

    @app.get("/api/v1/templates/foo")
    def exempt_route(request: Request) -> dict:
        return {"org_context": request.state.org_context is not None}

    return app


def test_middleware_attaches_org_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: authenticated principal → org context on the request."""
    monkeypatch.setattr(tenancy, "get_current_user", lambda request: ORG1_USER)
    client = TestClient(_make_app())
    response = client.get("/api/v1/whoami")
    assert response.status_code == 200
    assert response.json() == {"user_id": 10, "org_id": 1}


def test_no_tenant_identifier_is_403(monkeypatch: pytest.MonkeyPatch) -> None:
    """Failure path: unresolvable principal → no org context → 403."""
    monkeypatch.setattr(tenancy, "get_current_user", lambda request: None)
    client = TestClient(_make_app())
    response = client.get("/api/v1/whoami")
    assert response.status_code == 403


def test_cross_org_access_is_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """Failure path (IDOR guard): org 1 caller on org 2 resource → 404.

    404, not 403 — access_model.md §3.3: existence must not leak.
    """
    monkeypatch.setattr(tenancy, "get_current_user", lambda request: ORG1_USER)
    client = TestClient(_make_app())
    assert client.get("/api/v1/orgs/2/thing").status_code == 404
    assert client.get("/api/v1/orgs/1/thing").status_code == 200


def test_platform_admin_crosses_org_wall(monkeypatch: pytest.MonkeyPatch) -> None:
    """Instance scope contains every Org (access_model.md §3.1)."""
    admin = {"id": 1, "email": "root@example", "is_platform_admin": True, "organization_id": 1}
    monkeypatch.setattr(tenancy, "get_current_user", lambda request: admin)
    client = TestClient(_make_app())
    assert client.get("/api/v1/orgs/2/thing").status_code == 200


def test_resource_without_org_is_denied_to_non_admin() -> None:
    """Default-deny (access_model.md §5.1): org-less resource → 404."""
    ctx = OrgContext(user_id=10, org_id=1, is_platform_admin=False)
    with pytest.raises(Exception) as excinfo:
        require_org_access(ctx, None)
    assert getattr(excinfo.value, "status_code", None) == 404


def test_middleware_noop_on_exempt_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: tenant-exempt prefix skips principal resolution entirely."""
    calls: list[str] = []

    def _spy(request: Request) -> dict:
        calls.append(request.url.path)
        return ORG1_USER

    monkeypatch.setattr(tenancy, "get_current_user", _spy)
    client = TestClient(_make_app())
    response = client.get("/api/v1/templates/foo")
    assert response.status_code == 200
    assert response.json() == {"org_context": False}
    assert calls == []


def test_resolution_failure_is_fail_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """A broken resolver must never take down the request pipeline."""

    def _boom(request: Request) -> dict:
        raise RuntimeError("db down")

    monkeypatch.setattr(tenancy, "get_current_user", _boom)
    client = TestClient(_make_app())
    # Context is None, so the guard still refuses — but with a clean 403,
    # not a 500 from the middleware.
    assert client.get("/api/v1/whoami").status_code == 403


# ---------------------------------------------------------------------------
# BYOP IDOR guard (mirrors tests/routers/test_byop.py harness)
# ---------------------------------------------------------------------------

OWNER = {"id": 1, "email": "owner@org1.example", "is_platform_admin": False}
INTRUDER = {"id": 2, "email": "intruder@org2.example", "is_platform_admin": False}
ADMIN = {"id": 3, "email": "root@example", "is_platform_admin": True}

VALID_MANIFEST = """\
api_version: v1
kind: pipeline
metadata:
  name: tb-typer
  display_name: TB Typer
  version: 1.2.3
  license: MIT
engine:
  type: nextflow
  version: "23.10"
  entrypoint: main.nf
containers:
  - image: quay.io/tb/typer:1.2.3
"""

CREATE_PAYLOAD = {
    "source_type": "git",
    "source_url": "https://github.com/example/tb-typer",
    "source_ref": "v1.2.3",
    "manifest_yaml": VALID_MANIFEST,
}


@pytest.fixture()
def byop_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def _get_db() -> Iterator:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(
        byop,
        "validate_manifest",
        lambda *a, **k: ValidationReport(
            manifest_id="tb-typer-1.2.3",
            passed=True,
            checks=[CheckResult(check_name="schema_conformance", passed=True, message="ok")],
        ),
    )
    monkeypatch.setattr(
        byop,
        "run_sandbox",
        lambda **k: SandboxResult(
            pipeline_id=k.get("pipeline_id", "tb-typer-1.2.3"),
            outcome="SANDBOX_PASSED",
            steps=[StepResult(step_name="container_pull", passed=True, message="ok")],
            sandbox_log="pull ok",
        ),
    )

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db_dep] = _get_db
    yield app
    engine.dispose()


def _client_as(app: FastAPI, user: dict) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_byop_mutation_by_non_owner_is_404(byop_app: FastAPI, authz_grants) -> None:
    """Failure path (BYOP IDOR): another tenant cannot mutate by id."""
    authz_grants(OWNER["id"], [])
    authz_grants(INTRUDER["id"], [])
    created = _client_as(byop_app, OWNER).post("/api/v1/byop/pipelines", json=CREATE_PAYLOAD)
    assert created.status_code == 201
    pid = created.json()["id"]

    intruder = _client_as(byop_app, INTRUDER)
    patched = intruder.patch(f"/api/v1/byop/pipelines/{pid}", json={"description": "x"})
    assert patched.status_code == 404
    assert intruder.delete(f"/api/v1/byop/pipelines/{pid}").status_code == 404
    assert intruder.post(f"/api/v1/byop/pipelines/{pid}/deactivate").status_code == 404
    assert intruder.post(f"/api/v1/byop/pipelines/{pid}/archive").status_code == 404
    assert intruder.post(f"/api/v1/byop/pipelines/{pid}/revalidate").status_code == 404


def test_byop_owner_and_admin_can_mutate(byop_app: FastAPI, authz_grants) -> None:
    """The registrant needs no grant at all — the ownership policy carries them
    — while the admin is admitted by an instance-scoped grant, not by the
    is_platform_admin flag, which has been inert since M2-B1."""
    authz_grants(OWNER["id"], [])
    authz_grants(ADMIN["id"], [("pipeline:register_custom", ROOT)])
    created = _client_as(byop_app, OWNER).post("/api/v1/byop/pipelines", json=CREATE_PAYLOAD)
    pid = created.json()["id"]

    owner = _client_as(byop_app, OWNER)
    patched = owner.patch(f"/api/v1/byop/pipelines/{pid}", json={"description": "mine"})
    assert patched.status_code == 200

    admin = _client_as(byop_app, ADMIN)
    patched = admin.patch(f"/api/v1/byop/pipelines/{pid}", json={"description": "ops"})
    assert patched.status_code == 200


def test_byop_lab_member_can_mutate(byop_app: FastAPI, authz_grants) -> None:
    """A pipeline:register_custom holder on the pipeline's owner lab may mutate
    it. M2-B3 narrows who that is: §8.2 puts the verb in lab_lead, so mere lab
    membership is no longer enough — the grant is."""
    lab_scope = scope_uri(org=1, lab=7)
    authz_grants(OWNER["id"], [("pipeline:register_custom", lab_scope)])
    authz_grants(INTRUDER["id"], [("pipeline:register_custom", lab_scope)])
    payload = {**CREATE_PAYLOAD, "owner_lab_id": 7}
    created = _client_as(byop_app, OWNER).post("/api/v1/byop/pipelines", json=payload)
    assert created.status_code == 201
    pid = created.json()["id"]
    assert created.json()["owner_lab_id"] == 7

    member = _client_as(byop_app, INTRUDER)  # different user, holds the lab grant
    patched = member.patch(f"/api/v1/byop/pipelines/{pid}", json={"description": "lab"})
    assert patched.status_code == 200

    # Revoke it: a lab member without the verb is now a stranger to this row.
    authz_grants(INTRUDER["id"], [])
    denied = member.patch(f"/api/v1/byop/pipelines/{pid}", json={"description": "no"})
    assert denied.status_code == 404


def test_byop_private_pipeline_is_governed_by_its_registrant(
    byop_app: FastAPI, authz_grants
) -> None:
    """owner_lab_id is nullable because sharing_scope admits 'private'. Such a
    row has no lab scope, so only the registrant policy or an instance grant
    can reach it — M2-B3's answer to the nullable column."""
    authz_grants(OWNER["id"], [])
    authz_grants(INTRUDER["id"], [("pipeline:register_custom", scope_uri(org=1, lab=7))])
    created = _client_as(byop_app, OWNER).post("/api/v1/byop/pipelines", json=CREATE_PAYLOAD)
    assert created.status_code == 201
    assert created.json()["owner_lab_id"] is None
    pid = created.json()["id"]

    # The registrant, holding nothing, still governs it.
    assert (
        _client_as(byop_app, OWNER)
        .patch(f"/api/v1/byop/pipelines/{pid}", json={"description": "mine"})
        .status_code
        == 200
    )
    # A lab grant reaches lab-owned pipelines, not this one.
    assert (
        _client_as(byop_app, INTRUDER)
        .patch(f"/api/v1/byop/pipelines/{pid}", json={"description": "no"})
        .status_code
        == 404
    )


def test_byop_create_into_foreign_lab_is_403(byop_app: FastAPI, authz_grants) -> None:
    """Failure path: registering into a lab you hold no register verb at."""
    authz_grants(OWNER["id"], [("pipeline:register_custom", scope_uri(org=1, lab=7))])
    payload = {**CREATE_PAYLOAD, "owner_lab_id": 9}
    response = _client_as(byop_app, OWNER).post("/api/v1/byop/pipelines", json=payload)
    assert response.status_code == 403


def test_byop_create_registrant_rung_does_not_open_a_foreign_lab(
    byop_app: FastAPI, authz_grants
) -> None:
    """Regression: at creation the caller IS the registrant, so routing create
    through the ownership rung would match every time and make the lab check
    vacuous — any user could place a pipeline into any lab. Create asks the
    grant question only."""
    authz_grants(OWNER["id"], [])
    for lab in (7, 9):
        response = _client_as(byop_app, OWNER).post(
            "/api/v1/byop/pipelines", json={**CREATE_PAYLOAD, "owner_lab_id": lab}
        )
        assert response.status_code == 403, (lab, response.text)

    # With no lab named it is a private pipeline and needs no grant.
    assert (
        _client_as(byop_app, OWNER).post("/api/v1/byop/pipelines", json=CREATE_PAYLOAD).status_code
        == 201
    )


def test_byop_list_and_detail_stay_unscoped(byop_app: FastAPI) -> None:
    """Happy path: catalog browse (design §9) — any authenticated user."""
    created = _client_as(byop_app, OWNER).post("/api/v1/byop/pipelines", json=CREATE_PAYLOAD)
    pid = created.json()["id"]

    browser = _client_as(byop_app, INTRUDER)
    listing = browser.get("/api/v1/byop/pipelines")
    assert listing.status_code == 200
    assert [p["id"] for p in listing.json()] == [pid]
    assert browser.get(f"/api/v1/byop/pipelines/{pid}").status_code == 200
