"""Tests for shared.jackpot_register_client."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.jackpot_register_client import (  # noqa: E402
    JackpotRegisterClient,
    RegistrationError,
    register_result,
)


def _client(
    mock_transport: httpx.MockTransport,
    sleep: MagicMock | None = None,
) -> JackpotRegisterClient:
    http_client = httpx.Client(transport=mock_transport, base_url="http://stub")
    return JackpotRegisterClient(
        api_url="http://api.test",
        run_id="run-abc",
        pipeline_token="tok-xyz",  # noqa: S106 - test token
        client=http_client,
        sleep=sleep or MagicMock(),
    )


class TestConfigResolution:
    def test_requires_api_url(self, monkeypatch):
        monkeypatch.delenv("JACKPOT_API_URL", raising=False)
        monkeypatch.setenv("JACKPOT_RUN_ID", "r")
        monkeypatch.setenv("JACKPOT_PIPELINE_TOKEN", "t")
        with pytest.raises(RegistrationError, match="JACKPOT_API_URL"):
            JackpotRegisterClient()

    def test_reads_env_vars(self, monkeypatch):
        monkeypatch.setenv("JACKPOT_API_URL", "https://api.x")
        monkeypatch.setenv("JACKPOT_RUN_ID", "run-1")
        monkeypatch.setenv("JACKPOT_PIPELINE_TOKEN", "secret")
        client = JackpotRegisterClient()
        assert client._config.api_url == "https://api.x"
        assert client._config.run_id == "run-1"
        assert client._config.pipeline_token == "secret"

    def test_explicit_args_override_env(self, monkeypatch):
        monkeypatch.setenv("JACKPOT_API_URL", "https://env-api.x")
        monkeypatch.setenv("JACKPOT_RUN_ID", "env-run")
        monkeypatch.setenv("JACKPOT_PIPELINE_TOKEN", "env-tok")
        client = JackpotRegisterClient(
            api_url="https://explicit.x",
            run_id="explicit-run",
            pipeline_token="explicit-tok",  # noqa: S106
        )
        assert client._config.api_url == "https://explicit.x"
        assert client._config.run_id == "explicit-run"

    def test_strips_trailing_slash(self):
        client = JackpotRegisterClient(
            api_url="https://api.x/",
            run_id="r",
            pipeline_token="t",  # noqa: S106
        )
        assert client._config.api_url == "https://api.x"


class TestRegisterResult:
    def test_success_returns_json(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["headers"] = dict(request.headers)
            captured["body"] = request.content.decode()
            return httpx.Response(201, json={"status": "registered", "result_id": 42})

        client = _client(httpx.MockTransport(handler))
        result = client.register_result("pangolin_results", {"sample_id": "AZ-1"})
        assert result == {"status": "registered", "result_id": 42}
        assert captured["url"] == "http://api.test/api/v1/pipelines/run-abc/results/pangolin_results"
        assert captured["headers"]["x-pipeline-token"] == "tok-xyz"

    def test_requires_result_type(self):
        client = _client(httpx.MockTransport(lambda r: httpx.Response(200, json={})))
        with pytest.raises(RegistrationError, match="result_type"):
            client.register_result("", {"sample_id": "AZ-1"})

    def test_4xx_raises_immediately(self):
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(401, json={"error": "bad token"})

        sleep = MagicMock()
        client = _client(httpx.MockTransport(handler), sleep=sleep)
        with pytest.raises(RegistrationError) as excinfo:
            client.register_result("pangolin_results", {"sample_id": "AZ-1"})
        assert excinfo.value.status_code == 401
        assert calls == 1
        sleep.assert_not_called()

    def test_5xx_retries_then_succeeds(self):
        responses = iter(
            [
                httpx.Response(503, text="unavailable"),
                httpx.Response(500, text="boom"),
                httpx.Response(201, json={"status": "registered", "result_id": 7}),
            ]
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return next(responses)

        sleep = MagicMock()
        client = _client(httpx.MockTransport(handler), sleep=sleep)
        result = client.register_result("amr_results", {"sample_id": "AZ-2"})
        assert result["result_id"] == 7
        # Two backoffs (after the first and second 5xx)
        assert sleep.call_count == 2
        # Exponential: 1, then 2
        assert sleep.call_args_list[0][0][0] == pytest.approx(1.0)
        assert sleep.call_args_list[1][0][0] == pytest.approx(2.0)

    def test_5xx_exhausted_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="nope")

        client = _client(httpx.MockTransport(handler), sleep=MagicMock())
        with pytest.raises(RegistrationError) as excinfo:
            client.register_result("amr_results", {"sample_id": "AZ-3"})
        assert excinfo.value.status_code == 503

    def test_http_error_retries(self):
        attempts = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise httpx.ConnectError("refused")
            return httpx.Response(201, json={"status": "registered", "result_id": 1})

        client = _client(httpx.MockTransport(handler), sleep=MagicMock())
        result = client.register_result("pangolin_results", {"sample_id": "AZ-4"})
        assert result["result_id"] == 1

    def test_convenience_wrapper(self, monkeypatch):
        monkeypatch.setenv("JACKPOT_API_URL", "http://api.test")
        monkeypatch.setenv("JACKPOT_RUN_ID", "run-env")
        monkeypatch.setenv("JACKPOT_PIPELINE_TOKEN", "tok-env")

        def handler(request: httpx.Request) -> httpx.Response:
            assert "run-env" in str(request.url)
            return httpx.Response(201, json={"status": "registered", "result_id": 99})

        transport = httpx.MockTransport(handler)
        # Monkeypatch httpx.Client to use our transport
        real_init = httpx.Client.__init__

        def fake_init(self, *args, **kwargs):
            kwargs["transport"] = transport
            real_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.Client, "__init__", fake_init)
        result = register_result("pangolin_results", {"sample_id": "AZ-9"})
        assert result["result_id"] == 99
