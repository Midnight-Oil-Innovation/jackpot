"""The fake-gcs-server port retry must be able to fire (Critical Rule 74).

The retry exists because the host port is chosen before the container starts,
which leaves a window for something else to take it. A retry loop that cannot
fire is indistinguishable from a working one: the suite is green either way.

This caught a real dead guard. The first version of the retry wrapped only
`container.start()`, on the assumption that docker refuses a taken port. Under
colima it does not — the container starts and the symptom is a server nothing
can reach, so the loop never retried and the allocator was called exactly once.
"""

from __future__ import annotations

import http.server
import importlib.util
import socket
import threading
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

_spec = importlib.util.spec_from_file_location(
    "storage_conftest", Path(__file__).parent / "conftest.py"
)
assert _spec and _spec.loader
storage_conftest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(storage_conftest)


@pytest.fixture
def occupied_port() -> Generator[int, None, None]:
    """A host port held open for the duration of the test."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    try:
        yield sock.getsockname()[1]
    finally:
        sock.close()


def test_retry_recovers_when_the_chosen_port_is_taken(
    occupied_port: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_free_port = storage_conftest._free_host_port
    attempts: list[int] = []

    def hand_out_a_taken_port_twice() -> int:
        attempts.append(1)
        return occupied_port if len(attempts) <= 2 else real_free_port()

    monkeypatch.setattr(storage_conftest, "_free_host_port", hand_out_a_taken_port_twice)
    monkeypatch.setattr(storage_conftest, "_PROBE_TIMEOUT_SECONDS", 1.0)

    fixture: Any = storage_conftest.fake_gcs_container.__wrapped__()
    container, port = next(fixture)
    try:
        assert len(attempts) == 3, (
            f"the retry did not fire: the port allocator was called {len(attempts)}x. "
            "A collision must be detected and retried, not swallowed."
        )
        assert port != occupied_port
        assert container is not None
    finally:
        fixture.close()


class _NotFakeGcs(http.server.BaseHTTPRequestHandler):
    """A stranger on the port. Answers 404, which the old probe accepted."""

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's API
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"not fake-gcs-server")

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def port_held_by_a_stranger() -> Generator[int, None, None]:
    """A port answering HTTP 404 — reachable, but not fake-gcs-server."""
    server = http.server.HTTPServer(("127.0.0.1", 0), _NotFakeGcs)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


def test_retry_fires_when_the_port_answers_but_is_not_fake_gcs(
    port_held_by_a_stranger: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reachable port is not a correct port.

    The readiness probe is the retry's trigger, so whatever it accepts is
    treated as ours. It used to accept any 200 or 404 — this stub returns 404,
    so the fixture would have bound a stranger's port and every storage test
    would have run against it.
    """
    real_free_port = storage_conftest._free_host_port
    attempts: list[int] = []

    def hand_out_the_strangers_port_twice() -> int:
        attempts.append(1)
        return port_held_by_a_stranger if len(attempts) <= 2 else real_free_port()

    monkeypatch.setattr(storage_conftest, "_free_host_port", hand_out_the_strangers_port_twice)
    monkeypatch.setattr(storage_conftest, "_PROBE_TIMEOUT_SECONDS", 1.0)

    fixture: Any = storage_conftest.fake_gcs_container.__wrapped__()
    container, port = next(fixture)
    try:
        assert len(attempts) == 3, (
            f"the retry did not fire: allocator called {len(attempts)}x. A port that "
            "answers 404 is not fake-gcs-server and must not be accepted as ready."
        )
        assert port != port_held_by_a_stranger
        assert container is not None
    finally:
        fixture.close()
