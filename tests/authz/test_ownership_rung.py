# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""§5.3's ownership roster and LADDER_POLICIES' owner_id rungs must agree.

Ownership is an ALLOW policy rather than a grant (writing a grant row per
sample creation and deleting one per transfer is the alternative), and
``_matches`` compares capability by equality. So ownership reaches exactly the
verbs a rung names — there is no "ownership implies read/update" in general,
however natural that reads in prose.

Which is how the bug this file exists for got in. M3 replaced
``request-deletion``'s in-line "owner, or lab member" branch with
``require_capability("deletion:request")`` and left a comment saying ownership
survived as "LADDER_POLICIES' owner_id rung". It did not: the rungs named
``sample:read`` and ``sample:read_detail``, and a rung for one verb does
nothing for another. Nothing failed. An owner who had left the lab simply
could not request deletion of their own row, and no test stood on that side of
the contract.

The guard is the pattern ``test_catalog_preset_coverage.py`` already uses for
§8.2's presets, for the same reason: the doc and the code are one decision
recorded twice, so make them fail when they disagree rather than trusting
prose to keep up.
"""

import re
from pathlib import Path

from backend.authz.policy import LADDER_POLICIES, PRINCIPAL_ID

REPO_ROOT = Path(__file__).resolve().parents[2]
ACCESS_MODEL = REPO_ROOT / "docs" / "access_model.md"


def _rungs_in_code() -> set[str]:
    """Capabilities carrying an ``{"owner_id": PRINCIPAL_ID}`` ALLOW."""
    return {
        p["capability"]
        for p in LADDER_POLICIES
        if p["effect"] == "ALLOW" and p.get("resource", {}).get("owner_id") is PRINCIPAL_ID
    }


def _roster_in_doc() -> dict[str, bool]:
    """§5.3's roster: capability -> does it carry an ownership rung."""
    section = ACCESS_MODEL.read_text().split("#### The ownership rung, enumerated", 1)
    assert len(section) == 2, "§5.3's ownership roster heading is gone"
    roster: dict[str, bool] = {}
    for line in section[1].split("\n"):
        m = re.match(r"^\|\s*`([a-z_]+:[a-z_]+)`\s*\|\s*(\*\*)?(yes|no)(\*\*)?\s*\|", line)
        if m:
            roster[m.group(1)] = m.group(3) == "yes"
    return roster


def test_the_roster_is_actually_parsed():
    """Guard the guard: a regex that matched nothing would make every
    assertion below vacuously true, which is the failure mode this whole file
    is about."""
    roster = _roster_in_doc()
    assert len(roster) >= 5, roster
    assert roster["sample:read"] is True
    assert roster["sample:update"] is False


def test_every_documented_rung_exists_in_code():
    documented = {cap for cap, carried in _roster_in_doc().items() if carried}
    missing = documented - _rungs_in_code()
    assert not missing, (
        f"§5.3 says ownership carries {sorted(missing)}, but LADDER_POLICIES has no "
        "owner_id rung for them. This is the M3 defect exactly: a claim about where "
        "a rule lives, with no rule there. Add the rung or correct the roster."
    )


def test_every_rung_in_code_is_documented():
    undocumented = _rungs_in_code() - {cap for cap, carried in _roster_in_doc().items() if carried}
    assert not undocumented, (
        f"LADDER_POLICIES gives ownership {sorted(undocumented)}, which §5.3's roster "
        "does not list. Widening what ownership reaches is an access-model change and "
        "belongs in the doc, not only in the policy list."
    )


def test_capabilities_marked_no_really_have_no_rung():
    """A 'no' row is a recorded decision, not a description of the default.

    ``sample:update`` is the one that matters: an owner who has left a lab can
    still read and can still ask for deletion, but cannot edit metadata into a
    tenant they are no longer part of.
    """
    excluded = {cap for cap, carried in _roster_in_doc().items() if not carried}
    assert excluded, "the roster records no exclusions; sample:update should be one"
    leaked = excluded & _rungs_in_code()
    assert not leaked, f"§5.3 says ownership does NOT reach {sorted(leaked)}, but it does"
