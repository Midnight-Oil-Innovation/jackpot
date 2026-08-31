"""ACCESS-SEED: reseed of stored APGAP roles into preset capability grants.

Exercises ``backend.authz.reseed`` against an isolated in-memory SQLite
database with the minimal legacy schema (users, permission_groups,
lab_membership) plus the M0 grants table, all built via raw ``text()``
DDL — mirroring the raw-SQL implementation.
"""

import pytest
from sqlalchemy import create_engine, text

from backend.authz.reseed import (
    BIOINFORMATICS_EXTRA,
    GRANT_SOURCE,
    INSTANCE_SCOPE,
    PRESET_GRANTS,
    reseed,
)
from backend.authz.scope import scope_uri

ORG_ID = 4
LAB_ID = 7
LAB_SCOPE = scope_uri(org=ORG_ID, lab=LAB_ID)

_DDL = [
    """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        email TEXT NOT NULL,
        is_platform_admin BOOLEAN NOT NULL DEFAULT FALSE,
        is_data_analyst BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    """
    CREATE TABLE permission_groups (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE labs (
        id INTEGER PRIMARY KEY,
        organization_id INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE lab_membership (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        lab_id INTEGER NOT NULL,
        permission_group_id INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE authz_capability_grants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        principal_id TEXT NOT NULL,
        capability TEXT NOT NULL,
        scope_ref TEXT NOT NULL,
        conditions TEXT NOT NULL DEFAULT '{}',
        source TEXT NOT NULL DEFAULT '',
        UNIQUE (principal_id, capability, scope_ref)
    )
    """,
]

_GROUPS = [
    "Platform Admin",
    "Lab Director",
    "Lab Collaborator",
    "Lab Reader",
    "Bioinformatics User",
    "Data Analyst",
]


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        for ddl in _DDL:
            connection.execute(text(ddl))
        for i, name in enumerate(_GROUPS, start=1):
            connection.execute(
                text("INSERT INTO permission_groups (id, name) VALUES (:id, :name)"),
                {"id": i, "name": name},
            )
        yield connection
    engine.dispose()


def _add_user(conn, user_id, *, admin=False, analyst=False):
    conn.execute(
        text(
            "INSERT INTO users (id, email, is_platform_admin, is_data_analyst) "
            "VALUES (:id, :email, :admin, :analyst)"
        ),
        {"id": user_id, "email": f"u{user_id}@example.org", "admin": admin, "analyst": analyst},
    )


def _add_lab(conn, lab_id, org_id=ORG_ID):
    conn.execute(
        text("INSERT OR IGNORE INTO labs (id, organization_id) VALUES (:id, :org)"),
        {"id": lab_id, "org": org_id},
    )


def _add_membership(conn, user_id, lab_id, group_name):
    _add_lab(conn, lab_id)
    conn.execute(
        text(
            "INSERT INTO lab_membership (user_id, lab_id, permission_group_id) "
            "SELECT :user_id, :lab_id, id FROM permission_groups WHERE name = :name"
        ),
        {"user_id": user_id, "lab_id": lab_id, "name": group_name},
    )


def _grants(conn, principal_id=None):
    sql = "SELECT principal_id, capability, scope_ref, source FROM authz_capability_grants"
    params = {}
    if principal_id is not None:
        sql += " WHERE principal_id = :pid"
        params["pid"] = principal_id
    return conn.execute(text(sql), params).fetchall()


def test_preset_grants_constant_completeness():
    assert set(PRESET_GRANTS) == {
        "instance_administrator",
        "surveillance_officer",
        "lab_lead",
        "lab_member_rw",
        "lab_member_ro",
    }
    for preset, caps in PRESET_GRANTS.items():
        assert caps, preset
        for cap in caps:
            assert cap.strip(), f"blank capability in {preset}"
    assert "pipeline:run" not in PRESET_GRANTS["lab_member_rw"]
    assert BIOINFORMATICS_EXTRA == ["pipeline:run"]


def test_platform_admin_gets_instance_admin_grants(conn):
    _add_user(conn, 1, admin=True)
    reseed(conn)
    grants = _grants(conn, "1")
    assert {g.capability for g in grants} == set(PRESET_GRANTS["instance_administrator"])
    assert all(g.scope_ref == INSTANCE_SCOPE for g in grants)
    assert all(g.source == GRANT_SOURCE for g in grants)


def test_data_analyst_gets_surveillance_officer_grants(conn):
    _add_user(conn, 2, analyst=True)
    reseed(conn)
    grants = _grants(conn, "2")
    assert {g.capability for g in grants} == set(PRESET_GRANTS["surveillance_officer"])
    assert all(g.scope_ref == INSTANCE_SCOPE and g.source == GRANT_SOURCE for g in grants)


def test_platform_admin_subsumes_data_analyst(conn):
    _add_user(conn, 3, admin=True, analyst=True)
    reseed(conn)
    caps = {g.capability for g in _grants(conn, "3")}
    assert caps == set(PRESET_GRANTS["instance_administrator"])
    # Surveillance-Officer-only capabilities must not appear.
    assert "anomaly:review" not in caps
    assert "anomaly:triage" not in caps


def test_lab_lead_gets_lab_lead_grants(conn):
    _add_user(conn, 4)
    _add_membership(conn, 4, 7, "Lab Director")
    reseed(conn)
    grants = _grants(conn, "4")
    assert {g.capability for g in grants} == set(PRESET_GRANTS["lab_lead"])
    assert all(g.scope_ref == LAB_SCOPE and g.source == GRANT_SOURCE for g in grants)


def test_lab_member_rw_grants(conn):
    _add_user(conn, 5)
    _add_membership(conn, 5, 7, "Lab Collaborator")
    reseed(conn)
    grants = _grants(conn, "5")
    assert {g.capability for g in grants} == set(PRESET_GRANTS["lab_member_rw"])
    assert all(g.scope_ref == LAB_SCOPE for g in grants)


def test_lab_member_ro_grants(conn):
    _add_user(conn, 6)
    _add_membership(conn, 6, 7, "Lab Reader")
    reseed(conn)
    caps = {g.capability for g in _grants(conn, "6")}
    assert caps == set(PRESET_GRANTS["lab_member_ro"])
    write_caps = set(PRESET_GRANTS["lab_member_rw"]) - set(PRESET_GRANTS["lab_member_ro"])
    assert write_caps, "RW must exceed RO"
    assert not caps & write_caps


def test_bioinformatics_user_gets_rw_plus_pipeline_run(conn):
    _add_user(conn, 7)
    _add_membership(conn, 7, 7, "Bioinformatics User")
    reseed(conn)
    grants = _grants(conn, "7")
    caps = [g.capability for g in grants]
    assert set(caps) == set(PRESET_GRANTS["lab_member_rw"]) | {"pipeline:run"}
    assert caps.count("pipeline:run") == 1


def test_no_grants_without_matching_rows(conn):
    reseed(conn)
    assert _grants(conn) == []


def test_reseed_is_idempotent(conn):
    _add_user(conn, 8, admin=True)
    _add_user(conn, 9, analyst=True)
    _add_membership(conn, 9, 3, "Bioinformatics User")
    reseed(conn)
    first = len(_grants(conn))
    reseed(conn)
    assert len(_grants(conn)) == first


def test_unknown_membership_role_skips_and_warns(conn, caplog):
    _add_user(conn, 10)
    _add_membership(conn, 10, 2, "Data Analyst")  # boolean-carried role, not a lab preset
    with caplog.at_level("WARNING", logger="backend.authz.reseed"):
        reseed(conn)
    assert "unmapped" in caplog.text
    assert _grants(conn, "10") == []
