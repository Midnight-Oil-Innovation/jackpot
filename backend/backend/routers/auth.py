from auth.oauth import (
    check_domain_whitelist,
    exchange_google_code,
    get_user_by_email,
    issue_access_token,
    issue_refresh_token,
)
from config import get_settings
from fastapi import APIRouter, HTTPException, Request, Response

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()


@router.post("/google/login")
async def google_login(code: str, request: Request, response: Response) -> dict:
    """Exchange Google auth code for JWT cookies."""
    redirect_uri = settings.google_oauth_redirect_url
    user_info = await exchange_google_code(code, redirect_uri)
    email = user_info["email"]

    if not check_domain_whitelist(email):
        raise HTTPException(
            status_code=403,
            detail=f"Domain '{email.split('@')[1]}' is not authorised. "
            "Contact a Platform Admin.",
        )

    user = get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=403,
            detail="Account not found. A Platform Admin must create your "
            "account before you can log in.",
        )

    access_token = issue_access_token(user["id"], email)
    refresh_token = issue_refresh_token(user["id"], email)

    response.set_cookie(
        "access", access_token, httponly=True, secure=True, samesite="lax", max_age=900
    )
    response.set_cookie(
        "refresh", refresh_token, httponly=True, secure=True, samesite="lax", max_age=604800
    )

    return {"email": email, "name": user.get("name", "")}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie("access")
    response.delete_cookie("refresh")
    return {"status": "logged out"}
