import pytest


@pytest.mark.asyncio
async def test_cors_preflight_advertises_explicit_methods(client):
    # SEC-1 tightened CORSMiddleware from allow_methods=["*"] to an
    # explicit list. This test would fail (allow * back) if anyone
    # reverts the explicit list. The browser's preflight asks "may I
    # send a POST with these headers from this origin?" and the
    # middleware echoes back the configured allowlist.
    resp = await client.options(
        "/api/v1/auth/google/login",
        headers={
            "Origin": "http://localhost:8501",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert resp.status_code == 200, f"preflight failed: {resp.status_code} {resp.text}"
    allow_methods = resp.headers.get("access-control-allow-methods", "")
    assert allow_methods != "*", "SEC-1 regression: CORS allow_methods reverted to wildcard"
    for required in ("GET", "POST", "PATCH", "DELETE", "OPTIONS"):
        assert required in allow_methods, f"missing {required} in {allow_methods!r}"


@pytest.mark.asyncio
async def test_cors_preflight_allows_jackpot_specific_headers(client):
    # JACKPOT uses two non-standard request headers — the X-Mock-User-Email
    # (local-dev mock auth) and X-Request-ID (RequestIDMiddleware). The
    # SEC-1 explicit allowlist must include both or the frontend ApiClient
    # cannot send them past CORS preflight.
    resp = await client.options(
        "/api/v1/samples/",
        headers={
            "Origin": "http://localhost:8501",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-mock-user-email,x-request-id",
        },
    )
    assert resp.status_code == 200
    allow_headers = resp.headers.get("access-control-allow-headers", "").lower()
    assert allow_headers != "*", "SEC-1 regression: CORS allow_headers reverted to wildcard"
    assert "x-mock-user-email" in allow_headers
    assert "x-request-id" in allow_headers
    assert "authorization" in allow_headers
    assert "content-type" in allow_headers


@pytest.mark.asyncio
async def test_cors_preflight_rejects_disallowed_origin(client):
    # cors_origins is configured to localhost:8501 + localhost:4200.
    # An origin outside that list MUST NOT receive Access-Control-Allow-Origin.
    resp = await client.options(
        "/api/v1/auth/google/login",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    # Starlette's CORSMiddleware returns 400 for disallowed origins on preflight.
    # The Access-Control-Allow-Origin header MUST NOT be set or MUST NOT
    # echo the disallowed origin.
    allow_origin = resp.headers.get("access-control-allow-origin", "")
    assert allow_origin != "http://evil.example.com"
    assert allow_origin != "*"
