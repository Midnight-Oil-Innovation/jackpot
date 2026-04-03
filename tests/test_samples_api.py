import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["project"] == "JACKPOT"


@pytest.mark.asyncio
async def test_samples_stub_responds(client):
    resp = await client.get("/api/v1/samples/")
    # Stub returns 200 with not-implemented message
    assert resp.status_code == 200
