"""Every policy condition must say who is allowed to assert it.

A policy's ``conditions`` are facts **about the request**, and ``permit()`` has
no way to know whether the caller was entitled to assert one. That is correct
for an engine and dangerous for a router: M3 shipped
``deletion.separation_of_duties`` with a ``platform_admin_self_approve``
condition, and the route set it straight from the request body — so any
principal could lift the DENY by sending the flag. It was never exploitable
end to end (``deletion.py`` re-checked ``is_platform_admin``), which is
precisely why nothing failed: the defect was masked by a legacy check that was
itself scheduled for removal, and the hole would have opened during M2-DROP's
mechanical convert-the-readers pass.

Prose in learnings.md would not have caught that. This does. The registry
below is the forcing function — a new condition key does not compile away, it
fails here until someone writes down where the value comes from and what gates
it. Same shape as ``DELIBERATELY_UNHELD`` in test_catalog_preset_coverage.py,
and for the same reason: the entry IS the decision record.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from backend.authz.policy import ACTIVE_POLICIES

REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTERS = REPO_ROOT / "backend" / "backend" / "routers"
ACCESS_MODEL = REPO_ROOT / "docs" / "access_model.md"


@dataclass(frozen=True)
class ConditionSpec:
    """How one condition key's value is established, and what gates it."""

    established_by: str
    # The capability a router must check before asserting this key, or None
    # when the value is derived server-side and no caller can influence it.
    # None is a claim that has to be true — not a way to skip the question.
    gated_by: str | None


CONDITION_KEYS: dict[str, ConditionSpec] = {
    "platform_admin_self_approve": ConditionSpec(
        established_by=(
            "POST /samples/{id}/approve-deletion. The request body carries an "
            "ASSERTION, not the decision: the route ANDs it with "
            "permits(user, 'deletion:self_approve', sample_id=...), so a caller "
            "who sends the flag without holding the capability gets False. "
            "Lifting §6.2-1b's separation-of-duties DENY is an audited escape "
            "and must be earned, not claimed."
        ),
        gated_by="deletion:self_approve",
    ),
}


def _catalog_capabilities() -> set[str]:
    """§4 catalog verbs — same parse as test_catalog_preset_coverage."""
    return {
        m.group(1)
        for line in ACCESS_MODEL.read_text().split("\n")
        if (m := re.match(r"^\|\s*`([a-z_]+:[a-z_]+)`\s*\|", line))
    }


def _router_condition_keys() -> dict[str, set[str]]:
    """Condition keys each router passes to a guard, by file.

    AST rather than grep: ``conditions={...}`` spans lines and appears inside
    call expressions, and a regex that missed one would make this test pass by
    failing to look.
    """
    found: dict[str, set[str]] = {}
    for path in ROUTERS.rglob("*.py"):
        tree = ast.parse(path.read_text())
        keys: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg != "conditions" or not isinstance(kw.value, ast.Dict):
                    continue
                for k in kw.value.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        keys.add(k.value)
        if keys:
            found[path.name] = keys
    return found


def test_the_router_scan_actually_finds_something():
    """Guard the guard. An AST walk that matched nothing would make the
    registry check below vacuously true, which is the failure mode of every
    test that reads source code."""
    found = _router_condition_keys()
    assert found, "the AST scan found no conditions= anywhere; the walk is broken"
    assert "samples.py" in found, sorted(found)


def test_every_policy_condition_key_is_registered():
    """A condition the engine reads must have a recorded provenance."""
    used = {k for p in ACTIVE_POLICIES for k in p.get("conditions", {})}
    unregistered = used - set(CONDITION_KEYS)
    assert not unregistered, (
        f"policy conditions with no entry in CONDITION_KEYS: {sorted(unregistered)}. "
        "Add one saying where the value comes from and which capability gates it — "
        "a condition nobody gates is a DENY any caller can lift."
    )


def test_every_router_supplied_condition_key_is_registered():
    """The half that catches the actual bug.

    A route can pass a condition the policy set does not read yet — that is
    how M3's shipped and how a future one would. Registering it is what forces
    the author to answer "and who may assert this?".
    """
    supplied = {k for keys in _router_condition_keys().values() for k in keys}
    unregistered = supplied - set(CONDITION_KEYS)
    assert not unregistered, (
        f"routers pass condition keys with no entry in CONDITION_KEYS: "
        f"{sorted(unregistered)}. If the value comes from a request body it "
        "MUST be ANDed with a held capability at the call site."
    )


def test_the_registry_does_not_rot():
    """An entry for a key nothing uses any more is dead weight that reads as
    a live rule."""
    used = {k for p in ACTIVE_POLICIES for k in p.get("conditions", {})}
    used |= {k for keys in _router_condition_keys().values() for k in keys}
    for key in CONDITION_KEYS:
        assert key in used, f"{key} is registered but no policy or router uses it"


def test_gating_capabilities_are_real():
    """A gate naming a capability the catalog does not define is not a gate.

    Catches the rename that leaves the registry pointing at a verb nobody
    holds — which reads as protection while providing none.
    """
    catalog = _catalog_capabilities()
    for key, spec in CONDITION_KEYS.items():
        if spec.gated_by is None:
            continue
        assert spec.gated_by in catalog, (
            f"{key} claims to be gated by {spec.gated_by!r}, which is not in access_model.md §4"
        )


def test_registry_reasons_are_substantive():
    """ "Set by the route" is not a provenance. The entry is the decision
    record; a placeholder makes the guard ceremonial."""
    for key, spec in CONDITION_KEYS.items():
        assert len(spec.established_by) > 60, (
            f"{key}: give a real provenance, not {spec.established_by!r}"
        )


def test_ungated_keys_are_declared_deliberately():
    """``gated_by=None`` means "no caller can influence this value".

    Making that an explicit claim rather than a default is the point: today
    every key is gated, and a future server-derived one has to say so out loud
    rather than arriving as an omission.
    """
    ungated = [k for k, s in CONDITION_KEYS.items() if s.gated_by is None]
    assert ungated == [], (
        f"keys declared ungated: {ungated}. That is allowed, but each must be "
        "server-derived with no request-body path — re-read the call site before "
        "leaving this assertion relaxed."
    )
