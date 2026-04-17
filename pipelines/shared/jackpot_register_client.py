"""
JACKPOT result registration client.

Shared HTTP client used by every pipeline parser to POST typed results back
to the JACKPOT API. Reads run-specific config from environment variables
set by the pipeline wrapper:

    JACKPOT_API_URL         e.g. https://api.jackpot.example.com
    JACKPOT_RUN_ID          the run's external run_id
    JACKPOT_PIPELINE_TOKEN  the per-run secret stored on pipeline_runs

Parsers call a single method:

    client = JackpotRegisterClient()
    client.register_result("pangolin_results", {...})

On success returns the API's JSON response (includes ``result_id``).
Retries 5xx responses with exponential backoff, max 3 attempts.
Raises ``RegistrationError`` on 4xx or persistent 5xx.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RegistrationError(Exception):
    """Raised when a result registration cannot be completed."""

    def __init__(self, message: str, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


@dataclass(frozen=True)
class _ClientConfig:
    api_url: str
    run_id: str
    pipeline_token: str


def _load_config(
    api_url: str | None,
    run_id: str | None,
    pipeline_token: str | None,
) -> _ClientConfig:
    resolved_api = api_url or os.environ.get("JACKPOT_API_URL")
    resolved_run = run_id or os.environ.get("JACKPOT_RUN_ID")
    resolved_token = pipeline_token or os.environ.get("JACKPOT_PIPELINE_TOKEN")
    missing = [
        name
        for name, value in (
            ("JACKPOT_API_URL", resolved_api),
            ("JACKPOT_RUN_ID", resolved_run),
            ("JACKPOT_PIPELINE_TOKEN", resolved_token),
        )
        if not value
    ]
    if missing:
        raise RegistrationError(
            f"Missing required configuration: {', '.join(missing)}",
        )
    return _ClientConfig(
        api_url=resolved_api.rstrip("/"),
        run_id=resolved_run,
        pipeline_token=resolved_token,
    )


class JackpotRegisterClient:
    """POST typed pipeline results to the JACKPOT API."""

    MAX_ATTEMPTS = 3
    BASE_BACKOFF_SECONDS = 1.0
    DEFAULT_TIMEOUT_SECONDS = 30.0

    def __init__(
        self,
        api_url: str | None = None,
        run_id: str | None = None,
        pipeline_token: str | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.Client | None = None,
        sleep: Any = time.sleep,
    ) -> None:
        self._config = _load_config(api_url, run_id, pipeline_token)
        self._timeout = timeout
        self._sleep = sleep
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> JackpotRegisterClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def register_result(self, result_type: str, payload: dict) -> dict:
        """POST one typed result. Returns the API's parsed JSON response."""
        if not result_type:
            raise RegistrationError("result_type is required")
        url = (
            f"{self._config.api_url}/api/v1/pipelines/"
            f"{self._config.run_id}/results/{result_type}"
        )
        headers = {
            "X-Pipeline-Token": self._config.pipeline_token,
            "Content-Type": "application/json",
        }

        last_error: RegistrationError | None = None
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                response = self._client.post(url, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                last_error = RegistrationError(
                    f"HTTP error posting to {url}: {exc}",
                )
                if attempt < self.MAX_ATTEMPTS:
                    self._sleep(self.BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))
                    continue
                raise last_error from exc

            if 200 <= response.status_code < 300:
                return _parse_json(response)

            if 400 <= response.status_code < 500:
                raise RegistrationError(
                    f"{response.status_code} from {url}",
                    status_code=response.status_code,
                    body=_safe_body(response),
                )

            last_error = RegistrationError(
                f"{response.status_code} from {url}",
                status_code=response.status_code,
                body=_safe_body(response),
            )
            logger.warning(
                "register_result attempt %d/%d failed with %d",
                attempt,
                self.MAX_ATTEMPTS,
                response.status_code,
            )
            if attempt < self.MAX_ATTEMPTS:
                self._sleep(self.BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))

        assert last_error is not None
        raise last_error


def _parse_json(response: httpx.Response) -> dict:
    try:
        return response.json()
    except ValueError as exc:
        raise RegistrationError(
            "Server returned non-JSON success response",
            status_code=response.status_code,
            body=response.text,
        ) from exc


def _safe_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def register_result(
    result_type: str,
    payload: dict,
    *,
    api_url: str | None = None,
    run_id: str | None = None,
    pipeline_token: str | None = None,
) -> dict:
    """Convenience wrapper — single call without keeping a client around."""
    with JackpotRegisterClient(
        api_url=api_url,
        run_id=run_id,
        pipeline_token=pipeline_token,
    ) as client:
        return client.register_result(result_type, payload)
