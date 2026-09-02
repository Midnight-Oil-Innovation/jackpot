# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""M2-DROP: the downgrade can rebuild what the drop removed.

``d51c4361877d`` drops ``users.is_platform_admin`` / ``is_data_analyst``.
Dropping a column is normally one-way, and the migration's docstring claims
these two are an exception because the grants they were translated into still
exist — so ``downgrade()`` reconstructs them.

That claim is the reason the migration is safe to run, and until this file it
was only a claim. What is exercised here is the reconstruction SQL itself,
against real grants, rather than alembic's plumbing: the two UPDATE statements
are the part that can be wrong.

The choice of capability is the whole trick and is asserted directly below:
``user:manage`` and ``anomaly:review`` each belong to exactly one Instance
preset, while ``sample:read_surveillance`` belongs to BOTH and would silently
mark every surveillance officer as a platform admin.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text

from backend.authz.reseed import PRESET_GRANTS, sync_instance_preset
from backend.database import _get_engine, execute_query, execute_write


def _migration():
    """The migration module itself, loaded by path.

    ``backend/db/migrations/versions/`` is not an importable package — alembic
    loads revisions by file path and so does this. Importing rather than
    copying is the entire point: the previous version of this file pasted the
    reconstruction SQL and asserted in a comment that a migration edit would
    "fail loudly", which was false. Nothing connected the two, so editing
    downgrade() would have left these tests passing against a stale copy of
    SQL that no longer existed.
    """
    root = Path(__file__).resolve().parents[2]
    # Globbed on the revision id: alembic keys on that, not on the slug, so a
    # rename of the descriptive half should not break this.
    path = next(root.glob("backend/db/migrations/versions/d51c4361877d_*.py"))
    spec = importlib.util.spec_from_file_location("m2_drop_migration", path)
    assert spec is not None and spec.loader is not None, f"revision file unreadable: {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MIGRATION = _migration()
INSTANCE_SCOPE = _MIGRATION.INSTANCE_SCOPE
PROBES = dict(_MIGRATION.RECONSTRUCT_FROM)
ADMIN_PROBE = PROBES["is_platform_admin"]
ANALYST_PROBE = PROBES["is_data_analyst"]


def test_the_probe_capabilities_each_belong_to_exactly_one_instance_preset():
    """The premise the reconstruction rests on.

    "Instance preset" is the qualifier that matters: ``user:manage`` is also
    in ``lab_lead``, but only ever at a LAB scope, which the reconstruction's
    scope predicate excludes. If a probe were held by both INSTANCE presets it
    could not tell them apart, and the downgrade would mislabel one as the other. This is the
    trap M2-DROP-PRE slice 8's first test fell into with
    ``sample:read_surveillance``, so it is asserted rather than assumed.
    """
    admin = set(PRESET_GRANTS["instance_administrator"])
    officer = set(PRESET_GRANTS["surveillance_officer"])

    assert ADMIN_PROBE in admin and ADMIN_PROBE not in officer
    assert ANALYST_PROBE in officer and ANALYST_PROBE not in admin
    assert "sample:read_surveillance" in admin & officer, (
        "the capability the reconstruction must NOT use stopped being ambiguous; "
        "re-read the migration docstring before trusting either probe"
    )


def _user(email: str, name: str) -> int:
    return execute_write(
        "INSERT INTO users (email, name, organization_id, is_active) "
        "VALUES (:e, :n, 1, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET is_active = TRUE RETURNING id",
        {"e": email, "n": name},
    )[0]["id"]


def _drop_legacy_columns(conn) -> None:
    for column, _ in _MIGRATION.RECONSTRUCT_FROM:
        conn.execute(text(f"ALTER TABLE users DROP COLUMN IF EXISTS {column}"))


@pytest.fixture
def rebuilt():
    """Three principals holding one Instance role each, then the downgrade.

    Calls the migration's own ``reconstruct()`` rather than re-issuing its
    statements: the ADD COLUMN DDL is as much a part of the downgrade as the
    UPDATE, and a test that pastes ``BOOLEAN NOT NULL DEFAULT FALSE`` stops
    noticing when the column type changes.
    """
    ids = {
        "admin": _user("recon-admin@example.org", "Recon Admin"),
        "officer": _user("recon-officer@example.org", "Recon Officer"),
        "plain": _user("recon-plain@example.org", "Recon Plain"),
    }
    engine, _ = _get_engine()
    try:
        with engine.begin() as conn:
            sync_instance_preset(conn, user_id=ids["admin"], preset="instance_administrator")
            sync_instance_preset(conn, user_id=ids["officer"], preset="surveillance_officer")
            sync_instance_preset(conn, user_id=ids["plain"], preset=None)
            _MIGRATION.reconstruct(conn)
        yield ids
    finally:
        # try/finally, not a bare post-yield: a failure during SETUP would
        # otherwise leave the columns ADDed on the shared users table for the
        # rest of the session — a schema mutation every other authz test sees.
        with engine.begin() as conn:
            _drop_legacy_columns(conn)
        for uid in ids.values():
            execute_write(
                "DELETE FROM authz_capability_grants WHERE principal_id = :p", {"p": str(uid)}
            )
            execute_write("DELETE FROM users WHERE id = :i", {"i": uid})


def _flags(user_id: int) -> dict:
    return execute_query(
        "SELECT is_platform_admin, is_data_analyst FROM users WHERE id = :i", {"i": user_id}
    )[0]


def test_the_admin_flag_is_rebuilt_from_the_grant(rebuilt):
    row = _flags(rebuilt["admin"])
    assert row["is_platform_admin"] is True
    assert row["is_data_analyst"] is False, "an admin must not come back as an analyst too"


def test_the_analyst_flag_is_rebuilt_from_the_grant(rebuilt):
    row = _flags(rebuilt["officer"])
    assert row["is_data_analyst"] is True
    assert row["is_platform_admin"] is False, (
        "the officer was reconstructed as an admin — the probe capability is "
        "not unique to one preset"
    )


def test_a_lab_scoped_analyst_capability_does_not_reconstruct_a_global_flag():
    """Scope is load-bearing in the reconstruction, not decoration.

    ``is_data_analyst`` was a deployment-wide flag and
    ``surveillance_officer`` is an Instance-scope preset, so a lab-scoped
    ``anomaly:review`` must not come back as a global analyst. No preset
    issues one today, but a direct grant could — and widening a downgrade is
    how a schema rollback turns into a privilege grant.

    Pinned because a review proposed removing exactly this predicate.
    """
    uid = _user("recon-labscoped@example.org", "Lab Scoped")
    engine, _ = _get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO authz_capability_grants "
                    "(principal_id, capability, scope_ref, source) "
                    "VALUES (:p, :cap, 'instance://self/org/1/lab/1', 'direct')"
                ),
                {"p": str(uid), "cap": ANALYST_PROBE},
            )
            _MIGRATION.reconstruct(conn)
            row = (
                conn.execute(text("SELECT is_data_analyst FROM users WHERE id = :i"), {"i": uid})
                .mappings()
                .one()
            )
        assert row["is_data_analyst"] is False, (
            "a lab-scoped grant reconstructed a deployment-wide analyst flag"
        )
    finally:
        with engine.begin() as conn:
            _drop_legacy_columns(conn)
        execute_write(
            "DELETE FROM authz_capability_grants WHERE principal_id = :p", {"p": str(uid)}
        )
        execute_write("DELETE FROM users WHERE id = :i", {"i": uid})


@pytest.mark.parametrize(
    "extra_columns,extra_values,label",
    [
        ("not_after", "NOW() - INTERVAL '1 day'", "expired"),
        ("conditions", "CAST('{\"x\": 1}' AS JSONB)", "conditional"),
    ],
    ids=["expired", "conditional"],
)
def test_a_grant_the_engine_would_refuse_does_not_reconstruct_a_flag(
    extra_columns, extra_values, label
):
    """The reconstruction must refuse what ``permit()`` refuses.

    ``principal._CAPABILITY_HOLDERS_SQL`` is the reviewed answer to "who holds
    capability C at scope S", and it excludes expired grants and conditional
    ones — a condition is a fact about a request, and a downgrade has no
    request to evaluate it against. The first version of this migration
    omitted both predicates, so an expired ``user:manage`` would have restored
    ``is_platform_admin = TRUE``: a schema rollback handing out a role.

    No preset issues such a grant (``sync_instance_preset`` sets
    ``not_after=None`` and no conditions), which is exactly the reasoning that
    was judged insufficient for scope. A direct grant can.
    """
    uid = _user(f"recon-{label}@example.org", f"Recon {label.title()}")
    engine, _ = _get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO authz_capability_grants "
                    f"(principal_id, capability, scope_ref, source, {extra_columns}) "
                    f"VALUES (:p, :cap, :scope, 'direct', {extra_values})"
                ),
                {"p": str(uid), "cap": ADMIN_PROBE, "scope": INSTANCE_SCOPE},
            )
            _MIGRATION.reconstruct(conn)
            row = (
                conn.execute(text("SELECT is_platform_admin FROM users WHERE id = :i"), {"i": uid})
                .mappings()
                .one()
            )
        assert row["is_platform_admin"] is False, (
            f"a {label} grant reconstructed the admin flag — the downgrade is "
            "more permissive than the engine it is rebuilding from"
        )
    finally:
        with engine.begin() as conn:
            _drop_legacy_columns(conn)
        execute_write(
            "DELETE FROM authz_capability_grants WHERE principal_id = :p", {"p": str(uid)}
        )
        execute_write("DELETE FROM users WHERE id = :i", {"i": uid})


def test_a_principal_holding_nothing_comes_back_with_neither_flag(rebuilt):
    row = _flags(rebuilt["plain"])
    assert row["is_platform_admin"] is False
    assert row["is_data_analyst"] is False
