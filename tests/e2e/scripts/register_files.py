#!/usr/bin/env python3
"""E-1 — bulk-register paired-end FASTQs as ``file://`` references.

Walks a directory, pairs files by the conventional ``_R1`` / ``_R2``
suffix, and posts each pair to ``/api/v1/ingest/register`` with the
sample_id read from the parent directory name (or ``--sample-id-prefix
+ sequence number`` if a flat directory is supplied).

Only usable in local mode — ``file://`` URIs are rejected by the
``/register`` endpoint when ``settings.env != "local"`` (R-1 #2).

Usage
-----
    register_files.py <fastq_dir> [--sample-id-prefix PFX] [--lab-id LAB]

Successful output
-----------------
One line per registered pair::

    ✓ E1-SMOKE-001 → 2 sample_files rows (storage_state=EXTERNAL)

Exit codes
----------
- ``0``  every pair registered without error
- ``1``  one or more pairs failed; failures printed to stderr
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

_R1_RE = re.compile(r"(.*)_R1(\..*)$")


def _api_post(path: str, body: dict) -> dict:
    base = os.environ.get("JACKPOT_API_URL", "http://localhost:8000").rstrip("/")
    req = urllib.request.Request(  # noqa: S310 - dev helper, local URL only
        f"{base}{path}",
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read().decode() or "{}")


def _pair_directory(root: Path) -> list[tuple[str, Path, Path]]:
    pairs: list[tuple[str, Path, Path]] = []
    for r1 in sorted(root.rglob("*_R1*.fastq*")):
        m = _R1_RE.match(r1.name)
        if not m:
            continue
        r2 = r1.with_name(f"{m.group(1)}_R2{m.group(2)}")
        if not r2.exists():
            continue
        sample_id = r1.parent.name if r1.parent != root else m.group(1)
        pairs.append((sample_id, r1, r2))
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("fastq_dir", type=Path)
    parser.add_argument("--sample-id-prefix", default=None)
    parser.add_argument("--lab-id", type=int, default=1)
    args = parser.parse_args()

    if not args.fastq_dir.is_dir():
        print(f"not a directory: {args.fastq_dir}", file=sys.stderr)
        sys.exit(1)

    pairs = _pair_directory(args.fastq_dir.resolve())
    if not pairs:
        print(f"no _R1/_R2 pairs found under {args.fastq_dir}", file=sys.stderr)
        sys.exit(1)

    failures: list[str] = []
    for idx, (auto_sample_id, r1, r2) in enumerate(pairs, start=1):
        sample_id = f"{args.sample_id_prefix}{idx:03d}" if args.sample_id_prefix else auto_sample_id
        body = {
            "sample_metadata": {
                "sample_id": sample_id,
                "lab_id": args.lab_id,
            },
            "files": [
                {"role": "fastq_r1", "uri": f"file://{r1}"},
                {"role": "fastq_r2", "uri": f"file://{r2}"},
            ],
        }
        try:
            payload = _api_post("/api/v1/ingest/register", body)
            count = len(payload.get("files", []))
            print(f"✓ {sample_id} → {count} sample_files rows (storage_state=EXTERNAL)")
        except urllib.error.HTTPError as exc:
            err = exc.read().decode(errors="replace")
            failures.append(f"{sample_id}: HTTP {exc.code}: {err}")
            print(f"✗ {sample_id} failed", file=sys.stderr)

    if failures:
        for f in failures:
            print(f, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
