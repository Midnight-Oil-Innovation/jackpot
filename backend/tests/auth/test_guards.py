"""ACCESS-GUARD-MAP: require_capability guard tests (access_model.md §10.3)."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

import backend.auth.guards as guards_module
from backend.auth.guards import require_capability


def _principal(**overrides):
    user = {
        "id": 1,
        "email": "user1@test.com",
        "is_platform_admin": False,
        "is_data_analyst": False,
        "is_active": True,
        "organization_id": 1,
    }
    user.update(overrides)
    return user


def test_happy_path_returns_principal():
    principal = _principal(is_platform_admin=True)
    result = require_capability("sample:read_detail")(principal)
    assert result is principal


def test_happy_path_lab_member_returns_principal():
    principal = _principal(uid=5)
    membership = {"lab_id": 5, "is_lab_director": False}
    with patch("backend.auth.guards.get_user_lab_membership", return_value=membership):
        result = require_capability("sample:read_detail")(principal, lab_id=5)
    assert result is principal


def test_no_principal_raises_403():
    with pytest.raises(HTTPException) as exc:
        require_capability("sample:read_detail")(None)
    assert exc.value.status_code == 403
    assert "sample:read_detail" in exc.value.detail


def test_unprivileged_principal_raises_403():
    with pytest.raises(HTTPException) as exc:
        require_capability("org:manage")(_principal())
    assert exc.value.status_code == 403


def test_old_role_named_guards_not_importable():
    assert getattr(guards_module, "require_platform_admin", None) is None
    assert getattr(guards_module, "require_lab_role", None) is None
    assert getattr(guards_module, "require_lab_director", None) is None
    assert getattr(guards_module, "require_lab_access", None) is None
