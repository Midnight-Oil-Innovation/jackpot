import hmac
import logging
from typing import Any

from fastapi import HTTPException, Request
from jose import jwt

from backend.config import get_settings
from backend.credentials import CredentialError, CredentialNotFoundError, credentials
from backend.database import execute_query

logger = logging.getLogger(__name__)

FEDERATION_KEY_HEADER = "X-JACKPOT-Federation-Key"


def get_current_user(request: Request) -> dict:
    settings = get_settings()
    if settings.env == "local":
        rows = execute_query(
            "SELECT * FROM users WHERE email = :e AND is_active = TRUE LIMIT 1",
            {"e": settings.mock_user_email},
        )
        return (
            rows[0]
            if rows
            else {
                "id": 1,
                "email": settings.mock_user_email,
                "name": "Dev User",
                "is_platform_admin": True,
                "is_data_analyst": False,
                "is_active": True,
                "organization_id": 1,
            }
        )

    token = request.cookies.get("access")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    # Resolve the signing key separately: a credential-backend failure is a
    # 503 (service issue), not a 401 (bad token), and must not leak a raw
    # stack trace to the caller.
    try:
        signing_key = credentials.get("jwt_signing_key")
    except CredentialError as exc:
        logger.error("auth: jwt signing key unavailable: %s", exc)
        raise HTTPException(
            status_code=503, detail="Authentication temporarily unavailable."
        ) from exc
    try:
        payload = jwt.decode(token, signing_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Access token expired.") from exc
    except jwt.JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token.") from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type.")

    rows = execute_query(
        "SELECT id, email, name, is_platform_admin, is_data_analyst, "
        "is_active, organization_id FROM users "
        "WHERE id = :uid AND is_active = TRUE LIMIT 1",
        {"uid": payload["sub"]},
    )
    if not rows:
        raise HTTPException(status_code=401, detail="User not found or inactive.")
    return rows[0]


def get_user_lab_membership(user_id: int, lab_id: int) -> dict | None:
    rows = execute_query(
        "SELECT lm.*, pg.name AS permission_group_name, lm.is_lab_director "
        "FROM lab_membership lm "
        "JOIN permission_groups pg ON pg.id = lm.permission_group_id "
        "WHERE lm.user_id = :uid AND lm.lab_id = :lid LIMIT 1",
        {"uid": user_id, "lid": lab_id},
    )
    return rows[0] if rows else None


# Capabilities whose lab-scoped check accepts any lab or project membership
# (read plane); everything else lab-scoped requires lab directorship.
_MEMBER_LEVEL_CAPABILITIES = frozenset({"sample:read", "sample:read_detail"})


def require_capability(capability: str):
    """Guard factory: returns a callable raising HTTP 403 unless the current
    user may exercise ``capability`` (an access_model.md §4 ``domain:action``
    string, recorded in docs/endpoint_capability_map.md).

    Transitional M2-prerequisite implementation (access_model.md §10.3): the
    capability string at the call site is the single source of truth for what
    each route requires, but enforcement still runs the legacy structural
    checks until M2 wires in the permit() engine:

    - no authenticated principal            -> 403
    - platform admin                        -> pass (Instance-scope grant)
    - ``lab_id`` given, member-level cap    -> lab or project membership
    - ``lab_id`` given, any other cap       -> lab directorship
    - otherwise                             -> 403
    """

    def _guard(current_user: dict | None, lab_id: int | None = None) -> dict:
        if current_user is None:
            raise HTTPException(status_code=403, detail=f"capability '{capability}' required")
        if current_user.get("is_platform_admin"):
            return current_user
        if lab_id is not None:
            membership = get_user_lab_membership(current_user["id"], lab_id)
            if capability in _MEMBER_LEVEL_CAPABILITIES:
                if membership:
                    return current_user
                rows = execute_query(
                    "SELECT 1 FROM project_membership pm "
                    "JOIN projects p ON p.id = pm.project_id "
                    "WHERE pm.user_id = :uid AND p.lab_id = :lid LIMIT 1",
                    {"uid": current_user["id"], "lid": lab_id},
                )
                if rows:
                    return current_user
            elif membership and membership.get("is_lab_director"):
                return current_user
        raise HTTPException(status_code=403, detail=f"capability '{capability}' required")

    return _guard


def authenticate_federation_peer(request: Request, conn: Any = None) -> dict[str, Any] | None:
    # FED-E: validate X-JACKPOT-Federation-Key against every enabled row in
    # federated_instances. The expected key is resolved per-row through the
    # credentials facade (GCP Secret Manager in prod, InMemoryBackend in
    # tests). Comparisons are constant-time. Disabled instances are
    # excluded by the SQL filter so their keys cannot authenticate even if
    # the secret backend still resolves them.
    presented = request.headers.get(FEDERATION_KEY_HEADER)
    if not presented:
        return None

    rows = execute_query(
        "SELECT * FROM federated_instances WHERE federation_enabled = TRUE",
        conn=conn,
    )
    for row in rows:
        secret_name = row.get("api_key_secret_name")
        if not secret_name:
            continue
        try:
            expected = credentials.get(secret_name)
        except (CredentialNotFoundError, CredentialError) as exc:
            logger.warning(
                "federation auth: credential lookup failed for instance %s: %s",
                row.get("name"),
                exc,
            )
            continue
        # Strip surrounding whitespace: secrets created via shell `echo`
        # or an editor often carry a trailing newline in the store, which
        # would otherwise permanently fail the constant-time comparison and
        # lock out a correctly-configured peer.
        if hmac.compare_digest(presented.strip(), expected.strip()):
            return row
    return None


def require_federation_peer(request: Request, conn: Any = None) -> dict[str, Any]:
    # FED-E: thin wrapper that raises 401 when the X-JACKPOT-Federation-Key
    # header is missing or does not match any enabled instance. Routers that
    # also need to cross-check origin (e.g. /access-requests matching
    # requesting_instance_id) call authenticate_federation_peer directly so
    # they can produce a 403 instead of a 401.
    instance_row = authenticate_federation_peer(request, conn)
    if not instance_row:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing federation key.",
        )
    return instance_row
