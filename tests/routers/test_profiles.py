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
from fastapi import FastAPI, HTTPException
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


@pytest.fixture(autouse=True)
def _profile_authz(authz_grants):
    """M2-B5: reaching another principal's profile takes user:manage.

    The is_platform_admin flag has authorized nothing since M2-B1, so the
    admin persona needs the grant. The two ordinary users get none — self
    access is an identity comparison, not a capability (§4.7).
    """
    from backend.authz import ROOT

    authz_grants(ADMIN_ID, [("user:manage", ROOT)])
    authz_grants(USER_A_ID, [])
    authz_grants(USER_B_ID, [])


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
    response = _as(app, owner).post("/api/v1/profiles/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_profile_success(app: FastAPI, authz_grants) -> None:
    client = _as(app, USER_A)
    response = client.post(
        "/api/v1/profiles/",
        json={"display_name": "Alice", "bio": "hello", "avatar_url": "https://x/a.png"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["display_name"] == "Alice"
    assert body["bio"] == "hello"
    assert body["avatar_url"] == "https://x/a.png"
    assert body["user_id"] == str(USER_A_ID)


def test_create_profile_duplicate(app: FastAPI, authz_grants) -> None:
    _seed(app, USER_A)
    response = _as(app, USER_A).post("/api/v1/profiles/", json={"display_name": "Alice Again"})
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


def test_create_profile_concurrent_race_returns_409_not_500(app: FastAPI, authz_grants) -> None:
    """Two overlapping requests can both pass the existence check before
    either commits. Reproduce that interleaving directly with two
    sessions bound to the same in-memory engine, bypassing the
    endpoint's own (single-threaded, non-overlapping) request cycle."""
    from backend.routers.profiles import Profile, _commit_new_profile_or_409

    gen_a = app.dependency_overrides[get_db_dep]()
    gen_b = app.dependency_overrides[get_db_dep]()
    db_a = next(gen_a)
    db_b = next(gen_b)

    uid = str(USER_A_ID)
    assert db_a.query(Profile).filter(Profile.user_id == uid).one_or_none() is None
    assert db_b.query(Profile).filter(Profile.user_id == uid).one_or_none() is None

    db_a.add(Profile(user_id=uid, display_name="Alice"))
    _commit_new_profile_or_409(db_a)

    db_b.add(Profile(user_id=uid, display_name="Alice (racing request)"))
    with pytest.raises(HTTPException) as exc_info:
        _commit_new_profile_or_409(db_b)
    assert exc_info.value.status_code == 409

    for gen in (gen_a, gen_b):
        gen.close()


def test_read_own_profile(app: FastAPI, authz_grants) -> None:
    _seed(app, USER_A, display_name="Alice", bio="bio-A")
    response = _as(app, USER_A).get("/api/v1/profiles/me")
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Alice"
    assert body["bio"] == "bio-A"
    assert body["user_id"] == str(USER_A_ID)


def test_read_own_profile_not_found(app: FastAPI, authz_grants) -> None:
    response = _as(app, USER_A).get("/api/v1/profiles/me")
    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found."


def test_read_profile_by_id_self(app: FastAPI, authz_grants) -> None:
    _seed(app, USER_A)
    response = _as(app, USER_A).get(f"/api/v1/profiles/{USER_A_ID}")
    assert response.status_code == 200
    assert response.json()["user_id"] == str(USER_A_ID)


def test_read_profile_by_id_admin(app: FastAPI, authz_grants) -> None:
    _seed(app, USER_A)
    response = _as(app, ADMIN).get(f"/api/v1/profiles/{USER_A_ID}")
    assert response.status_code == 200
    assert response.json()["display_name"] == "Alice"


def test_read_profile_by_id_forbidden(app: FastAPI, authz_grants) -> None:
    _seed(app, USER_A)
    response = _as(app, USER_B).get(f"/api/v1/profiles/{USER_A_ID}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Not permitted to access this profile."


def test_read_profile_not_found(app: FastAPI, authz_grants) -> None:
    missing = uuid.uuid4()
    response = _as(app, ADMIN).get(f"/api/v1/profiles/{missing}")
    assert response.status_code == 404
    assert str(missing) in response.json()["detail"]


def test_update_profile_success(app: FastAPI, authz_grants) -> None:
    _seed(app, USER_A, display_name="Alice", bio="old")
    response = _as(app, USER_A).put(
        f"/api/v1/profiles/{USER_A_ID}",
        json={"display_name": "Alice Renamed", "bio": "new", "avatar_url": "https://x/n.png"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Alice Renamed"
    assert body["bio"] == "new"
    assert body["avatar_url"] == "https://x/n.png"


def test_update_profile_admin(app: FastAPI, authz_grants) -> None:
    _seed(app, USER_A, display_name="Alice")
    response = _as(app, ADMIN).put(
        f"/api/v1/profiles/{USER_A_ID}",
        json={"display_name": "AdminEdit"},
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "AdminEdit"


def test_update_profile_forbidden(app: FastAPI, authz_grants) -> None:
    _seed(app, USER_A)
    response = _as(app, USER_B).put(
        f"/api/v1/profiles/{USER_A_ID}",
        json={"display_name": "Hacked"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not permitted to update this profile."


def test_update_profile_not_found(app: FastAPI, authz_grants) -> None:
    missing = uuid.uuid4()
    response = _as(app, ADMIN).put(
        f"/api/v1/profiles/{missing}",
        json={"display_name": "Whatever"},
    )
    assert response.status_code == 404
    assert str(missing) in response.json()["detail"]


def test_delete_profile_success(app: FastAPI, authz_grants) -> None:
    _seed(app, USER_A)
    response = _as(app, ADMIN).delete(f"/api/v1/profiles/{USER_A_ID}")
    assert response.status_code == 204
    follow = _as(app, ADMIN).get(f"/api/v1/profiles/{USER_A_ID}")
    assert follow.status_code == 404


def test_delete_profile_forbidden(app: FastAPI, authz_grants) -> None:
    _seed(app, USER_A)
    response = _as(app, USER_A).delete(f"/api/v1/profiles/{USER_A_ID}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin required."


def test_delete_profile_not_found(app: FastAPI, authz_grants) -> None:
    missing = uuid.uuid4()
    response = _as(app, ADMIN).delete(f"/api/v1/profiles/{missing}")
    assert response.status_code == 404
    assert str(missing) in response.json()["detail"]
