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

import json
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
        # M2-DROP-PRE. §6.2-1b's escape — "unless a Platform Admin explicitly
        # self-approves" — was a request-body flag the route passed straight
        # into the policy condition, so ANY principal could set it and lift the
        # separation-of-duties DENY. (Not exploitable end to end: deletion.py
        # re-checked is_platform_admin. But that check is a legacy-column read
        # scheduled for removal, and removing it would have opened the hole.)
        # Making the escape a capability puts it back under the grant model:
        # the route now derives the condition from what the caller holds
        # instead of trusting what they sent. Confers no approval authority of
        # its own — see the §8.2 note.
        "deletion:self_approve",
        # M2-DROP-PRE slice 2. The last three admin-only deletion routes were
        # still reading users.is_platform_admin in-line because no verb named
        # them. All three are OPERATIONAL rather than consent acts — vacuum
        # and reverse-tombstone execute or unmake a decision the consent
        # authority already made, and the report is the record of one — which
        # is why the admin holds them while still holding neither
        # deletion:approve nor any content-read verb (§8.2's note).
        "deletion:read_report",
        "deletion:reverse_tombstone",
        "deletion:vacuum",
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
        # Same story, same scope argument, found later. M2 replaced
        # require_lab_director(user, lab_id) on the four /labs/{id}/members
        # routes with require_capability("user:manage") at Lab scope, and no
        # lab preset held the verb — so Lab Directors lost the roster of the
        # lab they direct, and M2-B5 then wired grant issuance into routes no
        # lab principal could reach. It is not in the endpoint map's
        # "Deliberate narrowings" list because nobody decided it.
        #
        # Safe because of scope and nothing else: the routes that administer
        # users at large (PATCH/DELETE /users/{id}) ask for user:manage with
        # no scope argument, which resolves to the instance root, and a lab://
        # grant does not contain the root — containment runs downward. §4.5's
        # "assign capabilities" reads at lab scope as "within this lab", which
        # is exactly what the four routes do. Pinned by
        # tests/test_lab_lead_member_management.py's two negative cases.
        "user:manage",
        # M2-DROP-PRE slice 2, all three replacing an in-line is_lab_director
        # test. sample:read_unscrubbed is the pre-scrub raw-FASTQ read and is
        # the one verb here the instance admin deliberately does NOT get: it
        # returns un-scrubbed sample CONTENT, and an operational admin holding
        # no sample:read_detail must not reach PII by a side door. The legacy
        # branch admitted a platform admin; this is a deliberate narrowing of
        # the same shape M3 applied to the deletion verbs.
        "sample:read_unscrubbed",
        "deletion:read_report",
        # Not a reuse of submission:approve: retraction is the deletion plane
        # reaching outward (B-CARE-3g), and folding the two together would
        # hand repository-retraction to every future preset that gains
        # submission approval for submission reasons.
        "submission:retract",
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
        # M2-DROP-PRE slice 2. _require_lab_tie admitted any lab member, and
        # the report writes nothing — see lab_member_ro.
        "deletion:read_report",
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
        # M2-DROP-PRE slice 2. The legacy _require_lab_tie on
        # GET /samples/{id}/deletion-report admitted ANY lab member,
        # read-only included. The report is lifecycle state plus an audit
        # trail — a governance record, not sample content — so it reads
        # like the other three additions above rather than like a data verb.
        "deletion:read_report",
    ],
}

#: APGAP role name → Instance-scope preset. The twin of MEMBERSHIP_PRESETS
#: for the two roles that are not lab-scoped, and named on the same axis so
#: that reads. Deliberately NOT `INSTANCE_ROLE_PRESETS`: that is one word
#: from INSTANCE_PRESETS, whose key space is disjoint from this one, so
#: `preset in <the wrong constant>` would be a silent False in a
#: validation position rather than an error.
#:
#: These names are Critical Rule 1's sacred enum values and are NOT going
#: away: they name permission_groups rows and are the vocabulary the E-1 UAT
#: matrix drives. What goes away is the boolean pair they used to be stored
#: as. So this map is a bridge between two live vocabularies, not a migration
#: artifact like INSTANCE_PRESET_FLAGS — it outlives M2-DROP.
INSTANCE_PRESET_BY_ROLE: dict[str, str] = {
    "Platform Admin": "instance_administrator",
    "Data Analyst": "surveillance_officer",
}

# APGAP permission_groups.name → preset key. 'Platform Admin' and
# 'Data Analyst' memberships are intentionally absent: those roles are not
# lab-scoped and are issued at Instance scope instead, via
# INSTANCE_PRESET_BY_ROLE above (§10.2).
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
# The optional :sample_id / :requester_id filters are what let the live sync
# (M2-SAMPLE-ACCESS-SYNC) reconcile one row against the SAME definition of
# "who currently has access" that the cutover reseed uses. A second query here
# would be a second answer, free to drift from this one — and the drift would
# be invisible, because both produce grants that permit() reads identically.
# NULL means "no filter"; the casts are required or PostgreSQL cannot infer a
# type for a NULL bind parameter.
_SAMPLE_ACCESS_SQL = text(
    """
    SELECT sag.requester_id AS user_id, s.id AS sample_id, s.lab_id, s.project_id,
           l.organization_id, sag.access_expires_at AS not_after
    FROM sample_access_grants sag
    JOIN samples s ON s.id = sag.sample_id
    JOIN labs l ON l.id = s.lab_id
    WHERE sag.revoked = FALSE
      AND (sag.access_expires_at IS NULL OR sag.access_expires_at > CURRENT_TIMESTAMP)
      AND (CAST(:sample_id AS INTEGER) IS NULL OR s.id = CAST(:sample_id AS INTEGER))
      AND (CAST(:requester_id AS INTEGER) IS NULL
           OR sag.requester_id = CAST(:requester_id AS INTEGER))
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
      AND (CAST(:sample_id AS INTEGER) IS NULL OR s.id = CAST(:sample_id AS INTEGER))
      AND (CAST(:requester_id AS INTEGER) IS NULL
           OR sar.requester_id = CAST(:requester_id AS INTEGER))
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


def _sample_access_rows(
    conn: Connection,
    *,
    sample_id: int | None = None,
    requester_id: int | None = None,
) -> list[dict]:
    """Approved per-sample access → Sample-scoped grants (§5's mapping table).

    Without this, every approved access request stops granting anything at
    cutover: the legacy ladder reads these tables directly and reseed did not
    look at them at all.

    Both filters default to None, which is the unfiltered whole-database read
    ``reseed()`` wants. :func:`sync_sample_access_grants` narrows them.
    """
    rows: list[dict] = []
    params = {"sample_id": sample_id, "requester_id": requester_id}
    for r in conn.execute(_SAMPLE_ACCESS_SQL, params).mappings():
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

    # One query and one precedence rule, shared with instance_preset(): the
    # cutover and the live path must not be able to disagree about what a
    # user carrying both flags holds (see instance_preset).
    flagged = conn.execute(
        text(
            "SELECT id, is_platform_admin, is_data_analyst FROM users "
            "WHERE is_platform_admin = TRUE OR is_data_analyst = TRUE"
        )
    ).fetchall()
    admins: list[int] = []
    analysts: list[int] = []
    for user_id, is_admin, is_analyst in flagged:
        preset = instance_preset(is_platform_admin=bool(is_admin), is_data_analyst=bool(is_analyst))
        if preset is None:
            continue
        (admins if preset == "instance_administrator" else analysts).append(user_id)
        rows.extend(_grant_rows(str(user_id), list(PRESET_GRANTS[preset]), INSTANCE_SCOPE))

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


_DELETE_INSTANCE_GRANTS = text(
    """
    DELETE FROM authz_capability_grants
     WHERE principal_id = :principal_id
       AND scope_ref = :scope_ref
       AND source = :source
    """
)


def instance_preset(*, is_platform_admin: bool, is_data_analyst: bool) -> str | None:
    """Which Instance-scope preset a user's stored flags map to, or None.

    The precedence is not cosmetic: :func:`reseed` reads analysts as
    ``is_data_analyst AND NOT is_platform_admin``, so a user carrying both
    flags gets the admin preset and only that. This function exists so the
    cutover path and the live path cannot answer that differently — a
    principal's grants must not depend on whether a PATCH or a reseed wrote
    them last.
    """
    if is_platform_admin:
        return "instance_administrator"
    if is_data_analyst:
        return "surveillance_officer"
    return None


#: Instance-scope preset -> the legacy flag pair that maps back to it.
#:
#: The forward map (:func:`instance_preset`) is many-to-one — a user carrying
#: BOTH flags resolves to the admin preset — so the inverse is a choice of
#: canonical representative rather than a true inverse. Written once and used
#: in both directions so the two cannot drift; round-tripped in
#: ``tests/test_role_assignment_grants.py``.
#:
#: M2-DROP deletes this: once the columns are gone the preset name is the only
#: representation and nothing needs translating.
INSTANCE_PRESET_FLAGS: dict[str, tuple[bool, bool]] = {
    "instance_administrator": (True, False),
    "surveillance_officer": (False, True),
}

#: The presets this deployment may issue at INSTANCE scope.
#:
#: Deliberately a subset of PRESET_GRANTS. The lab presets are real presets
#: issued through membership (M2-B5), where the scope comes from the lab being
#: joined; issuing one at the instance root would hand out lab_lead's
#: deletion:approve and sample:read_unscrubbed over every sample on the
#: deployment. This constant is what makes that unrepresentable rather than
#: merely unreachable.
#:
#: Derived rather than written out beside the map above and checked with an
#: assert: two literals that must agree can disagree, and a module-level
#: assert is stripped by ``python -O`` — absent exactly where a mismatch would
#: matter most. M2-DROP removes the map; inline this as a literal frozenset in
#: the same commit, and forgetting fails at import rather than at runtime.
INSTANCE_PRESETS: frozenset[str] = frozenset(INSTANCE_PRESET_FLAGS)


def sync_instance_preset(conn: Connection, *, user_id: int, preset: str | None) -> int:
    """Make one user's Instance-scope grants match ``preset``.

    ``preset=None`` removes them — the user holds no Instance-scope role.

    The only door onto Instance-scope grants. A flag-shaped twin
    (``sync_instance_grants``) existed while dev-login still spoke in
    booleans; M2-DROP-PRE slice 8 ended that and took the function with it,
    rather than leaving a callerless one to be read as live API.
    Delete-then-insert and ``source = 'reseed'``-scoped
    for the reasons given on the membership twin: the point is that the row
    and the grants agree afterwards, and a per-sample ``source = 'direct'``
    grant on the same principal must survive untouched.

    Returns the number of grants issued.
    """
    # INSTANCE_PRESETS, not PRESET_GRANTS: a lab preset is a valid preset and
    # an invalid thing to issue here. See the constant for what that would
    # hand out.
    if preset is not None and preset not in INSTANCE_PRESETS:
        raise ValueError(f"{preset!r} is not an Instance-scope preset")
    conn.execute(
        _DELETE_INSTANCE_GRANTS,
        {
            "principal_id": str(user_id),
            "scope_ref": INSTANCE_SCOPE,
            "source": GRANT_SOURCE,
        },
    )
    if preset is None:
        return 0
    rows = _grant_rows(str(user_id), list(PRESET_GRANTS[preset]), INSTANCE_SCOPE)
    for row in rows:
        conn.execute(_INSERT_GRANT, row)
    return len(rows)


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


# ── Live per-sample access → grants (M2-SAMPLE-ACCESS-SYNC) ──────────────
#
# The membership twin above, for the other thing that conveys access. Approving
# a request wrote `sample_access_grants` and nothing else, so between M2-B2
# (when the detail route started deciding on grants) and this function, every
# approved requester was denied: no policy reads the request tables and the
# only translation was reseed(), at migration time. It failed CLOSED, which is
# why it survived — the tests that would have caught it were asserting through
# the legacy helper, which read the tables directly.

_DELETE_SAMPLE_ACCESS_GRANTS = text(
    """
    DELETE FROM authz_capability_grants
     WHERE scope_ref = :scope_ref
       AND source = :source
       AND (CAST(:principal_id AS TEXT) IS NULL OR principal_id = CAST(:principal_id AS TEXT))
    """
)

_SAMPLE_SCOPE_SQL = text(
    """
    SELECT s.id, s.lab_id, s.project_id, l.organization_id
    FROM samples s JOIN labs l ON l.id = s.lab_id
    WHERE s.id = :sid
    """
)


def sample_scope(conn: Connection, sample_id: int) -> str | None:
    """Canonical Sample path, or None if the sample is gone.

    None rather than a raise: the deletion lifecycle syncs grants for samples
    it is in the middle of removing, and a vacuumed sample legitimately has no
    scope left to write grants at.
    """
    rows = conn.execute(_SAMPLE_SCOPE_SQL, {"sid": sample_id}).mappings().all()
    if not rows:
        return None
    r = rows[0]
    return scope_uri(
        org=r["organization_id"], lab=r["lab_id"], project=r["project_id"], sample=r["id"]
    )


def sync_sample_access_grants(
    conn: Connection | None, *, sample_id: int, requester_id: int | None = None
) -> int:
    """Make per-sample access grants match the access tables for one sample.

    ``requester_id=None`` reconciles every principal holding access to the
    sample — what the deletion lifecycle needs, since it revokes and restores
    in bulk. Passing one narrows it to that requester.

    State-reconciling rather than event-driven, and deliberately so: callers
    do not have to know whether they just granted, revoked, expired or
    restored. They say "this sample's access changed" and the grants are made
    to agree. Delete-then-insert for the same reason
    :func:`sync_membership_grants` uses it — a diff would have to reason about
    which capabilities survive the transition, and getting that wrong on the
    authorization path fails open.

    Scoped by ``source = 'direct'`` so it cannot disturb the ``'reseed'``
    membership grants that sit at the same principal.

    ``conn=None`` opens an auto-committed internal transaction, matching
    ``execute_write``'s documented convention — ``approve_deletion`` and the
    rest of the deletion lifecycle accept a None connection, and a sync that
    was stricter than the code calling it would turn a supported call shape
    into an AttributeError.

    Returns the number of grants issued.
    """
    if conn is None:
        from backend.database import _get_engine  # noqa: PLC0415 — migrations
        # import this module; keep the database import off that path.

        engine, _ = _get_engine()
        with engine.begin() as owned:
            return sync_sample_access_grants(owned, sample_id=sample_id, requester_id=requester_id)

    scope = sample_scope(conn, sample_id)
    if scope is None:
        logger.info(
            "sample access sync: sample %s no longer exists; no grants to reconcile",
            sample_id,
        )
        return 0

    conn.execute(
        _DELETE_SAMPLE_ACCESS_GRANTS,
        {
            "scope_ref": scope,
            "source": DIRECT_SOURCE,
            "principal_id": str(requester_id) if requester_id is not None else None,
        },
    )
    rows = _sample_access_rows(conn, sample_id=sample_id, requester_id=requester_id)
    for row in rows:
        conn.execute(_INSERT_GRANT, row)
    return len(rows)


# ── Sharing agreements → peer grants (M4-A) ──────────────────────────────
#
# The third sync, and the same shape as the two above: an operator-facing
# source table with its own lifecycle, projected into authz_capability_grants
# so permit() keeps having exactly one place to look. §7.3's agreement is
# "scoped, conditional capability grants to a specific peer-instance
# principal" — which is the grant row, so this is a projection rather than a
# translation.
#
# Dark at M4-A: nothing calls this on a request path. M4-B wires L1 federated
# visibility to load a PEER_INSTANCE principal, at which point these grants
# start deciding.

AGREEMENT_SOURCE = "agreement"

_DELETE_AGREEMENT_GRANTS = text(
    """
    DELETE FROM authz_capability_grants
     WHERE principal_id = :principal_id
       AND source = :source
    """
)

_AGREEMENT_GRANT_SQL = text(
    """
    SELECT sag.capability, sag.scope_ref, sag.conditions, sag.not_after
    FROM sharing_agreement_grants sag
    JOIN sharing_agreements a ON a.id = sag.agreement_id
    WHERE a.peer_instance_id = :peer AND a.active
    """
)

_INSERT_AGREEMENT_GRANT = text(
    """
    INSERT INTO authz_capability_grants
        (principal_id, capability, scope_ref, source, conditions, not_after)
    VALUES (:principal_id, :capability, :scope_ref, :source, :conditions, :not_after)
    ON CONFLICT DO NOTHING
    """
)


def sync_agreement_grants(conn: Connection, *, peer_instance_id: str) -> int:
    """Make one peer's agreement grants match its active agreements.

    Reconciles the whole peer, not one agreement: a peer may hold several, and
    the question the decision path asks is "what does this peer hold" — which
    no single agreement can answer. Deactivating one agreement must withdraw
    exactly its grants and leave the others, and a per-agreement sync would
    have to diff across siblings to get that right.

    Delete-then-insert scoped by ``source='agreement'``, for the same reason
    :func:`sync_membership_grants` does it: replacing outright is obviously
    correct where a diff has to reason about which capabilities survive a
    transition, and the source scoping keeps it off grants issued by any other
    path to the same principal.

    Returns the number of grants issued.
    """
    conn.execute(
        _DELETE_AGREEMENT_GRANTS,
        {"principal_id": str(peer_instance_id), "source": AGREEMENT_SOURCE},
    )
    rows = conn.execute(_AGREEMENT_GRANT_SQL, {"peer": peer_instance_id}).mappings().all()
    issued = 0
    for r in rows:
        conn.execute(
            _INSERT_AGREEMENT_GRANT,
            {
                "principal_id": str(peer_instance_id),
                "capability": r["capability"],
                "scope_ref": r["scope_ref"],
                "source": AGREEMENT_SOURCE,
                # json.dumps rather than the dict: the column is JSONB and the
                # driver will not adapt a bare dict on a text() insert.
                "conditions": json.dumps(r["conditions"] or {}),
                "not_after": r["not_after"],
            },
        )
        issued += 1
    logger.info(
        "agreement sync: peer %s now holds %d agreement-sourced grants",
        peer_instance_id,
        issued,
    )
    return issued


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
