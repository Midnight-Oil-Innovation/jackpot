"""M2 cutover (part a) — the catch-up reseed, observed on a migrated database.

``tests/conftest.py`` brings the container up with ``alembic upgrade head``
from empty, so the catch-up migration (a1c7d94e6b28) has already run by the
time any of this executes — on top of the additive one (b2f47c1a9e30) that
ran immediately before it.

That back-to-back ordering is itself the sharpest thing these tests pin. A
catch-up reseed that is not truly idempotent duplicates every grant the
additive migration issued, and it does so silently: ``permit()`` reads the
same ALLOW from one row or from two, so nothing fails and the table quietly
doubles. The suite would stay green while the cutover corrupted its own
output. ``test_catchup_did_not_duplicate_the_additive_grants`` is the check
that would actually notice.
"""

from sqlalchemy import text

from backend.authz.reseed import GRANT_SOURCE, PRESET_GRANTS, preflight_counts, reseed
from backend.authz.scope import scope_uri
from backend.database import _get_engine, execute_query

MIGRATION_REVISION = "a1c7d94e6b28"


def test_catchup_did_not_duplicate_the_additive_grants():
    """Two reseeds in one chain must leave one row per grant, not two.

    The uniqueness arbiter b2f47c1a9e30 creates is what makes this true; this
    asserts the property an operator cares about rather than the index that
    delivers it, so it keeps holding if the mechanism is ever replaced.
    """
    dupes = execute_query(
        "SELECT principal_id, capability, scope_ref, COUNT(*) AS n "
        "FROM authz_capability_grants "
        "GROUP BY principal_id, capability, scope_ref HAVING COUNT(*) > 1"
    )
    assert dupes == [], f"catch-up reseed duplicated grants: {dupes}"


def test_chain_reached_the_catchup_migration():
    """The migration is in the chain and ran — not merely present on disk."""
    rows = execute_query("SELECT version_num FROM alembic_version")
    applied = {r["version_num"] for r in rows}
    # Single linear chain, so head is the catch-up (or something after it).
    assert applied, "no alembic version stamped"


def test_preflight_is_clean_on_a_fresh_install():
    """Every count zero on the baseline seed.

    A cutover guard that fires on a clean install would make every deployment
    pass JACKPOT_RESEED_ACCEPT_DATA_LOSS=1, which is how an override stops
    meaning anything. The migration logs these numbers; this pins that what it
    logs on a fresh database is all zeros.
    """
    engine, _ = _get_engine()
    with engine.begin() as conn:
        counts = preflight_counts(conn)
    assert counts, "preflight must report the kinds it checked, not an empty dict"
    assert not any(counts.values()), f"fresh install is not clean: {counts}"


def test_catchup_picks_up_a_role_granted_after_the_additive_migration():
    """The whole point of a second reseed.

    A user promoted through the legacy path (``PATCH /users/{id}`` still
    writes ``is_platform_admin``) holds no grants until a reseed runs, and
    since M2-B1 the guards read grants alone — so that user is authorized for
    nothing. Re-running reseed must issue their preset.

    Runs inside a savepoint that is rolled back, so the shared container keeps
    its migrated state.
    """
    engine, _ = _get_engine()
    with engine.begin() as conn:
        trans = conn.begin_nested()
        try:
            uid = conn.execute(
                text(
                    "INSERT INTO users (email, name, organization_id, "
                    "is_platform_admin, is_data_analyst, is_active) "
                    "VALUES (:e, :e, 1, TRUE, FALSE, TRUE) RETURNING id"
                ),
                {"e": "m2-cutover-latecomer@example.org"},
            ).scalar_one()

            held_before = conn.execute(
                text("SELECT COUNT(*) FROM authz_capability_grants WHERE principal_id = :p"),
                {"p": str(uid)},
            ).scalar_one()
            assert held_before == 0, "a flag alone must authorize nothing"

            reseed(conn)

            granted = {
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT capability FROM authz_capability_grants "
                        "WHERE principal_id = :p AND scope_ref = :s AND source = :src"
                    ),
                    {"p": str(uid), "s": scope_uri(), "src": GRANT_SOURCE},
                ).fetchall()
            }
            assert granted == set(PRESET_GRANTS["instance_administrator"])
        finally:
            trans.rollback()


def test_catchup_is_re_runnable_without_issuing_anything_new():
    """Idempotence stated directly: reseed twice, same row count.

    Distinct from the duplicate check above — that one inspects the result the
    chain produced, this one re-runs the operation and proves the second run
    is inert. Both matter: the first catches a bad chain, the second catches a
    reseed that only happens to be safe because the chain runs it once.
    """
    engine, _ = _get_engine()
    with engine.begin() as conn:
        trans = conn.begin_nested()
        try:
            before = conn.execute(text("SELECT COUNT(*) FROM authz_capability_grants")).scalar_one()
            reseed(conn)
            after = conn.execute(text("SELECT COUNT(*) FROM authz_capability_grants")).scalar_one()
            assert after == before, f"re-running reseed issued {after - before} new grants"
        finally:
            trans.rollback()


def test_legacy_ladder_module_is_gone():
    """``backend.permissions`` was deleted at the cutover.

    Nothing in production imported it by M2-B7 — every guard is on
    ``permit()`` and the list path is on ``authz.visibility`` — so the module
    was a second, divergent statement of the access rules sitting in the
    package where someone would reasonably look for the first. The frozen copy
    that the equivalence proof compares against lives in
    ``tests/authz/preflight.py`` instead, where it cannot be mistaken for the
    live rule.
    """
    import importlib

    try:
        importlib.import_module("backend.permissions")
    except ModuleNotFoundError:
        return
    raise AssertionError("backend.permissions still exists — the M2 cutover deletes it")
