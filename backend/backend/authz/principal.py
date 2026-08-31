"""Principal loading for route guards (access_model.md §2.1, §5).

``permit()`` is pure — it takes the grants it needs rather than fetching them
(§5.2 implementation note). This module is the fetch half: one query turning
``authz_capability_grants`` rows into a :class:`Principal`, plus the scope
lookup a route needs to name the resource it is acting on.

Kept out of ``auth/guards.py`` so the decision inputs stay testable without a
FastAPI request, and out of ``engine.py`` so the engine keeps having no I/O.
"""

from typing import Any

from backend.authz.engine import CapabilityGrant, Principal, PrincipalKind
from backend.authz.scope import scope_uri
from backend.database import execute_query

_GRANTS_SQL = (
    "SELECT capability, scope_ref, conditions, source, not_after "
    "FROM authz_capability_grants WHERE principal_id = :pid"
)

_LAB_ORG_SQL = "SELECT organization_id FROM labs WHERE id = :lid"

_SAMPLE_LINEAGE_SQL = (
    "SELECT l.organization_id, s.lab_id, s.project_id "
    "FROM samples s JOIN labs l ON l.id = s.lab_id WHERE s.id = :sid"
)


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


def sample_resource_scope(sample_id: int, *, conn: Any = None) -> str:
    """Canonical scope URI for a sample, resolving its full lineage (§3.1.1).

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
    return scope_uri(
        org=row["organization_id"],
        lab=row["lab_id"],
        project=row["project_id"],
        sample=sample_id,
    )
