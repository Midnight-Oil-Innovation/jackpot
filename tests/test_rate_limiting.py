from types import SimpleNamespace

import pytest

from backend.config import get_settings
from backend.rate_limit import _key_func, limiter


def test_key_func_takes_rightmost_xforwardedfor():
    # GCP Cloud Load Balancer appends the real client IP to the right
    # of X-Forwarded-For. The leftmost entries are client-controlled.
    # If the limiter keyed on the leftmost, an attacker could rotate
    # fake IPs to bypass the quota or spoof a victim's IP to poison
    # their bucket. This test locks in the rightmost-takes-priority
    # behavior so the spoofing window stays closed.
    spoofed = SimpleNamespace(
        headers={"x-forwarded-for": "1.1.1.1, 2.2.2.2, 203.0.113.42"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert _key_func(spoofed) == "203.0.113.42"


def test_key_func_strips_whitespace_around_ip():
    req = SimpleNamespace(
        headers={"x-forwarded-for": "   198.51.100.1  "},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert _key_func(req) == "198.51.100.1"


def test_key_func_falls_back_to_remote_address_when_no_xff_header():
    req = SimpleNamespace(
        headers={},
        client=SimpleNamespace(host="10.0.0.5"),
    )
    assert _key_func(req) == "10.0.0.5"


def test_key_func_falls_back_when_xff_rightmost_is_empty():
    # `X-Forwarded-For: 1.2.3.4,` (trailing comma) splits to ["1.2.3.4", ""].
    # If we returned the empty rightmost as the bucket key, all such
    # requests would share one quota — a subtle DoS path. Fall through
    # to the peer instead.
    req = SimpleNamespace(
        headers={"x-forwarded-for": "1.2.3.4,"},
        client=SimpleNamespace(host="10.0.0.99"),
    )
    assert _key_func(req) == "10.0.0.99"


@pytest.fixture
def enable_limiter(monkeypatch):
    # Override the conftest default which disables the limiter for the rest
    # of the suite. Reset slowapi's in-memory storage so quotas don't leak
    # in from earlier tests.
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    get_settings.cache_clear()
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.reset()
    limiter.enabled = False


@pytest.mark.asyncio
async def test_auth_login_rate_limit_blocks_after_quota(enable_limiter, client):
    # 5/minute on /api/v1/auth/google/login. Send 6 requests; the first 5
    # should pass through to the handler (which fails on the missing OAuth
    # `code`, returning 422 — proving the limiter let it through), the 6th
    # should be rejected by the limiter with 429.
    statuses = []
    for _ in range(6):
        resp = await client.post("/api/v1/auth/google/login", params={"code": "x"})
        statuses.append(resp.status_code)

    assert statuses[:5].count(429) == 0, f"first 5 should not be 429; got {statuses[:5]}"
    assert statuses[5] == 429, f"6th request should be 429; got {statuses[5]}"

    body = (await client.post("/api/v1/auth/google/login", params={"code": "x"})).json()
    assert body.get("success") is False
    assert body.get("error", {}).get("code") == "HTTP_429"


@pytest.mark.asyncio
async def test_rate_limit_429_carries_retry_after_header(enable_limiter, client):
    # Trip the auth limit (5/min), then verify the 6th response carries
    # Retry-After + RateLimit-* hints so clients can back off correctly.
    # This guards the explicit _inject_headers call in main.py's custom
    # 429 handler — without it, the JACKPOT envelope would land bare.
    for _ in range(5):
        await client.post("/api/v1/auth/google/login", params={"code": "x"})
    blocked = await client.post("/api/v1/auth/google/login", params={"code": "x"})

    assert blocked.status_code == 429
    headers_lower = {k.lower(): v for k, v in blocked.headers.items()}
    assert "retry-after" in headers_lower, f"missing Retry-After in {blocked.headers}"
    # The window is "5/minute" so the wait should be a positive number of
    # seconds well under 60. Asserting > 0 catches a misconfigured handler
    # that emits the header with a stub value.
    retry_after = int(headers_lower["retry-after"])
    assert 0 < retry_after <= 60, f"unexpected Retry-After value {retry_after}"
    # The configured ceiling — if this drifts the test forces an audit.
    assert int(headers_lower["x-ratelimit-limit"]) == 5
    # We just ate the entire budget; remaining must be zero.
    assert int(headers_lower["x-ratelimit-remaining"]) == 0


@pytest.mark.asyncio
async def test_rate_limiter_disabled_by_default_in_tests(client):
    # The conftest override sets RATE_LIMIT_ENABLED=false. Verify the
    # limiter respects that — sending more than the auth quota in a single
    # tick should not produce any 429s.
    statuses = [
        (await client.post("/api/v1/auth/google/login", params={"code": "x"})).status_code
        for _ in range(10)
    ]
    assert 429 not in statuses, f"limiter should be off in tests; got {statuses}"
