"""Every §4 capability has a holder, or an explicit reason it has none.

This is the guard for a failure that has now happened four times: a verb is
added to `access_model.md` §4's catalog, no preset in `reseed.py` is updated,
and the route that needs it becomes reachable by nobody. It has been found by
hand each time — `pipeline:promote` and `pipeline:register_custom` in M2-B1,
`pipeline:read` in M2-B3-PRE, and six more here in M2-B4.

The catalog and the presets are two lists that must agree, and nothing made
them. This does.

The allowlist below is the other half. "Held by no human preset" is a real and
common answer — a SERVICE verb, a peer verb, a rule carried by a policy
instead of a grant — so the test is not "everything must be granted" but
"every gap is a decision someone wrote down".
"""

import re
from pathlib import Path

from backend.authz.policy import LADDER_POLICIES
from backend.authz.reseed import PRESET_GRANTS

REPO_ROOT = Path(__file__).resolve().parents[2]
ACCESS_MODEL = REPO_ROOT / "docs" / "access_model.md"

# capability -> why no human preset holds it. Adding an entry is a decision;
# the reason is the record of it.
DELIBERATELY_UNHELD: dict[str, str] = {
    "pipeline:write_results": (
        "SERVICE only. Held by the per-run principal M2-B6 constructs from a "
        "pipeline run, and by §8.4's Data Source Lab peer preset at M5. A "
        "human holding it could forge results for a run they did not launch."
    ),
    "compute:he_aggregate": "§8.4 Data Source Lab preset (M5) — a peer, not a human.",
    "compute:he_query": "§8.4 Data Source Lab preset (M5) — a peer, not a human.",
    "compute:register_dataset": "§8.4 Data Source Lab preset (M5) — a peer, not a human.",
    "federation:push": (
        "§8.3 federation preset, held by a PEER_INSTANCE principal via a "
        "sharing agreement (§4.4). Not a human capability."
    ),
    "access:request": (
        "Carried by an ALLOW policy on sharing_level = DISCOVERABLE (M2-B2), "
        "not by a grant. The requester is by definition not a member of the "
        "sample's lab, so no lab-scoped grant could ever cover the target."
    ),
    "sample:hard_delete": (
        "Deliberately granted by nobody by default. The deletion lifecycle is "
        "M3's, and permanent deletion should be an explicit per-deployment "
        "assignment rather than something a preset confers."
    ),
    "scrub:approve_skip": (
        "No route consumes it yet — the scrub-override approval workflow is "
        "unbuilt. Critical Rule 18 says Lab Director approves, so it belongs "
        "in lab_lead when that route lands. This entry is the reminder."
    ),
}


def _catalog_capabilities() -> list[str]:
    """Verbs from §4's catalog tables — rows whose first cell is a code span."""
    seen: dict[str, None] = {}
    for line in ACCESS_MODEL.read_text().split("\n"):
        m = re.match(r"^\|\s*`([a-z_]+:[a-z_]+)`\s*\|", line)
        if m:
            seen[m.group(1)] = None
    return list(seen)


def test_the_catalog_is_actually_parsed():
    """Guard the guard: a parser that silently matched nothing would make
    every assertion below vacuously true."""
    caps = _catalog_capabilities()
    assert len(caps) > 30, caps
    for expected in ("sample:read", "pipeline:run", "org:manage", "submission:prepare"):
        assert expected in caps, expected


def test_every_catalog_capability_has_a_holder_or_a_reason():
    held = {c for caps in PRESET_GRANTS.values() for c in caps}
    policy_carried = {p["capability"] for p in LADDER_POLICIES}
    unexplained = [
        c
        for c in _catalog_capabilities()
        if c not in held and c not in DELIBERATELY_UNHELD and c not in policy_carried
    ]
    assert not unexplained, (
        f"capabilities in access_model.md §4 that no preset grants and no "
        f"policy carries: {unexplained}. A route needing one of these is "
        f"reachable by nobody. Either add it to a preset in reseed.py, or add "
        f"it to DELIBERATELY_UNHELD with the reason."
    )


def test_no_preset_grants_a_capability_the_catalog_does_not_define():
    """The other direction. A typo in a preset is silent otherwise — the
    grant is issued and matches nothing, so the route it was meant to open
    stays shut."""
    catalog = set(_catalog_capabilities())
    for preset, caps in PRESET_GRANTS.items():
        for capability in caps:
            assert capability in catalog, (
                f"{preset} grants {capability!r}, which is not in "
                f"access_model.md §4. Typo, or a catalog entry never written."
            )


def test_the_allowlist_does_not_rot():
    """An entry that later gets granted anyway is a contradiction, and an
    entry for a verb the catalog dropped is dead weight."""
    catalog = set(_catalog_capabilities())
    held = {c for caps in PRESET_GRANTS.values() for c in caps}
    for capability, reason in DELIBERATELY_UNHELD.items():
        assert capability in catalog, f"{capability} is allowlisted but not in §4"
        assert capability not in held, (
            f"{capability} is allowlisted as held by no preset, but "
            f"{[k for k, c in PRESET_GRANTS.items() if capability in c]} grants it"
        )
        assert len(reason) > 40, f"{capability}: give a real reason, not {reason!r}"


# ── §8.2's preset blocks vs PRESET_GRANTS ────────────────────────────────
#
# The catalog check above catches "verb with no holder". This catches the
# other drift, and it is the one that did real damage: §8.2's Lab Member
# (read-write) block listed pipeline:run while reseed.py withheld it, and the
# batch that found the contradiction (M2-B3) had already written a "deliberate
# narrowing" into four documents before the review caught it. Code and prose
# had appeared to agree because one was derived from the other.

_DOC_PRESET_NAMES = {
    "Instance Administrator": "instance_administrator",
    "Lab Lead": "lab_lead",
    "Lab Member (read-write)": "lab_member_rw",
    "Lab Member (read-only)": "lab_member_ro",
    "Surveillance Officer": "surveillance_officer",
}


def _doc_presets() -> dict[str, set[str]]:
    """Capability lists from §8.2's fenced preset blocks."""
    text = ACCESS_MODEL.read_text()
    blocks = re.findall(
        r'Preset "([^"]+)":\n  scope-template:[^\n]*\n  capabilities: '
        r"((?:[^\n]*\n(?:                [^\n]*\n)*))",
        text,
    )
    out: dict[str, set[str]] = {}
    for doc_name, raw in blocks:
        key = _DOC_PRESET_NAMES.get(doc_name)
        if key is None:
            continue
        out[key] = {c.strip().rstrip(",") for c in raw.replace("\n", " ").split(",") if ":" in c}
    return out


def test_the_preset_blocks_are_actually_parsed():
    """Guard the guard again: a regex that stopped matching would turn the
    agreement test into a no-op, which is the failure mode of every test that
    reads prose."""
    parsed = _doc_presets()
    assert set(parsed) == set(_DOC_PRESET_NAMES.values()), sorted(parsed)
    for key, caps in parsed.items():
        assert len(caps) >= 3, (key, caps)


def test_reseed_presets_match_the_documented_ones():
    doc = _doc_presets()
    for key, documented in doc.items():
        implemented = set(PRESET_GRANTS[key])
        assert implemented == documented, (
            f"{key} disagrees with access_model.md §8.2 — "
            f"doc-only={sorted(documented - implemented)}, "
            f"code-only={sorted(implemented - documented)}. "
            "These are one decision recorded twice; fix whichever is wrong, "
            "but do not let them differ."
        )
