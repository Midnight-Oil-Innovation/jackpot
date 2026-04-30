"""
M-3: Parser version-range allowlist tests.

The shared :func:`shared.version_check.check_pipeline_version` is what
every wrapper will call at run start to decide whether the incoming
pipeline version is in its parser's ``SUPPORTED_PIPELINE_VERSIONS``
list.  The spec is explicit that a mismatch **warns but does not
hard-block**, so these tests assert both the accept path and the
warn-and-proceed path, and that the warning message is self-describing
enough to drop straight into a ``pipeline_events`` row.

The second class walks every wrapped pipeline and confirms it exposes
a non-empty ``SUPPORTED_PIPELINE_VERSIONS`` — catches the case where
a new pipeline is added to ``pipelines/`` but the launcher-side
version gate is silently bypassed because the constant is missing.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.version_check import VersionCheckResult, check_pipeline_version  # noqa: E402

# Keep this list in sync with the README parser version matrix.  Any
# new wrapper added to pipelines/ MUST also appear here — the
# roundtrip test asserts import-ability + non-empty support list.
_WRAPPED_PIPELINES: list[tuple[str, str]] = [
    ("cecret", "UPHL-BioNGS/Cecret"),
    ("viralrecon", "nf-core/viralrecon"),
    ("walkercreek", "UPHL-BioNGS/walkercreek"),
    ("bactopia", "bactopia/bactopia"),
    ("grandeur", "UPHL-BioNGS/Grandeur"),
    ("mycosnp", "CDCgov/mycosnp-nf"),
    ("tb_profiler", "jodyphelan/tb-profiler"),
    ("mag", "nf-core/mag"),
    ("taxprofiler", "nf-core/taxprofiler"),
    ("pathogensurveillance", "nf-core/pathogensurveillance"),
]


class TestCheckPipelineVersion:
    def test_supported_version_returns_is_supported_true(self):
        result = check_pipeline_version("nf-core/pathogensurveillance", "1.1.0", ["1.1.0"])
        assert isinstance(result, VersionCheckResult)
        assert result.is_supported is True
        assert result.warning_message is None
        assert result.pipeline_version == "1.1.0"
        assert result.supported_versions == ("1.1.0",)

    def test_unsupported_version_emits_warning_without_raising(self):
        result = check_pipeline_version("nf-core/pathogensurveillance", "1.2.0", ["1.1.0"])
        assert result.is_supported is False
        # The helper never raises — the spec says warn-and-continue.
        assert result.warning_message is not None
        # Warning must name the pipeline and the offending version so
        # the pipeline_events row is self-describing.
        assert "nf-core/pathogensurveillance" in result.warning_message
        assert "1.2.0" in result.warning_message
        assert "1.1.0" in result.warning_message

    def test_empty_support_list_still_returns_structured_result(self):
        """Edge case: parser module with an empty allowlist (e.g.
        forthcoming pipeline stub) must still produce a clean warning
        rather than surprising the caller with an exception."""
        result = check_pipeline_version("future-pipeline", "0.0.1", [])
        assert result.is_supported is False
        assert result.warning_message is not None
        assert "future-pipeline" in result.warning_message

    def test_supported_versions_snapshot_is_immutable(self):
        """The returned tuple is the caller's contract for logging —
        it must not mutate if the source list is later reassigned."""
        support = ["1.1.0", "1.1.1"]
        result = check_pipeline_version("x", "1.1.0", support)
        support.append("2.0.0")
        assert result.supported_versions == ("1.1.0", "1.1.1")

    def test_iterable_input_accepted_not_just_list(self):
        """Wrappers may pass a tuple or generator — constraint the
        parameter type to ``Iterable[str]`` and make sure both work."""
        result = check_pipeline_version("x", "1", ("1", "2"))
        assert result.is_supported is True
        result = check_pipeline_version("x", "1", (v for v in ["1", "2"]))
        assert result.is_supported is True


class TestWrappedPipelineVersionMatrix:
    @pytest.mark.parametrize(
        "module_name,upstream_name",
        _WRAPPED_PIPELINES,
        ids=[m for m, _ in _WRAPPED_PIPELINES],
    )
    def test_every_wrapper_declares_nonempty_support_list(
        self, module_name: str, upstream_name: str
    ):
        """Guard against silent launcher bypass: a wrapper with no
        ``SUPPORTED_PIPELINE_VERSIONS`` would let any version through
        the check. Enforce import + non-empty list for all wrappers."""
        module = importlib.import_module(f"pipelines.{module_name}.parsers")
        assert hasattr(module, "SUPPORTED_PIPELINE_VERSIONS"), (
            f"{module_name}: parsers package missing SUPPORTED_PIPELINE_VERSIONS"
        )
        versions = module.SUPPORTED_PIPELINE_VERSIONS
        assert isinstance(versions, list) and len(versions) >= 1, (
            f"{module_name}: SUPPORTED_PIPELINE_VERSIONS must be a non-empty list"
        )
        for v in versions:
            assert isinstance(v, str) and v, (
                f"{module_name}: non-string or empty version in allowlist: {v!r}"
            )
        # Sanity: the helper accepts the first declared version.
        first = versions[0]
        result = check_pipeline_version(upstream_name, first, versions)
        assert result.is_supported is True, (
            f"{module_name}: first declared version {first!r} unexpectedly rejected"
        )
