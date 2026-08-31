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
    ReseedPreflightError,
    preflight_counts,
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
        permission_group_id INTEGER NOT NULL,
        is_lab_director BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    """
    CREATE TABLE projects (
        id INTEGER PRIMARY KEY,
        lab_id INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE project_membership (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        project_id INTEGER NOT NULL,
        permission_group_id INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE samples (
        id INTEGER PRIMARY KEY,
        lab_id INTEGER NOT NULL,
        project_id INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE sample_access_grants (
        id INTEGER PRIMARY KEY,
        requester_id INTEGER NOT NULL,
        sample_id INTEGER NOT NULL,
        revoked BOOLEAN NOT NULL DEFAULT FALSE,
        access_expires_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE sample_access_requests (
        id INTEGER PRIMARY KEY,
        requester_id INTEGER NOT NULL,
        sample_id INTEGER NOT NULL,
        status TEXT NOT NULL
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
        not_after TIMESTAMP,
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


def _add_project_membership(conn, *, user_id, project_id, lab_id):
    _add_lab(conn, lab_id)
    conn.execute(
        text("INSERT OR IGNORE INTO projects (id, lab_id) VALUES (:p, :l)"),
        {"p": project_id, "l": lab_id},
    )
    conn.execute(
        text(
            "INSERT INTO project_membership (user_id, project_id, permission_group_id) "
            "SELECT :u, :p, id FROM permission_groups WHERE name = 'Lab Reader'"
        ),
        {"u": user_id, "p": project_id},
    )


def _add_membership(conn, user_id, lab_id, group_name, director=False):
    _add_lab(conn, lab_id)
    conn.execute(
        text(
            "INSERT INTO lab_membership "
            "(user_id, lab_id, permission_group_id, is_lab_director) "
            "SELECT :user_id, :lab_id, id, :director FROM permission_groups "
            "WHERE name = :name"
        ),
        {"user_id": user_id, "lab_id": lab_id, "name": group_name, "director": director},
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
    # force=True: the pre-flight guard refuses this row (that is
    # TestPreflightGuard's subject); this test is about what the reseed body
    # does once an operator has accepted the loss.
    with caplog.at_level("WARNING", logger="backend.authz.reseed"):
        reseed(conn, force=True)
    assert "unmapped" in caplog.text
    assert _grants(conn, "10") == []


class TestPreflightGuard:
    """M2-PRE-4 — refuse to reseed data whose effective access would change."""

    def test_clean_data_passes(self, conn):
        _add_user(conn, 1)
        _add_membership(conn, 1, 7, "Lab Director", director=True)
        assert not any(preflight_counts(conn).values())
        reseed(conn)  # no force needed
        assert _grants(conn, "1")

    def test_director_flag_group_mismatch_aborts(self, conn):
        _add_user(conn, 2)
        # Legacy trusts the flag (all capabilities); reseed trusts the group
        # (member-RW only), so this user silently loses director access.
        _add_membership(conn, 2, 7, "Lab Collaborator", director=True)
        with pytest.raises(ReseedPreflightError) as exc:
            reseed(conn)
        assert exc.value.counts["director_flag_group_mismatch"] == 1
        assert _grants(conn, "2") == [], "must abort before inserting anything"

    def test_unmapped_group_aborts(self, conn):
        _add_user(conn, 3)
        _add_membership(conn, 3, 7, "Data Analyst")
        with pytest.raises(ReseedPreflightError) as exc:
            reseed(conn)
        assert exc.value.counts["unmapped_permission_group"] == 1

    def test_project_only_membership_aborts(self, conn):
        _add_user(conn, 4)
        _add_project_membership(conn, user_id=4, project_id=1, lab_id=7)
        with pytest.raises(ReseedPreflightError) as exc:
            reseed(conn)
        assert exc.value.counts["project_only_membership"] == 1

    def test_project_member_who_also_has_lab_membership_is_not_counted(self, conn):
        # Only members who would LOSE access count: a project member who also
        # holds lab_membership is reseeded normally.
        _add_user(conn, 5)
        _add_membership(conn, 5, 7, "Lab Reader")
        _add_project_membership(conn, user_id=5, project_id=1, lab_id=7)
        assert preflight_counts(conn)["project_only_membership"] == 0
        reseed(conn)

    def test_force_proceeds_and_warns(self, conn, caplog):
        _add_user(conn, 6)
        _add_membership(conn, 6, 7, "Lab Collaborator", director=True)
        with caplog.at_level("WARNING", logger="backend.authz.reseed"):
            reseed(conn, force=True)
        assert "force=True" in caplog.text
        assert _grants(conn, "6"), "force must still perform the reseed"

    def test_counts_are_reported_together(self, conn):
        """All three surface at once — fixing one must not hide the others."""
        _add_user(conn, 7)
        _add_membership(conn, 7, 7, "Lab Collaborator", director=True)
        _add_user(conn, 8)
        _add_membership(conn, 8, 7, "Data Analyst")
        _add_user(conn, 9)
        _add_project_membership(conn, user_id=9, project_id=2, lab_id=8)
        with pytest.raises(ReseedPreflightError) as exc:
            reseed(conn)
        assert exc.value.counts == {
            "director_flag_group_mismatch": 1,
            "unmapped_permission_group": 1,
            "project_only_membership": 1,
        }
        # The operator sees which kinds, not just that something failed.
        for kind in exc.value.counts:
            assert kind in str(exc.value)


class TestSampleAccessGrants:
    """M2-B2-PRE-C — approved per-sample access survives the cutover."""

    def _sample(self, conn, sample_id=500, lab_id=7, project_id=3):
        _add_lab(conn, lab_id)
        conn.execute(
            text("INSERT INTO samples (id, lab_id, project_id) VALUES (:s, :l, :p)"),
            {"s": sample_id, "l": lab_id, "p": project_id},
        )
        return scope_uri(org=ORG_ID, lab=lab_id, project=project_id, sample=sample_id)

    def test_live_grant_becomes_a_sample_scoped_grant(self, conn):
        _add_user(conn, 20)
        scope = self._sample(conn)
        conn.execute(
            text(
                "INSERT INTO sample_access_grants (requester_id, sample_id, revoked) "
                "VALUES (20, 500, FALSE)"
            )
        )
        reseed(conn)
        grants = _grants(conn, "20")
        assert {g.capability for g in grants} == {"sample:read", "sample:read_detail"}
        assert all(g.scope_ref == scope and g.source == "direct" for g in grants)

    def test_revoked_grant_is_not_reseeded(self, conn):
        _add_user(conn, 21)
        self._sample(conn, sample_id=501)
        conn.execute(
            text(
                "INSERT INTO sample_access_grants (requester_id, sample_id, revoked) "
                "VALUES (21, 501, TRUE)"
            )
        )
        reseed(conn)
        assert _grants(conn, "21") == []

    def test_expired_grant_is_not_reseeded(self, conn):
        _add_user(conn, 22)
        self._sample(conn, sample_id=502)
        conn.execute(
            text(
                "INSERT INTO sample_access_grants "
                "(requester_id, sample_id, revoked, access_expires_at) "
                "VALUES (22, 502, FALSE, '2000-01-01 00:00:00')"
            )
        )
        reseed(conn)
        assert _grants(conn, "22") == []

    def test_expiry_is_carried_onto_the_grant(self, conn):
        _add_user(conn, 23)
        self._sample(conn, sample_id=503)
        conn.execute(
            text(
                "INSERT INTO sample_access_grants "
                "(requester_id, sample_id, revoked, access_expires_at) "
                "VALUES (23, 503, FALSE, '2999-01-01 00:00:00')"
            )
        )
        reseed(conn)
        rows = conn.execute(
            text("SELECT not_after FROM authz_capability_grants WHERE principal_id = '23'")
        ).fetchall()
        assert rows and all(r[0] is not None for r in rows), (
            "an unbounded grant would outlive its expiry"
        )

    def test_approved_request_without_a_grant_row_is_covered(self, conn):
        """The documented fallback rung — pre-grants-table data."""
        _add_user(conn, 24)
        self._sample(conn, sample_id=504)
        conn.execute(
            text(
                "INSERT INTO sample_access_requests (requester_id, sample_id, status) "
                "VALUES (24, 504, 'APPROVED')"
            )
        )
        reseed(conn)
        assert {g.capability for g in _grants(conn, "24")} == {
            "sample:read",
            "sample:read_detail",
        }

    def test_pending_request_grants_nothing(self, conn):
        _add_user(conn, 25)
        self._sample(conn, sample_id=505)
        conn.execute(
            text(
                "INSERT INTO sample_access_requests (requester_id, sample_id, status) "
                "VALUES (25, 505, 'PENDING')"
            )
        )
        reseed(conn)
        assert _grants(conn, "25") == []
