"""Unit tests for nf-core/taxprofiler parsers (L-3)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.taxprofiler import collect_files, parse  # noqa: E402
from pipelines.taxprofiler.parsers import bracken, diamond, kraken2  # noqa: E402
from pipelines.taxprofiler.parsers.bracken import BrackenParseError  # noqa: E402
from shared.parsers import RunMetadata  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "taxprofiler"
METADATA = RunMetadata(
    run_id="run-taxp-1",
    pipeline_name="nf-core/taxprofiler",
    pipeline_version="1.2.0",
)


class TestKraken2:
    def test_retains_full_ranked_list(self):
        results = kraken2.parse(FIXTURES / "kraken2", METADATA)
        # Metagenomic mode keeps every row — 9 in the fixture.
        assert len(results) == 9
        assert {r.result_type for r in results} == {"taxonomic_profile"}
        ids = [r.payload["taxon_id"] for r in results]
        # Top species hit is Escherichia coli (S-rank, taxid 562) but we no
        # longer filter — so other ranks appear too.
        assert "562" in ids
        assert "2" in ids  # Bacteria (domain)

    def test_reference_db_from_filename(self):
        [sample_row] = [
            r
            for r in kraken2.parse(FIXTURES / "kraken2", METADATA)
            if r.payload["taxon_id"] == "562"
        ]
        assert sample_row.payload["reference_database"] == "standard"
        assert sample_row.payload["sample_id"] == "AZ-META-001"

    def test_missing_dir(self, tmp_path):
        assert kraken2.parse(tmp_path / "nope", METADATA) == []

    def test_ignores_non_report_files(self, tmp_path):
        d = tmp_path / "kraken2"
        d.mkdir()
        (d / "AZ_standard.kraken2.kraken2.report.txt").write_text(
            " 90.00\t100\t100\tS\t9606\tHomo sapiens\n"
        )
        (d / "run.log").write_text("not a report")
        results = kraken2.parse(d, METADATA)
        assert len(results) == 1
        assert results[0].payload["taxon_id"] == "9606"


class TestBracken:
    def test_parses_fixture(self):
        results = bracken.parse(FIXTURES / "bracken", METADATA)
        assert len(results) == 5
        assert {r.result_type for r in results} == {"taxonomic_profile"}
        first = results[0].payload
        assert first["sample_id"] == "AZ-META-001"
        assert first["taxon_id"] == "562"
        assert first["taxon_name"] == "Escherichia coli"
        assert first["rank"] == "species"
        # 0.450 → 45.0 percent.
        assert first["abundance_percent"] == pytest.approx(45.0)
        assert first["read_count"] == 45000
        assert first["reference_database"] == "standard"
        assert first["tool_name"] == "bracken"

    def test_fraction_rounded_to_four_decimals(self, tmp_path):
        d = tmp_path / "bracken"
        d.mkdir()
        (d / "AZ-1_std.bracken.tsv").write_text(
            "name\ttaxonomy_id\ttaxonomy_lvl\tkraken_assigned_reads\t"
            "added_reads\tnew_est_reads\tfraction_total_reads\n"
            "Foo\t1\tS\t10\t1\t11\t0.123456789\n"
        )
        [r] = bracken.parse(d, METADATA)
        # 0.123456789 * 100 rounded to 4 places.
        assert r.payload["abundance_percent"] == 12.3457

    def test_missing_required_columns_raises(self, tmp_path):
        d = tmp_path / "bracken"
        d.mkdir()
        (d / "AZ-1_std.bracken.tsv").write_text("name\ttaxonomy_id\nFoo\t1\n")
        with pytest.raises(BrackenParseError, match="required columns"):
            bracken.parse(d, METADATA)

    def test_missing_dir(self, tmp_path):
        assert bracken.parse(tmp_path / "nope", METADATA) == []


class TestDiamond:
    def test_summarises_fixture(self):
        [result] = diamond.parse(FIXTURES / "diamond", METADATA)
        assert result.result_type == "pipeline_metrics"
        payload = result.payload
        assert payload["sample_id"] == "AZ-META-001"
        assert payload["total_hits"] == 4
        assert payload["top_subject"] == "sp|P12345|RPOB_ECOLI"
        assert payload["top_bitscore"] == pytest.approx(2654.1)
        assert payload["top_identity_percent"] == pytest.approx(99.87)
        assert payload["reference_database"] == "nr"
        assert payload["tool_name"] == "diamond"

    def test_empty_file_emits_zero_hits(self, tmp_path):
        d = tmp_path / "diamond"
        d.mkdir()
        (d / "AZ-2_nr.diamond.tsv").write_text("")
        [r] = diamond.parse(d, METADATA)
        assert r.payload["total_hits"] == 0
        assert "top_subject" not in r.payload

    def test_malformed_rows_skipped(self, tmp_path):
        d = tmp_path / "diamond"
        d.mkdir()
        # Row 1 has only 3 cols → skipped; row 2 is valid.
        (d / "AZ-3_nr.diamond.tsv").write_text(
            "c1\tsub1\t99.0\nc2\tsub2\t99.0\t100\t1\t0\t1\t100\t1\t100\t0.0\t1500.0\n"
        )
        [r] = diamond.parse(d, METADATA)
        assert r.payload["total_hits"] == 1
        assert r.payload["top_subject"] == "sub2"

    def test_missing_dir(self, tmp_path):
        assert diamond.parse(tmp_path / "nope", METADATA) == []


class TestPipeline:
    def test_parse_orchestrates_all_classifiers(self):
        results = parse(FIXTURES, METADATA)
        types_seen = [r.result_type for r in results]
        assert types_seen.count("taxonomic_profile") == 14  # 9 kraken2 + 5 bracken
        assert types_seen.count("pipeline_metrics") == 1  # diamond

    def test_collect_files_empty(self):
        assert collect_files(FIXTURES, METADATA) == []

    def test_empty_tree(self, tmp_path):
        assert parse(tmp_path, METADATA) == []


def test_shared_kraken2_parser_used():
    """taxprofiler.kraken2 must defer to shared.parsers.kraken2.
    Guard test: if someone forks the shared parser, catch it here."""
    from pipelines.taxprofiler.parsers import kraken2 as taxp_kraken2
    from shared.parsers import kraken2 as shared_kraken2

    assert taxp_kraken2.shared_kraken2 is shared_kraken2
