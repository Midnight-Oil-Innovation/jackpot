"""Unit tests for viralrecon parsers (J-5)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.viralrecon import collect_files, parse  # noqa: E402
from pipelines.viralrecon.parsers import consensus, variants  # noqa: E402
from shared.parsers import RunMetadata  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "viralrecon"
METADATA = RunMetadata(
    run_id="run-viralrecon-1",
    pipeline_name="viralrecon",
    pipeline_version="2.6.0",
)


class TestPipelineParse:
    def test_parses_full_fixture_tree(self):
        results = parse(FIXTURES, METADATA)
        by_type: dict[str, int] = {}
        for r in results:
            by_type[r.result_type] = by_type.get(r.result_type, 0) + 1
        assert by_type["pangolin_results"] == 1
        assert by_type["nextclade_results"] == 1
        assert by_type["pipeline_metrics"] == 1
        assert by_type["wastewater_lineage_abundance"] == 3

    def test_collects_consensus_files(self):
        files = collect_files(FIXTURES, METADATA)
        assert len(files) == 1
        assert files[0].sample_id == "AZ-WW-001"
        assert files[0].file_subtype == "consensus"
        assert "bcftools" in files[0].relative_path

    def test_handles_missing_everything(self, tmp_path):
        assert parse(tmp_path, METADATA) == []
        assert collect_files(tmp_path, METADATA) == []


class TestIVarVariants:
    def test_fixture_summarises_pass_and_fail(self):
        [result] = variants.parse(FIXTURES / "variants" / "ivar" / "AZ-WW-001.tsv", METADATA)
        payload = result.payload
        assert result.result_type == "pipeline_metrics"
        assert payload["sample_id"] == "AZ-WW-001"
        assert payload["variant_caller"] == "ivar"
        assert payload["total_variants"] == 5
        assert payload["pass_variants"] == 4
        assert payload["fail_variants"] == 1
        assert payload["source_file"].endswith("AZ-WW-001.tsv")

    def test_missing_required_columns(self, tmp_path):
        bad = tmp_path / "AZ-1.tsv"
        bad.write_text("REGION\tPOS\nMN908947.3\t100\n")
        with pytest.raises(ValueError, match="missing required columns"):
            variants.parse(bad, METADATA)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            variants.parse(tmp_path / "nope.tsv", METADATA)

    def test_sample_id_from_compound_suffix(self, tmp_path):
        f = tmp_path / "AZ-XYZ.variants.tsv"
        f.write_text("REGION\tPOS\tREF\tALT\tPASS\nMN908947.3\t241\tC\tT\tTRUE\n")
        [result] = variants.parse(f, METADATA)
        assert result.payload["sample_id"] == "AZ-XYZ"


class TestConsensus:
    def test_collects_from_bcftools_subdir(self):
        artifacts = consensus.collect(
            FIXTURES / "consensus" / "bcftools",
            METADATA,
        )
        assert [a.sample_id for a in artifacts] == ["AZ-WW-001"]
        assert artifacts[0].relative_path == "consensus/bcftools/AZ-WW-001.consensus.fa"

    def test_accepts_ivar_subdir(self, tmp_path):
        d = tmp_path / "consensus" / "ivar"
        d.mkdir(parents=True)
        (d / "AZ-2.consensus.fa").write_text(">AZ-2\nACGT\n")
        artifacts = consensus.collect(d, METADATA)
        assert artifacts[0].relative_path == "consensus/ivar/AZ-2.consensus.fa"

    def test_ignores_non_fasta(self, tmp_path):
        d = tmp_path / "consensus" / "bcftools"
        d.mkdir(parents=True)
        (d / "AZ-1.consensus.fa").write_text(">AZ-1\nACGT\n")
        (d / "AZ-1.bam").write_text("binary")
        artifacts = consensus.collect(d, METADATA)
        assert len(artifacts) == 1
