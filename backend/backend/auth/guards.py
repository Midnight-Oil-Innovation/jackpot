import hmac
import logging
from typing import Any

from fastapi import HTTPException, Request
from jose import jwt

from backend.authz.engine import Context, Decision, Resource, permit
from backend.authz.principal import lab_resource_scope, load_principal
from backend.authz.scope import scope_uri
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


def require_capability(capability: str):
    """Guard factory: returns a callable raising HTTP 403 unless the current
    user holds ``capability`` at a scope covering the resource.

    M2-B1: enforcement is ``permit()`` (access_model.md §5). The legacy
    structural ladder — platform-admin bypass, lab membership, the
    project→lab join, the director flag — is gone from this function. What
    replaces each rung:

    - platform admin        -> an ``instance://self`` grant from the §8.2
                               Instance Administrator preset, which contains
                               every lab path by ordinary prefix containment
                               (ADR 0015). No bypass branch.
    - lab membership        -> lab-scoped grants from the member presets
    - directorship          -> the Lab Lead preset's enumerated capabilities
    - project→lab join      -> nothing. Project-only members hold no grants;
                               reseed's pre-flight guard counts them so an
                               operator sees the loss before it happens
                               (``project_only_membership``).

    ``policies=[]`` is passed deliberately, not as a placeholder: DB-backed
    policy loading is not wired until M3, and the engine raises on ``None``
    rather than silently treating "no policies" as "policies not loaded".
    Every route reaching this guard is decided by structural grants alone;
    the attribute-policy paths (PUBLIC samples, sovereignty DENY) belong to
    the sample-visibility plane, which M2-B7 moves onto
    ``visibility_sql_clause``.
    """

    def _guard(current_user: dict | None, lab_id: int | None = None) -> dict:
        if current_user is None:
            raise HTTPException(status_code=403, detail=f"capability '{capability}' required")

        principal = load_principal(current_user["id"])

        try:
            scope = lab_resource_scope(lab_id) if lab_id is not None else scope_uri()
        except ValueError:
            # No such lab. Whether the caller may learn that depends on their
            # reach: someone holding the capability instance-wide can already
            # enumerate labs, so let them through and let the route answer 404.
            # For everyone else the answer is the same 403 a real-but-denied
            # lab produces — under org isolation, existence is itself the
            # secret (§3.2: another org must not learn of a lab's data, users,
            # "or existence"), so the two cases must be indistinguishable.
            if (
                permit(
                    principal,
                    capability,
                    Resource(scope=scope_uri()),
                    Context(conditions={}),
                    policies=[],
                )
                is Decision.ALLOW
            ):
                return current_user
            logger.info(
                "authz: DENY user=%s capability=%s unknown lab_id=%s",
                current_user.get("id"),
                capability,
                lab_id,
            )
            raise HTTPException(
                status_code=403, detail=f"capability '{capability}' required"
            ) from None
        decision = permit(
            principal,
            capability,
            Resource(scope=scope),
            Context(conditions={}),
            policies=[],
        )
        if decision is Decision.ALLOW:
            return current_user

        logger.info(
            "authz: DENY user=%s capability=%s scope=%s",
            current_user.get("id"),
            capability,
            scope,
        )
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
