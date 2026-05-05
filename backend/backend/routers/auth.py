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
from backend.config import get_settings
from backend.credentials import credentials
from backend.database import execute_query, execute_write, get_db_dep
from backend.rate_limit import limiter

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

    rows = execute_query(
        "SELECT * FROM refresh_tokens WHERE jti = :jti LIMIT 1",
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

    response.delete_cookie("access")
    response.delete_cookie("refresh")
    return {"status": "logged out"}
