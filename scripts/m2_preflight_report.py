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
        if "AUTH-ONLY BY DESIGN" in self.notes and self.capability == "—":
            # Authentication suffices: the resource is the caller, or there is
            # no resource. Not a gap — a decision. See the map's header.
            # A row carrying BOTH the marker and a capability is a split route
            # (self path ungated, cross-principal path guarded) and belongs in
            # ROUTE_LOCAL — it still needs a guard written.
            return "auth_only_by_design"
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
PROPOSED_CAPABILITIES: dict[tuple[str, str], str] = {}


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
    by_design = [r for r in rows if r.klass == "auth_only_by_design"]
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
        f"`require_capability`, {len(auth_only)} carrying a target capability "
        f"but not yet guarded (ROUTE_LOCAL), {len(by_design)} AUTH-ONLY BY "
        f"DESIGN (permanently ungated — authentication is the whole decision), "
        f"{len(gaps)} catalog gaps, {len(public) + len(verify)} PUBLIC "
        f"({len(verify)} pending intent verification)."
    )
    out.append("")

    out.append("## 1. Catalog gaps")
    out.append("")
    if not gaps:
        out.append("None. Every gap the ACCESS-GUARD-MAP pass found was resolved in")
        out.append("review and written into `docs/endpoint_capability_map.md`. Most")
        out.append("took a capability, adding `pipeline:read`, `lab:read`,")
        out.append("`org:read`, `import:read`, `import:manage`,")
        out.append("`submission:prepare`, `access:request`, and `token:manage` to")
        out.append(f"the §4 catalog. The remaining {len(by_design)} were marked")
        out.append("AUTH-ONLY BY DESIGN — self-scope routes, the stateless")
        out.append("validation utility, and the sequencing-lab registry, where")
        out.append("authentication is the whole decision (§4.7). Those stay ungated")
        out.append("after M2 and are covered by route-level tests rather than the")
        out.append("capability matrix. The two personal-token routes carry both a")
        out.append("capability and the marker: the self path is ungated, and")
        out.append("`token:manage` gates only reaching another principal's tokens,")
        out.append("so they remain ROUTE_LOCAL work.")
    else:
        out.append("Proposals follow the §4 `domain:action` convention; existing verbs")
        out.append("reused where one fits. Edit the proposal column in review; the M2")
        out.append("cutover session writes the agreed values into the map and the §4")
        out.append("catalog.")
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
    if not verify:
        out.append("None. The three rows previously pending were reviewed against")
        out.append("the handlers: `auth/dev-login` is confirmed PUBLIC and gated")
        out.append('(`env != "local"` returns 404 as the handler\'s first statement),')
        out.append("and the two pipeline callbacks were **misclassified** — both")
        out.append("authenticate a per-run `X-Pipeline-Token` with")
        out.append("`hmac.compare_digest` and 401 on mismatch, with wrong-token and")
        out.append("missing-token cases already pinned by tests. They are now")
        out.append("SERVICE-authenticated rows carrying `pipeline:write_results`,")
        out.append("and M2 adds the SERVICE-principal `permit()` call that separates")
        out.append("authentication from authorization on them (§4.6, §9.4).")
    else:
        for r in verify:
            out.append(f"- ☐ **{r.method} `{r.path}`** — {r.notes}")
    out.append("")

    out.append("## 3. ROUTE_LOCAL rows (auth-only today)")
    out.append("")
    out.append(f"{len(auth_only)} routes carry `get_current_user` plus in-route ad-hoc")
    out.append("checks and a target capability the map names but no guard enforces yet")
    out.append(f"(a further {len(by_design)} are AUTH-ONLY BY DESIGN and stay that way).")
    out.append("Two of them authenticate a per-run pipeline token rather than a user")
    out.append("JWT — the weblog receiver and the result-registration callback — and")
    out.append("take a SERVICE principal at M2 rather than a human one.")
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
    out.append("- **Data-quality divergences are guarded at migration time, not")
    out.append("  reconciled ahead of M2**: `flag-group-mismatch`,")
    out.append("  `unmapped-group-skipped`, and `project-membership-no-grants` all")
    out.append("  depend on membership rows no deployment holds yet (`instances/`")
    out.append("  contains only `ci`; the baseline migration seeds one admin and one")
    out.append("  Lab Director). A pre-M2 sweep would pass vacuously. M2 must give")
    out.append("  `reseed()` a pre-flight guard that counts all three conditions")
    out.append("  before inserting, aborts with the counts, and takes an explicit")
    out.append("  operator override to proceed — so the check runs on whichever DB")
    out.append("  actually has the rows, including operators we never meet.")
    out.append("")
    return "\n".join(out)


def main() -> None:
    rows = parse_map(MAP_PATH)
    REPORT_PATH.write_text(generate_report(rows))
    print(f"wrote {REPORT_PATH} ({len(rows)} map rows)")


if __name__ == "__main__":
    main()
