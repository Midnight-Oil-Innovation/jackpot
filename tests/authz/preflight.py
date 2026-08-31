"""M2 pre-cutover verification harness (access_model.md §11.3).

Shared by tests/authz/test_cutover_preflight.py now and by the M2
cutover's tests/authz/test_cutover.py later. Everything here is dark:
it seeds namespaced legacy-model data into the shared testcontainer
PostgreSQL, runs ``reseed()`` to obtain the new-model grants, and
compares legacy guard/visibility decisions against ``permit()`` /
``authz.visibility.visibility_sql_clause`` cell by cell.

Divergences between the two models are not bugs in this harness —
surfacing them BEFORE the irreversible cutover is its purpose. Every
known divergence is registered in ``EXPECTED_DIVERGENCES`` with a
rationale destined for the M2 cutover PR body; the consuming tests
assert both zero UNEXPECTED cells and that every registry key fires
(a registry entry that stops matching means behavior moved and the
documentation is stale).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException

from backend.auth.guards import require_capability
from backend.authz import (
    CapabilityGrant,
    Context,
    Decision,
    Principal,
    PrincipalKind,
    Resource,
    permit,
)
from backend.database import execute_query, execute_write

EMAIL_PREFIX = "preflight-p"
SAMPLE_PREFIX = "PREFLT-"
ORG_NAME = "Preflight Org"
LAB_A_NAME = "Preflight Lab A"
LAB_B_NAME = "Preflight Lab B"
PROJECT_NAME = "Preflight Project A1"

INSTANCE_SCOPE = "instance://self"

# DDL verbatim from backend/alembic/versions/20260829_reseed_roles_to_grants.py —
# the uniqueness arbiter reseed()'s ON CONFLICT DO NOTHING requires. The live
# chain (a7c3e91d54b0) does NOT create it; without it a second reseed silently
# duplicates every grant. Creating it here mirrors cutover conditions and pins
# the migration's create-index-before-reseed ordering as load-bearing.
UNIQUE_INDEX_DDL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS "
    "authz_capability_grants_principal_capability_scope_uniq "
    "ON authz_capability_grants (principal_id, capability, scope_ref)"
)
UNIQUE_INDEX_DROP = "DROP INDEX IF EXISTS authz_capability_grants_principal_capability_scope_uniq"


def lab_scope(lab_id: int) -> str:
    return f"lab://{lab_id}"


# ──────────────────────────────────────────────────────────────────────────
# Personas
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class Persona:
    key: str  # "P1".."P12"
    email: str
    is_platform_admin: bool = False
    is_data_analyst: bool = False
    # (lab_key, permission_group_name, is_lab_director_flag)
    memberships: tuple[tuple[str, str, bool], ...] = ()
    project_member: bool = False  # membership in the lab-A project

    user_id: int = 0  # filled by seed


def _personas() -> list[Persona]:
    e = lambda n: f"{EMAIL_PREFIX}{n}@example.org"  # noqa: E731
    return [
        Persona("P1", e(1), is_platform_admin=True),
        Persona("P2", e(2), is_data_analyst=True),
        Persona("P3", e(3), is_platform_admin=True, is_data_analyst=True),
        Persona("P4", e(4), memberships=(("A", "Lab Director", True),)),
        Persona("P5", e(5), memberships=(("A", "Lab Collaborator", False),)),
        Persona("P6", e(6), memberships=(("A", "Lab Reader", False),)),
        Persona("P7", e(7), memberships=(("A", "Bioinformatics User", False),)),
        Persona(
            "P8",
            e(8),
            memberships=(("A", "Lab Director", True), ("B", "Lab Reader", False)),
        ),
        # Unmapped group name: 'Data Analyst' exists in permission_groups but
        # reseed.MEMBERSHIP_PRESETS has no entry for it — must skip + warn.
        Persona("P9", e(9), memberships=(("A", "Data Analyst", False),)),
        Persona("P10", e(10)),
        # Flag/group disagreement trap: Collaborator group name but the
        # is_lab_director flag set. Legacy _guard trusts the flag; reseed
        # trusts the group name.
        Persona("P11", e(11), memberships=(("A", "Lab Collaborator", True),)),
        Persona("P12", e(12), project_member=True),
    ]


@dataclass
class SeededWorld:
    personas: dict[str, Persona]
    lab_a: int
    lab_b: int
    org_id: int
    project_id: int
    sample_ids: dict[str, int]  # sample_key -> samples.id


# ──────────────────────────────────────────────────────────────────────────
# Seeding / teardown (namespaced; the container DB is shared suite-wide)
# ──────────────────────────────────────────────────────────────────────────


def seed_world() -> SeededWorld:
    org = execute_write(
        "INSERT INTO organizations (display_name) VALUES (:n) RETURNING id",
        {"n": ORG_NAME},
    )[0]["id"]
    lab_a = execute_write(
        "INSERT INTO labs (organization_id, display_name) VALUES (:o, :n) RETURNING id",
        {"o": org, "n": LAB_A_NAME},
    )[0]["id"]
    lab_b = execute_write(
        "INSERT INTO labs (organization_id, display_name) VALUES (:o, :n) RETURNING id",
        {"o": org, "n": LAB_B_NAME},
    )[0]["id"]
    lab_ids = {"A": lab_a, "B": lab_b}

    personas = {p.key: p for p in _personas()}
    for p in personas.values():
        p.user_id = execute_write(
            "INSERT INTO users (email, name, organization_id, is_platform_admin, "
            "is_data_analyst, is_active) VALUES (:e, :e, :o, :pa, :da, TRUE) "
            "RETURNING id",
            {"e": p.email, "o": org, "pa": p.is_platform_admin, "da": p.is_data_analyst},
        )[0]["id"]
        for lab_key, group_name, director_flag in p.memberships:
            execute_write(
                "INSERT INTO lab_membership "
                "(user_id, lab_id, permission_group_id, is_lab_director) "
                "SELECT :u, :l, pg.id, :d FROM permission_groups pg "
                "WHERE pg.name = :g",
                {"u": p.user_id, "l": lab_ids[lab_key], "d": director_flag, "g": group_name},
            )

    project_id = execute_write(
        "INSERT INTO projects (lab_id, display_name) VALUES (:l, :n) RETURNING id",
        {"l": lab_a, "n": PROJECT_NAME},
    )[0]["id"]
    p12 = personas["P12"]
    execute_write(
        "INSERT INTO project_membership (user_id, project_id, permission_group_id) "
        "SELECT :u, :p, pg.id FROM permission_groups pg WHERE pg.name = 'Lab Reader'",
        {"u": p12.user_id, "p": project_id},
    )

    # Samples: one row per legacy _base_access / visibility-clause rung.
    owner_default = personas["P4"].user_id  # lab-A director owns the neutral rows
    p10 = personas["P10"].user_id

    def sample(key: str, lab: int, *, sharing="PRIVATE", surveillance=False, owner=None):
        return key, execute_write(
            """
            INSERT INTO samples (
                sample_id, lab_id, project_id, owner_id, source_type, organism_name,
                type_of_experiment, library_preparation_method, sequencing_protocol,
                sequencing_platform, sequencing_lab, date_collected, date_sequenced,
                collection_facility, collection_location_country, sharing_level,
                fastq_r1_uri, surveillance_relevant
            ) VALUES (
                :sid, :lab, :proj, :owner, 'Human',
                'Severe acute respiratory syndrome coronavirus 2',
                'WGS', 'ARTIC', 'https://www.protocols.io/view/artic-v4-1',
                'Illumina', 'Example Sequencing Lab', '2026-01-15', '2026-01-17',
                'Example Hospital', 'United States', :share,
                'gs://preflight/R1.fastq.gz', :surv
            ) RETURNING id
            """,
            {
                "sid": f"{SAMPLE_PREFIX}{key}",
                "lab": lab,
                "proj": project_id,
                "owner": owner or owner_default,
                "share": sharing,
                "surv": surveillance,
            },
        )[0]["id"]

    sample_ids = dict(
        [
            sample("A-PRIV", lab_a),
            sample("B-PRIV", lab_b),
            sample("B-PUB", lab_b, sharing="PUBLIC"),
            sample("B-DISC", lab_b, sharing="DISCOVERABLE"),
            sample("B-SURV", lab_b, surveillance=True),
            sample("B-OWN", lab_b, owner=p10),
            sample("B-REQ", lab_b),
            sample("B-GRANT", lab_b),
        ]
    )

    execute_write(
        "INSERT INTO sample_access_requests (sample_id, requester_id, owner_id, status) "
        "VALUES (:s, :r, :o, 'APPROVED')",
        {"s": sample_ids["B-REQ"], "r": p10, "o": owner_default},
    )
    execute_write(
        "INSERT INTO sample_access_grants (sample_id, requester_id, revoked) "
        "VALUES (:s, :r, FALSE)",
        {"s": sample_ids["B-GRANT"], "r": p10},
    )

    return SeededWorld(
        personas=personas,
        lab_a=lab_a,
        lab_b=lab_b,
        org_id=org,
        project_id=project_id,
        sample_ids=sample_ids,
    )


def teardown_world(world: SeededWorld) -> None:
    ids = [p.user_id for p in world.personas.values()]
    # authz_capability_grants is dark — nothing but reseed writes it; clear all.
    execute_write("DELETE FROM authz_capability_grants", {})
    execute_write(
        "DELETE FROM sample_access_grants WHERE sample_id IN "
        "(SELECT id FROM samples WHERE sample_id LIKE :p)",
        {"p": f"{SAMPLE_PREFIX}%"},
    )
    execute_write(
        "DELETE FROM sample_access_requests WHERE sample_id IN "
        "(SELECT id FROM samples WHERE sample_id LIKE :p)",
        {"p": f"{SAMPLE_PREFIX}%"},
    )
    execute_write("DELETE FROM samples WHERE sample_id LIKE :p", {"p": f"{SAMPLE_PREFIX}%"})
    execute_write("DELETE FROM project_membership WHERE user_id = ANY(:ids)", {"ids": ids})
    execute_write("DELETE FROM projects WHERE display_name = :n", {"n": PROJECT_NAME})
    execute_write("DELETE FROM lab_membership WHERE user_id = ANY(:ids)", {"ids": ids})
    execute_write("DELETE FROM users WHERE email LIKE :p", {"p": f"{EMAIL_PREFIX}%"})
    execute_write(
        "DELETE FROM labs WHERE display_name IN (:a, :b)",
        {"a": LAB_A_NAME, "b": LAB_B_NAME},
    )
    execute_write("DELETE FROM organizations WHERE display_name = :n", {"n": ORG_NAME})
    execute_write(UNIQUE_INDEX_DROP, {})


# ──────────────────────────────────────────────────────────────────────────
# Adapters
# ──────────────────────────────────────────────────────────────────────────


def load_principal(user_id: int) -> Principal:
    """Reseeded grants rows → Principal, the shape M2 guards will build."""
    rows = execute_query(
        "SELECT capability, scope_ref, conditions, source "
        "FROM authz_capability_grants WHERE principal_id = :pid",
        {"pid": str(user_id)},
    )
    grants = [
        CapabilityGrant(
            capability=r["capability"],
            scope_ref=r["scope_ref"],
            conditions=r["conditions"] or {},
            source=r["source"] or "",
        )
        for r in rows
    ]
    return Principal(kind=PrincipalKind.HUMAN, id=str(user_id), on_behalf_of=None, grants=grants)


def user_dict(p: Persona) -> dict:
    """The current_user dict shape guards.require_capability consumes."""
    return {
        "id": p.user_id,
        "email": p.email,
        "is_platform_admin": p.is_platform_admin,
        "is_data_analyst": p.is_data_analyst,
    }


def legacy_guard(p: Persona, capability: str, lab_id: int | None) -> bool:
    try:
        require_capability(capability)(user_dict(p), lab_id=lab_id)
        return True
    except HTTPException:
        return False


def new_guard(principal: Principal, capability: str, scope: str) -> bool:
    # policies=[] (never None — engine raises NotImplementedError pre-M2).
    decision = permit(
        principal, capability, Resource(scope=scope), Context(conditions={}), policies=[]
    )
    return decision is Decision.ALLOW


# ──────────────────────────────────────────────────────────────────────────
# Equivalence matrix
# ──────────────────────────────────────────────────────────────────────────

# Distinct capabilities across the map's require_capability rows plus the
# reseed presets' lab-plane verbs — the comparison vocabulary.
MATRIX_CAPABILITIES = [
    "org:manage",
    "user:manage",
    "whitelist:manage",
    "federation:configure_peer",
    "pipeline:promote",
    "pipeline:run",
    "sample:read",
    "sample:read_detail",
    "sample:create",
    "sample:update",
    "sample:archive",
    "deletion:request",
    "sample:read_surveillance",
]

_MEMBER_LEVEL = {"sample:read", "sample:read_detail"}
_MEMBER_RW_ONLY = {"sample:create", "sample:update", "deletion:request"}


@dataclass
class Cell:
    persona: str
    capability: str
    lab_key: str | None  # "A" / "B" / None (instance)
    scope: str
    legacy: bool
    new: bool

    @property
    def diverged(self) -> bool:
        return self.legacy != self.new


# key -> (predicate(cell, world), rationale). Rationales are lifted verbatim
# into docs/m2_preflight_report.md and, from there, the cutover PR body.
EXPECTED_DIVERGENCES: dict[str, tuple[Callable[[Cell], bool], str]] = {
    "admin-bypass-vs-scoped-grants": (
        lambda c: c.persona in {"P1", "P3"} and c.legacy and not c.new,
        "Legacy platform-admin bypass (guards.py:108) allows every capability "
        "everywhere; reseeded instance_administrator grants are scoped to "
        "instance://self, and _scope_contains is pure URI-prefix, so "
        "instance://self does NOT contain lab://N. Every lab-scoped admin "
        "cell, and every instance cell for a capability outside the §8.2 "
        "admin preset, denies under the new model. RESOLVED by ADR 0015 "
        "(docs/adr/0015-single-rooted-scope-uri.md): every scope becomes a "
        "path under instance://self, so the admin grant prefixes lab scopes "
        "structurally. This class disappears once M2 lands the canonical "
        "serialization; until then the divergence stands and is asserted.",
    ),
    "surveillance-cap-new-only": (
        lambda c: c.persona == "P2"
        and c.capability == "sample:read_surveillance"
        and c.lab_key is None
        and c.new
        and not c.legacy,
        "Data analysts gain an explicit instance-scoped "
        "sample:read_surveillance grant from the surveillance_officer preset; "
        "the legacy guard has no analyst branch at all (analyst rights lived "
        "only in the visibility ladder). New model intentionally allows.",
    ),
    "director-passes-all-lab-caps": (
        lambda c: c.persona in {"P4", "P8"} and c.lab_key == "A" and c.legacy and not c.new,
        "Legacy directorship is all-capabilities-at-lab (guards.py:123 "
        "trusts is_lab_director for ANY non-member-level capability); the "
        "lab_lead preset enumerates 12 capabilities, so out-of-preset verbs "
        "(org:manage, user:manage, whitelist:manage, federation:*, "
        "pipeline:promote, sample:read_surveillance at lab scope) deny under "
        "the new model. Intentional §8.2 narrowing — document per-route in "
        "the cutover PR.",
    ),
    "member-rw-write-caps-new-only": (
        lambda c: c.persona in {"P5", "P7"}
        and c.lab_key == "A"
        and c.new
        and not c.legacy
        and (c.capability in _MEMBER_RW_ONLY or c.capability == "pipeline:run"),
        "Legacy require_capability demands directorship for every "
        "non-member-level capability, so collaborators could not "
        "create/update via a guarded route; the lab_member_rw preset "
        "intentionally grants sample:create/update/deletion:request (and "
        "pipeline:run for Bioinformatics User). New model intentionally "
        "allows — §8.2/§8.5 design.",
    ),
    "flag-group-mismatch": (
        lambda c: c.persona == "P11" and c.lab_key == "A" and c.legacy and not c.new,
        "lab_membership rows where is_lab_director=TRUE but the permission "
        "group says Collaborator: legacy trusts the flag (all caps pass), "
        "reseed trusts the group name (member-RW grants only), so these "
        "users lose director-level access at cutover. Detected at migration "
        "time by reseed's pre-flight guard, not reconciled ahead of it: no "
        "deployment holds real membership rows yet, so a pre-M2 sweep would "
        "pass vacuously. The guard aborts with counts on any operator DB "
        "where the flag and the group disagree.",
    ),
    "project-membership-no-grants": (
        lambda c: c.persona == "P12"
        and c.lab_key == "A"
        and c.capability in _MEMBER_LEVEL
        and c.legacy
        and not c.new,
        "Legacy member-level checks accept project membership via the "
        "project→lab join (guards.py:115-122); reseed reads only "
        "lab_membership, so project-only users lose guarded read access. "
        "Cutover either reseeds project memberships or accepts the "
        "narrowing explicitly; reseed's pre-flight guard reports the count "
        "at migration time so the choice is made against real numbers "
        "rather than assumed to be zero.",
    ),
    "unmapped-group-skipped": (
        lambda c: c.persona == "P9"
        and c.lab_key == "A"
        and c.capability in _MEMBER_LEVEL
        and c.legacy
        and not c.new,
        "Memberships with a permission-group name absent from "
        "MEMBERSHIP_PRESETS ('Data Analyst' as a lab membership) are "
        "skipped with a warning by reseed — those users lose all guarded "
        "access at cutover. Reseed's pre-flight guard counts them before "
        "inserting anything and aborts unless the operator has explicitly "
        "accepted the loss; triage happens at migration time on the DB that "
        "actually has the rows, not ahead of M2 on one that does not.",
    ),
}


def run_matrix(world: SeededWorld) -> tuple[list[Cell], list[Cell], set[str]]:
    """Return (all cells, unexpected divergences, fired registry keys)."""
    principals = {k: load_principal(p.user_id) for k, p in world.personas.items()}
    lab_ids = {"A": world.lab_a, "B": world.lab_b, None: None}

    cells: list[Cell] = []
    for pkey, persona in world.personas.items():
        for cap in MATRIX_CAPABILITIES:
            for lab_key in ("A", "B", None):
                lab_id = lab_ids[lab_key]
                scope = lab_scope(lab_id) if lab_id is not None else INSTANCE_SCOPE
                cells.append(
                    Cell(
                        persona=pkey,
                        capability=cap,
                        lab_key=lab_key,
                        scope=scope,
                        legacy=legacy_guard(persona, cap, lab_id),
                        new=new_guard(principals[pkey], cap, scope),
                    )
                )

    unexpected: list[Cell] = []
    fired: set[str] = set()
    for cell in cells:
        if not cell.diverged:
            continue
        matched = [k for k, (pred, _) in EXPECTED_DIVERGENCES.items() if pred(cell)]
        if matched:
            fired.update(matched)
        else:
            unexpected.append(cell)
    return cells, unexpected, fired


# ──────────────────────────────────────────────────────────────────────────
# Visibility legacy-only classification (test 2c)
# ──────────────────────────────────────────────────────────────────────────


def classify_legacy_only_visibility(persona: Persona, sample_key: str) -> str | None:
    """Attribute a legacy-visible-but-not-new-visible row to a documented
    divergence class. None = unattributable (test fails)."""
    if persona.is_platform_admin:
        return "admin-bypass-vs-scoped-grants"
    if sample_key == "B-OWN" and persona.key == "P10":
        return "reseed-reads-only-lab-membership"  # ownership rung
    if persona.key == "P4" and sample_key != "B-OWN":
        # P4 is the seed's default owner_id, so the legacy ownership rung
        # shows it every lab-B row it owns; same reseed-has-no-ownership
        # class as P10's B-OWN case.
        return "reseed-reads-only-lab-membership"
    if sample_key in {"B-PUB", "B-DISC"}:
        return "reseed-reads-only-lab-membership"  # sharing-level rungs
    if sample_key == "B-SURV" and persona.is_data_analyst:
        return "reseed-reads-only-lab-membership"  # analyst×surveillance rung
    if sample_key in {"B-REQ", "B-GRANT"} and persona.key == "P10":
        return "reseed-reads-only-lab-membership"  # request/grant rungs
    if persona.key == "P12":
        return "project-membership-no-grants"
    if persona.key == "P9":
        return "unmapped-group-skipped"
    if persona.key == "P11":
        return "flag-group-mismatch"
    return None
