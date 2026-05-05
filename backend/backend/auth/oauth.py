import secrets
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import HTTPException
from jose import jwt

from backend.config import get_settings
from backend.credentials import credentials
from backend.database import execute_query, execute_write

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


async def exchange_google_code(code: str, redirect_uri: str) -> dict[str, str]:
    """Exchange Google auth code for user email and name."""
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": credentials.get("google_oauth_client_secret"),
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange Google auth code.")
    payload = jwt.decode(resp.json()["id_token"], key="", options={"verify_signature": False})
    return {"email": payload["email"], "name": payload.get("name", "")}


def _new_jti() -> str:
    # 16 url-safe random bytes ≈ 22 chars; ample entropy for a JWT ID
    # whose only role is to key a server-side row in refresh_tokens.
    return secrets.token_urlsafe(16)


def issue_access_token(user_id: int, email: str, *, jti: str | None = None) -> str:
    """Mint a stateless access JWT.

    P1: every access token now carries a ``jti`` claim. Access tokens are
    not tracked server-side (still stateless and short-lived), but having a
    JTI makes downstream audit/debug work easier without breaking
    backwards-compatibility (the claim is ignored by older guards).
    """
    settings = get_settings()
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "exp": datetime.now(UTC) + timedelta(seconds=settings.access_token_lifetime_seconds),
            "type": "access",
            "jti": jti or _new_jti(),
        },
        credentials.get("jwt_signing_key"),
        algorithm="HS256",
    )


def issue_refresh_token(
    user_id: int,
    email: str,
    *,
    jti: str | None = None,
) -> tuple[str, str, datetime, datetime]:
    """Mint a refresh JWT and return ``(token, jti, issued_at, expires_at)``.

    P1: callers need the JTI and the issued/expiry timestamps so they can
    register the token in ``refresh_tokens`` for single-use rotation.
    Returning a tuple keeps the caller honest — there is no path that
    issues a refresh token without obtaining the bookkeeping needed to
    track it.
    """
    settings = get_settings()
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(seconds=settings.refresh_token_lifetime_seconds)
    token_jti = jti or _new_jti()
    encoded = jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "iat": int(issued_at.timestamp()),
            "exp": expires_at,
            "type": "refresh",
            "jti": token_jti,
        },
        credentials.get("jwt_signing_key"),
        algorithm="HS256",
    )
    return encoded, token_jti, issued_at, expires_at


def register_refresh_token(
    *,
    jti: str,
    user_id: int,
    issued_at: datetime,
    expires_at: datetime,
    db_conn,
) -> None:
    """Insert a freshly-minted refresh-token row.

    Wraps ``execute_write`` so callers do not have to duplicate the SQL
    or remember the column order. The caller passes ``db_conn`` so the
    insert participates in the same transaction as the surrounding
    request handler.
    """
    execute_write(
        """
        INSERT INTO refresh_tokens (
            jti, user_id, issued_at, expires_at
        ) VALUES (
            :jti, :user_id, :issued_at, :expires_at
        )
        """,
        {
            "jti": jti,
            "user_id": user_id,
            "issued_at": issued_at,
            "expires_at": expires_at,
        },
        conn=db_conn,
    )


def check_domain_whitelist(email: str) -> bool:
    domain = email.split("@")[-1].lower()
    rows = execute_query(
        "SELECT 1 FROM domain_whitelist WHERE LOWER(domain) = :d LIMIT 1",
        {"d": domain},
    )
    return bool(rows)


def get_user_by_email(email: str) -> dict | None:
    rows = execute_query(
        "SELECT * FROM users WHERE email = :e AND is_active = TRUE LIMIT 1",
        {"e": email},
    )
    return rows[0] if rows else None
