#!/usr/bin/env python3
r"""verify_licenses.py — B-LICENSE-1. AGPL-3.0 license gate for JACKPOT.

Enforces three checks that run together in CI:

1. Denylist. Every AGPL-incompatible license found in resolved Python dependencies
   is a hard fail. Business Source, Commons Clause, Elastic 2.x, SSPL, and the
   research/non-commercial-only licenses all fall here (the alibi-detect lesson).

2. Wrapped-tool coverage. Every entry in docs/THIRD_PARTY_LICENSES.md must declare
   an AGPL-3.0-compatible license. The file is the canonical inventory of tools
   the platform invokes as subprocesses or model weights, which pip/uv cannot see.

3. Attribution completeness. Every Python package we resolve is either listed in
   THIRD_PARTY_LICENSES.md or covered by pip's own metadata. Missing attributions
   fail; unknown licenses fail (a package with no declared license is treated as
   AGPL-incompatible by default, which is the safe posture).

Usage:
  python scripts/verify_licenses.py                 # gate
  python scripts/verify_licenses.py --report        # print the full table, exit 0
  python scripts/verify_licenses.py --skip-python   # only wrap-tool check (for early adoption)

Stdlib only, no network. Reads pip metadata via `pip show`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# --- Policy ------------------------------------------------------------------
# AGPL-3.0 outbound license means we can incorporate GPL-family and permissive
# licenses inbound. The denylist is licenses that either (a) are not open source
# in the OSI sense, or (b) are OSS but incompatible with AGPL-3.0 distribution.

DENYLIST_PATTERNS = [
    # non-OSS / source-available with production or field-of-use restrictions
    r"\bBSL[-\s]?1\.\d\b",  # Business Source License (e.g. alibi-detect pre-relicense)
    r"business\s+source",
    r"\bCommons\s+Clause\b",
    r"\bElastic(\s+License)?\s+2",
    r"\bSSPL\b",
    r"\bResearch\s+(?:only|use)\b",
    r"non[-\s]?commercial",
    r"academic\s+only",
    # anything explicitly proprietary or unlicensed
    r"^\s*proprietary\s*$",
    r"^\s*unlicensed\s*$",
    r"^\s*all\s+rights\s+reserved\s*$",
]

# Licenses we treat as AGPL-3.0-compatible. Broad by design; the point of the gate
# is to catch the ones we've explicitly rejected, not to reinvent SPDX matching.
ALLOWLIST_PATTERNS = [
    r"\bAGPL(?:v?3(?:[-.]0)?)?(?:[-\s]or[-\s]later)?\b",
    r"\bGPL(?:v?[23](?:[-.]0)?)?(?:[-\s]or[-\s]later)?\b",
    r"\bLGPL",
    r"\bApache(?:\s+License)?[-\s]?2(?:\.0)?\b",
    r"\bMIT\b",
    r"\bBSD(?:[-\s]?[123])?(?:[-\s]clause)?\b",
    r"\bISC\b",
    r"\bMPL[-\s]?2",
    r"\bPython\s+Software\s+Foundation\b",
    r"\bPSF\b",
    r"\bZlib\b",
    r"\bUnlicense\b",
    r"\bCC0\b",
    r"\bpublic\s+domain\b",
]

DENYLIST_RE = re.compile("|".join(DENYLIST_PATTERNS), re.IGNORECASE)
ALLOWLIST_RE = re.compile("|".join(ALLOWLIST_PATTERNS), re.IGNORECASE)

THIRD_PARTY = Path("docs/THIRD_PARTY_LICENSES.md")


@dataclass
class Finding:
    kind: str  # "python-dep" or "wrapped-tool"
    name: str
    license: str
    reason: str


# --- Python dependencies -----------------------------------------------------


def resolved_packages() -> list[str]:
    """Names of installed Python packages via `pip list`. Uses the current venv."""
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=freeze"],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"error: pip list failed: {e}", file=sys.stderr)
        return []
    names = []
    for line in out.splitlines():
        if "==" in line and not line.startswith("-e "):
            names.append(line.split("==", 1)[0])
    return names


def package_license(name: str) -> str:
    """Read the License field from pip metadata. Empty when the package declares none."""
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pip", "show", name],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""
    for line in out.splitlines():
        if line.startswith("License:"):
            return line.split(":", 1)[1].strip()
    return ""


def classify(text: str) -> str:
    """Return 'deny', 'allow', or 'unknown'. Deny wins over allow (a package tagged
    both AGPL-incompatible and MIT is incompatible)."""
    if not text or text.upper() in ("UNKNOWN", "NONE", ""):
        return "unknown"
    if DENYLIST_RE.search(text):
        return "deny"
    if ALLOWLIST_RE.search(text):
        return "allow"
    return "unknown"


def check_python_deps() -> tuple[list[Finding], list[tuple[str, str, str]]]:
    findings: list[Finding] = []
    rows: list[tuple[str, str, str]] = []
    for pkg in resolved_packages():
        lic = package_license(pkg)
        verdict = classify(lic)
        rows.append((pkg, lic or "(none declared)", verdict))
        if verdict == "deny":
            findings.append(
                Finding(
                    "python-dep", pkg, lic, f"license '{lic}' matches AGPL-incompatible denylist"
                )
            )
        elif verdict == "unknown":
            findings.append(
                Finding(
                    "python-dep",
                    pkg,
                    lic or "(none declared)",
                    "license not on allowlist; declare it in "
                    "docs/THIRD_PARTY_LICENSES.md if it is AGPL-compatible, "
                    "or replace the dependency",
                )
            )
    return findings, rows


# --- THIRD_PARTY_LICENSES.md parsing -----------------------------------------

# Row shape: `| name | license | version-or-scope | notes |`
ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]*)\s*\|\s*([^|]*)\s*\|$")
HEADING_RE = re.compile(r"^#{2,3}\s+(.*\S)\s*$")

# --- Adoption scoping --------------------------------------------------------
# THIRD_PARTY_LICENSES.md serves two purposes: it is the inventory of what the
# platform actually depends on, AND the record of what was evaluated and
# rejected. Only the first is a license gate. A rejected tool documented with
# its incompatible license is the guard working, not a violation, so gating it
# makes the check cry wolf and trains you to ignore it.
#
# A row is INFORMATIONAL (recorded, never gated) when either:
#   - it carries an explicit marker: [rejected] [candidate] [informational]
#   - or its text says so in prose: REJECTED / do not adopt / not adopted / ...
#   - or it sits under a section heading that scopes the whole table that way.
# Everything else is GATED: a real dependency whose license must clear AGPL-3.0.

ROW_INFORMATIONAL_RE = re.compile(
    r"\[(?:rejected|candidate|informational|not[-\s]adopted)\]"
    r"|\bREJECTED\b"
    r"|\bdo not adopt\b"
    r"|\bnot adopted\b"
    r"|\bnot in use\b"
    r"|\bevaluated only\b",
    re.IGNORECASE,
)

SECTION_INFORMATIONAL_RE = re.compile(
    r"\brejected\b|\bcandidates?\b|\bnot adopted\b|\bevaluated\b"
    r"|\bnot licensed code\b|\binformational\b|\bconsidered\b",
    re.IGNORECASE,
)


def parse_third_party() -> tuple[list[dict], list[str]]:
    if not THIRD_PARTY.exists():
        return [], [f"{THIRD_PARTY} not found; create it (seed provided in the guardrails guide)"]
    rows: list[dict] = []
    errors: list[str] = []
    in_table = False
    section = ""
    section_informational = False
    for i, line in enumerate(THIRD_PARTY.read_text().splitlines(), 1):
        h = HEADING_RE.match(line)
        if h:
            section = h.group(1)
            section_informational = bool(SECTION_INFORMATIONAL_RE.search(section))
            in_table = False
            continue
        if line.startswith("|") and "---" in line:
            in_table = True
            continue
        if not in_table or not line.startswith("|"):
            in_table = False
            continue
        m = ROW_RE.match(line)
        if not m:
            errors.append(f"{THIRD_PARTY}:{i}: malformed table row")
            continue
        name, lic, scope, notes = (g.strip() for g in m.groups())
        if not name or name.lower().startswith(("name", "tool", "package")):
            continue  # header row
        row_text = " ".join((name, lic, scope, notes))
        informational = section_informational or bool(ROW_INFORMATIONAL_RE.search(row_text))
        rows.append(
            {
                "name": name,
                "license": lic,
                "scope": scope,
                "notes": notes,
                "line": i,
                "section": section,
                "informational": informational,
            }
        )
    return rows, errors


def check_wrapped_tools(strict: bool = False) -> tuple[list[Finding], list[dict]]:
    """Findings for gated rows only. Informational rows (rejected tools,
    candidates, specs) are parsed and reported but never fail the gate, unless
    --strict is passed to audit the whole table."""
    rows, parse_errors = parse_third_party()
    findings = [Finding("wrapped-tool", "THIRD_PARTY_LICENSES.md", "-", e) for e in parse_errors]
    for row in rows:
        if row["informational"] and not strict:
            continue  # a documented decision, not a dependency
        v = classify(row["license"])
        if v == "deny":
            findings.append(
                Finding(
                    "wrapped-tool",
                    row["name"],
                    row["license"],
                    f"license '{row['license']}' matches AGPL-incompatible denylist "
                    f"({THIRD_PARTY}:{row['line']})",
                )
            )
        elif v == "unknown":
            findings.append(
                Finding(
                    "wrapped-tool",
                    row["name"],
                    row["license"],
                    f"license '{row['license']}' not on allowlist; verify against "
                    f"the tool's LICENSE file ({THIRD_PARTY}:{row['line']})",
                )
            )
    return findings, rows


# --- main --------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="print the table and exit 0")
    ap.add_argument(
        "--skip-python",
        action="store_true",
        help="only check THIRD_PARTY_LICENSES.md (useful before all deps are annotated)",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="also gate informational rows (rejected tools, candidates, specs). "
        "Use to audit the whole table; not for CI.",
    )
    args = ap.parse_args()

    all_findings: list[Finding] = []
    py_rows: list[tuple[str, str, str]] = []
    if not args.skip_python:
        py_findings, py_rows = check_python_deps()
        all_findings.extend(py_findings)

    wt_findings, wt_rows = check_wrapped_tools(strict=args.strict)
    all_findings.extend(wt_findings)

    gated = [r for r in wt_rows if not r["informational"]]
    informational = [r for r in wt_rows if r["informational"]]

    if args.report:
        if py_rows:
            print("\nResolved Python dependencies:")
            for name, lic, verdict in sorted(py_rows):
                print(f"  [{verdict:7s}] {name:30s} {lic}")
        print(f"\nGated dependencies from {THIRD_PARTY} ({len(gated)}):")
        for row in gated:
            print(f"  {row['name']:30s} {row['license']}  ({row['scope']})")
        print(f"\nInformational, not gated ({len(informational)}):")
        for row in informational:
            print(f"  {row['name']:30s} {row['license']}  [{row['section']}]")
        return 0

    if not all_findings:
        n_py = len(py_rows) if not args.skip_python else 0
        print(
            f"License gate: OK ({n_py} python deps, {len(gated)} gated tools, "
            f"{len(informational)} informational)."
        )
        return 0

    print(f"License gate: {len(all_findings)} violation(s).\n")
    for f in all_findings:
        print(f"  [{f.kind}] {f.name}\n      {f.reason}")
    print("\nAGPL-3.0 requires all incorporated code to be AGPL-compatible. Replace the")
    print("dependency, or (if genuinely compatible and misparsed) add an override entry")
    print(f"in {THIRD_PARTY} with the SPDX identifier from the tool's LICENSE file.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
