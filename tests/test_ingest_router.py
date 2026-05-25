"""R-1 #2 — URI scheme allowlist on POST /api/v1/ingest/register.

The /register endpoint accepts a list of file URIs, each of which is
fingerprinted via :func:`backend.file_fingerprint.cheap_fingerprint`
(httpx for http/https, local read for file:// and bare paths). Without
a scheme allowlist, any authenticated user could (a) trigger SSRF into
internal infrastructure (cloud metadata service, internal admin
endpoints) or (b) read arbitrary local files on the API container.

Allowlisted schemes: gs, s3, sra. file:// is permitted only when
``settings.env == "local"`` (the brief's option (b) — a non-production
gate, not a silent bypass) so the F-6 local-dev workflow keeps working.

The rejection cases are exercised as direct unit tests of
:func:`_validate_register_uri_scheme` so they don't depend on the
auth path's ``env == "local"`` mock-user fallback. One HTTP
integration test confirms a rejection surfaces as a 400 response.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.config import get_settings
from backend.routers import ingest as ingest_module
from backend.routers.ingest import _validate_register_uri_scheme


def _minimal_metadata(sample_id: str) -> dict:
    return {
        "sample_id": sample_id,
        "organism_name": "Severe acute respiratory syndrome coronavirus 2",
        "source_type": "Human",
        "date_collected": "2026-01-15",
        "date_collected_precision": "day",
        "date_sequenced": "2026-01-17",
        "collection_location_country": "United States",
        "collection_location_state": "California",
        "sequencing_platform": "Illumina",
        "sequencing_lab": "Example Sequencing Lab",
        "type_of_experiment": "WGS",
        "library_preparation_method": "ARTIC",
        "nucleic_acid_extraction_method": ["QIAamp DSP Viral RNA"],
        "sequencing_protocol": "https://www.protocols.io/view/artic-v4-1",
        "collection_facility": "Example Hospital",
        "purpose_for_collection": ["clinical"],
        "sharing_level": "PRIVATE",
        "external_case_id": "CASE-R1-2-001",
        "biospecimen_type": "nasopharyngeal_swab",
        "reason_for_collection": ["clinical"],
        "host_disease": ["covid-19"],
        "project_id": 1,
        "lab_id": 1,
    }


@pytest.fixture
def strict_uri_allowlist(monkeypatch):
    """Force the local-dev gate off so file:// is rejected like in
    production. Avoids flipping ENV away from "local" (which would
    break the mock-user auth path)."""
    monkeypatch.setattr(ingest_module, "_REGISTER_LOCAL_DEV_URI_SCHEMES", frozenset())
    yield


def _assert_unsupported_scheme_400(exc: HTTPException) -> None:
    assert exc.status_code == 400
    detail = exc.detail
    assert isinstance(detail, str)
    assert "Unsupported URI scheme" in detail
    # Defense in depth: rejected scheme not echoed verbatim.
    assert "gs://" in detail
    assert "s3://" in detail
    assert "sra://" in detail


# ─────────────────────── strict-mode rejections (unit) ──────────────────


def test_register_rejects_http_uri(strict_uri_allowlist):
    """SSRF vector: http:// would resolve through httpx to internal
    infrastructure (cloud metadata, admin endpoints). Reject."""
    with pytest.raises(HTTPException) as exc_info:
        _validate_register_uri_scheme("http://internal-host/admin")
    _assert_unsupported_scheme_400(exc_info.value)


def test_register_rejects_https_uri(strict_uri_allowlist):
    with pytest.raises(HTTPException) as exc_info:
        _validate_register_uri_scheme("https://internal-host/x")
    _assert_unsupported_scheme_400(exc_info.value)


def test_register_rejects_file_uri(strict_uri_allowlist):
    """In production (strict mode), file:// must be rejected to block
    arbitrary local-file read on the API container."""
    with pytest.raises(HTTPException) as exc_info:
        _validate_register_uri_scheme("file:///etc/passwd")
    _assert_unsupported_scheme_400(exc_info.value)


def test_register_rejects_bare_path(strict_uri_allowlist):
    """Bare paths (no scheme) resolve as local-file reads via httpx
    follow-redirects defaults; reject."""
    with pytest.raises(HTTPException) as exc_info:
        _validate_register_uri_scheme("/etc/passwd")
    _assert_unsupported_scheme_400(exc_info.value)


def test_register_rejects_data_uri(strict_uri_allowlist):
    """Defense in depth — data: URIs would inline arbitrary bytes
    bypassing the URI-as-reference contract."""
    with pytest.raises(HTTPException) as exc_info:
        _validate_register_uri_scheme("data:text/plain;base64,QUFB")
    _assert_unsupported_scheme_400(exc_info.value)


# ─────────────────────── strict-mode acceptance ──────────────────────────


def test_register_accepts_gs_uri(strict_uri_allowlist):
    """gs:// is in the allowlist; validator returns silently."""
    _validate_register_uri_scheme("gs://example-bucket/test.fastq.gz")


def test_register_accepts_s3_uri(strict_uri_allowlist):
    _validate_register_uri_scheme("s3://example-bucket/test.fastq.gz")


def test_register_accepts_sra_uri(strict_uri_allowlist):
    _validate_register_uri_scheme("sra://SRR12345")


# ─────────────────────── local-dev gate: file:// allowed ─────────────────


def test_register_file_uri_allowed_in_local_env():
    """When settings.env == "local" (the test default), file:// passes
    the scheme allowlist so the F-6 local-dev workflow keeps working.
    The existing test_ingest_register.py tests rely on this gate."""
    assert get_settings().env == "local"
    # Should not raise — file is in _REGISTER_LOCAL_DEV_URI_SCHEMES
    # and env == "local".
    _validate_register_uri_scheme("file:///tmp/anything.fastq")


# ─────────────────────── HTTP integration ────────────────────────────────


@pytest.mark.asyncio
async def test_register_rejects_unsupported_scheme_with_400(client, strict_uri_allowlist):
    """End-to-end check: a rejected scheme bubbles up to a 400 response
    with the structured error envelope, before any DB row is written."""
    resp = await client.post(
        "/api/v1/ingest/register",
        json={
            "sample_metadata": _minimal_metadata("R1-HTTP-INTEGRATION"),
            "files": [{"role": "R1", "uri": "http://169.254.169.254/latest"}],
        },
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    # main.py's HTTPException → envelope handler puts a string detail
    # under error.message (and the dict-shaped path puts it under
    # error.detail). The string-detail path applies here.
    assert "Unsupported URI scheme" in body["error"]["message"]
