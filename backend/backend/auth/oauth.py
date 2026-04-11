from datetime import UTC, datetime, timedelta

import httpx
from fastapi import HTTPException
from jose import jwt

from backend.config import get_settings
from backend.database import execute_query

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=7)


async def exchange_google_code(code: str, redirect_uri: str) -> dict[str, str]:
    """Exchange Google auth code for user email and name."""
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange Google auth code.")
    payload = jwt.decode(resp.json()["id_token"], options={"verify_signature": False})
    return {"email": payload["email"], "name": payload.get("name", "")}


def issue_access_token(user_id: int, email: str) -> str:
    settings = get_settings()
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "exp": datetime.now(UTC) + ACCESS_TOKEN_TTL,
            "type": "access",
        },
        settings.secret_key,
        algorithm="HS256",
    )


def issue_refresh_token(user_id: int, email: str) -> str:
    settings = get_settings()
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "exp": datetime.now(UTC) + REFRESH_TOKEN_TTL,
            "type": "refresh",
        },
        settings.secret_key,
        algorithm="HS256",
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
