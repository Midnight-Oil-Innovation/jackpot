"""Stub routers MUST return HTTP 501, not 200.

Per Phase 22 review action item 10 (closed in P0e C.3): clients that
don't inspect the response body would treat a 200 with
`{"status": "not implemented"}` as success and continue. 501 makes
the unimplemented status loud at the HTTP layer.

This test pins the contract for all 7 currently-stub routers. As each
gets a real implementation (Phase 24+ work), update the test to expect
the real status code rather than removing the test.
"""

import pytest

STUB_ROUTERS = [
    ("/api/v1/datasets/", "datasets"),
    ("/api/v1/notifications/", "notifications"),
    ("/api/v1/archive-requests/", "archive_requests"),
    ("/api/v1/saved-searches/", "saved_searches"),
    ("/api/v1/billing/", "billing"),
    ("/api/v1/dataset-access/", "dataset_access"),
    ("/api/v1/ncbi-submissions/", "ncbi_submissions"),
]


@pytest.mark.parametrize("path,name", STUB_ROUTERS)
@pytest.mark.asyncio
async def test_stub_router_returns_501(client, path, name):
    response = await client.get(path)
    assert response.status_code == 501, (
        f"{name} should be 501; got {response.status_code} (body: {response.text})"
    )


@pytest.mark.parametrize("path,name", STUB_ROUTERS)
@pytest.mark.asyncio
async def test_stub_router_returns_envelope(client, path, name):
    """The 501 must flow through the JACKPOT envelope handler
    (`_http_exception_to_envelope` in main.py) per Critical Rule 24."""
    response = await client.get(path)
    body = response.json()
    assert body.get("success") is False
    assert body.get("error", {}).get("code") == "HTTP_501"
    # Message should reference the stub-status of the router.
    assert "not yet implemented" in body["error"]["message"].lower()
