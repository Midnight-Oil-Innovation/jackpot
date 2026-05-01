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
        rightmost = fwd.split(",")[-1].strip()
        if rightmost:
            return rightmost
        # Trailing comma / all-whitespace value: don't bucket every such
        # request to the same empty-string key — fall through to the peer.
    return get_remote_address(request)


# swallow_errors: if the rate-limit storage backend is ever unavailable
# (in-memory today; a shared backend later for multi-pod), a raised
# storage exception inside _inject_headers would otherwise turn the 429
# into a 500 — strictly worse than just sending 429 without the
# Retry-After hint. Swallowed exceptions still surface via
# logger.exception, so a misconfigured backend is observable.
limiter = Limiter(
    key_func=_key_func,
    enabled=get_settings().rate_limit_enabled,
    headers_enabled=True,
    swallow_errors=True,
)
