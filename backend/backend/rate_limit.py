from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.config import get_settings


def _key_func(request) -> str:
    # GCP Cloud Load Balancer (and most production reverse proxies) APPEND
    # the real client IP to the right of X-Forwarded-For. The leftmost
    # entries are client-controlled — using the leftmost would let an
    # attacker either bypass the limit (rotate fake leftmost IPs) or
    # poison a victim's quota by spoofing their IP. Take the rightmost
    # entry, which the proxy sets and the client cannot forge.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[-1].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=_key_func,
    enabled=get_settings().rate_limit_enabled,
    headers_enabled=True,
)
