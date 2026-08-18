# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""User profile CRUD endpoints (P0g G-5).

Five REST endpoints mounted at ``/profiles`` for managing a one-to-one
user profile record:

* ``POST   /profiles/``            — create the caller's own profile
* ``GET    /profiles/me``          — read the caller's own profile
* ``GET    /profiles/{user_id}``   — read any profile (admin or self)
* ``PUT    /profiles/{user_id}``   — full update (admin or self)
* ``DELETE /profiles/{user_id}``   — delete (admin only)

The SQLAlchemy ``Profile`` ORM model and the Pydantic v2 schemas live in
this module so the tests can spin up an in-memory SQLite instance and
exercise every branch without Postgres.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session

from backend.auth.guards import get_current_user
from backend.database import get_db_dep


class Base(DeclarativeBase):
    """Profile-router-local declarative base.

    Kept separate from any global metadata so the in-memory SQLite test
    harness can call ``Base.metadata.create_all`` without touching the
    real schema.
    """


class Profile(Base):
    __tablename__ = "user_profiles"

    user_id = Column(String(36), primary_key=True)
    display_name = Column(String(255), nullable=False)
    bio = Column(String(2048), nullable=True)
    avatar_url = Column(String(1024), nullable=True)


class ProfileCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    display_name: str = Field(..., min_length=1, max_length=255)
    bio: str | None = Field(default=None, max_length=2048)
    avatar_url: str | None = Field(default=None, max_length=1024)


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    display_name: str = Field(..., min_length=1, max_length=255)
    bio: str | None = Field(default=None, max_length=2048)
    avatar_url: str | None = Field(default=None, max_length=1024)


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    display_name: str
    bio: str | None = None
    avatar_url: str | None = None


router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


def _is_admin(user: dict) -> bool:
    return bool(user.get("is_platform_admin"))


def _uid_str(user: dict) -> str:
    return str(user["id"])


def _commit_new_profile_or_409(db: Session) -> None:
    """Commit a freshly-``add``ed ``Profile``, translating a PK collision to 409.

    The existence check in ``create_profile`` happens in its own
    transaction, so two concurrent requests for the same user can both
    pass it before either commits — a classic check-then-create race.
    Whichever commits second hits the ``user_id`` primary-key
    constraint; catching that here turns it into the same 409 the
    check already returns for the non-concurrent case, instead of an
    unhandled ``IntegrityError`` surfacing as a bare 500.
    """
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Profile already exists for this user."
        ) from exc


@router.post("/", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: ProfileCreate,
    db: Annotated[Session, Depends(get_db_dep)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> Profile:
    uid = _uid_str(current_user)
    if db.query(Profile).filter(Profile.user_id == uid).one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Profile already exists for this user.")
    profile = Profile(user_id=uid, **payload.model_dump())
    db.add(profile)
    _commit_new_profile_or_409(db)
    db.refresh(profile)
    return profile


@router.get("/me", response_model=ProfileRead)
def read_own_profile(
    db: Annotated[Session, Depends(get_db_dep)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> Profile:
    uid = _uid_str(current_user)
    profile = db.query(Profile).filter(Profile.user_id == uid).one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return profile


@router.get("/{user_id}", response_model=ProfileRead)
def read_profile_by_id(
    user_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db_dep)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> Profile:
    target = str(user_id)
    if not _is_admin(current_user) and _uid_str(current_user) != target:
        raise HTTPException(status_code=403, detail="Not permitted to access this profile.")
    profile = db.query(Profile).filter(Profile.user_id == target).one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile {user_id} not found.")
    return profile


@router.put("/{user_id}", response_model=ProfileRead)
def update_profile(
    user_id: uuid.UUID,
    payload: ProfileUpdate,
    db: Annotated[Session, Depends(get_db_dep)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> Profile:
    target = str(user_id)
    if not _is_admin(current_user) and _uid_str(current_user) != target:
        raise HTTPException(status_code=403, detail="Not permitted to update this profile.")
    profile = db.query(Profile).filter(Profile.user_id == target).one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile {user_id} not found.")
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_profile(
    user_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db_dep)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> Response:
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin required.")
    target = str(user_id)
    profile = db.query(Profile).filter(Profile.user_id == target).one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile {user_id} not found.")
    db.delete(profile)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
