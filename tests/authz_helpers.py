"""Test helpers for the capability-grant model (M2-B1).

Lives in its own module rather than tests/conftest.py: `from conftest
import ...` resolves to whichever conftest pytest loaded for the current
directory, which in a full-suite run is tests/routers/conftest.py, not the
top-level one.
"""


def sync_grants_from_legacy_roles() -> None:
    """Materialize capability grants for users a test created directly.

    Since M2-B1 the route guards decide on grants alone — creating a user row
    with ``is_platform_admin = TRUE`` authorizes nothing by itself, which is
    the point of removing the bypass. Tests that insert users and then call a
    guarded route need those roles translated, exactly as the migration does
    it, so this calls the real ``reseed()`` rather than hand-inserting grants:
    a test that hand-wrote grants could pass against a reseed that no longer
    produces them.

    ``force=True`` because a shared container may hold deliberately-broken
    fixtures from the authz suite (unmapped groups, flag/group mismatches);
    the pre-flight guard is exercised in its own tests, not here.
    """
    from sqlalchemy import text

    from backend.authz.reseed import reseed
    from backend.database import _get_engine

    engine, _ = _get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "authz_capability_grants_principal_capability_scope_uniq "
                "ON authz_capability_grants (principal_id, capability, scope_ref)"
            )
        )
        reseed(conn, force=True)
