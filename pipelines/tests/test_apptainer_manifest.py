"""Tests for ``pipelines.apptainer_manifest`` (P0h H-2).

Covers the parser contract for the manifest file format, the
filesystem loader, and the in-tree per-pipeline manifests so any
future addition that violates the format (typos, dropped @upstream
directive, missing register-process container) trips a test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipelines.apptainer_manifest import (
    ApptainerManifest,
    list_pipelines_with_manifests,
    load_manifest,
    parse_manifest_text,
)

# Ten pipelines ship in this repo (Sessions J–M); each needs a
# manifest under H-2. If a future PR adds a pipeline without a
# manifest, the suite below catches it.
EXPECTED_PIPELINES = [
    "bactopia",
    "cecret",
    "grandeur",
    "mag",
    "mycosnp",
    "pathogensurveillance",
    "taxprofiler",
    "tb_profiler",
    "viralrecon",
    "walkercreek",
]


# ─────────────── parse_manifest_text contract ────────────────


def test_parse_strips_comments_and_blank_lines():
    text = """\
# header comment
docker.io/library/python:3.12-slim-bookworm

# blank above and below

quay.io/biocontainers/samtools:1.20--h50ea8bc_0
"""
    parsed = parse_manifest_text(text, pipeline="fixture")
    assert parsed.pipeline == "fixture"
    assert parsed.images == (
        "docker.io/library/python:3.12-slim-bookworm",
        "quay.io/biocontainers/samtools:1.20--h50ea8bc_0",
    )
    assert parsed.directives == ()


def test_parse_collects_directives_separately():
    text = """\
@upstream nf-core/viralrecon
@upstream-config https://example.com/conf/modules.config
@audit-status partial
docker.io/library/python:3.12-slim-bookworm
"""
    parsed = parse_manifest_text(text, pipeline="viralrecon")
    assert parsed.images == ("docker.io/library/python:3.12-slim-bookworm",)
    assert parsed.directives == (
        ("upstream", "nf-core/viralrecon"),
        ("upstream-config", "https://example.com/conf/modules.config"),
        ("audit-status", "partial"),
    )
    assert parsed.upstream == "nf-core/viralrecon"


def test_parse_preserves_image_order():
    text = "alpha:1\nbeta:2\ngamma:3\n"
    parsed = parse_manifest_text(text, pipeline="fixture")
    assert parsed.images == ("alpha:1", "beta:2", "gamma:3")


def test_parse_tolerates_unknown_directives():
    text = """\
@invented foo bar
docker.io/library/python:3.12-slim-bookworm
"""
    parsed = parse_manifest_text(text, pipeline="fixture")
    assert ("invented", "foo bar") in parsed.directives
    assert parsed.images == ("docker.io/library/python:3.12-slim-bookworm",)
    # An unknown directive does NOT count as upstream metadata.
    assert parsed.upstream is None


def test_parse_strips_trailing_whitespace():
    text = "docker.io/library/python:3.12-slim-bookworm   \n"
    parsed = parse_manifest_text(text, pipeline="fixture")
    assert parsed.images == ("docker.io/library/python:3.12-slim-bookworm",)


def test_parse_empty_input_yields_empty_manifest():
    parsed = parse_manifest_text("", pipeline="fixture")
    assert isinstance(parsed, ApptainerManifest)
    assert parsed.images == ()
    assert parsed.directives == ()


# ─────────────── load_manifest filesystem behaviour ────────────────


def test_load_manifest_uses_root_override(tmp_path: Path):
    pipeline_dir = tmp_path / "fakepipe"
    pipeline_dir.mkdir()
    (pipeline_dir / "apptainer_images.txt").write_text(
        "@upstream foo/bar\nimage:tag\n",
        encoding="utf-8",
    )
    parsed = load_manifest("fakepipe", root=tmp_path)
    assert parsed.upstream == "foo/bar"
    assert parsed.images == ("image:tag",)


def test_load_manifest_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_manifest("nope", root=tmp_path)


def test_list_pipelines_with_manifests_skips_dirs_without_manifest(tmp_path: Path):
    (tmp_path / "with_manifest").mkdir()
    (tmp_path / "with_manifest" / "apptainer_images.txt").write_text("img:1\n")
    (tmp_path / "no_manifest").mkdir()
    assert list_pipelines_with_manifests(root=tmp_path) == ["with_manifest"]


# ─────────────── in-tree manifest hygiene ────────────────


@pytest.mark.parametrize("pipeline", EXPECTED_PIPELINES)
def test_in_tree_manifest_loads(pipeline: str):
    """Every shipped pipeline has a parseable manifest."""
    parsed = load_manifest(pipeline)
    assert parsed.pipeline == pipeline


@pytest.mark.parametrize("pipeline", EXPECTED_PIPELINES)
def test_in_tree_manifest_declares_upstream(pipeline: str):
    """The audit doc relies on every manifest declaring @upstream."""
    parsed = load_manifest(pipeline)
    assert parsed.upstream is not None, (
        f"{pipeline}/apptainer_images.txt missing @upstream directive"
    )


@pytest.mark.parametrize("pipeline", EXPECTED_PIPELINES)
def test_in_tree_manifest_includes_register_python(pipeline: str):
    """Every wrapper invokes a Python register process; pre-staging
    must include a Python container so apptainer-only clusters can
    actually run the REGISTER_RESULTS step."""
    parsed = load_manifest(pipeline)
    assert any("python" in img.lower() for img in parsed.images), (
        f"{pipeline}/apptainer_images.txt does not list a python container"
    )


def test_list_pipelines_with_manifests_in_tree_matches_expected():
    """Catch a future pipeline added without a manifest."""
    actual = list_pipelines_with_manifests()
    assert sorted(actual) == sorted(EXPECTED_PIPELINES)
