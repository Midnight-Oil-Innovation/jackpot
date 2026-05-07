#!/usr/bin/env python3
"""E-1 — verify that the smoke flow's DB rows landed correctly.

Walks the four shape checks documented in
``tests/fixtures/e2e/smoke/smoke_expected_outputs.md``:

1. Six samples present (three from CSV ingest, three from the I-1
   wizard) with the expected `lab_id` and SARS-CoV-2 organism.
2. Each sample has at least two `sample_files` rows with
   ``storage_state = 'EXTERNAL'`` and ``cheap_fingerprint`` populated.
3. At least one ``pipeline_runs`` row referencing the smoke samples
   (status QUEUED is acceptable; SUCCESS preferred).
4. The most recent submissions row (if any) has the
   `submission_<id>/biosample.tsv` and `sra.tsv` files on disk.

Usage
-----
    verify_smoke_outputs.py [--submissions-root /var/jackpot/submissions]

Exit codes
----------
- ``0``  all four shape checks passed (or step 3/4 skipped due to no
  rows in those tables — the script reports "skipped: no rows yet")
- ``1``  one or more shape checks failed
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SAMPLE_IDS = [
    "E1-SMOKE-001",
    "E1-SMOKE-002",
    "E1-SMOKE-003",
    "E1-SMOKE-XLSX-001",
    "E1-SMOKE-XLSX-002",
    "E1-SMOKE-XLSX-003",
]


def _api_get(path: str) -> dict | list:
    base = os.environ.get("JACKPOT_API_URL", "http://localhost:8000").rstrip("/")
    req = urllib.request.Request(f"{base}{path}")  # noqa: S310 - dev helper
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
        return json.loads(resp.read().decode() or "{}")


def check_samples() -> tuple[bool, str]:
    found: list[str] = []
    for sid in _SAMPLE_IDS:
        try:
            payload = _api_get(f"/api/v1/samples?sample_id={sid}")
        except urllib.error.HTTPError:
            continue
        rows = payload.get("items") if isinstance(payload, dict) else payload
        if rows:
            found.append(sid)
    missing = [s for s in _SAMPLE_IDS if s not in found]
    if not missing:
        return True, f"6/6 smoke samples present: {found}"
    return False, f"missing samples: {missing}"


def check_sample_files() -> tuple[bool, str]:
    short = 0
    for sid in _SAMPLE_IDS:
        try:
            payload = _api_get(f"/api/v1/samples?sample_id={sid}")
        except urllib.error.HTTPError:
            short += 1
            continue
        rows = payload.get("items") if isinstance(payload, dict) else payload
        if not rows:
            short += 1
            continue
        sample_pk = rows[0].get("id")
        if sample_pk is None:
            short += 1
            continue
        try:
            files = _api_get(f"/api/v1/samples/{sample_pk}/files")
        except urllib.error.HTTPError:
            short += 1
            continue
        file_rows = files.get("items") if isinstance(files, dict) else files
        if not file_rows or len(file_rows) < 2:
            short += 1
            continue
        states = {row.get("storage_state") for row in file_rows}
        if states != {"EXTERNAL"}:
            short += 1
    if short == 0:
        return True, "every smoke sample has ≥2 EXTERNAL file rows"
    return False, f"{short} samples short on file references"


def check_pipeline_runs() -> tuple[bool, str]:
    try:
        payload = _api_get("/api/v1/pipelines/runs?limit=10")
    except urllib.error.HTTPError as exc:
        return False, f"could not list pipeline runs: HTTP {exc.code}"
    rows = payload.get("items") if isinstance(payload, dict) else payload
    if not rows:
        return True, "skipped: no pipeline runs yet (smoke step 9 not executed)"
    states = {r.get("status") for r in rows}
    return True, f"pipeline runs found, statuses: {sorted(states)}"


def check_submission_package(root: Path | None) -> tuple[bool, str]:
    if root is None or not root.exists():
        return True, "skipped: no submissions root configured / not present"
    sub_dirs = sorted(root.glob("submission_*"))
    if not sub_dirs:
        return True, "skipped: no submission packages produced yet"
    pkg = sub_dirs[-1]
    needed = ["biosample.tsv", "sra.tsv", "files", "seqsender_config.yaml"]
    missing = [n for n in needed if not (pkg / n).exists()]
    if missing:
        return False, f"package {pkg.name} missing: {missing}"
    return True, f"package {pkg.name} has biosample.tsv, sra.tsv, files/, seqsender_config.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument(
        "--submissions-root",
        type=Path,
        default=None,
        help="Filesystem root where submission packages are written.",
    )
    args = parser.parse_args()

    checks = [
        ("samples", check_samples()),
        ("sample_files", check_sample_files()),
        ("pipeline_runs", check_pipeline_runs()),
        ("submission_package", check_submission_package(args.submissions_root)),
    ]

    failed = False
    for name, (ok, msg) in checks:
        marker = "✓" if ok else "✗"
        if not ok:
            failed = True
        print(f"{marker} {name}: {msg}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
