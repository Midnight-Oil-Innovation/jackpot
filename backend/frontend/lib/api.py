"""
Single HTTP client used by every Streamlit page.

Every call goes through ``ApiClient``. Pages never reach for ``requests``
or ``httpx`` directly — that keeps auth, error surfacing, and base-URL
config in one place so the React migration only has to swap this file.

Error handling contract
-----------------------

Backend responses follow the envelope shape from
``backend/responses.py``:

    success: {"success": true,  "data": ..., ...}
    error:   {"success": false, "error": {"code": ..., "message": ...}}

``ApiClient`` unwraps the success envelope and returns ``data`` directly.
On an error response it raises ``ApiError`` which carries the original
HTTP status, error code, and server message so pages can render a
consistent ``st.error`` without constructing it themselves. Network
failures (connection refused, timeout) also raise ``ApiError`` with
``code="NETWORK"`` so the UI layer does not have to distinguish.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_TIMEOUT_SEC = 20.0


class ApiError(Exception):
    """Anything an API call can go wrong with — HTTP error or network."""

    def __init__(self, code: str, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class ApiClient:
    """Thin wrapper around ``httpx.Client`` with the JACKPOT envelope."""

    def __init__(
        self,
        base_url: str | None = None,
        cookies: dict[str, str] | None = None,
        mock_user_email: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("JACKPOT_API_URL") or "http://localhost:8000"
        ).rstrip("/")
        self._cookies = dict(cookies or {})
        self._mock_email = mock_user_email or os.getenv("MOCK_USER_EMAIL")
        self._timeout = timeout

    # ── public surface ──────────────────────────────────────────────────

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(
        self,
        path: str,
        json_body: dict | None = None,
        params: dict | None = None,
        files: dict | None = None,
        data: dict | None = None,
    ) -> Any:
        return self._request(
            "POST", path, params=params, json_body=json_body, files=files, data=data
        )

    def patch(self, path: str, json_body: dict | None = None) -> Any:
        return self._request("PATCH", path, json_body=json_body)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    # ── internal ─────────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Accept": "application/json"}
        if self._mock_email:
            # Test / local dev: the server's get_current_user looks up the
            # MOCK_USER_EMAIL env var on the API process, so the header is a
            # hint used only by test fixtures. We still ship it for parity.
            h["X-Mock-User-Email"] = self._mock_email
        return h

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        files: dict | None = None,
        data: dict | None = None,
    ) -> Any:
        url = self.base_url + ("/" + path.lstrip("/"))
        try:
            with httpx.Client(timeout=self._timeout, cookies=self._cookies) as c:
                resp = c.request(
                    method,
                    url,
                    params=params,
                    json=json_body if files is None else None,
                    files=files,
                    data=data,
                    headers=self._headers(),
                )
        except httpx.HTTPError as exc:
            raise ApiError("NETWORK", f"Network error: {exc}", 0) from exc

        # Some endpoints (templates, downloads) return non-JSON payloads.
        ctype = resp.headers.get("content-type", "")
        if "application/json" not in ctype:
            if resp.status_code >= 400:
                raise ApiError("HTTP_ERROR", resp.text or resp.reason_phrase, resp.status_code)
            return resp.content

        try:
            body = resp.json()
        except ValueError as exc:
            raise ApiError(
                "BAD_RESPONSE", "Server returned invalid JSON.", resp.status_code
            ) from exc

        if resp.status_code >= 400 or (isinstance(body, dict) and body.get("success") is False):
            err = (body or {}).get("error") or {}
            raise ApiError(
                err.get("code") or f"HTTP_{resp.status_code}",
                err.get("message") or resp.text or "Request failed.",
                resp.status_code,
            )

        if isinstance(body, dict) and "data" in body:
            return body["data"]
        return body


# ── module-level default client ──────────────────────────────────────────

_default_client: ApiClient | None = None


def get_client() -> ApiClient:
    """Return a singleton client sharing a cookie jar across pages."""
    global _default_client
    if _default_client is None:
        _default_client = ApiClient()
    return _default_client


def set_client(client: ApiClient) -> None:
    """Replace the default client — used by test fixtures to inject mocks."""
    global _default_client
    _default_client = client
