"""Access control helpers for samples.

Two levels of access are distinguished:

* ``can_see_sample`` — list-level visibility. Adds ``DISCOVERABLE`` to the
  access matrix so discoverable samples show up in search results.
* ``can_access_sample`` — detail-level access. ``DISCOVERABLE`` alone is
  NOT sufficient; the row is visible in lists, but detail requires an
  approved access request.

Both helpers reuse the same authorisation ladder and short-circuit on the
first matching rule.
"""

from enum import Enum

from backend.database import execute_query


class PermissionGroups(str, Enum):
    """APGAP-identical role names. DO NOT rename."""

    PLATFORM_ADMIN = "Platform Admin"
    LAB_DIRECTOR = "Lab Director"
    LAB_COLLABORATOR = "Lab Collaborator"
    LAB_READER = "Lab Reader"
    BIOINFORMATICS_USER = "Bioinformatics User"
    DATA_ANALYST = "Data Analyst"


def _is_lab_member(user_id: int, lab_id: int, conn) -> bool:
    rows = execute_query(
        "SELECT 1 FROM lab_membership WHERE user_id = :uid AND lab_id = :lid LIMIT 1",
        {"uid": user_id, "lid": lab_id},
        conn=conn,
    )
    return bool(rows)


def _is_project_member(user_id: int, project_id: int, conn) -> bool:
    rows = execute_query(
        "SELECT 1 FROM project_membership WHERE user_id = :uid AND project_id = :pid LIMIT 1",
        {"uid": user_id, "pid": project_id},
        conn=conn,
    )
    return bool(rows)


def _has_approved_access_request(user_id: int, sample_id: int, conn) -> bool:
    """True iff the user holds an active access path to this sample.

    Two paths are honoured:

    * ``sample_access_grants`` row that is not revoked and either has no
      ``access_expires_at`` or whose expiry is in the future. This is the
      durable artefact created by the approve endpoint and the canonical
      source of truth for time-bounded access.
    * ``sample_access_requests`` with ``status = 'APPROVED'``. Kept as a
      fallback so any pre-grants-table data (and existing test fixtures
      that insert directly into the requests table) continues to grant
      access without behaviour change. The expiry job transitions
      requests to ``EXPIRED`` when their grant lapses, so an APPROVED
      request still in the table is necessarily still active.
    """
    rows = execute_query(
        """
        SELECT 1 FROM sample_access_grants
        WHERE requester_id = :uid AND sample_id = :sid
          AND revoked = FALSE
          AND (access_expires_at IS NULL OR access_expires_at > NOW())
        UNION ALL
        SELECT 1 FROM sample_access_requests
        WHERE requester_id = :uid AND sample_id = :sid AND status = 'APPROVED'
        LIMIT 1
        """,
        {"uid": user_id, "sid": sample_id},
        conn=conn,
    )
    return bool(rows)


def _base_access(user: dict, sample: dict, conn) -> bool:
    """Ladder shared by can_access_sample and can_see_sample."""
    if user.get("is_platform_admin"):
        return True
    if sample.get("owner_id") == user.get("id"):
        return True
    if _is_lab_member(user["id"], sample["lab_id"], conn):
        return True
    if _is_project_member(user["id"], sample["project_id"], conn):
        return True
    if sample.get("sharing_level") == "PUBLIC":
        return True
    if user.get("is_data_analyst") and sample.get("surveillance_relevant"):
        return True
    return _has_approved_access_request(user["id"], sample["id"], conn)


def can_access_sample(user: dict, sample: dict, conn=None) -> bool:
    """True iff user may read full detail of sample.

    DISCOVERABLE alone is NOT sufficient — detail requires an approved
    request or one of the stronger ties (ownership, lab/project, PUBLIC,
    ADHS oversight for surveillance-relevant samples).
    """
    return _base_access(user, sample, conn)


def can_see_sample(user: dict, sample: dict, conn=None) -> bool:
    """True iff user may see sample in a list.

    Superset of can_access_sample: also allows DISCOVERABLE samples.
    """
    if sample.get("sharing_level") == "DISCOVERABLE":
        return True
    return _base_access(user, sample, conn)


def visibility_sql_clause(user: dict) -> tuple[str, dict]:
    """Return a SQL fragment + params that matches rows this user can SEE.

    Used by the samples list endpoint to filter at the database tier
    rather than iterating rows in Python. Covers the same ladder as
    ``can_see_sample`` (including DISCOVERABLE).

    Platform Admins get a trivial TRUE clause.
    """
    if user.get("is_platform_admin"):
        return "TRUE", {}

    params: dict = {"uid": user["id"]}
    clauses = [
        "s.owner_id = :uid",
        "s.sharing_level IN ('PUBLIC', 'DISCOVERABLE')",
        "EXISTS (SELECT 1 FROM lab_membership lm WHERE lm.user_id = :uid AND lm.lab_id = s.lab_id)",
        "EXISTS (SELECT 1 FROM project_membership pm "
        "WHERE pm.user_id = :uid AND pm.project_id = s.project_id)",
        "EXISTS (SELECT 1 FROM sample_access_requests sar "
        "WHERE sar.requester_id = :uid AND sar.sample_id = s.id "
        "AND sar.status = 'APPROVED')",
        "EXISTS (SELECT 1 FROM sample_access_grants sag "
        "WHERE sag.requester_id = :uid AND sag.sample_id = s.id "
        "AND sag.revoked = FALSE "
        "AND (sag.access_expires_at IS NULL OR sag.access_expires_at > NOW()))",
    ]
    if user.get("is_data_analyst"):
        clauses.append("s.surveillance_relevant = TRUE")
    return "(" + " OR ".join(clauses) + ")", params
