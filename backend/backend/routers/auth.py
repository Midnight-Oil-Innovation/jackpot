import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from jose import jwt
from jose.exceptions import JWTError
from pydantic import BaseModel

from backend.audit import AuditActions, log_audit
from backend.auth.oauth import (
    check_domain_whitelist,
    exchange_google_code,
    get_user_by_email,
    issue_access_token,
    issue_refresh_token,
    register_refresh_token,
)
from backend.authz.reseed import sync_instance_grants, sync_membership_grants
from backend.config import get_settings
from backend.credentials import credentials
from backend.database import execute_query, execute_write, get_db_dep
from backend.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()


class RefreshBody(BaseModel):
    """Optional JSON body for /refresh — programmatic clients (SDK, CLI)
    that cannot use httpOnly cookies submit the refresh token here."""

    refresh_token: str | None = None


def _set_session_cookies(response: Response, *, access_token: str, refresh_token: str) -> None:
    """Apply the (access, refresh) cookie pair with attributes that match
    the existing login flow. Centralised so /google/login and /refresh
    cannot drift apart on cookie attributes."""
    s = get_settings()
    response.set_cookie(
        "access",
        access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=s.access_token_lifetime_seconds,
    )
    response.set_cookie(
        "refresh",
        refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=s.refresh_token_lifetime_seconds,
    )


@router.post("/google/login")
@limiter.limit(settings.rate_limit_auth)
async def google_login(
    code: str,
    request: Request,
    response: Response,
    db=Depends(get_db_dep),  # noqa: B008
) -> dict:
    """Exchange Google auth code for JWT cookies."""
    redirect_uri = settings.google_oauth_redirect_url
    user_info = await exchange_google_code(code, redirect_uri)
    email = user_info["email"]

    if not check_domain_whitelist(email):
        raise HTTPException(
            status_code=403,
            detail=f"Domain '{email.split('@')[1]}' is not authorised. Contact a Platform Admin.",
        )

    user = get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=403,
            detail="Account not found. A Platform Admin must create your "
            "account before you can log in.",
        )

    access_token = issue_access_token(user["id"], email)
    refresh_token, refresh_jti, issued_at, expires_at = issue_refresh_token(user["id"], email)

    # P1: register the refresh JTI so /refresh can rotate it later. The
    # insert shares the request transaction (db_conn=db) so a failure
    # here would roll back the issued cookies' bookkeeping atomically.
    register_refresh_token(
        jti=refresh_jti,
        user_id=user["id"],
        issued_at=issued_at,
        expires_at=expires_at,
        db_conn=db,
    )

    _set_session_cookies(response, access_token=access_token, refresh_token=refresh_token)

    return {"email": email, "name": user.get("name", "")}


def _error_detail(code: str, message: str, **extra: object) -> dict:
    """Bundle a structured error detail. The HTTPException handler in
    main.py preserves dict-shaped detail under ``detail``; clients read
    ``error.detail.error_code`` to discriminate the six refresh failure
    modes documented in the P1 spec."""
    detail: dict = {"error_code": code, "message": message}
    detail.update(extra)
    return detail


def _extract_refresh_token(request: Request, body: RefreshBody | None) -> str | None:
    """Cookie wins over body when both are present (defense against the
    confused-deputy case where a programmatic client accidentally
    forwards a stale cookie)."""
    cookie_token = request.cookies.get("refresh")
    if cookie_token:
        return cookie_token
    if body is not None and body.refresh_token:
        return body.refresh_token
    return None


@router.post("/refresh")
@limiter.limit(settings.rate_limit_auth)
async def refresh(
    request: Request,
    response: Response,
    body: RefreshBody | None = None,
    db=Depends(get_db_dep),  # noqa: B008
) -> dict:
    """Rotate a refresh token, issuing a fresh access + refresh pair.

    Token rotation is single-use: the presented refresh token is marked
    ``revoked_reason='rotated'`` and points at the new JTI. A second
    presentation of the same token is treated as a replay attempt — see
    the TOKEN_REPLAY_DETECTED branch below.
    """
    raw_token = _extract_refresh_token(request, body)
    if not raw_token:
        raise HTTPException(
            status_code=401,
            detail=_error_detail(
                "MISSING_REFRESH_TOKEN",
                "Refresh token required. Provide via 'refresh' cookie "
                "or 'refresh_token' body field.",
            ),
        )

    try:
        payload = jwt.decode(
            raw_token,
            credentials.get("jwt_signing_key"),
            algorithms=["HS256"],
        )
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail=_error_detail(
                "INVALID_REFRESH_TOKEN",
                "Refresh token is invalid or expired.",
            ),
        ) from None

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=401,
            detail=_error_detail(
                "WRONG_TOKEN_TYPE",
                "Provided token is not a refresh token.",
            ),
        )

    jti = payload.get("jti")
    user_id_claim = payload.get("sub")
    if not jti or not user_id_claim:
        raise HTTPException(
            status_code=401,
            detail=_error_detail(
                "INVALID_REFRESH_TOKEN",
                "Refresh token missing required claims.",
            ),
        )
    try:
        user_id = int(user_id_claim)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail=_error_detail(
                "INVALID_REFRESH_TOKEN",
                "Refresh token has malformed subject claim.",
            ),
        ) from None

    # R-1 #6: row-lock the JTI for the duration of the rotation. Without
    # the lock, two concurrent /refresh requests presenting the same
    # token both pass the revoked_at IS NULL check and both perform
    # rotation — issuing two valid refresh tokens for one original. The
    # FOR UPDATE clause serialises rotations on the same JTI; the second
    # request waits for the first to commit, then sees revoked_at set
    # and falls into the replay-detection branch below.
    rows = execute_query(
        "SELECT * FROM refresh_tokens WHERE jti = :jti FOR UPDATE",
        {"jti": jti},
        conn=db,
    )
    if not rows:
        raise HTTPException(
            status_code=401,
            detail=_error_detail(
                "TOKEN_NOT_TRACKED",
                "Refresh token is not registered. Please log in again.",
            ),
        )
    row = rows[0]

    if row["revoked_at"] is not None:
        if row["revoked_reason"] == "rotated":
            # Replay: the legitimate user already rotated this token. The
            # most likely explanation is that an attacker captured the
            # refresh token before rotation and is replaying it after.
            # Defense in depth: revoke every active refresh token for the
            # user so the attacker's other captures (if any) are killed too.
            execute_write(
                """
                UPDATE refresh_tokens
                   SET revoked_at = NOW(),
                       revoked_reason = 'replay_detected'
                 WHERE user_id = :user_id
                   AND revoked_at IS NULL
                """,
                {"user_id": user_id},
                conn=db,
            )
            log_audit(
                action=AuditActions.AUTH_TOKEN_REPLAY_DETECTED,
                actor_id=user_id,
                resource_type="refresh_token",
                resource_id=jti,
                before=None,
                after=None,
                metadata={"jti": jti, "user_id": user_id},
                db_conn=db,
            )
            # Defense in depth must persist even though the response is
            # 401: commit the bulk-revoke + audit row before raising,
            # otherwise get_db_dep's rollback nukes the side effect.
            db.commit()
            raise HTTPException(
                status_code=401,
                detail=_error_detail(
                    "TOKEN_REPLAY_DETECTED",
                    "This refresh token was already used. All your "
                    "active sessions have been revoked. Please log in again.",
                ),
            )
        raise HTTPException(
            status_code=401,
            detail=_error_detail(
                "TOKEN_REVOKED",
                "Refresh token has been revoked. Please log in again.",
                revoked_reason=row["revoked_reason"],
            ),
        )

    email_claim = payload.get("email", "")
    new_access_token = issue_access_token(user_id, email_claim)
    new_refresh_token, new_refresh_jti, issued_at, expires_at = issue_refresh_token(
        user_id, email_claim
    )

    register_refresh_token(
        jti=new_refresh_jti,
        user_id=user_id,
        issued_at=issued_at,
        expires_at=expires_at,
        db_conn=db,
    )
    execute_write(
        """
        UPDATE refresh_tokens
           SET revoked_at = NOW(),
               revoked_reason = 'rotated',
               replaced_by_jti = :new_jti
         WHERE jti = :old_jti
        """,
        {"new_jti": new_refresh_jti, "old_jti": jti},
        conn=db,
    )

    log_audit(
        action=AuditActions.AUTH_TOKEN_REFRESHED,
        actor_id=user_id,
        resource_type="refresh_token",
        resource_id=new_refresh_jti,
        before=None,
        after=None,
        metadata={"old_jti": jti, "new_jti": new_refresh_jti},
        db_conn=db,
    )

    _set_session_cookies(response, access_token=new_access_token, refresh_token=new_refresh_token)

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": get_settings().access_token_lifetime_seconds,
    }


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db=Depends(get_db_dep),  # noqa: B008
) -> dict:
    """Clear session cookies and revoke the current refresh token.

    Best-effort: if the refresh cookie is missing, malformed, or expired
    the endpoint still succeeds — the user's intent to end the session
    is honored regardless of token state. ``verify_exp=False`` lets us
    still revoke an expired-but-otherwise-valid token in the table so
    operators auditing the table see a clean ``logout`` reason rather
    than an orphaned active row that quietly aged out.
    """
    raw_refresh = request.cookies.get("refresh")
    if raw_refresh:
        try:
            payload = jwt.decode(
                raw_refresh,
                credentials.get("jwt_signing_key"),
                algorithms=["HS256"],
                options={"verify_exp": False},
            )
            jti = payload.get("jti")
            user_id_claim = payload.get("sub")
            user_id: int | None = None
            if user_id_claim is not None:
                try:
                    user_id = int(user_id_claim)
                except (TypeError, ValueError):
                    user_id = None
            if jti:
                execute_write(
                    """
                    UPDATE refresh_tokens
                       SET revoked_at = NOW(),
                           revoked_reason = 'logout'
                     WHERE jti = :jti AND revoked_at IS NULL
                    """,
                    {"jti": jti},
                    conn=db,
                )
                if user_id is not None:
                    log_audit(
                        action=AuditActions.AUTH_LOGOUT,
                        actor_id=user_id,
                        resource_type="refresh_token",
                        resource_id=jti,
                        before=None,
                        after=None,
                        metadata={"jti": jti},
                        db_conn=db,
                    )
        except JWTError:
            # Logout works even if the refresh token is unparseable.
            pass
        except Exception as exc:  # noqa: BLE001 — logout is best-effort
            # A credential-backend hiccup or a DB error (e.g. the
            # refresh_tokens table missing pre-migration) must not block
            # the user from ending their session. Log and still clear
            # cookies below.
            logger.warning("logout: refresh-token revocation failed: %s", exc)

    response.delete_cookie("access")
    response.delete_cookie("refresh")
    return {"status": "logged out"}


# =============================================================================
# E-1: dev-only role-switch endpoint
# =============================================================================
#
# POST /api/v1/auth/dev-login mutates the cached ``settings.mock_user_email``
# so subsequent same-process requests resolve as the supplied identity. It
# 404s outside ``settings.env == "local"`` and never sets cookies — local
# mode bypasses JWT validation in ``backend.auth.guards.get_current_user``.
#
# The endpoint exists so the E-1 UAT can drive all six roles from a single
# backend run without restarts. ``set_role.sh`` and ``dev_login.sh`` in
# ``tests/e2e/scripts/`` are the supported callers; programmatic tests
# may also call it directly.

_DEV_LOGIN_LAB_ROLES = {
    "Lab Director": ("Lab Director", True),
    "Lab Collaborator": ("Lab Collaborator", False),
    "Lab Reader": ("Lab Reader", False),
    "Bioinformatics User": ("Bioinformatics User", False),
}
_DEV_LOGIN_GLOBAL_ROLES = frozenset({"Platform Admin", "Data Analyst"})
_DEV_LOGIN_ALL_ROLES = _DEV_LOGIN_GLOBAL_ROLES | frozenset(_DEV_LOGIN_LAB_ROLES)


class DevLoginBody(BaseModel):
    """Request body for ``POST /api/v1/auth/dev-login``."""

    email: str
    role: str | None = None
    lab_id: int | None = None
    name: str | None = None


def _validate_dev_login_payload(payload: "DevLoginBody") -> tuple[str, str | None]:
    """Email/role/lab_id validation. Raises HTTPException on any invalid input.
    Returns (email, role)."""
    email = (payload.email or "").strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(status_code=400, detail="email must be a valid email address.")

    role = payload.role
    if role is not None and role not in _DEV_LOGIN_ALL_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"role must be one of: {sorted(_DEV_LOGIN_ALL_ROLES)}",
        )

    # Section 7: Platform Admin and Data Analyst do NOT take lab assignments.
    if role in ("Platform Admin", "Data Analyst") and payload.lab_id is not None:
        raise HTTPException(
            status_code=400,
            detail=f"{role} cannot be assigned to a lab.",
        )

    return email, role


def _get_or_create_dev_user(
    email: str, name: str | None, role: str | None, db: Any
) -> tuple[dict, bool]:
    """Look up the dev-login user by email, updating role flags if the
    caller specified a role, or create one against the first organization.
    Raises HTTPException(500) if no organization exists. Returns (user, created)."""
    is_platform_admin = role == "Platform Admin"
    is_data_analyst = role == "Data Analyst"
    rows = execute_query(
        "SELECT id, email, name, is_platform_admin, is_data_analyst, "
        "is_active, organization_id "
        "FROM users WHERE email = :e LIMIT 1",
        {"e": email},
        conn=db,
    )
    if rows:
        user = rows[0]
        if role is not None:
            execute_write(
                "UPDATE users SET is_platform_admin = :pa, is_data_analyst = :da WHERE id = :uid",
                {"pa": is_platform_admin, "da": is_data_analyst, "uid": user["id"]},
                conn=db,
            )
            user["is_platform_admin"] = is_platform_admin
            user["is_data_analyst"] = is_data_analyst
            # Writing the flags is the role assignment, so it has to issue the
            # grants — dev-login exists to drive the full RBAC matrix from a
            # script, and a role that grants nothing drives nothing.
            sync_instance_grants(
                db,
                user_id=user["id"],
                is_platform_admin=is_platform_admin,
                is_data_analyst=is_data_analyst,
            )
        return user, False

    org_rows = execute_query("SELECT id FROM organizations ORDER BY id LIMIT 1", {}, conn=db)
    if not org_rows:
        raise HTTPException(
            status_code=500,
            detail="No organizations exist; cannot create dev-login user.",
        )
    org_id = org_rows[0]["id"]
    new_rows = execute_write(
        "INSERT INTO users (email, name, organization_id, "
        "is_platform_admin, is_data_analyst) "
        "VALUES (:e, :n, :org, :pa, :da) "
        "RETURNING id, email, name, is_platform_admin, is_data_analyst, "
        "is_active, organization_id",
        {
            "e": email,
            "n": name or email.split("@", 1)[0],
            "org": org_id,
            "pa": is_platform_admin,
            "da": is_data_analyst,
        },
        conn=db,
    )
    created_user = new_rows[0]
    sync_instance_grants(
        db,
        user_id=created_user["id"],
        is_platform_admin=is_platform_admin,
        is_data_analyst=is_data_analyst,
    )
    return created_user, True


def _upsert_dev_lab_membership(
    role: str | None, lab_id: int | None, user_id: int, db: Any
) -> dict | None:
    """Upsert lab_membership for a lab-scoped dev-login role. Raises
    HTTPException on missing labs/permission_groups. Returns membership info,
    or None when the role isn't lab-scoped."""
    if role not in _DEV_LOGIN_LAB_ROLES:
        return None

    if lab_id is None:
        lab_rows = execute_query("SELECT id FROM labs ORDER BY id LIMIT 1", {}, conn=db)
        if not lab_rows:
            raise HTTPException(
                status_code=400,
                detail="No labs exist; pass lab_id or create a lab first.",
            )
        # int() rather than a cast: the row value is Unknown to the type
        # checker, and sync_membership_grants below takes a real int.
        lab_id = int(lab_rows[0]["id"])

    pg_name, is_director = _DEV_LOGIN_LAB_ROLES[role]
    pg_rows = execute_query(
        "SELECT id FROM permission_groups WHERE name = :n LIMIT 1",
        {"n": pg_name},
        conn=db,
    )
    if not pg_rows:
        raise HTTPException(
            status_code=500,
            detail=f"permission_groups row '{pg_name}' missing.",
        )
    pg_id = pg_rows[0]["id"]

    execute_write(
        """
        INSERT INTO lab_membership
            (user_id, lab_id, permission_group_id,
             is_lab_director, granted_by_id)
        VALUES (:uid, :lid, :pg, :idir, :uid)
        ON CONFLICT (user_id, lab_id) DO UPDATE
        SET permission_group_id = EXCLUDED.permission_group_id,
            is_lab_director = EXCLUDED.is_lab_director
        """,
        {"uid": user_id, "lid": lab_id, "pg": pg_id, "idir": is_director},
        conn=db,
    )
    # The same call labs.py makes after its own membership writes (M2-B5).
    # This site was missed: a lab_membership row stopped being a decision
    # input at M2-B1, so without this the dev user is a Lab Director in the
    # row and a stranger to every route.
    sync_membership_grants(db, user_id=user_id, lab_id=lab_id, group_name=pg_name)
    return {
        "lab_id": lab_id,
        "permission_group": pg_name,
        "is_lab_director": is_director,
    }


@router.post("/dev-login")
def dev_login(
    payload: DevLoginBody,
    db=Depends(get_db_dep),  # noqa: B008
) -> dict:
    """LOCAL-ONLY: switch the active mock user.

    Returns ``404 Not Found`` when ``settings.env`` is anything other than
    ``"local"``. The endpoint creates the user/lab-membership rows when
    they do not already exist so a freshly-seeded database can be driven
    through the full RBAC matrix from a script.
    """
    s = get_settings()
    if s.env != "local":
        raise HTTPException(status_code=404, detail="Not Found")

    email, role = _validate_dev_login_payload(payload)
    user, created = _get_or_create_dev_user(email, payload.name, role, db)
    membership_info = _upsert_dev_lab_membership(role, payload.lab_id, user["id"], db)

    log_audit(
        action=AuditActions.AUTH_DEV_LOGIN,
        actor_id=user["id"],
        resource_type="user",
        resource_id=str(user["id"]),
        before=None,
        after=None,
        metadata={
            "email": email,
            "role": role,
            "lab_id": membership_info["lab_id"] if membership_info else None,
            "created": created,
        },
        db_conn=db,
    )
    db.commit()

    # Mutate the cached Settings so subsequent same-process requests
    # resolve as this identity. lru_cache returns the singleton, so
    # this attribute write is visible to all later get_settings() calls.
    s.mock_user_email = email

    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "is_platform_admin": user["is_platform_admin"],
            "is_data_analyst": user["is_data_analyst"],
        },
        "membership": membership_info,
        "active_role": role,
    }
