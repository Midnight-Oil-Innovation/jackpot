#!/usr/bin/env python3
"""scripts/pull_phinvads.py — snapshot PHIN VADS vocabularies before the sunset.

CDC sunsets **all PHIN systems on November 30, 2026** and has named no successor
(https://www.cdc.gov/phin/php/sunset/). After that date the PHIN VADS-authored
value sets are not re-fetchable from anywhere, so this is a one-way door: the
acquisition has a deadline, the integration does not. This script does the
acquisition and nothing else — nothing in the backend reads the output yet.

WHAT IS PULLED, AND WHY THAT LINE
---------------------------------
Three things die with the service and two do not, so the scope is drawn on
authorship rather than on usefulness:

  value_sets.ndjson.gz   All ~1,999 ValueSet resources, concepts included.
                         This is the CDC-authored curation — the reason to
                         snapshot at all. A value set names an external code
                         system by OID and enumerates only the subset in scope.

  code_systems.ndjson.gz Metadata for all ~221 CodeSystems with the ``concept``
                         list stripped. Small, and it is what tells you which
                         terminology an OID in a value set's ``compose.include``
                         refers to.

  code_system_concepts/  Full concept lists for PHIN-authored code systems only
                         (OID under ``2.16.840.1.114222``, the CDC arc).

Full concept lists for LOINC, SNOMED CT, ICD-10-CM and friends are deliberately
NOT pulled. They are not PHIN VADS content: they outlive the sunset, come from
their own publishers, and carry their own redistribution terms — SNOMED CT in
particular requires an affiliate license, which is not a thing to vendor into an
AGPL-3.0 repository by accident. They are also large enough to be their own
problem: SNOMED CT is 47 MB of JSON from this API, LOINC 15 MB, ICD-10-CM 10 MB.

PAGINATION
----------
The FHIR STU3 endpoint returns 5 resources per bundle (``restws.valueset
.threshold``, server-side, not a client parameter) and pages with an opaque
``_getpages`` token on a ``next`` link. So ~400 sequential requests for the value
sets. There is no bulk export.

A failed run restarts from the beginning. The per-request retry ladder is the
defence against the 502 a long serial walk against a government host will
eventually meet; a whole-walk resume is deliberately not built, because it would
have to append to a half-written archive and recount it, and an append onto a
truncated file produces a corrupt snapshot that looks exactly like a good one —
the failure mode this module's tests exist to prevent. A full re-run is ~15
minutes.

USAGE
-----
    uv run python scripts/pull_phinvads.py --out schema/schema/phinvads
    uv run python scripts/pull_phinvads.py --out /tmp/probe --limit 3   # smoke
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://phinvads.cdc.gov/baseStu3"

#: The site's WAF rejects requests without a browser-shaped User-Agent — the
#: default httpx one gets a "Request Rejected" interstitial with HTTP 200, which
#: is why `_get` validates the content type rather than trusting the status code.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)

#: OID arc for CDC/PHIN-authored code systems. Concepts under this arc vanish
#: with the service; everything else has a publisher that outlives it.
PHIN_OID_PREFIX = "2.16.840.1.114222"

REQUEST_TIMEOUT = 120.0
RETRY_DELAYS = (2, 8, 30)
POLITE_DELAY = 0.4


class PullError(RuntimeError):
    """A request failed in a way retrying will not fix."""


# ------------------------------------------------------------------ http


def _get(client: httpx.Client, url: str) -> dict[str, Any]:
    """GET one JSON resource, retrying transient failures.

    Rejects non-JSON responses explicitly: the WAF answers with HTTP 200 and an
    HTML "Request Rejected" page, so status code alone does not mean success.
    """
    last_error: Exception | None = None
    for delay in (*RETRY_DELAYS, None):
        try:
            response = client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type:
                raise PullError(
                    f"{url} returned {content_type!r}, not JSON — "
                    f"first bytes: {response.text[:120]!r}"
                )
            return response.json()
        except (httpx.HTTPError, PullError, json.JSONDecodeError) as exc:
            last_error = exc
            if delay is None:
                break
            print(f"  retry in {delay}s after {type(exc).__name__}: {exc}", file=sys.stderr)
            time.sleep(delay)
    raise PullError(
        f"GET {url} failed after {len(RETRY_DELAYS)} retries: {last_error}"
    ) from last_error


def _next_url(bundle: dict[str, Any]) -> str | None:
    for link in bundle.get("link") or []:
        if link.get("relation") == "next":
            return link.get("url")
    return None


def walk_bundle(
    client: httpx.Client,
    start_url: str,
    *,
    limit: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield every resource from a paged FHIR searchset bundle.

    Following every ``next`` link is the whole job: a walk that stops at the
    first page returns five resources and reports success.
    """
    url: str | None = start_url
    pages = 0
    while url:
        bundle = _get(client, url)
        for entry in bundle.get("entry") or []:
            resource = entry.get("resource")
            if resource:
                yield resource
        url = _next_url(bundle)
        pages += 1
        if limit is not None and pages >= limit:
            return
        if url:
            time.sleep(POLITE_DELAY)


# ------------------------------------------------------------------ pull


def _oid(resource: dict[str, Any]) -> str:
    """The bare OID for a resource. ``id`` is the OID on this server."""
    return str(resource.get("id") or "")


def is_phin_authored(resource: dict[str, Any]) -> bool:
    """True when a code system's concepts die with the service.

    Matches the CDC arc on an OID-component boundary — ``2.16.840.1.1142229``
    would be a different arc, and startswith alone would admit it.
    """
    oid = _oid(resource)
    return oid == PHIN_OID_PREFIX or oid.startswith(PHIN_OID_PREFIX + ".")


def _write_ndjson(path: Path, resources: Iterable[dict[str, Any]], label: str) -> int:
    """Stream resources to a gzipped NDJSON file, one JSON object per line.

    Gzipped because the raw value sets are ~84 MB, which is a permanent addition
    to every clone of the repository forever, and GitHub starts warning at 50 MB
    per file. JSON compresses about tenfold. NDJSON survives it: the file still
    streams a record at a time through ``gzip.open``.
    """
    count = 0
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as handle:
        for resource in resources:
            handle.write(json.dumps(resource, separators=(",", ":"), sort_keys=True) + "\n")
            count += 1
            if count % 100 == 0:
                print(f"  {label}: {count}", flush=True)
    return count


def pull(out_dir: Path, *, limit: int | None = None) -> dict[str, Any]:
    """Pull the snapshot into ``out_dir`` and return the manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    concepts_dir = out_dir / "code_system_concepts"
    concepts_dir.mkdir(exist_ok=True)

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    manifest: dict[str, Any] = {
        "source": BASE_URL,
        "pulled_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sunset_date": "2026-11-30",
        "note": (
            "Snapshot of CDC PHIN VADS taken before the November 30, 2026 sunset of all "
            "PHIN systems. Concept lists for non-PHIN code systems (LOINC, SNOMED CT, "
            "ICD-*) are deliberately excluded — see scripts/pull_phinvads.py."
        ),
        "files": {},
    }

    with httpx.Client(headers=headers, timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        print("value sets...", flush=True)
        value_sets_path = out_dir / "value_sets.ndjson.gz"
        n_value_sets = _write_ndjson(
            value_sets_path,
            walk_bundle(client, f"{BASE_URL}/ValueSet", limit=limit),
            "value sets",
        )

        print("code systems...", flush=True)
        systems = list(walk_bundle(client, f"{BASE_URL}/CodeSystem", limit=limit))
        code_systems_path = out_dir / "code_systems.ndjson.gz"
        n_code_systems = _write_ndjson(
            code_systems_path,
            (dict(system, concept=[], count=system.get("count")) for system in systems),
            "code systems",
        )

        phin_systems = [system for system in systems if is_phin_authored(system)]
        print(f"PHIN-authored concept lists: {len(phin_systems)} of {len(systems)}", flush=True)
        for system in phin_systems:
            oid = _oid(system)
            target = concepts_dir / f"{oid}.json.gz"
            if target.exists():
                continue
            full = _get(client, f"{BASE_URL}/CodeSystem/{oid}")
            with gzip.open(target, "wt", encoding="utf-8", compresslevel=9) as handle:
                handle.write(json.dumps(full, separators=(",", ":"), sort_keys=True))
            print(f"  {oid} ({full.get('name')}): {full.get('count')} concepts", flush=True)
            time.sleep(POLITE_DELAY)

    for path in (value_sets_path, code_systems_path):
        with path.open("rb") as handle:
            manifest["files"][path.name] = {
                "sha256": hashlib.file_digest(handle, "sha256").hexdigest(),
                "bytes": path.stat().st_size,
            }
    manifest["counts"] = {
        "value_sets": n_value_sets,
        "code_systems": n_code_systems,
        "phin_authored_concept_files": len(list(concepts_dir.glob("*.json.gz"))),
    }

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Snapshot PHIN VADS vocabularies before the 2026-11-30 sunset."
    )
    parser.add_argument("--out", type=Path, default=Path("schema/schema/phinvads"))
    parser.add_argument(
        "--limit", type=int, default=None, help="stop after N pages per bundle (smoke test)"
    )
    args = parser.parse_args(argv)

    try:
        manifest = pull(args.out, limit=args.limit)
    except PullError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(manifest["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
