#!/usr/bin/env python3
"""Generate docs/m2_preflight_report.md from docs/endpoint_capability_map.md.

Stdlib-only. The report is the M2 cutover session's input: the capability
proposals for every catalog-gap row (maintainer reviews/edits them — the
map itself stays untouched until cutover), the PUBLIC-verify-intent rows
awaiting sign-off, the ROUTE_LOCAL classification of auth-only rows, and
the known divergence classes mirrored from
tests/authz/preflight.py::EXPECTED_DIVERGENCES.

Run:  uv run python scripts/m2_preflight_report.py
The paired drift test (tests/authz/test_cutover_preflight.py::TestPreflightReport)
fails when the committed report is stale.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = REPO_ROOT / "docs" / "endpoint_capability_map.md"
REPORT_PATH = REPO_ROOT / "docs" / "m2_preflight_report.md"


@dataclass
class MapRow:
    method: str
    path: str
    capability: str
    scope: str
    notes: str

    @property
    def klass(self) -> str:
        if "PUBLIC" in self.notes:
            return "public"
        if self.capability == "—":
            return "catalog_gap"
        if "require_capability" in self.notes:
            return "require_capability"
        return "auth_only"

    @property
    def verify_intent(self) -> bool:
        return "verify intent" in self.notes


def parse_map(path: Path) -> list[MapRow]:
    rows: list[MapRow] = []
    for line in path.read_text().splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 5 or cells[0] in ("Method", "--------"):
            continue
        if set(cells[0]) <= {"-"}:
            continue
        rows.append(
            MapRow(
                method=cells[0],
                path=cells[1].strip("`"),
                capability=cells[2].strip("`"),
                scope=cells[3],
                notes=cells[4],
            )
        )
    return rows


# Capability PROPOSALS for the catalog-gap rows, following the §4
# domain:action convention and reusing existing verbs where one fits.
# These are proposals only — the maintainer reviews/edits this table, and
# the M2 cutover session writes the agreed values into the map + catalog.
PROPOSED_CAPABILITIES: dict[tuple[str, str], str] = {
    ("GET", "/api/v1/byop/telemetry"): "pipeline:read",
    ("GET", "/api/v1/byop/pipelines"): "pipeline:read",
    ("GET", "/api/v1/byop/pipelines/{pipeline_id}"): "pipeline:read",
    (
        "POST",
        "/api/v1/dataharmonizer/validate",
    ): "metadata:validate (new verb — stateless utility; or keep auth-only)",
    ("GET", "/api/v1/import_mappings/"): "import:read (new domain)",
    ("GET", "/api/v1/import_mappings/{mapping_id}"): "import:read (new domain)",
    ("POST", "/api/v1/import_mappings/"): "import:manage (new domain)",
    ("PATCH", "/api/v1/import_mappings/{mapping_id}"): "import:manage (new domain)",
    ("DELETE", "/api/v1/import_mappings/{mapping_id}"): "import:manage (new domain)",
    ("GET", "/api/v1/labs/"): "lab:read (new verb)",
    ("GET", "/api/v1/labs/{lab_id}"): "lab:read (new verb)",
    ("GET", "/api/v1/organizations/{org_id}"): "org:read (new verb)",
    ("GET", "/api/v1/pipelines/"): "pipeline:read",
    ("POST", "/api/v1/profiles/"): "profile:manage (new domain — execution profiles)",
    ("GET", "/api/v1/profiles/me"): "user:read_self (new verb — self-scope)",
    (
        "POST",
        "/api/v1/sample-access/requests",
    ): "access:request (new verb, pairs with access:approve_request)",
    ("GET", "/api/v1/sequencing-labs/"): "sequencing_lab:read (new domain)",
    ("GET", "/api/v1/sequencing-labs/{seq_lab_id}"): "sequencing_lab:read (new domain)",
    ("POST", "/api/v1/submissions/"): "submission:prepare (new verb)",
    ("PATCH", "/api/v1/submissions/{submission_id}"): "submission:prepare (new verb)",
    ("DELETE", "/api/v1/submissions/{submission_id}"): "submission:prepare (new verb)",
    ("POST", "/api/v1/submissions/{submission_id}/samples"): "submission:prepare (new verb)",
    ("DELETE", "/api/v1/submissions/{submission_id}/samples"): "submission:prepare (new verb)",
    ("POST", "/api/v1/submissions/{submission_id}/validate"): "submission:prepare (new verb)",
    ("POST", "/api/v1/submissions/{submission_id}/generate"): "submission:prepare (new verb)",
    ("GET", "/api/v1/tokens/"): "token:manage (new domain — self-scope resource)",
    ("POST", "/api/v1/tokens/"): "token:manage (new domain — self-scope resource)",
    ("DELETE", "/api/v1/tokens/{token_id}"): "token:manage (new domain — self-scope resource)",
    ("GET", "/api/v1/users/me"): "user:read_self (new verb — self-scope)",
}


# Rationales mirrored from tests/authz/preflight.py::EXPECTED_DIVERGENCES —
# the drift test imports both and the cutover PR body lifts this section.
# File-path import: `tests` is shadowed by the cli package's regular
# `cli/tests` package, so the dotted path is not importable here.
def _load_expected_divergences():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_preflight", REPO_ROOT / "tests" / "authz" / "preflight.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # dataclass string-annotation resolution needs the module registered.
    sys.modules["_preflight"] = mod
    spec.loader.exec_module(mod)
    return mod.EXPECTED_DIVERGENCES


EXPECTED_DIVERGENCES = _load_expected_divergences()


def generate_report(rows: list[MapRow]) -> str:
    gaps = [r for r in rows if r.klass == "catalog_gap"]
    verify = [r for r in rows if r.verify_intent]
    auth_only = [r for r in rows if r.klass == "auth_only"]
    public = [r for r in rows if r.klass == "public" and not r.verify_intent]
    wired = [r for r in rows if r.klass == "require_capability"]

    out: list[str] = []
    out.append("> **Status:** Reference — generated M2 pre-cutover checklist. Regenerate with")
    out.append("> `uv run python scripts/m2_preflight_report.py`; do not edit by hand")
    out.append("> except to tick checkboxes / annotate decisions inline in review.")
    out.append("")
    out.append("# M2 Pre-Cutover Report")
    out.append("")
    out.append(
        f"Map totals: {len(rows)} endpoints — {len(wired)} already wired to "
        f"`require_capability`, {len(auth_only)} auth-only (ROUTE_LOCAL), "
        f"{len(gaps)} catalog gaps, {len(public) + len(verify)} PUBLIC "
        f"({len(verify)} pending intent verification)."
    )
    out.append("")

    out.append("## 1. Catalog gaps — proposed capabilities (maintainer review required)")
    out.append("")
    out.append("Proposals follow the §4 `domain:action` convention; existing verbs")
    out.append("reused where one fits. Edit the proposal column in review; the M2")
    out.append("cutover session writes the agreed values into the map and the §4")
    out.append("catalog. The map file itself is deliberately untouched until then.")
    out.append("")
    out.append("| ✓ | Method | Path | Scope | Proposed capability |")
    out.append("|---|--------|------|-------|---------------------|")
    for r in gaps:
        proposal = PROPOSED_CAPABILITIES.get(
            (r.method, r.path), "(no proposal — resolve in review)"
        )
        out.append(f"| ☐ | {r.method} | `{r.path}` | {r.scope} | `{proposal}` |")
    out.append("")

    out.append("## 2. PUBLIC rows pending intent verification")
    out.append("")
    for r in verify:
        out.append(f"- ☐ **{r.method} `{r.path}`** — {r.notes}")
    out.append("")

    out.append("## 3. ROUTE_LOCAL rows (auth-only today)")
    out.append("")
    out.append(f"{len(auth_only)} routes carry `get_current_user` plus in-route ad-hoc")
    out.append("checks (ownership, visibility, director-or-admin). No single legacy")
    out.append("decision function exists per route, so they are NOT machine-comparable")
    out.append("pre-cutover; the preflight equivalence matrix covers only the wired")
    out.append("`require_capability` rows and the sample read/see/list ladder. Each")
    out.append("ROUTE_LOCAL row must be verified by route-level tests in the M2 PR")
    out.append("itself when its guard is rewritten.")
    out.append("")

    out.append("## 4. Known divergence classes (legacy vs. new model)")
    out.append("")
    out.append("Mirrored from `tests/authz/preflight.py::EXPECTED_DIVERGENCES`; the")
    out.append("preflight matrix asserts each class fires and nothing else diverges.")
    out.append("Lift this section into the M2 cutover PR body.")
    out.append("")
    for key, (_, rationale) in EXPECTED_DIVERGENCES.items():
        out.append(f"### `{key}`")
        out.append("")
        out.append(rationale)
        out.append("")

    out.append("## 5. Additional preflight findings")
    out.append("")
    out.append("- **Unique-index ordering is load-bearing**: the live chain's")
    out.append("  `authz_capability_grants` has no `(principal_id, capability,")
    out.append("  scope_ref)` unique index; `reseed()`'s `ON CONFLICT DO NOTHING`")
    out.append("  only dedupes once the staged migration creates it (it does, before")
    out.append("  calling reseed). Pinned by")
    out.append("  `test_reseed_duplicates_without_index`.")
    out.append("- **Federation PEER_INSTANCE principals** have no reseed source —")
    out.append("  peer-key routes keep their own auth path; out of the matrix.")
    out.append("- **`require_capability` call sites that never pass `lab_id`** are")
    out.append("  admin-only in practice regardless of the declared Scope column;")
    out.append("  the cutover rewrite must take the map's Scope as authoritative.")
    out.append("")
    return "\n".join(out)


def main() -> None:
    rows = parse_map(MAP_PATH)
    REPORT_PATH.write_text(generate_report(rows))
    print(f"wrote {REPORT_PATH} ({len(rows)} map rows)")


if __name__ == "__main__":
    main()
