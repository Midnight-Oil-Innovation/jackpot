# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""M2-DROP-PRE slice 5: the identity dict carries no legacy role flags.

``get_current_user`` and the CSV-import user lookup both used to select
``users.is_platform_admin`` / ``users.is_data_analyst`` into the dict they
return. Since M2-B1 nothing decides on either value — authorization is
``permit()`` over grants — so the columns rode along as dead weight, and the
local-dev fallback identity advertised ``is_platform_admin: True`` for a
principal whose authority actually comes from whatever grants user 1 holds.

The two SELECT pass-throughs have no runtime observable: the values had no
consumer, which is precisely why a re-add would be invisible, so those are
pinned over source. The fallback dict is different — it IS the return value of
``get_current_user`` on the local branch, so it is asserted against the real
call.

The three consumers this file deliberately left alone at slice 5 —
``routers/auth.py``'s dev-login response, ``routers/users.py``'s PATCH
contract, and the frontend reading ``GET /api/v1/users/me`` — were retired
by slices 6, 7 and 8 respectively. What remains anywhere in production is
WRITES: ``auth.py`` and ``users.py`` keep the columns in step because
``reseed()`` reads them, and M2-DROP deletes the writes with the columns.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import backend.auth.guards as guards_module
import backend.imports as imports_module

LEGACY_FLAGS = frozenset({"is_platform_admin", "is_data_analyst"})

# The two SELECTs this slice narrowed.
NARROWED_MODULES = (guards_module, imports_module)


def _executable_source(module) -> str:
    """Module source with comments and docstrings gone, string literals kept.

    Both files legitimately *name* the flags in prose explaining why they no
    longer read them, so a raw substring scan false-positives. ``ast`` never
    records comments, so only docstrings need blanking — and unlike a
    hand-rolled line scanner it cannot go blind partway through a file: if
    ``ast.parse`` succeeds, every statement is in the tree. A line-oriented
    stripper mistakes the CLOSING delimiter of a multi-line SQL literal for a
    docstring opener and silently swallows the rest of the module, which in a
    SQL-heavy file like imports.py is where a re-added flag would land.

    Matches the house pattern in ``test_condition_registry.py``, which walks
    router sources the same way.
    """
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
            and ast.get_docstring(node) is not None
        ):
            node.body[0].value.value = ""
    return ast.unparse(tree)


@pytest.mark.parametrize("module", NARROWED_MODULES, ids=lambda m: m.__name__)
@pytest.mark.parametrize("flag", sorted(LEGACY_FLAGS))
def test_no_legacy_flag_is_selected_or_assigned(module, flag: str) -> None:
    offenders = [
        line for line in _executable_source(module).splitlines() if re.search(rf"\b{flag}\b", line)
    ]
    assert offenders == [], (
        f"{module.__name__} references {flag} in executable code. Nothing "
        f"consumes it — re-adding it restores a dead read, not a bypass. "
        f"Offending lines:\n" + "\n".join(offenders)
    )


def test_the_local_dev_fallback_identity_claims_no_role(monkeypatch) -> None:
    """The fallback identity must not advertise a role it cannot confer.

    It fires when ``MOCK_USER_EMAIL`` matches no row, so its authority is
    whatever grants user 1 holds — possibly none. Carrying
    ``is_platform_admin: True`` made a grantless identity read as an admin to
    anyone inspecting it, without changing a single decision.

    ``request=None`` is safe: the local branch returns before touching it.
    """
    monkeypatch.setattr(guards_module.get_settings(), "env", "local")
    monkeypatch.setattr(guards_module, "execute_query", lambda *a, **k: [])

    identity = guards_module.get_current_user(request=None)

    assert identity["id"] == 1
    assert not LEGACY_FLAGS & identity.keys(), (
        f"local-dev fallback identity still claims {LEGACY_FLAGS & identity.keys()}"
    )
