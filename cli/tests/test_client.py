"""
tests/test_client.py
~~~~~~~~~~~~~~~~~~~~
Tests for jackpot.core.client.JACKPOTClient.

Uses pytest-httpx to intercept httpx calls.
"""
import pytest
import httpx
from pytest_httpx import HTTPXMock

from jackpot.core.client import JACKPOTClient
from jackpot.core.exceptions import (
    AuthError,
    NotFoundError,
    TokenExpiredError,
    ValidationError,
    ConflictError,
    ServerError,
)


API_URL = "http://testserver"
TOKEN   = "jk_test_abc123"


@pytest.fixture
def client() -> JACKPOTClient:
    return JACKPOTClient(api_url=API_URL, token=TOKEN)


class TestClientInit:
    def test_trailing_slash_stripped(self):
        c = JACKPOTClient(api_url="http://testserver/", token="tok")
        assert c.api_url == "http://testserver"

    def test_auth_header_set(self):
        c = JACKPOTClient(api_url=API_URL, token="mytoken")
        assert c._headers["Authorization"] == "Bearer mytoken"


class TestURLConstruction:
    def test_path_with_leading_slash(self, client):
        assert client._url("/api/v1/samples") == "http://testserver/api/v1/samples"

    def test_path_without_leading_slash(self, client):
        assert client._url("api/v1/samples") == "http://testserver/api/v1/samples"


class TestErrorMapping:
    def test_401_raises_token_expired(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=401,
            json={"success": False, "error": {"code": "UNAUTHORIZED",
                                               "message": "Token expired"}},
        )
        with pytest.raises(TokenExpiredError):
            client.get("/api/v1/samples/")

    def test_403_raises_auth_error(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=403,
            json={"success": False, "error": {"code": "ACCESS_DENIED",
                                               "message": "Access denied"}},
        )
        with pytest.raises(AuthError):
            client.get("/api/v1/samples/AZ-001")

    def test_404_raises_not_found(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=404,
            json={"success": False, "error": {"code": "NOT_FOUND",
                                               "message": "Sample not found"}},
        )
        with pytest.raises(NotFoundError):
            client.get("/api/v1/samples/NOTEXIST")

    def test_422_raises_validation_error_with_details(
        self, client, httpx_mock: HTTPXMock
    ):
        httpx_mock.add_response(
            status_code=422,
            json={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Metadata validation failed.",
                    "detail": {
                        "errors":        ["date_collected: required"],
                        "tier2_missing": ["collection_location_state"],
                        "tier3_missing": ["originating_lab"],
                    },
                },
            },
        )
        with pytest.raises(ValidationError) as exc_info:
            client.post("/api/v1/ingest/upload", json={})

        err = exc_info.value
        assert "date_collected: required" in err.errors
        assert "collection_location_state" in err.tier2_missing
        assert "originating_lab" in err.tier3_missing

    def test_500_raises_server_error(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=500,
            json={"success": False, "error": {"code": "INTERNAL_ERROR",
                                               "message": "Unexpected error"}},
        )
        with pytest.raises(ServerError):
            client.get("/api/v1/samples/")


class TestSuccessUnwrapping:
    def test_unwraps_data_field(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=200,
            json={"success": True, "data": {"sample_id": "AZ-001"}},
        )
        result = client.get("/api/v1/samples/AZ-001")
        assert result == {"sample_id": "AZ-001"}

    def test_unwraps_list_data(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=200,
            json={"success": True, "data": [{"sample_id": "AZ-001"},
                                             {"sample_id": "AZ-002"}]},
        )
        result = client.get("/api/v1/samples/")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_returns_full_body_without_data_key(self, client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=200,
            json={"success": True, "message": "Deleted"},
        )
        result = client.delete("/api/v1/samples/AZ-001")
        assert result["message"] == "Deleted"
