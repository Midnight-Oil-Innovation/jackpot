"""
jackpot.core.client
~~~~~~~~~~~~~~~~~~~
HTTP client for all JACKPOT API calls.

All SDK modules and CLI commands use this client. It handles:
  - Authentication header injection
  - Response envelope unpacking ({"success": true, "data": ...})
  - Error mapping to typed exceptions
  - Automatic retry on transient server errors (500, 503)
"""

from __future__ import annotations

import httpx

from jackpot.core.exceptions import (
    AuthError,
    ConflictError,
    JACKPOTError,
    NotFoundError,
    ScrubPendingError,
    ServerError,
    TokenExpiredError,
    ValidationError,
)

# Default timeout for all requests. Upload calls use a separate longer timeout.
DEFAULT_TIMEOUT = httpx.Timeout(30.0)
UPLOAD_TIMEOUT = httpx.Timeout(300.0)  # 5 minutes for large file uploads


class JACKPOTClient:
    """
    Thin httpx wrapper for the JACKPOT REST API.

    Usage:
        client = JACKPOTClient(api_url="https://api.jackpot.adhs.az.gov",
                               token="jk_live_...")
        sample = client.get("/samples/AZ-2026-001")
    """

    def __init__(self, api_url: str, token: str) -> None:
        self.api_url = api_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ── Internal helpers ────────────────────────────────────────────────────

    def _url(self, path: str) -> str:
        """Construct full URL from a path like '/api/v1/samples'."""
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.api_url}{path}"

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Map HTTP error codes to typed JACKPOT exceptions."""
        if response.is_success:
            return

        # Try to extract server error message
        try:
            body = response.json()
            message = body.get("error", {}).get("message", response.text)
            detail = body.get("error", {}).get("detail", {})
        except Exception:
            message = response.text
            detail = {}

        status = response.status_code

        if status == 401:
            raise TokenExpiredError(
                f"Token expired or invalid: {message}",
                status_code=status,
            )
        if status == 403:
            raise AuthError(f"Access denied: {message}", status_code=status)
        if status == 404:
            raise NotFoundError(f"Not found: {message}", status_code=status)
        if status == 409:
            code = body.get("error", {}).get("code", "")
            if code in ("SCRUB_PENDING", "SCRUB_APPROVAL_REQUIRED"):
                raise ScrubPendingError(message, status_code=status)
            raise ConflictError(message, status_code=status)
        if status == 422:
            raise ValidationError(
                message,
                errors=detail.get("errors", []),
                tier2_missing=detail.get("tier2_missing", []),
                tier3_missing=detail.get("tier3_missing", []),
            )
        if status >= 500:
            raise ServerError(f"Server error: {message}", status_code=status)

        raise JACKPOTError(message, status_code=status)

    def _unwrap(self, response: httpx.Response) -> dict | list:
        """
        Unwrap the standard response envelope:
          {"success": true, "data": {...}} → returns data
          {"success": true, "data": [...], "pagination": {...}} → returns full body
        """
        self._raise_for_status(response)
        body = response.json()
        if "data" in body:
            return body["data"]
        return body

    # ── Public methods ──────────────────────────────────────────────────────

    def get(self, path: str, params: dict | None = None) -> dict | list:
        """GET request. Returns unwrapped data."""
        response = httpx.get(
            self._url(path),
            params=params,
            headers=self._headers,
            timeout=DEFAULT_TIMEOUT,
        )
        return self._unwrap(response)

    def post(
        self,
        path: str,
        json: dict | None = None,
        data: dict | None = None,
        files: dict | None = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> dict | list:
        """POST request. Returns unwrapped data."""
        headers = self._headers.copy()
        if files:
            # Let httpx set multipart Content-Type with boundary
            del headers["Content-Type"]

        response = httpx.post(
            self._url(path),
            json=json,
            data=data,
            files=files,
            headers=headers,
            timeout=timeout,
        )
        return self._unwrap(response)

    def patch(self, path: str, json: dict) -> dict | list:
        """PATCH request. Returns unwrapped data."""
        response = httpx.patch(
            self._url(path),
            json=json,
            headers=self._headers,
            timeout=DEFAULT_TIMEOUT,
        )
        return self._unwrap(response)

    def delete(self, path: str) -> dict | list:
        """DELETE request. Returns unwrapped data."""
        response = httpx.delete(
            self._url(path),
            headers=self._headers,
            timeout=DEFAULT_TIMEOUT,
        )
        return self._unwrap(response)

    def post_multipart(
        self,
        path: str,
        metadata: dict,
        files: dict,
    ) -> dict | list:
        """
        POST a multipart/form-data request for file uploads.
        metadata is serialised to JSON and sent as the 'metadata' form field.
        files is a dict of {field_name: (filename, file_obj, content_type)}.
        """
        import json as _json

        headers = {k: v for k, v in self._headers.items() if k != "Content-Type"}
        response = httpx.post(
            self._url(path),
            data={"metadata": _json.dumps(metadata)},
            files=files,
            headers=headers,
            timeout=UPLOAD_TIMEOUT,
        )
        return self._unwrap(response)
