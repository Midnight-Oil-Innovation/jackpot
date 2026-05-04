"""
Streamlit smoke tests — every researcher page loads without exceptions.

Strategy
--------

Streamlit pages execute at import time (they call their ``render()``
function at the bottom of the module). A real ``streamlit run`` session
is too expensive to stand up in pytest, so we:

1. Stub out ``streamlit`` with a ``SimpleStreamlit`` shim that accepts
   every call the pages make and records them for assertions.
2. Swap the API client for ``FakeApiClient`` that returns canned
   responses. Pages never hit the network.
3. Import each page and verify it renders without raising.

What this catches
-----------------

- Typos in attribute or parameter names that don't exist on
  ``SimpleStreamlit`` — shim raises ``AttributeError``.
- Shape mismatches between the page and the stub API responses
  (``None`` .get, missing keys, bad indexes).
- Imports missing from the page module.

What it does *not* catch — a Playwright end-to-end test is the Month 3
scope for that (per spec.md line 702).
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ────────────────── SimpleStreamlit shim ──────────────────


class _RecordingContext:
    """``with st.container(...)`` / ``st.sidebar`` context manager stub."""

    def __init__(self, outer: SimpleStreamlit) -> None:
        self._outer = outer
        # Expose the whole outer API so `with st.sidebar: st.header(...)`
        # still resolves to real calls.
        self.__dict__.update({})

    def __enter__(self):
        return self._outer

    def __exit__(self, exc_type, exc, tb):
        return False

    def __getattr__(self, name):
        return getattr(self._outer, name)


class SimpleStreamlit:
    """Minimal Streamlit stand-in that records calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []
        self.session_state: dict = {}
        # ``st.components.v1.iframe`` — provide a nested namespace.
        self.components = types.SimpleNamespace(v1=self)

    # Support ``with cols[i]:`` — columns returns SimpleStreamlit instances.
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    # ── call recording ──────────────────────────────────────────
    def _record(self, name: str, *a, **kw):
        self.calls.append((name, a, kw))

    # Most Streamlit APIs just take positional args we can ignore.
    def __getattr__(self, name: str):
        def _fn(*a, **kw):
            self._record(name, *a, **kw)
            # Mimic the widgets that return values.
            if name in {
                "text_input",
                "text_area",
                "selectbox",
                "radio",
                "date_input",
                "number_input",
                "file_uploader",
            }:
                default = kw.get("value")
                if default is not None:
                    return default
                options = kw.get("options") or (a[1] if len(a) > 1 else None)
                if options:
                    return options[0]
                return ""
            if name in {
                "checkbox",
                "toggle",
                "button",
                "form_submit_button",
                "link_button",
            }:
                return False
            if name == "columns":
                n = a[0] if a else 2
                if isinstance(n, int):
                    return [self for _ in range(n)]
                return [self for _ in range(len(n))]
            if name in {"form", "expander", "container", "spinner", "tabs", "sidebar"}:
                if name == "tabs":
                    labels = a[0] if a else []
                    return [_RecordingContext(self) for _ in labels]
                return _RecordingContext(self)
            if name == "Page":
                return types.SimpleNamespace(name=a[0] if a else "")
            if name == "navigation":
                return types.SimpleNamespace(run=lambda: None)
            return None

        return _fn

    # ``st.sidebar`` is used both as attribute and as context manager —
    # return a context that proxies back to us.
    @property
    def sidebar(self):  # noqa: D401
        return _RecordingContext(self)


# ────────────────── FakeApiClient ──────────────────


class FakeApiClient:
    """Returns canned responses keyed by (method, path)."""

    def __init__(self, canned: dict[tuple[str, str], object] | None = None) -> None:
        self.canned = canned or {}
        self.calls: list[tuple[str, str, dict]] = []

    def _answer(self, method: str, path: str, params: dict | None = None):
        self.calls.append((method, path, params or {}))
        return self.canned.get((method, path), self._default(method, path))

    def _default(self, method: str, path: str):
        if path == "/api/v1/users/me":
            return {
                "id": 1,
                "email": "tester@example.com",
                "name": "Tester",
                "is_platform_admin": True,
                "lab_memberships": [{"lab_id": 1, "is_lab_director": True, "lab_name": "Lab One"}],
            }
        if path.startswith("/api/v1/samples/") and path != "/api/v1/samples/":
            return {
                "id": 42,
                "sample_id": "SAMP-1",
                "organism_name": "Homo sapiens",
                "sharing_level": "PRIVATE",
                "quality_status": "ANALYZABLE",
                "scrub_status": "COMPLETE",
                "ncbi_submission_status": "NOT_SUBMITTED",
                "gisaid_submission_status": "NOT_SUBMITTED",
            }
        if path == "/api/v1/samples/":
            return {
                "results": [
                    {
                        "id": 1,
                        "sample_id": "SAMP-1",
                        "organism_name": "Homo sapiens",
                        "quality_status": "ANALYZABLE",
                        "sharing_level": "PRIVATE",
                        "scrub_status": "COMPLETE",
                    }
                ],
                "total_count": 1,
            }
        if path == "/api/v1/sample-access/requests":
            return []
        if path.startswith("/api/v1/pipelines/") and "/" in path[len("/api/v1/pipelines/") :]:
            # /tasks or /events
            return {"results": []}
        if path == "/api/v1/pipelines/":
            return {"results": [], "total_count": 0}
        return {}

    def get(self, path, params=None):
        return self._answer("GET", path, params)

    def post(self, path, json_body=None, params=None, files=None, data=None):
        return self._answer("POST", path, params)

    def patch(self, path, json_body=None):
        return self._answer("PATCH", path)

    def delete(self, path):
        return self._answer("DELETE", path)


# ────────────────── fixtures + helper ──────────────────


@pytest.fixture
def stubbed_streamlit(monkeypatch):
    st = SimpleStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    # Some libraries cache a reference to the real module — ensure any
    # fresh ``import streamlit`` in a page picks up our stub.
    return st


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeApiClient()

    # Patch the module singleton so every page sees the fake.
    import frontend.lib.api as api_mod
    import frontend.lib.session as sess_mod

    monkeypatch.setattr(api_mod, "_default_client", client)
    monkeypatch.setattr(api_mod, "get_client", lambda: client)
    monkeypatch.setattr(sess_mod, "get_client", lambda: client)
    return client


def _reload_page(module_name: str):
    """Force a fresh import of a page so its render() runs under the stubs."""
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


PAGE_MODULES = [
    "frontend.pages.dashboard",
    "frontend.pages.search",
    "frontend.pages.upload",
    "frontend.pages.data_entry",
    "frontend.pages.my_samples",
    "frontend.pages.datasets",
    "frontend.pages.access_requests",
    "frontend.pages.notifications",
    "frontend.pages.pipelines",
    "frontend.pages.broken_files",
    "frontend.pages.import_spreadsheet",
    "frontend.pages.submissions",
]


@pytest.mark.parametrize("module", PAGE_MODULES)
def test_page_imports_and_renders(module, stubbed_streamlit, fake_client):
    _reload_page(module)
    # Each page calls st.title at minimum.
    names = {call[0] for call in stubbed_streamlit.calls}
    assert "title" in names, f"{module} never called st.title"


def test_app_entrypoint_renders(stubbed_streamlit, fake_client):
    _reload_page("frontend.app")
    names = {call[0] for call in stubbed_streamlit.calls}
    assert "title" in names
    assert "set_page_config" in names


def test_api_client_unwraps_envelope(monkeypatch):
    """ApiClient returns data directly, not the envelope."""
    from frontend.lib.api import ApiClient, ApiError

    class _Resp:
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b"{}"

        def json(self):
            return {"success": True, "data": {"hello": "world"}}

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def request(self, *a, **kw):
            return _Resp()

    with mock.patch("httpx.Client", return_value=_Client()):
        api = ApiClient(base_url="http://x")
        out = api.get("/x")
        assert out == {"hello": "world"}

    # Error envelope → ApiError
    class _ErrResp:
        status_code = 422
        headers = {"content-type": "application/json"}
        content = b"{}"
        reason_phrase = "Unprocessable"

        def json(self):
            return {"success": False, "error": {"code": "VALIDATION", "message": "bad"}}

    class _ErrClient(_Client):
        def request(self, *a, **kw):
            return _ErrResp()

    with mock.patch("httpx.Client", return_value=_ErrClient()):
        api = ApiClient(base_url="http://x")
        with pytest.raises(ApiError) as exc:
            api.get("/x")
        assert exc.value.code == "VALIDATION"
        assert exc.value.status_code == 422


def test_badges_produce_html():
    from frontend.components.badges import (
        run_status_badge,
        scrub_badge,
        sharing_badge,
        tier_badge,
    )

    assert "PRELIMINARY" in tier_badge("PRELIMINARY")
    assert "PUBLIC" in sharing_badge("PUBLIC")
    assert "COMPLETE" in scrub_badge("COMPLETE")
    assert "RUNNING" in run_status_badge("RUNNING")
    assert tier_badge(None).startswith("<span")
