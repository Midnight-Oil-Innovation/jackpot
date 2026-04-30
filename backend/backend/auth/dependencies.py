from fastapi import Request

from backend.auth.guards import get_current_user


def current_user(request: Request) -> dict:
    """FastAPI dependency — inject current user into route handlers."""
    return get_current_user(request)
