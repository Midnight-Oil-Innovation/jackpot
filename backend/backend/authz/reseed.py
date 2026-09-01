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

Note on ``pipeline:run``: it is part of the Lab Member RW preset. This module
previously excluded it and added it back only for Bioinformatics User, reading
§8.5's "folded into Lab Member RW + ``pipeline:run``" as meaning RW lacks it.
§8.2's preset block is the definition and says otherwise — it lists
``pipeline:run`` under Lab Member (read-write), with the note "can run
pipelines but not approve submissions or access requests" — and on that
reading §8.5's phrasing is just loose: if RW already holds the verb, a
Bioinformatics User simply *is* a Lab Member RW. Corrected in M2-B3, which
found the contradiction; ``BIOINFORMATICS_EXTRA`` is gone with it.
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
        # M2-B4: the read-plane and admin verbs the M2 catalog review added to
        # §4 without anyone updating §8.2's preset blocks. token:manage is
        # here and nowhere else — §4.5 scopes it to acting on ANOTHER
        # principal's tokens, which is administrative by definition; a
        # caller's own tokens are auth-only (§4.7).
        "lab:read",
        "org:read",
        "import:read",
        "token:manage",
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
        # M2-B3-PRE: pipeline:read was in the §4 catalog but in no preset, so
        # every route that needs it was reachable by nobody — the same bug
        # this preset's two entries above were added to fix. The instance
        # admin's grant is at instance scope and so covers every project.
        "pipeline:read",
    ],
    "surveillance_officer": [
        "sample:read_surveillance",
        "anomaly:review",
        "anomaly:triage",
    ],
    "lab_lead": [
        # See lab_member_ro for why every lab preset holds pipeline:read.
        "pipeline:read",
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
        # M2-B4. A Lab Lead prepares as well as approves — §6.2-1b's
        # separation-of-duties DENY covers deletion, not submissions, so
        # holding both is not a conflict here.
        "submission:prepare",
        "import:read",
        "import:manage",
        "lab:read",
        "org:read",
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
        # M2-B4. §8.2's note on this preset says a member "can run pipelines
        # but not approve submissions or access requests" — which distinguishes
        # preparing from approving rather than putting submissions out of
        # reach. Building the package is the work; approving it is governance,
        # and that stays with Lab Lead.
        "submission:prepare",
        "import:read",
        "import:manage",
        "lab:read",
        "org:read",
        "pipeline:read",
        # §8.2's preset block lists pipeline:run here. See the module
        # docstring: excluding it was a misreading of §8.5's role-mapping
        # prose, and it cost Lab Collaborators the ability to launch.
        "pipeline:run",
        "sample:read",
        "sample:read_detail",
        "sample:create",
        "sample:update",
        "deletion:request",
    ],
    "lab_member_ro": [
        # M2-B3-PRE. §4 defines pipeline:read as "read the pipeline zoo, the
        # BYOP registry, and run status", and run status is what a lab member
        # needs to see a run on their own lab's samples. It sits in every lab
        # preset including read-only: watching a run is not running one, and
        # pipeline:run — the launch verb — is held by Lab Lead and Lab Member
        # RW but not by read-only. Scoped at the member's lab, which
        # contains that lab's projects by ordinary containment (§3.1), so it
        # conveys nothing about any other lab's runs.
        "pipeline:read",
        # M2-B4: read-plane verbs a read-only member plainly needs — the lab
        # directory, the org they belong to, and the mapping configs that make
        # an import legible. None of the three writes anything.
        "lab:read",
        "org:read",
        "import:read",
        "sample:read",
        "sample:read_detail",
    ],
}

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
    INSERT INTO authz_capability_grants
        (principal_id, capability, scope_ref, source, not_after)
    VALUES (:principal_id, :capability, :scope_ref, :source, :not_after)
    ON CONFLICT DO NOTHING
    """
)

# Per-sample access, from both places the legacy ladder reads it
# (permissions.py:67). The grants table is the canonical artefact; APPROVED
# requests without a grant row are the documented fallback for pre-grants-table
# data, and the expiry job transitions a request to EXPIRED when its grant
# lapses, so an APPROVED row still present is necessarily still active.
_SAMPLE_ACCESS_SQL = text(
    """
    SELECT sag.requester_id AS user_id, s.id AS sample_id, s.lab_id, s.project_id,
           l.organization_id, sag.access_expires_at AS not_after
    FROM sample_access_grants sag
    JOIN samples s ON s.id = sag.sample_id
    JOIN labs l ON l.id = s.lab_id
    WHERE sag.revoked = FALSE
      AND (sag.access_expires_at IS NULL OR sag.access_expires_at > CURRENT_TIMESTAMP)
    UNION
    SELECT sar.requester_id, s.id, s.lab_id, s.project_id,
           l.organization_id, NULL
    FROM sample_access_requests sar
    JOIN samples s ON s.id = sar.sample_id
    JOIN labs l ON l.id = s.lab_id
    WHERE sar.status = 'APPROVED'
      AND NOT EXISTS (
        SELECT 1 FROM sample_access_grants g
        WHERE g.requester_id = sar.requester_id AND g.sample_id = sar.sample_id
      )
    """
)

# What an approved request conveys: read the sample, in a list and in detail.
SAMPLE_ACCESS_CAPABILITIES = ["sample:read", "sample:read_detail"]
DIRECT_SOURCE = "direct"


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


def _grant_rows(
    principal_id: str,
    capabilities: list[str],
    scope_ref: str,
    *,
    source: str = GRANT_SOURCE,
    not_after=None,
) -> list[dict]:
    return [
        {
            "principal_id": principal_id,
            "capability": cap,
            "scope_ref": scope_ref,
            "source": source,
            "not_after": not_after,
        }
        for cap in capabilities
    ]


def _sample_access_rows(conn: Connection) -> list[dict]:
    """Approved per-sample access → Sample-scoped grants (§5's mapping table).

    Without this, every approved access request stops granting anything at
    cutover: the legacy ladder reads these tables directly and reseed did not
    look at them at all.
    """
    rows: list[dict] = []
    for r in conn.execute(_SAMPLE_ACCESS_SQL).mappings():
        scope = scope_uri(
            org=r["organization_id"],
            lab=r["lab_id"],
            project=r["project_id"],
            sample=r["sample_id"],
        )
        rows.extend(
            _grant_rows(
                str(r["user_id"]),
                SAMPLE_ACCESS_CAPABILITIES,
                scope,
                source=DIRECT_SOURCE,
                not_after=r["not_after"],
            )
        )
    return rows


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
        # Bioinformatics User needs no extra capability: it maps to
        # lab_member_rw, which holds pipeline:run (§8.2).
        rows.extend(_grant_rows(str(user_id), list(PRESET_GRANTS[preset]), scope))

    access_rows = _sample_access_rows(conn)
    rows.extend(access_rows)

    before = conn.execute(text("SELECT COUNT(*) FROM authz_capability_grants")).scalar_one()
    if rows:  # executemany rejects an empty parameter list
        conn.execute(_INSERT_GRANT, rows)
    after = conn.execute(text("SELECT COUNT(*) FROM authz_capability_grants")).scalar_one()

    logger.info(
        "reseed: %d per-sample access grants issued from approved requests (source=%s)",
        len(access_rows),
        DIRECT_SOURCE,
    )
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


# ── Live membership → grants (M2-B5) ─────────────────────────────────────
#
# reseed() translates every stored role at cutover. These do the same for one
# membership as it changes, which is what makes membership mean anything after
# cutover: a lab_membership row is not a decision input any more, so a member
# added on Tuesday holds nothing until someone runs a reseed. §4.5 already
# scopes user:manage as "create/modify/deactivate users, assign capabilities"
# — issuing the grants IS the assignment, not a side effect of it.

_DELETE_MEMBERSHIP_GRANTS = text(
    """
    DELETE FROM authz_capability_grants
     WHERE principal_id = :principal_id
       AND scope_ref = :scope_ref
       AND source = :source
    """
)


def _membership_capabilities(group_name: str) -> list[str] | None:
    """Preset capabilities for an APGAP group, or None if it maps to none."""
    preset = MEMBERSHIP_PRESETS.get(group_name)
    return list(PRESET_GRANTS[preset]) if preset else None


def sync_membership_grants(
    conn: Connection, *, user_id: int, lab_id: int, group_name: str | None
) -> int:
    """Make one user's grants at one lab match their membership.

    ``group_name=None`` removes the membership's grants — used when the
    membership itself is deleted.

    Delete-then-insert rather than a diff: the whole point is that the row
    and the grants agree afterwards, and a diff would have to reason about
    which of the previous group's capabilities the new group also has. Scoped
    by ``source = 'reseed'`` so it cannot touch a per-sample access grant
    (``source = 'direct'``) that happens to sit at the same principal.

    Returns the number of grants issued.
    """
    org_rows = (
        conn.execute(text("SELECT organization_id FROM labs WHERE id = :lid"), {"lid": lab_id})
        .mappings()
        .all()
    )
    if not org_rows:
        raise ValueError(f"unknown lab_id {lab_id!r} — cannot scope membership grants")
    scope = _lab_scope(org_rows[0]["organization_id"], lab_id)

    conn.execute(
        _DELETE_MEMBERSHIP_GRANTS,
        {"principal_id": str(user_id), "scope_ref": scope, "source": GRANT_SOURCE},
    )
    if group_name is None:
        return 0
    capabilities = _membership_capabilities(group_name)
    if capabilities is None:
        logger.warning(
            "membership sync: permission group %r maps to no preset; user %s holds "
            "no grants at lab %s",
            group_name,
            user_id,
            lab_id,
        )
        return 0
    rows = _grant_rows(str(user_id), capabilities, scope)
    for row in rows:
        conn.execute(_INSERT_GRANT, row)
    return len(rows)


def group_name_for_id(conn: Connection, permission_group_id: int) -> str | None:
    rows = (
        conn.execute(
            text("SELECT name FROM permission_groups WHERE id = :pg"),
            {"pg": permission_group_id},
        )
        .mappings()
        .all()
    )
    return rows[0]["name"] if rows else None
