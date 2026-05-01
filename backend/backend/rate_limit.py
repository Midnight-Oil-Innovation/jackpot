from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.config import get_settings


def _key_func(request) -> str:
    # Prefer a stable header chain when behind a proxy (GKE / Cloud Load
    # Balancer set X-Forwarded-For); fall back to the immediate peer.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=_key_func,
    enabled=get_settings().rate_limit_enabled,
    headers_enabled=True,
)
