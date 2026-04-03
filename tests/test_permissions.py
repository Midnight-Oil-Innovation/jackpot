from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend.auth.guards import (
    require_lab_access,
    require_lab_director,
    require_platform_admin,
)


def make_user(is_platform_admin=False, is_data_analyst=False, uid=1):
    return {
        "id": uid,
        "email": f"user{uid}@test.com",
        "is_platform_admin": is_platform_admin,
        "is_data_analyst": is_data_analyst,
        "is_active": True,
        "organization_id": 1,
    }


def test_platform_admin_passes():
    require_platform_admin(make_user(is_platform_admin=True))


def test_non_admin_denied():
    with pytest.raises(HTTPException) as exc:
        require_platform_admin(make_user())
    assert exc.value.status_code == 403


def test_data_analyst_not_platform_admin():
    with pytest.raises(HTTPException):
        require_platform_admin(make_user(is_data_analyst=True))


def test_lab_director_passes():
    membership = {"lab_id": 5, "is_lab_admin": True, "permission_group_name": "Lab Director"}
    with patch("backend.auth.guards.get_user_lab_membership", return_value=membership):
        require_lab_director(make_user(uid=2), lab_id=5)


def test_platform_admin_bypasses_director_check():
    with patch("backend.auth.guards.get_user_lab_membership", return_value=None):
        require_lab_director(make_user(is_platform_admin=True), lab_id=5)


def test_lab_collaborator_not_director():
    membership = {"lab_id": 5, "is_lab_admin": False, "permission_group_name": "Lab Collaborator"}
    with patch("backend.auth.guards.get_user_lab_membership", return_value=membership):
        with pytest.raises(HTTPException) as exc:
            require_lab_director(make_user(uid=3), lab_id=5)
        assert exc.value.status_code == 403


@pytest.mark.parametrize(
    "role",
    [
        "Lab Director",
        "Lab Collaborator",
        "Lab Reader",
        "Bioinformatics User",
    ],
)
def test_all_lab_roles_have_access(role):
    membership = {
        "lab_id": 5,
        "is_lab_admin": role == "Lab Director",
        "permission_group_name": role,
    }
    with patch("backend.auth.guards.get_user_lab_membership", return_value=membership):
        require_lab_access(make_user(uid=5), lab_id=5)


def test_non_member_denied_lab_access():
    with (
        pytest.raises(HTTPException) as exc,
        patch("backend.auth.guards.get_user_lab_membership", return_value=None),
        patch("backend.auth.guards.execute_query", return_value=[]),
    ):
        require_lab_access(make_user(uid=7), lab_id=5)
    assert exc.value.status_code == 403
