"""Principal loading for route guards (access_model.md §2.1, §5).

``permit()`` is pure — it takes the grants it needs rather than fetching them
(§5.2 implementation note). This module is the fetch half: one query turning
``authz_capability_grants`` rows into a :class:`Principal`, plus the scope
lookup a route needs to name the resource it is acting on.

Kept out of ``auth/guards.py`` so the decision inputs stay testable without a
FastAPI request, and out of ``engine.py`` so the engine keeps having no I/O.
"""

from datetime import UTC, datetime
from typing import Any

from backend.authz.engine import CapabilityGrant, Principal, PrincipalKind, Resource
from backend.authz.scope import scope_uri
from backend.database import execute_query

_GRANTS_SQL = (
    "SELECT capability, scope_ref, conditions, source, not_after "
    "FROM authz_capability_grants WHERE principal_id = :pid"
)

_LAB_ORG_SQL = "SELECT organization_id FROM labs WHERE id = :lid"

_PROJECT_LINEAGE_SQL = (
    "SELECT l.organization_id, p.lab_id "
    "FROM projects p JOIN labs l ON l.id = p.lab_id WHERE p.id = :pid"
)

# The three attribute columns are selected alongside the lineage because the
# attribute-policies (policy.LADDER_POLICIES) read them on every sample-scoped
# decision. Fetching them here keeps the guard at one query: a second round
# trip per request buys nothing, and a guard that fetched the scope but not the
# attributes would silently evaluate every policy against a missing value —
# which reads as DENY, quietly removing the PUBLIC, surveillance and ownership
# rungs rather than failing loudly.
_SAMPLE_LINEAGE_SQL = (
    "SELECT l.organization_id, s.lab_id, s.project_id, "
    "s.sharing_level, s.surveillance_relevant, s.owner_id, "
    "s.deletion_status, s.deletion_requested_by_user_id "
    "FROM samples s JOIN labs l ON l.id = s.lab_id WHERE s.id = :sid"
)

# Attribute names the policies read -> the sample column carrying each. Also
# the mapping visibility._attr_sql needs for the SQL half (M2-B7), kept here so
# the two halves cannot name different columns.
SAMPLE_ATTRIBUTE_COLUMNS: dict[str, str] = {
    "sharing_level": "s.sharing_level",
    "surveillance_relevant": "s.surveillance_relevant",
    "owner_id": "s.owner_id",
    # M3. Read by deletion.separation_of_duties. A DENY policy that reads an
    # attribute the resource does not carry is not inert — the attribute comes
    # back None and the predicate compares against None, so the policy fires
    # or not for a reason unrelated to the row. Every attribute a DENY reads
    # must be loaded here, or the DENY is deciding on absence.
    "deletion_status": "s.deletion_status",
    "deletion_requested_by_user_id": "s.deletion_requested_by_user_id",
}


def load_principal(
    user_id: int | str,
    *,
    kind: PrincipalKind = PrincipalKind.HUMAN,
    conn: Any = None,
) -> Principal:
    """Build the principal's full grant set in one query.

    Every grant is loaded, not just those matching the capability under test:
    ``permit()`` filters, and a guard that pre-filtered would have to know the
    engine's matching rules — the duplication §2.1 warns about.
    """
    rows = execute_query(_GRANTS_SQL, {"pid": str(user_id)}, conn=conn)
    return Principal(
        kind=kind,
        id=str(user_id),
        on_behalf_of=None,
        grants=[
            CapabilityGrant(
                capability=r["capability"],
                scope_ref=r["scope_ref"],
                conditions=r["conditions"] or {},
                source=r["source"] or "",
                not_after=r["not_after"],
            )
            for r in rows
        ],
    )


# The reverse of _GRANTS_SQL: not "what does this principal hold" but "who
# holds this". The containment test is _scope_contains transcribed to SQL and
# runs the same direction — the GRANT scope must contain the RESOURCE scope,
# so `:scope LIKE scope_ref || '/%'` and never the other way round. The
# rstrip mirrors the Python: a scope_ref stored with a trailing slash would
# otherwise build a pattern with a doubled separator matching nothing.
#
# The join to `users` is load-bearing rather than decorative: peer principals
# share this table with an id that is a federated_instances UUID, and a caller
# asking for people gets only rows that are people.
_CAPABILITY_HOLDERS_SQL = (
    "SELECT DISTINCT u.id FROM authz_capability_grants g "
    "JOIN users u ON CAST(u.id AS TEXT) = g.principal_id "
    "WHERE g.capability = :cap "
    "AND u.is_active = TRUE "
    "AND g.conditions = CAST('{}' AS JSONB) "
    "AND (g.not_after IS NULL OR g.not_after > :now) "
    "AND (g.scope_ref = :scope OR :scope LIKE RTRIM(g.scope_ref, '/') || '/%') "
    "ORDER BY u.id"
)


def capability_holders(capability: str, scope: str, *, conn: Any = None) -> list[int]:
    """Active users whose grants cover ``scope`` for ``capability``.

    The reverse lookup, for background work that has to reach the people
    responsible for something — B-CARE-4's non-compliant-peer alert is the
    first caller, replacing a ``users.is_platform_admin`` SELECT.

    **This is not a decision function.** It answers "who would plausibly be
    permitted", which is the right question for addressing a notification and
    the wrong one for allowing an action: it sees grants only, so it is blind
    to the DENY policies that ``permit()`` applies per resource, and a DENY is
    exactly what deny-wins says must be consulted before anyone is allowed
    anything. Authorizing off this list would reintroduce the second decision
    point §2.1 exists to prevent. Route guards call ``permit()``.

    Conditional grants are excluded rather than assumed satisfied. A condition
    is a fact about a request (§5), and a scheduled job has no request to
    check it against; the engine's own rule for an input it cannot evaluate is
    to refuse — ``Context.now`` unset costs a time-bounded grant its effect
    rather than granting it unbounded. Refusing here can only shorten a
    notification list, never widen access.
    """
    rows = execute_query(
        _CAPABILITY_HOLDERS_SQL,
        {"cap": capability, "scope": scope, "now": datetime.now(UTC)},
        conn=conn,
    )
    return [r["id"] for r in rows]


def load_peer_principal(peer_instance_id: str, *, conn: Any = None) -> Principal:
    """A federated peer as the engine sees it (§2.1, §7.3).

    Thin on purpose. ``load_principal`` was already kind-agnostic — it reads
    ``authz_capability_grants`` by principal id and takes the kind as an
    argument — so a peer needs no separate loading path, and giving it one
    would be the second decision point §2.1 exists to avoid. This exists to be
    findable: a reader looking for "how does a peer get its grants" should not
    have to know that the answer is the human loader with a different enum.

    The id is the ``federated_instances.id`` UUID that
    ``authenticate_federation_peer`` resolves a key to, stringified — the same
    value ``sync_agreement_grants`` writes as ``principal_id``.

    Default-deny falls out (§5.1, §7.3): a peer with no active agreement loads
    with an empty grant list, so it can authenticate and do nothing.
    """
    return load_principal(peer_instance_id, kind=PrincipalKind.PEER_INSTANCE, conn=conn)


def lab_resource_scope(lab_id: int, *, conn: Any = None) -> str:
    """Canonical scope URI for a lab, resolving its org (§3.1.1).

    The org segment is not decoration: a lab path that skipped it would not be
    contained by an org-scoped grant, so an org-wide grant would silently stop
    working. Raises ``ValueError`` for an unknown lab rather than inventing a
    scope — a scope naming a lab that does not exist would be contained by the
    instance grant and quietly authorize an admin against nothing.
    """
    rows = execute_query(_LAB_ORG_SQL, {"lid": lab_id}, conn=conn)
    if not rows:
        raise ValueError(f"unknown lab_id {lab_id!r} — cannot build a resource scope")
    return scope_uri(org=rows[0]["organization_id"], lab=lab_id)


def project_resource_scope(project_id: int, *, conn: Any = None) -> str:
    """Canonical scope URI for a project, resolving its lab and org (§3.1.1).

    The pipeline plane decides at Project scope: a run belongs to a project,
    and §4.2's compute verbs are scoped there so a cryptWWDB service principal
    can hold ``pipeline:write_results`` on one project and nothing else (§9.4).

    Naming the project rather than approximating it by its lab is what makes
    that possible — a lab-scoped check would let any grant on the lab satisfy
    a per-project one. Containment still runs the other way: a lab member's
    ``…/lab/7`` grant contains ``…/lab/7/project/12``, so scoping down here
    takes nothing away from them.

    Raises ``ValueError`` for an unknown project; the guard turns that into
    the same answer a denied project gets.
    """
    rows = execute_query(_PROJECT_LINEAGE_SQL, {"pid": project_id}, conn=conn)
    if not rows:
        raise ValueError(f"unknown project id {project_id!r} — cannot build a resource scope")
    return scope_uri(org=rows[0]["organization_id"], lab=rows[0]["lab_id"], project=project_id)


def sample_resource(sample_id: int, *, conn: Any = None) -> Resource:
    """The sample as the engine sees it: its scope plus the policy attributes.

    A sample must be named at Sample scope, not approximated by its lab: a
    grant issued AT sample scope — the per-sample access mechanism §3.1 lists
    for that level, and what an approved access request becomes — does not
    contain the lab, so checking a lab scope instead would make those grants
    invisible while appearing to work for lab members.

    Raises ``ValueError`` for an unknown sample; the guard turns that into the
    same answer a denied sample gets.
    """
    rows = execute_query(_SAMPLE_LINEAGE_SQL, {"sid": sample_id}, conn=conn)
    if not rows:
        raise ValueError(f"unknown sample id {sample_id!r} — cannot build a resource scope")
    row = rows[0]
    return Resource(
        scope=scope_uri(
            org=row["organization_id"],
            lab=row["lab_id"],
            project=row["project_id"],
            sample=sample_id,
        ),
        attributes={attr: row[attr] for attr in SAMPLE_ATTRIBUTE_COLUMNS},
    )


def sample_resource_scope(sample_id: int, *, conn: Any = None) -> str:
    """Canonical scope URI for a sample (§3.1.1). See :func:`sample_resource`."""
    return sample_resource(sample_id, conn=conn).scope


# ── SERVICE principals (M2-B6, access_model.md §4.6, §8.4, §9.4) ─────────

PIPELINE_RUN_CAPABILITIES: list[str] = ["pipeline:write_results"]
"""What a running pipeline may do, and — by omission — what it may not.

The omission is the point. §8.4's Data Source Lab preset spells it out:
"EXPLICITLY NOT GRANTED: sample:read_detail, sample:read ... The absence is
the security property, not an oversight." A principal that can write results
for a run and cannot read the samples that run consumed is the
"computes without seeing" guarantee (§4.6) expressed as a capability set
rather than as a promise about how tokens happen to be minted.

Adding a read verb here would silently undo that, which is why the negative
is asserted by a test rather than left to review.
"""


def pipeline_run_principal(run: dict[str, Any]) -> Principal:
    """The SERVICE principal for a pipeline run's own callbacks.

    Not loaded from ``authz_capability_grants``: this principal has no rows
    and should not. It exists for the duration of one run, its credential is
    the per-run ``X-Pipeline-Token``, and its authority is bounded by the
    project that run belongs to — so the grant is constructed from the run
    rather than stored, exactly as a sample's scope is derived rather than
    stored (ADR 0015).

    **What this does and does not buy, honestly.** The positive check cannot
    fail today: the scope is built from the same run the token authenticated
    against, so ``permit()`` always ALLOWs. The value is not a new failure
    mode, it is that the principal now *exists* with an enumerated capability
    set and that ``permit()`` is the chokepoint. When M4/M5 introduce a
    ``data_source_lab`` peer carrying the §8.4 preset, the route asks the same
    question of a different principal and the answer differs — without the
    route changing. Today the token collapses authentication and
    authorization; this separates them so the collapse is not load-bearing.

    Raises ``ValueError`` if the run names no project — ``pipeline_runs
    .project_id`` is NOT NULL, so that means a caller passed a row it did not
    fetch the column for, and inventing an instance-root scope there would
    hand a pipeline callback authority over the whole deployment.
    """
    project_id = run.get("project_id")
    if project_id is None:
        raise ValueError(
            f"run {run.get('run_id')!r} has no project_id — cannot scope a SERVICE principal"
        )
    return Principal(
        kind=PrincipalKind.SERVICE,
        id=f"pipeline-run:{run.get('run_id')}",
        on_behalf_of=None,
        grants=[
            CapabilityGrant(
                capability=capability,
                scope_ref=project_resource_scope(project_id),
                source="pipeline_token",
            )
            for capability in PIPELINE_RUN_CAPABILITIES
        ],
    )
