"""Unit tests for mycosnp parsers (K-5)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.mycosnp import collect_files, parse  # noqa: E402
from pipelines.mycosnp.parsers import snippy, tree, typing  # noqa: E402
from pipelines.mycosnp.parsers.tree import RUN_LEVEL_SAMPLE_ID  # noqa: E402
from pipelines.mycosnp.parsers.typing import FungalTypingParseError  # noqa: E402
from shared.parsers import RunMetadata  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "mycosnp"
METADATA = RunMetadata(
    run_id="run-mycosnp-1",
    pipeline_name="mycosnp",
    pipeline_version="2.1",
)


class TestSnippy:
    def test_parses_multi_sample_fixture(self):
        results = snippy.parse(FIXTURES / "snippy", METADATA)
        ids = {r.payload["sample_id"] for r in results}
        assert ids == {"AZ-F-001", "AZ-F-002"}

        az1 = next(r for r in results if r.payload["sample_id"] == "AZ-F-001")
        assert az1.result_type == "pipeline_metrics"
        assert az1.payload["snp_count"] == 241
        assert az1.payload["insertion_count"] == 5
        assert az1.payload["deletion_count"] == 8
        assert az1.payload["total_variants"] == 259
        assert az1.payload["reference"] == "CandidaAurisB11205"

    def test_minimal_counts(self):
        results = snippy.parse(FIXTURES / "snippy", METADATA)
        az2 = next(r for r in results if r.payload["sample_id"] == "AZ-F-002")
        # Only SNP + total supplied → other counts silently absent (not zero).
        assert az2.payload["snp_count"] == 198
        assert "insertion_count" not in az2.payload

    def test_falls_back_to_summary_txt(self, tmp_path):
        d = tmp_path / "snippy" / "SAMPLE-X"
        d.mkdir(parents=True)
        (d / "summary.txt").write_text("Reference\tREFX\nVariant-SNP\t10\nVariantTotal\t10\n")
        [result] = snippy.parse(tmp_path / "snippy", METADATA)
        assert result.payload["sample_id"] == "SAMPLE-X"
        assert result.payload["snp_count"] == 10

    def test_missing_dir(self, tmp_path):
        assert snippy.parse(tmp_path / "nope", METADATA) == []


class TestTree:
    def test_collects_newick_with_run_level_id(self):
        artifacts = tree.collect(FIXTURES / "tree", METADATA)
        assert len(artifacts) == 1
        assert artifacts[0].sample_id == RUN_LEVEL_SAMPLE_ID
        assert artifacts[0].file_type == "newick"
        assert artifacts[0].file_subtype == "snp_tree"
        # relative_path is rooted at the parent of the tree dir
        assert artifacts[0].relative_path.endswith("tree/core.aln.treefile")

    def test_ignores_unrelated_files(self, tmp_path):
        d = tmp_path / "tree"
        d.mkdir()
        (d / "core.aln.treefile").write_text("(A,B);\n")
        (d / "extra.log").write_text("log")
        artifacts = tree.collect(d, METADATA)
        assert len(artifacts) == 1

    def test_missing_dir(self, tmp_path):
        assert tree.collect(tmp_path / "nope", METADATA) == []


class TestFungalTyping:
    def test_parses_fixture(self):
        results = typing.parse(FIXTURES / "typing", METADATA)
        assert len(results) == 2
        ids = [r.payload["sample_id"] for r in results]
        assert ids == ["AZ-F-001", "AZ-F-002"]
        first = results[0].payload
        assert first["scheme"] == "cauris"
        assert first["sequence_type"] == "1"
        assert first["clade"] == "Clade_I"
        assert first["allele_calls"]["CAS4"] == "5"
        assert first["tool_name"] == "mycosnp_typing"

    def test_missing_columns_raises(self, tmp_path):
        d = tmp_path / "typing"
        d.mkdir()
        (d / "bad.tsv").write_text("sample_id\tscheme\nAZ-X\tfoo\n")
        with pytest.raises(FungalTypingParseError, match="sequence_type"):
            typing.parse(d, METADATA)

    def test_missing_dir(self, tmp_path):
        assert typing.parse(tmp_path / "nope", METADATA) == []


class TestPipeline:
    def test_parse_full_tree(self):
        results = parse(FIXTURES, METADATA)
        types_seen = {r.result_type for r in results}
        assert "pipeline_metrics" in types_seen
        assert "typing_results" in types_seen

    def test_collect_files_returns_tree(self):
        artifacts = collect_files(FIXTURES, METADATA)
        assert len(artifacts) == 1
        assert artifacts[0].file_subtype == "snp_tree"

    def test_empty_tree(self, tmp_path):
        assert parse(tmp_path, METADATA) == []
        assert collect_files(tmp_path, METADATA) == []
