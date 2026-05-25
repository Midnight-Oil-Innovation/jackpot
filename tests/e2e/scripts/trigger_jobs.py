#!/usr/bin/env python3
"""E-1 — manually invoke a JACKPOT background job.

The APScheduler runs F-4 (compute_full_content_hash), F-5
(verify_file_references), the I-2 daily embargo release, and a few
others on cron-like schedules. The UAT does not have time to wait an
hour or a day, so this script exec's the function inside the api
container and waits for it to finish.

Usage
-----
    trigger_jobs.py <job_name>

Supported jobs
--------------
- ``compute_full_content_hash``     — F-4 full-content-hash sweep
- ``verify_file_references``        — F-5 broken-file detector
- ``release_embargoed_submissions`` — I-2 embargo release
- ``run_access_request_job``        — sample-access auto-approve / expiry

Exit codes
----------
- ``0``  job completed; ``returned`` block printed to stdout
- ``1``  unknown job or runtime error
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys

_JOBS = {
    "compute_full_content_hash": "from backend.jobs import compute_full_content_hash as j",
    "verify_file_references": "from backend.jobs import verify_file_references as j",
    "release_embargoed_submissions": (
        "from backend.jobs import release_embargoed_submissions as j"
    ),
    "run_access_request_job": "from backend.jobs import run_access_request_job as j",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("job", choices=sorted(_JOBS.keys()))
    parser.add_argument(
        "--container",
        default="jackpot_api",
        help="Container name (default: jackpot_api).",
    )
    args = parser.parse_args()

    snippet = (
        f"import asyncio, json; {_JOBS[args.job]}; "
        f"r = asyncio.run(j()); print(json.dumps(r, default=str))"
    )

    cmd = [
        "docker",
        "exec",
        args.container,
        "/opt/venv/bin/python",
        "-c",
        snippet,
    ]
    print(f"→ {shlex.join(cmd)}", file=sys.stderr)
    try:
        out = subprocess.check_output(cmd, text=True)
    except subprocess.CalledProcessError as exc:
        print(f"job failed: rc={exc.returncode}", file=sys.stderr)
        if exc.output:
            print(exc.output, file=sys.stderr)
        sys.exit(1)

    last_line = out.strip().splitlines()[-1] if out.strip() else "{}"
    try:
        parsed = json.loads(last_line)
    except json.JSONDecodeError:
        print(f"job ran but produced non-JSON output:\n{out}")
        sys.exit(0)
    print(json.dumps({"job": args.job, "returned": parsed}, indent=2))


if __name__ == "__main__":
    main()
