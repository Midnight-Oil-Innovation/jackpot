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
        # Caching decorators must return the wrapped function unchanged,
        # whether used bare (@st.cache_resource) or called (@st.cache_data(ttl=...)).
        if name in {"cache_data", "cache_resource"}:

            def _cache(*ca, **ckw):
                if ca and callable(ca[0]):
                    return ca[0]
                return lambda f: f

            return _cache

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
            if name == "multiselect":
                default = kw.get("default")
                if default is not None:
                    return list(default)
                options = kw.get("options") or (a[1] if len(a) > 1 else None)
                return list(options) if options else []
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
    "frontend.pages.wastewater",
    "frontend.pages.wastewater_multi_target",
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


# ---------------------------------------------------------------------------
# M2-DROP-PRE slice 6 — the frontend stops asking "are you an admin?"
# ---------------------------------------------------------------------------


def test_incoming_requests_renders_for_a_non_director(stubbed_streamlit, monkeypatch):
    """The approver tab must not gate on directorship or the admin flag.

    ``GET /sample-access/requests`` already scopes to what the caller can
    approve (M2-B7). The pre-filter this replaces returned early for anyone
    who was neither a Lab Director nor a platform admin, so a principal
    holding ``access:approve_request`` through a grant never reached the
    request. Identity here holds neither: no memberships, no legacy flag.
    """
    client = FakeApiClient(
        canned={
            ("GET", "/api/v1/users/me"): {
                "id": 7,
                "email": "grantholder@example.org",
                "name": "Grant Holder",
                "lab_memberships": [],
            },
            ("GET", "/api/v1/sample-access/requests"): [
                {"id": 99, "sample_id": 42, "requester_id": 8, "requested_duration_days": 30}
            ],
        }
    )
    import frontend.lib.api as api_mod
    import frontend.lib.session as sess_mod

    monkeypatch.setattr(api_mod, "get_client", lambda: client)
    monkeypatch.setattr(sess_mod, "get_client", lambda: client)

    page = _reload_page("frontend.pages.access_requests")
    # Scoped to the explicit call: importing the page runs render(), and the
    # *other* tab issues a lab_id-free request to the same endpoint. Asserting
    # over the whole log stands on that call and passes no matter what this
    # tab does — which it did, against the pre-slice code.
    client.calls.clear()
    page._render_incoming_tab(client)

    assert client.calls == [("GET", "/api/v1/sample-access/requests", {"status": "PENDING"})], (
        "expected exactly one unfiltered request: pre-slice this was [] for a "
        "non-director, or carried a client-side lab_id filter for a director"
    )


def test_pipeline_manage_controls_follow_can_manage_not_admin(stubbed_streamlit, monkeypatch):
    """Mutate controls render from the server's per-row answer, per row.

    A caller who is not a platform admin but whose lab owns the pipeline can
    deactivate and archive it — ``_may_manage`` admits the owning lab and the
    registrant. Gating on ``is_platform_admin`` hid the controls from exactly
    that person, and showed them for every row or none.

    The identity here holds no legacy flag and no directorship, and the two
    rows disagree: the controls must follow the rows, not the caller.
    """
    client = FakeApiClient(
        canned={
            ("GET", "/api/v1/users/me"): {
                "id": 7,
                "email": "labmember@example.org",
                "name": "Lab Member",
                "lab_memberships": [{"lab_id": 1, "is_lab_director": False, "lab_name": "L1"}],
            },
            ("GET", "/api/v1/byop/pipelines"): [
                {
                    "id": 1,
                    "name": "mine",
                    "display_name": "Mine",
                    "pipeline_status": "ACTIVE",
                    "can_manage": True,
                },
                {
                    "id": 2,
                    "name": "theirs",
                    "display_name": "Theirs",
                    "pipeline_status": "ACTIVE",
                    "can_manage": False,
                },
            ],
        }
    )
    import frontend.lib.api as api_mod
    import frontend.lib.session as sess_mod

    monkeypatch.setattr(api_mod, "get_client", lambda: client)
    monkeypatch.setattr(sess_mod, "get_client", lambda: client)

    page = _reload_page("frontend.pages.pipelines")
    page._render_byop_catalog(client)

    keys = {kw.get("key") for name, _, kw in stubbed_streamlit.calls if name == "button"}
    assert {"byop.deact.1", "byop.arch.1"} <= keys, (
        "manageable row lost its controls — a non-admin who may manage sees nothing"
    )
    assert not {"byop.deact.2", "byop.arch.2"} & keys, (
        "unmanageable row offered controls the server would refuse"
    )
