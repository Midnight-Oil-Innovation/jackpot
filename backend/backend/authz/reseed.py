"""One-time APGAP-role → capability-grant reseed (access_model.md §10.2).

Reads the legacy stored roles (``users.is_platform_admin``,
``users.is_data_analyst``, ``lab_membership`` joined to
``permission_groups``) and issues the matching preset grants into
``authz_capability_grants`` per the §8.5 mapping table. Designed to be
called from inside the M2 cutover Alembic migration via
``reseed(op.get_bind())`` — the same migration then removes the legacy
columns, so there is never a dual-authoritative window.

All SQL is raw ``text()``; no ORM. Idempotent: inserts use
``ON CONFLICT DO NOTHING`` against the unique
``(principal_id, capability, scope_ref)`` index the containing migration
creates.

Note on ``pipeline:run``: the §8.5 mapping folds Bioinformatics User into
Lab Member RW *plus* ``pipeline:run`` as an independent extra capability,
so ``PRESET_GRANTS["lab_member_rw"]`` deliberately excludes it —
``BIOINFORMATICS_EXTRA`` is the only place it is added for memberships.
"""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

# Capability lists verbatim from access_model.md §8.2 preset definitions,
# capability names from the §4 catalog.
PRESET_GRANTS: dict[str, list[str]] = {
    "instance_administrator": [
        "org:manage",
        "user:manage",
        "key:rotate",
        "whitelist:manage",
        "audit:read",
        "access:approve_request",
        "access:revoke",
        "federation:configure_peer",
        "federation:write_agreement",
        "federation:review_request",
        "federation:approve_request",
        "anomaly:configure_detector",
        "sample:read_surveillance",
    ],
    "surveillance_officer": [
        "sample:read_surveillance",
        "anomaly:review",
        "anomaly:triage",
    ],
    "lab_lead": [
        "sample:read",
        "sample:read_detail",
        "sample:create",
        "sample:update",
        "sample:archive",
        "sample:soft_delete",
        "deletion:request",
        "deletion:approve",
        "access:approve_request",
        "access:revoke",
        "pipeline:run",
        "submission:approve",
    ],
    "lab_member_rw": [
        "sample:read",
        "sample:read_detail",
        "sample:create",
        "sample:update",
        "deletion:request",
    ],
    "lab_member_ro": [
        "sample:read",
        "sample:read_detail",
    ],
}

# Bioinformatics User = lab_member_rw capabilities + pipeline:run (§8.5).
BIOINFORMATICS_EXTRA: list[str] = ["pipeline:run"]

# APGAP permission_groups.name → preset key. 'Platform Admin' and
# 'Data Analyst' memberships are intentionally absent: those roles are
# carried by the users booleans and reseeded at Instance scope (§10.2).
MEMBERSHIP_PRESETS: dict[str, str] = {
    "Lab Director": "lab_lead",
    "Lab Collaborator": "lab_member_rw",
    "Lab Reader": "lab_member_ro",
    "Bioinformatics User": "lab_member_rw",
}

INSTANCE_SCOPE = "instance://self"
GRANT_SOURCE = "reseed"

_INSERT_GRANT = text(
    """
    INSERT INTO authz_capability_grants (principal_id, capability, scope_ref, source)
    VALUES (:principal_id, :capability, :scope_ref, :source)
    ON CONFLICT DO NOTHING
    """
)


def _lab_scope(lab_id: int) -> str:
    return f"lab://{lab_id}"


def _grant_rows(principal_id: str, capabilities: list[str], scope_ref: str) -> list[dict]:
    return [
        {
            "principal_id": principal_id,
            "capability": cap,
            "scope_ref": scope_ref,
            "source": GRANT_SOURCE,
        }
        for cap in capabilities
    ]


def reseed(conn: Connection) -> None:
    """Translate every stored APGAP role into preset grants (§8.5 mapping).

    Runs inside the caller's transaction (the migration provides it).
    Re-entrant: duplicate grants are skipped via ON CONFLICT DO NOTHING.
    """
    rows: list[dict] = []

    admins = conn.execute(text("SELECT id FROM users WHERE is_platform_admin = TRUE")).fetchall()
    for (user_id,) in admins:
        rows.extend(
            _grant_rows(str(user_id), PRESET_GRANTS["instance_administrator"], INSTANCE_SCOPE)
        )

    analysts = conn.execute(
        text("SELECT id FROM users WHERE is_data_analyst = TRUE AND is_platform_admin = FALSE")
    ).fetchall()
    for (user_id,) in analysts:
        rows.extend(
            _grant_rows(str(user_id), PRESET_GRANTS["surveillance_officer"], INSTANCE_SCOPE)
        )

    memberships = conn.execute(
        text(
            "SELECT lm.user_id, lm.lab_id, pg.name "
            "FROM lab_membership lm "
            "JOIN permission_groups pg ON pg.id = lm.permission_group_id"
        )
    ).fetchall()
    skipped = 0
    for user_id, lab_id, group_name in memberships:
        preset = MEMBERSHIP_PRESETS.get(group_name)
        if preset is None:
            skipped += 1
            logger.warning(
                "reseed: lab_membership (user=%s, lab=%s) has unmapped "
                "permission group %r — skipped, no grants issued",
                user_id,
                lab_id,
                group_name,
            )
            continue
        scope = _lab_scope(lab_id)
        capabilities = list(PRESET_GRANTS[preset])
        if group_name == "Bioinformatics User":
            capabilities.extend(BIOINFORMATICS_EXTRA)
        rows.extend(_grant_rows(str(user_id), capabilities, scope))

    before = conn.execute(text("SELECT COUNT(*) FROM authz_capability_grants")).scalar_one()
    if rows:  # executemany rejects an empty parameter list
        conn.execute(_INSERT_GRANT, rows)
    after = conn.execute(text("SELECT COUNT(*) FROM authz_capability_grants")).scalar_one()

    logger.info(
        "reseed: %d platform admins, %d data analysts, %d lab memberships "
        "(%d skipped/unmapped) read; %d grants attempted, %d inserted",
        len(admins),
        len(analysts),
        len(memberships),
        skipped,
        len(rows),
        after - before,
    )
