"""Test helpers for the capability-grant model (M2-B1, M2-DROP).

Lives in its own module rather than tests/conftest.py: `from conftest
import ...` resolves to whichever conftest pytest loaded for the current
directory, which in a full-suite run is tests/routers/conftest.py, not the
top-level one.
"""

from sqlalchemy import text

from backend.authz.reseed import (
    INSTANCE_PRESETS,
    sync_instance_preset,
    sync_membership_grants,
    sync_sample_access_grants,
)
from backend.database import _get_engine

#: The preset a test means when it used to write ``is_platform_admin = TRUE``.
ADMIN_PRESET = "instance_administrator"
#: ...and ``is_data_analyst = TRUE``.
ANALYST_PRESET = "surveillance_officer"


def _ensure_grant_uniq(conn) -> None:
    conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "authz_capability_grants_principal_capability_scope_uniq "
            "ON authz_capability_grants (principal_id, capability, scope_ref)"
        )
    )


def grant_instance_preset(user_id: int, preset: str | None = ADMIN_PRESET) -> None:
    """Give a test-created user their Instance-scope role.

    Replaces the pre-M2-DROP idiom of inserting a user row with
    ``is_platform_admin = TRUE`` and calling ``reseed()`` to translate it.
    That column is gone, so there is nothing left to translate: the grants
    ARE the role now, and this issues them through the same
    ``sync_instance_preset`` the routes use — a test that hand-wrote grant
    rows could pass against a production path that no longer produces them.

    ``preset=None`` removes the role, which is how a test asserts the
    negative case.
    """
    if preset is not None and preset not in INSTANCE_PRESETS:
        raise ValueError(f"{preset!r} is not an Instance-scope preset")
    engine, _ = _get_engine()
    with engine.begin() as conn:
        _ensure_grant_uniq(conn)
        sync_instance_preset(conn, user_id=user_id, preset=preset)


def sync_grants_from_legacy_roles() -> None:
    """Materialize membership grants for lab_membership rows a test created.

    The Instance half of this is gone with M2-DROP: it used to call
    ``reseed()``, which reads ``users.is_platform_admin`` /
    ``is_data_analyst``, and those columns no longer exist. Tests wanting an
    Instance-scope role call :func:`grant_instance_preset` explicitly, which
    is more honest anyway — the role is now something a test *grants* rather
    than something it stores and hopes gets translated.

    The other two halves are unchanged and still real, and both run through
    the same production functions the routes do:

    * membership — ``lab_membership`` joined to ``permission_groups``, which
      are live tables, via ``sync_membership_grants`` per row;
    * per-sample access — an APPROVED ``sample_access_requests`` row is legacy
      state, not a decision input, so it has to become the sample-scoped grant
      the engine reads, via ``sync_sample_access_grants``.

    Dropping the second one is a mistake worth naming: it fails as a 403 on a
    request that was approved, which reads like an authorization regression
    rather than a missing fixture step.
    """
    engine, _ = _get_engine()
    with engine.begin() as conn:
        _ensure_grant_uniq(conn)
        rows = conn.execute(
            text(
                "SELECT lm.user_id, lm.lab_id, pg.name AS group_name "
                "FROM lab_membership lm "
                "JOIN permission_groups pg ON pg.id = lm.permission_group_id"
            )
        ).mappings()
        for r in rows:
            sync_membership_grants(
                conn,
                user_id=r["user_id"],
                lab_id=r["lab_id"],
                group_name=r["group_name"],
            )
        samples = conn.execute(
            text("SELECT DISTINCT sample_id FROM sample_access_requests")
        ).scalars()
        for sample_id in list(samples):
            sync_sample_access_grants(conn, sample_id=sample_id)
