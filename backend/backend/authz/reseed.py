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

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from backend.authz.scope import scope_uri

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
        # POST /ingest/globus records a sequencing-facility deposit and
        # notifies the assigned Lab Directors — it creates no samples. It was
        # mapped to sample:create from its router rather than its behavior,
        # and since it passes no lab_id it needed sample:create at INSTANCE
        # scope, which no preset grants: the route was reachable by nobody.
        # A narrow verb keeps the §8.2 governance/data-plane split intact
        # instead of making the admin a data-plane superuser (M2-B1).
        "deposit:record",
        # M2-B1: both verbs are used by wired routes but appeared in no
        # preset, so after reseed nobody could hold them and
        # pipelines/{id}/promote and the custom-pipeline registration route
        # were unreachable by every principal. Promotion is a
        # deployment-lifecycle act, so it sits with the instance admin.
        "pipeline:promote",
        "pipeline:register_custom",
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
        # BYOP registration is lab-level work — the endpoint-capability map
        # scopes every byop route at Lab — so a Lab Lead registers their own
        # pipelines without an instance admin in the loop (M2-B1).
        "pipeline:register_custom",
        # PATCH /labs/{id} and POST /projects both require org:manage, so
        # without this a Lab Lead could not rename their own lab or create a
        # project in it — work the legacy director flag allowed and nobody
        # intended to remove. Safe because grants are SCOPED: this one is
        # issued at lab://<their lab>, so it authorizes org:manage only within
        # that subtree, never on the org or on another lab (§5 containment).
        # The verb reads oddly at lab scope; a narrower lab:manage /
        # project:create pair is the tidier vocabulary and is M2-B5's call,
        # not a reason to leave directors locked out now.
        "org:manage",
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

INSTANCE_SCOPE = scope_uri()
GRANT_SOURCE = "reseed"

_INSERT_GRANT = text(
    """
    INSERT INTO authz_capability_grants (principal_id, capability, scope_ref, source)
    VALUES (:principal_id, :capability, :scope_ref, :source)
    ON CONFLICT DO NOTHING
    """
)


# ── Pre-flight data-quality guard (M2-PRE-4) ─────────────────────────────


class ReseedPreflightError(RuntimeError):
    """Raised when the source data would change users' effective access.

    Carries ``counts`` so the migration can print them; the message is what an
    operator sees when ``alembic upgrade head`` stops.
    """

    def __init__(self, counts: dict[str, int]):
        self.counts = counts
        super().__init__(
            "reseed pre-flight found rows whose access changes at cutover: "
            + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()) if v)
            + ". Reconcile them, or re-run with force=True to accept the "
            "change deliberately. See docs/m2_preflight_report.md §4."
        )


# Each query counts rows whose effective access CHANGES at cutover. They are
# separate rather than one UNION so the operator sees which kind, and so a
# zero for one does not hide a non-zero for another.
_PREFLIGHT_COUNTS: dict[str, str] = {
    # Legacy trusts lab_membership.is_lab_director for every non-member-level
    # capability; reseed trusts the permission group. Where they disagree the
    # user silently drops from lab_lead to whatever the group says.
    "director_flag_group_mismatch": (
        "SELECT COUNT(*) FROM lab_membership lm "
        "JOIN permission_groups pg ON pg.id = lm.permission_group_id "
        "WHERE lm.is_lab_director = TRUE AND pg.name <> 'Lab Director'"
    ),
    # A group absent from MEMBERSHIP_PRESETS is skipped with a warning, so the
    # user ends the cutover holding no grants at all.
    "unmapped_permission_group": (
        "SELECT COUNT(*) FROM lab_membership lm "
        "JOIN permission_groups pg ON pg.id = lm.permission_group_id "
        "WHERE pg.name NOT IN :preset_names"
    ),
    # Legacy member-level checks accept project membership via the
    # project->lab join (guards.py); reseed reads lab_membership only, so a
    # project-only member loses guarded read access.
    "project_only_membership": (
        "SELECT COUNT(DISTINCT pm.user_id) FROM project_membership pm "
        "JOIN projects p ON p.id = pm.project_id "
        "WHERE NOT EXISTS ("
        "  SELECT 1 FROM lab_membership lm "
        "  WHERE lm.user_id = pm.user_id AND lm.lab_id = p.lab_id"
        ")"
    ),
}


def preflight_counts(conn: Connection) -> dict[str, int]:
    """Count rows whose effective access would change at cutover.

    Read-only. Runs before any INSERT so the numbers describe the source data,
    not the result of a partial reseed.
    """
    counts: dict[str, int] = {}
    for name, sql in _PREFLIGHT_COUNTS.items():
        stmt = text(sql)
        params: dict[str, object] = {}
        if ":preset_names" in sql:
            stmt = stmt.bindparams(bindparam("preset_names", expanding=True))
            params["preset_names"] = list(MEMBERSHIP_PRESETS)
        counts[name] = conn.execute(stmt, params).scalar_one()
    return counts


def _lab_scope(org_id: int, lab_id: int) -> str:
    """Canonical lab path (§3.1.1, ADR 0015).

    The org segment is why the membership query joins ``labs``: a lab scope
    that did not run through its org would not be contained by an org-scoped
    grant, and — the reason the cutover was blocked — the old ``lab://{id}``
    form shared no root with ``instance://self``, so an instance-scoped admin
    grant contained nothing.
    """
    return scope_uri(org=org_id, lab=lab_id)


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


def reseed(conn: Connection, *, force: bool = False) -> None:
    """Translate every stored APGAP role into preset grants (§8.5 mapping).

    Runs inside the caller's transaction (the migration provides it).
    Re-entrant: duplicate grants are skipped via ON CONFLICT DO NOTHING.

    Refuses to run when :func:`preflight_counts` finds rows whose effective
    access changes at cutover, unless ``force=True``. The check ships here
    rather than being performed once by a maintainer beforehand because no
    deployment we can inspect holds real membership rows — a pre-cutover sweep
    would pass vacuously — and because it must run for operators we never meet
    (Critical Rule 55).
    """
    counts = preflight_counts(conn)
    if any(counts.values()):
        if not force:
            raise ReseedPreflightError(counts)
        logger.warning(
            "reseed: proceeding with force=True over pre-flight findings: %s",
            {k: v for k, v in counts.items() if v},
        )

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
            "SELECT lm.user_id, lm.lab_id, l.organization_id, pg.name "
            "FROM lab_membership lm "
            "JOIN permission_groups pg ON pg.id = lm.permission_group_id "
            "JOIN labs l ON l.id = lm.lab_id"
        )
    ).fetchall()
    skipped = 0
    for user_id, lab_id, org_id, group_name in memberships:
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
        scope = _lab_scope(org_id, lab_id)
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
