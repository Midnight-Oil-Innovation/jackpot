# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Tests for the P0g G-5 user-profiles router.

Uses ``TestClient`` against a minimal FastAPI app that mounts only
``backend.routers.profiles.router``. ``get_db_dep`` is overridden with
an in-memory SQLite engine and ``get_current_user`` is overridden per
test with a hand-built user dict — no Postgres, no real auth.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.auth.guards import get_current_user
from backend.database import get_db_dep
from backend.routers.profiles import Base, router

USER_A_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_B_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
ADMIN_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")

USER_A = {"id": USER_A_ID, "email": "a@example.org", "is_platform_admin": False}
USER_B = {"id": USER_B_ID, "email": "b@example.org", "is_platform_admin": False}
ADMIN = {"id": ADMIN_ID, "email": "admin@example.org", "is_platform_admin": True}


@pytest.fixture
def app() -> Iterator[FastAPI]:
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
    try:
        yield fresh
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _as(app: FastAPI, user: dict) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _seed(
    app: FastAPI,
    owner: dict,
    display_name: str = "Alice",
    bio: str | None = None,
    avatar_url: str | None = None,
) -> dict:
    payload: dict = {"display_name": display_name}
    if bio is not None:
        payload["bio"] = bio
    if avatar_url is not None:
        payload["avatar_url"] = avatar_url
    response = _as(app, owner).post("/profiles/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_profile_success(app: FastAPI) -> None:
    client = _as(app, USER_A)
    response = client.post(
        "/profiles/",
        json={"display_name": "Alice", "bio": "hello", "avatar_url": "https://x/a.png"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["display_name"] == "Alice"
    assert body["bio"] == "hello"
    assert body["avatar_url"] == "https://x/a.png"
    assert body["user_id"] == str(USER_A_ID)


def test_create_profile_duplicate(app: FastAPI) -> None:
    _seed(app, USER_A)
    response = _as(app, USER_A).post("/profiles/", json={"display_name": "Alice Again"})
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


def test_read_own_profile(app: FastAPI) -> None:
    _seed(app, USER_A, display_name="Alice", bio="bio-A")
    response = _as(app, USER_A).get("/profiles/me")
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Alice"
    assert body["bio"] == "bio-A"
    assert body["user_id"] == str(USER_A_ID)


def test_read_own_profile_not_found(app: FastAPI) -> None:
    response = _as(app, USER_A).get("/profiles/me")
    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found."


def test_read_profile_by_id_self(app: FastAPI) -> None:
    _seed(app, USER_A)
    response = _as(app, USER_A).get(f"/profiles/{USER_A_ID}")
    assert response.status_code == 200
    assert response.json()["user_id"] == str(USER_A_ID)


def test_read_profile_by_id_admin(app: FastAPI) -> None:
    _seed(app, USER_A)
    response = _as(app, ADMIN).get(f"/profiles/{USER_A_ID}")
    assert response.status_code == 200
    assert response.json()["display_name"] == "Alice"


def test_read_profile_by_id_forbidden(app: FastAPI) -> None:
    _seed(app, USER_A)
    response = _as(app, USER_B).get(f"/profiles/{USER_A_ID}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Not permitted to access this profile."


def test_read_profile_not_found(app: FastAPI) -> None:
    missing = uuid.uuid4()
    response = _as(app, ADMIN).get(f"/profiles/{missing}")
    assert response.status_code == 404
    assert str(missing) in response.json()["detail"]


def test_update_profile_success(app: FastAPI) -> None:
    _seed(app, USER_A, display_name="Alice", bio="old")
    response = _as(app, USER_A).put(
        f"/profiles/{USER_A_ID}",
        json={"display_name": "Alice Renamed", "bio": "new", "avatar_url": "https://x/n.png"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Alice Renamed"
    assert body["bio"] == "new"
    assert body["avatar_url"] == "https://x/n.png"


def test_update_profile_admin(app: FastAPI) -> None:
    _seed(app, USER_A, display_name="Alice")
    response = _as(app, ADMIN).put(
        f"/profiles/{USER_A_ID}",
        json={"display_name": "AdminEdit"},
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "AdminEdit"


def test_update_profile_forbidden(app: FastAPI) -> None:
    _seed(app, USER_A)
    response = _as(app, USER_B).put(
        f"/profiles/{USER_A_ID}",
        json={"display_name": "Hacked"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not permitted to update this profile."


def test_update_profile_not_found(app: FastAPI) -> None:
    missing = uuid.uuid4()
    response = _as(app, ADMIN).put(
        f"/profiles/{missing}",
        json={"display_name": "Whatever"},
    )
    assert response.status_code == 404
    assert str(missing) in response.json()["detail"]


def test_delete_profile_success(app: FastAPI) -> None:
    _seed(app, USER_A)
    response = _as(app, ADMIN).delete(f"/profiles/{USER_A_ID}")
    assert response.status_code == 204
    follow = _as(app, ADMIN).get(f"/profiles/{USER_A_ID}")
    assert follow.status_code == 404


def test_delete_profile_forbidden(app: FastAPI) -> None:
    _seed(app, USER_A)
    response = _as(app, USER_A).delete(f"/profiles/{USER_A_ID}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin required."


def test_delete_profile_not_found(app: FastAPI) -> None:
    missing = uuid.uuid4()
    response = _as(app, ADMIN).delete(f"/profiles/{missing}")
    assert response.status_code == 404
    assert str(missing) in response.json()["detail"]
