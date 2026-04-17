"""Unit tests for the Cecret parsers (J-5)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.cecret import collect_files, parse  # noqa: E402
from pipelines.cecret.parsers import consensus, freyja  # noqa: E402
from pipelines.cecret.parsers.freyja import FreyjaParseError  # noqa: E402
from shared.parsers import RunMetadata  # noqa: E402
from shared.parsers.nextclade import NextcladeParseError  # noqa: E402
from shared.parsers.nextclade import parse as parse_nextclade  # noqa: E402
from shared.parsers.pangolin import PangolinParseError  # noqa: E402
from shared.parsers.pangolin import parse as parse_pangolin  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "cecret"
METADATA = RunMetadata(
    run_id="run-cecret-1",
    pipeline_name="cecret",
    pipeline_version="3.66",
)


class TestPangolin:
    def test_parses_fixture(self):
        results = parse_pangolin(FIXTURES / "pangolin" / "lineage_report.csv", METADATA)
        assert len(results) == 2
        assert {r.result_type for r in results} == {"pangolin_results"}
        first = results[0].payload
        assert first["sample_id"] == "AZ-001"
        assert first["lineage"] == "BA.2.86"
        assert first["conflict"] == 0.0
        assert first["scorpio_call"] == "Omicron (BA.2-like)"
        assert first["pangolin_version"] == "4.3.1"
        assert first["pangolin_data_version"] == "PUSHER-v1.25"
        assert first["qc_status"] == "pass"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_pangolin(tmp_path / "missing.csv", METADATA)

    def test_missing_required_column(self, tmp_path):
        bad = tmp_path / "lineage_report.csv"
        bad.write_text("taxon,lineage\nAZ-1,BA.2.86\n")  # no pangolin_version
        with pytest.raises(PangolinParseError, match="pangolin_version"):
            parse_pangolin(bad, METADATA)

    def test_blank_numeric_becomes_none(self, tmp_path):
        bad = tmp_path / "lineage_report.csv"
        bad.write_text(
            "taxon,lineage,conflict,ambiguity_score,pangolin_version\nAZ-1,BA.2,,,4.3.1\n"
        )
        [result] = parse_pangolin(bad, METADATA)
        assert result.payload["sample_id"] == "AZ-1"
        assert "conflict" not in result.payload
        assert "ambiguity_score" not in result.payload

    def test_skips_empty_taxon_row(self, tmp_path):
        bad = tmp_path / "lineage_report.csv"
        bad.write_text("taxon,lineage,pangolin_version\n,BA.2,4.3.1\nAZ-1,BA.2,4.3.1\n")
        results = parse_pangolin(bad, METADATA)
        assert len(results) == 1
        assert results[0].payload["sample_id"] == "AZ-1"


class TestNextclade:
    def test_parses_fixture(self):
        results = parse_nextclade(FIXTURES / "nextclade" / "nextclade.tsv", METADATA)
        assert len(results) == 2
        first = results[0].payload
        assert first["sample_id"] == "AZ-001"
        assert first["clade"] == "23I (BA.2.86)"
        assert first["qc_overall_status"] == "good"
        assert first["qc_overall_score"] == 2.5
        assert first["total_substitutions"] == 57
        assert first["substitutions"] == ["T670G", "C913T"]
        assert first["aa_substitutions"] == ["S:P681H", "ORF1a:K856R"]
        assert first["nextclade_pango"] == "BA.2.86"
        # Sibling nextclade.version.txt supplies the version
        assert first["nextclade_version"] == "3.8.2"

    def test_missing_required_column(self, tmp_path):
        bad = tmp_path / "nextclade.tsv"
        bad.write_text("index\tclade\n0\t23I\n")
        with pytest.raises(NextcladeParseError, match="seqName"):
            parse_nextclade(bad, METADATA)

    def test_falls_back_to_metadata_version(self, tmp_path):
        f = tmp_path / "nextclade.tsv"
        f.write_text("seqName\tclade\nAZ-1\t23I\n")
        [result] = parse_nextclade(f, METADATA)
        assert result.payload["nextclade_version"] == METADATA.pipeline_version

    def test_explicit_version_override(self, tmp_path):
        f = tmp_path / "nextclade.tsv"
        f.write_text("seqName\tclade\nAZ-1\t23I\n")
        [result] = parse_nextclade(
            f,
            METADATA,
            nextclade_version="3.9.0",
            dataset_name="sars-cov-2",
            dataset_version="2024-07-17",
        )
        assert result.payload["nextclade_version"] == "3.9.0"
        assert result.payload["dataset_name"] == "sars-cov-2"


class TestFreyja:
    def test_parses_fixture(self):
        results = freyja.parse(FIXTURES / "freyja" / "aggregated-freyja.tsv", METADATA)
        # Sample 1 has 3 lineages, sample 2 has 3 lineages → 6 rows total
        assert len(results) == 6
        first = results[0].payload
        assert first["sample_id"] == "AZ-WW-001"
        assert first["lineage"] == "BA.2.86"
        assert first["abundance"] == pytest.approx(0.55)
        assert first["tool_name"] == "freyja"
        assert first["coverage_depth"] == pytest.approx(99.5)
        # Ordering preserves row-level lineage order
        assert [r.payload["lineage"] for r in results[:3]] == ["BA.2.86", "JN.1", "AY.4"]

    def test_mismatched_lengths_raises(self, tmp_path):
        f = tmp_path / "aggregated.tsv"
        f.write_text("\tlineages\tabundances\tcoverage\nX.tsv\tBA.2 JN.1\t0.5\t99.0\n")
        with pytest.raises(FreyjaParseError, match="length mismatch"):
            freyja.parse(f, METADATA)

    def test_missing_columns_raises(self, tmp_path):
        f = tmp_path / "aggregated.tsv"
        f.write_text("sample\tdata\nX\tY\n")
        with pytest.raises(FreyjaParseError, match="required columns"):
            freyja.parse(f, METADATA)

    def test_drops_near_zero_abundance(self, tmp_path):
        f = tmp_path / "aggregated.tsv"
        f.write_text(
            "\tlineages\tabundances\tcoverage\n"
            "X.freyja.tsv\tBA.2 JN.1 AY.4\t0.99 0.000000001 0.01\t98\n"
        )
        results = freyja.parse(f, METADATA)
        assert len(results) == 2
        assert [r.payload["lineage"] for r in results] == ["BA.2", "AY.4"]

    def test_explicit_versions(self, tmp_path):
        f = tmp_path / "aggregated.tsv"
        f.write_text("\tlineages\tabundances\tcoverage\nS.freyja.tsv\tBA.2\t1.0\t100\n")
        [result] = freyja.parse(f, METADATA, tool_version="1.5.0", barcode_version="2024-08-19")
        assert result.payload["tool_version"] == "1.5.0"
        assert result.payload["barcode_version"] == "2024-08-19"


class TestConsensus:
    def test_collects_fixture(self):
        artifacts = consensus.collect(FIXTURES / "consensus", METADATA)
        ids = sorted(a.sample_id for a in artifacts)
        assert ids == ["AZ-001", "AZ-002"]
        assert all(a.file_type == "fasta" for a in artifacts)
        assert all(a.file_subtype == "consensus" for a in artifacts)
        assert all(a.relative_path.startswith("consensus/") for a in artifacts)

    def test_ignores_unrelated_files(self, tmp_path):
        d = tmp_path / "consensus"
        d.mkdir()
        (d / "AZ-1.consensus.fa").write_text(">AZ-1\nACGT\n")
        (d / "README.txt").write_text("ignore me")
        (d / "AZ-2.bam").write_text("not fasta")
        artifacts = consensus.collect(d, METADATA)
        assert [a.sample_id for a in artifacts] == ["AZ-1"]

    def test_accepts_gzipped(self, tmp_path):
        d = tmp_path / "consensus"
        d.mkdir()
        (d / "AZ-1.consensus.fa.gz").write_bytes(b"\x1f\x8b\x08...")
        artifacts = consensus.collect(d, METADATA)
        assert artifacts[0].sample_id == "AZ-1"

    def test_returns_empty_for_missing_dir(self, tmp_path):
        assert consensus.collect(tmp_path / "nope", METADATA) == []


class TestPipelineLevelParse:
    def test_parses_full_fixture_tree(self):
        results = parse(FIXTURES, METADATA)
        types_seen = {r.result_type for r in results}
        assert "pangolin_results" in types_seen
        assert "nextclade_results" in types_seen
        assert "wastewater_lineage_abundance" in types_seen

    def test_collects_files_for_full_tree(self):
        files = collect_files(FIXTURES, METADATA)
        assert {f.sample_id for f in files} == {"AZ-001", "AZ-002"}

    def test_skips_absent_sub_outputs(self, tmp_path):
        # Empty directory — nothing to parse
        assert parse(tmp_path, METADATA) == []
        assert collect_files(tmp_path, METADATA) == []
