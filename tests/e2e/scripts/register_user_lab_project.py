#!/usr/bin/env python3
"""E-1 — create a user, lab, and project as Platform Admin.

Used by the UAT setup phase to lay down the multi-role substrate. Calls
the public REST API (no internal Python imports), so it works against
either the dev container or a remote deployment that is configured for
the same operator.

Usage
-----
    register_user_lab_project.py <name> <role> [--lab-name LAB] [--project-name PROJECT]

Arguments
---------
- ``name``  — display name for the new user (the email is generated
  as ``<slug>@example.org`` if ``--email`` is omitted).
- ``role``  — one of: Platform Admin, Lab Director, Lab Collaborator,
  Lab Reader, Bioinformatics User, Data Analyst.

Successful output
-----------------
JSON to stdout with the created user, lab, and project rows::

    {"user": {"id": 7, ...}, "lab": {"id": 3, ...}, "project": {"id": 5, ...}}

Exit codes
----------
- ``0``  full chain succeeded
- ``1``  argument error or HTTP error from the API
- ``2``  the script could not authenticate as Platform Admin to begin
  with (run ``dev_login.sh admin@example.org "Platform Admin"`` first)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-") or "user"


def _api_call(method: str, path: str, body: dict | None = None) -> dict:
    base = os.environ.get("JACKPOT_API_URL", "http://localhost:8000").rstrip("/")
    url = f"{base}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(  # noqa: S310 - dev helper, local URL only
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            payload = resp.read().decode()
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        print(f"HTTP {exc.code} on {method} {path}: {body_text}", file=sys.stderr)
        sys.exit(1)
    return json.loads(payload) if payload else {}


def _ensure_platform_admin() -> None:
    body = _api_call(
        "POST",
        "/api/v1/auth/dev-login",
        {"email": "admin@example.org", "role": "Platform Admin"},
    )
    if body.get("instance_preset") != "instance_administrator":
        print("could not switch to Platform Admin via dev-login", file=sys.stderr)
        sys.exit(2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name")
    parser.add_argument(
        "role",
        choices=[
            "Platform Admin",
            "Lab Director",
            "Lab Collaborator",
            "Lab Reader",
            "Bioinformatics User",
            "Data Analyst",
        ],
    )
    parser.add_argument("--email")
    parser.add_argument("--lab-name", default=None)
    parser.add_argument("--project-name", default=None)
    args = parser.parse_args()

    _ensure_platform_admin()

    email = args.email or f"{_slug(args.name)}@example.org"
    lab_role_set = {
        "Lab Director",
        "Lab Collaborator",
        "Lab Reader",
        "Bioinformatics User",
    }
    out: dict = {}
    if args.role in lab_role_set:
        lab_name = args.lab_name or f"{args.name} Lab"
        lab = _api_call(
            "POST",
            "/api/v1/labs",
            {"display_name": lab_name, "description": "E-1 UAT scaffold lab"},
        )
        lab_id = lab.get("id") or lab.get("lab_id")
        out["lab"] = lab

        project_name = args.project_name or f"{args.name} Project"
        project = _api_call(
            "POST",
            "/api/v1/projects",
            {
                "lab_id": lab_id,
                "display_name": project_name,
                "description": "E-1 UAT scaffold project",
                "pathogen_scope": ["Severe acute respiratory syndrome coronavirus 2"],
            },
        )
        out["project"] = project
    else:
        lab_id = None

    user = _api_call(
        "POST",
        "/api/v1/auth/dev-login",
        {
            "email": email,
            "name": args.name,
            "role": args.role,
            **({"lab_id": lab_id} if lab_id is not None else {}),
        },
    )
    out["user"] = user

    json.dump(out, sys.stdout, indent=2, default=str)
    print()


if __name__ == "__main__":
    main()
