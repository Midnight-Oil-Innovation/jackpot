"""Regression checks for scripts/verify_licenses.py.

The Python half of the license gate was silently a no-op: it shelled out to
`pip list`, uv-managed venvs have no pip, and the failure path returned an
empty list. The gate reported OK on zero packages checked. These tests fail if
that class of silent pass comes back.
"""

from __future__ import annotations

import importlib.util
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import distribution as _distribution
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "verify_licenses.py"
_spec = importlib.util.spec_from_file_location("verify_licenses", _SCRIPT)
assert _spec and _spec.loader
verify_licenses = importlib.util.module_from_spec(_spec)
# Register before exec: @dataclass resolves sys.modules[cls.__module__] and gets
# None for a module that was never registered.
sys.modules[_spec.name] = verify_licenses
_spec.loader.exec_module(verify_licenses)


def _installed(name: str) -> bool:
    try:
        _distribution(name)
    except PackageNotFoundError:
        return False
    return True


def test_resolved_packages_is_not_empty():
    """The original bug: an empty list meant the gate passed without checking."""
    assert len(verify_licenses.resolved_packages()) > 50


@pytest.mark.parametrize(
    "text",
    [
        "Apache Software License",  # trove phrasing, carries no version number
        "Apache-2.0",
        "BSD License",
        "0BSD",  # no word boundary between 0 and B
        "HPND",
        "Historical Permission Notice and Disclaimer (HPND)",
        "W3C License",
        "ISC License (ISCL)",
        "MIT",
        "BSD-3-Clause AND TCL",
    ],
)
def test_permissive_licenses_classify_as_allow(text):
    assert verify_licenses.classify(text) == "allow"


@pytest.mark.parametrize("text", ["SSPL", "Business Source License 1.1", "non-commercial"])
def test_incompatible_licenses_still_denied(text):
    assert verify_licenses.classify(text) == "deny"


@pytest.mark.skipif(not _installed("detect-secrets"), reason="dev dependency not installed")
def test_classifier_wins_over_free_text_license_field():
    """detect-secrets sets License to a bare copyright line ("Copyright Yelp,
    Inc. 2020") and declares Apache only via its trove classifier."""
    assert verify_licenses.package_license("detect-secrets") == "Apache Software License"


def test_third_party_overrides_resolve_packages_with_no_metadata():
    """google-crc32c declares no license at all; the doc row is what clears it.
    The gate's own error message points at that file, so it has to be read."""
    findings, rows = verify_licenses.check_python_deps()
    assert rows, "no packages inspected"
    assert [f.name for f in findings] == []


def test_skip_wrapped_tools_gates_python_only(monkeypatch):
    """CI enforces the Python half via --skip-wrapped-tools while the wrapped-tool
    table stays report-only. If wrapped-tool findings leak into that exit code, the
    enforcing step goes permanently red and gets disabled."""
    monkeypatch.setattr("sys.argv", ["verify_licenses.py", "--skip-wrapped-tools"])
    assert verify_licenses.main() == 0
    # Same run without the flag still fails on the outstanding wrapped-tool rows.
    monkeypatch.setattr("sys.argv", ["verify_licenses.py"])
    assert verify_licenses.main() == 1
