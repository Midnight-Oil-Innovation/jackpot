"""M2 additive migration (b2f47c1a9e30) — observed on a migrated database.

``tests/conftest.py`` brings the container up with ``alembic upgrade head``
from empty, so every assertion here is against a database the real chain
produced — including the baseline migration's operator-agnostic seed (one
platform admin, one Lab Director membership).

What this pins that the unit tests cannot: the migration is *in the chain and
runs*. `reseed()` being correct in isolation says nothing about whether the
cutover will actually have grants to check against.
"""

from sqlalchemy import text

from backend.authz.reseed import GRANT_SOURCE, PRESET_GRANTS
from backend.authz.scope import scope_uri
from backend.database import _get_engine, execute_query


def _reseeded(where: str, params: dict | None = None) -> list[dict]:
    return execute_query(
        "SELECT principal_id, capability, scope_ref FROM authz_capability_grants "
        f"WHERE source = :src AND {where}",  # noqa: S608
        {"src": GRANT_SOURCE, **(params or {})},
    )


def test_migration_created_the_unique_index():
    """Without it reseed's ON CONFLICT DO NOTHING dedupes nothing."""
    rows = execute_query(
        "SELECT indexdef FROM pg_indexes WHERE indexname = :n",
        {"n": "authz_capability_grants_principal_capability_scope_uniq"},
    )
    assert rows, "the additive migration must create the uniqueness arbiter"
    assert "UNIQUE" in rows[0]["indexdef"]
    for col in ("principal_id", "capability", "scope_ref"):
        assert col in rows[0]["indexdef"]


def test_baseline_admin_holds_instance_scoped_grants():
    """The seeded platform admin comes out of the migration with the §8.2 preset."""
    # Post-M2-DROP the baseline admin is identified by the grant the additive
    # migration issued, not by a column. Same subject, surviving evidence.
    # Joined to users and pinned to the seeded account. Selecting any holder
    # of user:manage at instance scope was fine when the column identified
    # exactly one; the suite now creates instance admins of its own, so
    # admins[0] would assert against whichever one the planner returned.
    admins = execute_query(
        "SELECT u.id FROM users u "
        "JOIN authz_capability_grants g ON g.principal_id = u.id::text "
        "WHERE g.capability = 'user:manage' AND g.scope_ref = 'instance://self' "
        "AND u.email = 'admin@example.org'"
    )
    assert admins, "baseline migration seeds a platform admin"

    granted = {
        r["capability"]
        for r in _reseeded(
            "principal_id = :p AND scope_ref = :s",
            {"p": str(admins[0]["id"]), "s": scope_uri()},
        )
    }
    assert granted == set(PRESET_GRANTS["instance_administrator"])


def test_every_reseeded_scope_is_canonical():
    """No grant may carry a pre-ADR-0015 scope shape.

    A single ``lab://7`` row surviving here would be invisible to every
    instance-scoped grant, which is the failure mode that blocked the cutover.
    """
    for row in _reseeded("TRUE"):
        assert row["scope_ref"].startswith(scope_uri()), row


def test_reseed_did_not_abort_on_the_baseline_seed():
    """The pre-flight guard must pass on a clean install, not merely exist.

    A guard that blocks `alembic upgrade head` on a fresh database would make
    every deployment require the override, which is how an override becomes
    reflexive and stops protecting anything.
    """
    assert _reseeded("TRUE"), "migration ran but issued no grants"


def test_downgrade_removes_only_what_the_migration_issued():
    """The downgrade's DELETE is predicated on source, not on the table.

    Run inside a savepoint that is rolled back, so the shared container keeps
    the migrated state. What this protects: a grant issued by any other path —
    a direct award, a future federation agreement — must survive a downgrade
    of this migration, because this migration did not create it.
    """
    engine, _ = _get_engine()
    with engine.begin() as conn:
        trans = conn.begin_nested()
        try:
            conn.execute(
                text(
                    "INSERT INTO authz_capability_grants "
                    "(principal_id, capability, scope_ref, source) "
                    "VALUES ('999999', 'sample:read_detail', :s, 'direct')"
                ),
                {"s": scope_uri(org=1, lab=1)},
            )
            before = conn.execute(
                text("SELECT COUNT(*) FROM authz_capability_grants WHERE source = :s"),
                {"s": GRANT_SOURCE},
            ).scalar_one()
            assert before, "expected reseeded rows to delete"

            # The downgrade body.
            conn.execute(
                text("DELETE FROM authz_capability_grants WHERE source = :s"),
                {"s": GRANT_SOURCE},
            )

            assert (
                conn.execute(
                    text("SELECT COUNT(*) FROM authz_capability_grants WHERE source = :s"),
                    {"s": GRANT_SOURCE},
                ).scalar_one()
                == 0
            )
            survived = conn.execute(
                text(
                    "SELECT COUNT(*) FROM authz_capability_grants "
                    "WHERE principal_id = '999999' AND source = 'direct'"
                )
            ).scalar_one()
            assert survived == 1, "downgrade must not remove grants it did not issue"
        finally:
            trans.rollback()
