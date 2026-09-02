"""Checks for scripts/pull_phinvads.py.

The PHIN VADS snapshot is a one-way door — CDC sunsets all PHIN systems on
2026-11-30 and named no successor — so a silently-truncated pull is the failure
that matters. It looks exactly like a successful one: a manifest, a plausible
file, and no error. Every check here is aimed at that.

No network. The FHIR server is an ``httpx.MockTransport``.
"""

from __future__ import annotations

import gzip
import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "pull_phinvads.py"
_spec = importlib.util.spec_from_file_location("pull_phinvads", _SCRIPT)
assert _spec and _spec.loader
pull_phinvads = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = pull_phinvads
_spec.loader.exec_module(pull_phinvads)

BASE = pull_phinvads.BASE_URL

#: Captured before any monkeypatch of ``httpx.Client`` — the end-to-end tests
#: replace that name, and ``client_for`` must not recurse into its own stub.
_REAL_CLIENT = httpx.Client


def bundle(resources: list[dict], next_url: str | None) -> dict:
    links = [{"relation": "self", "url": "https://example.invalid/self"}]
    if next_url:
        links.append({"relation": "next", "url": next_url})
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(resources),
        "link": links,
        "entry": [{"resource": r} for r in resources],
    }


def value_set(oid: str) -> dict:
    return {"resourceType": "ValueSet", "id": oid, "name": f"PHVS_{oid}"}


def code_system(oid: str, n_concepts: int = 3) -> dict:
    return {
        "resourceType": "CodeSystem",
        "id": oid,
        "name": f"PH_{oid}",
        "count": n_concepts,
        "concept": [{"code": str(i), "display": f"c{i}"} for i in range(n_concepts)],
    }


@pytest.fixture(autouse=True)
def _no_sleeping(monkeypatch):
    """The retry ladder is 2 + 8 + 30 seconds. Not in a unit test."""
    monkeypatch.setattr(pull_phinvads.time, "sleep", lambda _seconds: None)


def _read_ndjson_gz(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def client_for(handler) -> httpx.Client:
    return _REAL_CLIENT(transport=httpx.MockTransport(handler), follow_redirects=True)


# ----------------------------------------------------------------- pagination


def test_walk_follows_every_next_link_to_the_end():
    """Three pages of five, not the five the first page happened to carry."""
    pages = {
        f"{BASE}/ValueSet": bundle([value_set(f"a{i}") for i in range(5)], f"{BASE}/p2"),
        f"{BASE}/p2": bundle([value_set(f"b{i}") for i in range(5)], f"{BASE}/p3"),
        f"{BASE}/p3": bundle([value_set(f"c{i}") for i in range(5)], None),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=pages[str(request.url)])

    with client_for(handler) as client:
        got = list(pull_phinvads.walk_bundle(client, f"{BASE}/ValueSet"))

    assert len(got) == 15
    assert [r["id"] for r in got[:2]] == ["a0", "a1"]
    assert got[-1]["id"] == "c4"


def test_walk_checkpoints_each_page_and_signals_the_end_with_none():
    seen: list[str | None] = []
    pages = {
        f"{BASE}/ValueSet": bundle([value_set("a")], f"{BASE}/p2"),
        f"{BASE}/p2": bundle([value_set("b")], None),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=pages[str(request.url)])

    with client_for(handler) as client:
        list(pull_phinvads.walk_bundle(client, f"{BASE}/ValueSet", on_page=seen.append))

    assert seen == [f"{BASE}/p2", None]


def test_limit_stops_the_walk_early():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=bundle([value_set("x")], f"{BASE}/forever"))

    with client_for(handler) as client:
        got = list(pull_phinvads.walk_bundle(client, f"{BASE}/ValueSet", limit=4))

    assert len(got) == 4


# ----------------------------------------------------------------- the WAF


def test_html_rejection_served_as_http_200_is_not_treated_as_data():
    """The WAF answers a blocked request with 200 and an HTML page.

    Trusting the status code here would write an empty NDJSON and a manifest
    saying so, which is the shape of a successful pull.
    """
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="<html><head><title>Request Rejected</title></head></html>",
        )

    with (
        client_for(handler) as client,
        pytest.raises(pull_phinvads.PullError, match="not JSON"),
    ):
        pull_phinvads._get(client, f"{BASE}/ValueSet")

    assert len(calls) == len(pull_phinvads.RETRY_DELAYS) + 1


def test_a_transient_failure_is_retried_and_then_succeeds():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(502, text="bad gateway")
        return httpx.Response(200, json=bundle([value_set("a")], None))

    with client_for(handler) as client:
        got = pull_phinvads._get(client, f"{BASE}/ValueSet")

    assert len(calls) == 2
    assert got["entry"][0]["resource"]["id"] == "a"


# ----------------------------------------------------------------- scope line


@pytest.mark.parametrize(
    ("oid", "expected"),
    [
        ("2.16.840.1.114222", True),  # the arc root itself
        ("2.16.840.1.114222.4.5.274", True),  # a PHIN-authored code system
        ("2.16.840.1.113883.6.96", False),  # SNOMED CT
        ("2.16.840.1.113883.6.1", False),  # LOINC
        ("2.16.840.1.1142229", False),  # neighbouring arc, not a child
        ("2.16.840.1.11422", False),  # prefix of the arc, not under it
        ("", False),
    ],
)
def test_phin_authorship_matches_on_an_oid_component_boundary(oid, expected):
    """`startswith` alone admits 2.16.840.1.1142229, a different arc entirely."""
    assert pull_phinvads.is_phin_authored({"id": oid}) is expected


# ----------------------------------------------------------------- end to end


def _stub_server(value_set_pages, code_systems):
    """Serve paged ValueSet/CodeSystem bundles plus per-OID CodeSystem reads."""
    routes: dict[str, dict] = {}
    for i, page in enumerate(value_set_pages):
        url = f"{BASE}/ValueSet" if i == 0 else f"{BASE}/vs{i}"
        nxt = f"{BASE}/vs{i + 1}" if i + 1 < len(value_set_pages) else None
        routes[url] = bundle(page, nxt)
    routes[f"{BASE}/CodeSystem"] = bundle(code_systems, None)
    for system in code_systems:
        routes[f"{BASE}/CodeSystem/{system['id']}"] = system

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=routes[str(request.url)])

    return handler


def test_pull_writes_the_snapshot_with_provenance(tmp_path, monkeypatch):
    handler = _stub_server(
        value_set_pages=[[value_set("vs1"), value_set("vs2")], [value_set("vs3")]],
        code_systems=[
            code_system("2.16.840.1.114222.4.5.274", n_concepts=4),  # PHIN
            code_system("2.16.840.1.113883.6.96", n_concepts=537792),  # SNOMED
        ],
    )
    monkeypatch.setattr(pull_phinvads.httpx, "Client", lambda **_kw: client_for(handler))

    manifest = pull_phinvads.pull(tmp_path / "snap")
    out = tmp_path / "snap"

    assert manifest["counts"] == {
        "value_sets": 3,
        "code_systems": 2,
        "phin_authored_concept_files": 1,
    }
    assert manifest["sunset_date"] == "2026-11-30"
    assert manifest["source"] == BASE
    for name in ("value_sets.ndjson.gz", "code_systems.ndjson.gz"):
        assert len(manifest["files"][name]["sha256"]) == 64
        assert manifest["files"][name]["bytes"] > 0

    lines = _read_ndjson_gz(out / "value_sets.ndjson.gz")
    assert [row["id"] for row in lines] == ["vs1", "vs2", "vs3"]


def test_code_system_concepts_are_stripped_but_the_count_is_kept(tmp_path, monkeypatch):
    """The whole point of the scope line: SNOMED's 537k concepts stay out of git.

    Its metadata row must still say how many there were, or the snapshot cannot
    tell a code system that was excluded from one that was empty.
    """
    handler = _stub_server(
        value_set_pages=[[value_set("vs1")]],
        code_systems=[
            code_system("2.16.840.1.114222.4.5.274", n_concepts=4),
            code_system("2.16.840.1.113883.6.96", n_concepts=537792),
        ],
    )
    monkeypatch.setattr(pull_phinvads.httpx, "Client", lambda **_kw: client_for(handler))

    out = tmp_path / "snap"
    pull_phinvads.pull(out)

    rows = {row["id"]: row for row in _read_ndjson_gz(out / "code_systems.ndjson.gz")}
    snomed = rows["2.16.840.1.113883.6.96"]
    assert snomed["concept"] == []
    assert snomed["count"] == 537792

    concepts_dir = out / "code_system_concepts"
    assert [p.name for p in concepts_dir.glob("*.json.gz")] == ["2.16.840.1.114222.4.5.274.json.gz"]
    with gzip.open(concepts_dir / "2.16.840.1.114222.4.5.274.json.gz", "rt") as handle:
        kept = json.load(handle)
    assert len(kept["concept"]) == 4


def test_resume_state_is_cleared_only_on_a_completed_pull(tmp_path, monkeypatch):
    handler = _stub_server(
        value_set_pages=[[value_set("vs1")]],
        code_systems=[code_system("2.16.840.1.114222.4.5.274")],
    )
    monkeypatch.setattr(pull_phinvads.httpx, "Client", lambda **_kw: client_for(handler))

    out = tmp_path / "snap"
    out.mkdir()
    state = out / ".pull_state.json"
    state.write_text('{"next": "https://example.invalid/stale"}')

    pull_phinvads.pull(out, state_path=state)

    assert not state.exists()
