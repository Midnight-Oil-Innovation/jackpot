"""Tests for shared.hamronization_normalizer."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.hamronization_normalizer import (  # noqa: E402
    HamronizationError,
    HamronizeInput,
    normalize,
    parse_canonical_tsv,
    run_hamronize,
)

CANONICAL_TSV = (
    "gene_symbol\tgene_name\tdrug_class\tantimicrobial_agent\t"
    "coverage_percentage\tsequence_identity\treference_database_name\t"
    "reference_accession\tinput_sequence_id\tinput_gene_start\t"
    "input_gene_stop\tstrand_orientation\tanalysis_software_name\t"
    "analysis_software_version\tpredicted_phenotype\n"
    "mcr-1\tmcr-1 phosphoethanolamine transferase\tcolistin\tcolistin\t"
    "99.5\t99.1\tNCBI\tNG_047603.1\tcontig_1\t1000\t2620\t+\t"
    "amrfinderplus\t3.12.8\tRESISTANT\n"
    "blaTEM-1\tbeta-lactamase TEM-1\tbeta-lactam\tampicillin\t"
    "100.0\t100.0\tNCBI\tNG_050145.1\tcontig_2\t500\t1361\t-\t"
    "amrfinderplus\t3.12.8\tRESISTANT\n"
)


class TestParseCanonicalTSV:
    def test_parses_two_rows(self):
        results = parse_canonical_tsv(CANONICAL_TSV, sample_id="AZ-1")
        assert len(results) == 2
        assert results[0].gene_symbol == "mcr-1"
        assert results[0].sample_id == "AZ-1"
        assert results[0].drug_class == "colistin"
        assert results[0].coverage_percent == pytest.approx(99.5)
        assert results[0].identity_percent == pytest.approx(99.1)
        assert results[0].reference_database == "NCBI"
        assert results[0].start_pos == 1000
        assert results[0].end_pos == 2620
        assert results[0].tool_name == "amrfinderplus"
        assert results[0].tool_version == "3.12.8"
        assert results[0].resistance_phenotype == "RESISTANT"
        assert results[1].gene_symbol == "blaTEM-1"

    def test_empty_input_returns_empty_list(self):
        assert parse_canonical_tsv("", sample_id="AZ-1") == []

    def test_skips_rows_with_no_gene_symbol(self):
        bad = "gene_symbol\tanalysis_software_name\n\tamrfinderplus\nmcr-1\tamrfinderplus\n"
        results = parse_canonical_tsv(bad, sample_id="AZ-1")
        assert len(results) == 1
        assert results[0].gene_symbol == "mcr-1"

    def test_coerces_numerics_bad_value_to_none(self):
        broken = (
            "gene_symbol\tanalysis_software_name\tcoverage_percentage\n"
            "mcr-1\tamrfinderplus\tnot-a-number\n"
        )
        [result] = parse_canonical_tsv(broken, sample_id="AZ-1")
        assert result.coverage_percent is None


class TestRunHamronize:
    def _spec(self, tmp_path: Path, tool: str = "amrfinderplus") -> HamronizeInput:
        raw = tmp_path / "amrfinderplus.tsv"
        raw.write_text("header\nrow\n")
        return HamronizeInput(
            tool=tool,
            raw_output_path=raw,
            sample_id="AZ-1",
            analysis_software_version="3.12.8",
            reference_database_version="2024-09-05",
            input_file_name="AZ-1.contigs.fa",
        )

    def test_unsupported_tool_raises(self, tmp_path):
        spec = self._spec(tmp_path, tool="madeuptool")
        with pytest.raises(HamronizationError, match="Unsupported tool"):
            run_hamronize(spec, executable="/usr/bin/hamronize")

    def test_missing_input_raises(self, tmp_path):
        spec = HamronizeInput(
            tool="amrfinderplus",
            raw_output_path=tmp_path / "does-not-exist.tsv",
            sample_id="AZ-1",
            analysis_software_version="3.12.8",
            reference_database_version="2024-09-05",
        )
        with pytest.raises(HamronizationError, match="does not exist"):
            run_hamronize(spec, executable="/usr/bin/hamronize")

    def test_missing_executable_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _: None)
        spec = self._spec(tmp_path)
        with pytest.raises(HamronizationError, match="not found"):
            run_hamronize(spec)

    def test_nonzero_exit_raises(self, tmp_path):
        spec = self._spec(tmp_path)

        def fake_runner(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, "", "boom")

        with pytest.raises(HamronizationError, match="boom"):
            run_hamronize(spec, executable="/usr/bin/hamronize", runner=fake_runner)

    def test_success_returns_stdout(self, tmp_path):
        spec = self._spec(tmp_path)

        captured = {}

        def fake_runner(cmd, **kwargs):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0, CANONICAL_TSV, "")

        output = run_hamronize(spec, executable="/usr/bin/hamronize", runner=fake_runner)
        assert output == CANONICAL_TSV
        assert "amrfinderplus" in captured["cmd"]
        assert "3.12.8" in captured["cmd"]
        assert "AZ-1.contigs.fa" in captured["cmd"]


class TestNormalize:
    def test_end_to_end(self, tmp_path, monkeypatch):
        raw = tmp_path / "amrfinderplus.tsv"
        raw.write_text("stub\n")
        spec = HamronizeInput(
            tool="amrfinderplus",
            raw_output_path=raw,
            sample_id="AZ-XYZ",
            analysis_software_version="3.12.8",
            reference_database_version="2024-09-05",
        )
        fake_runner = MagicMock(
            return_value=subprocess.CompletedProcess(["hamronize"], 0, CANONICAL_TSV, "")
        )
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/hamronize")
        results = normalize(spec, runner=fake_runner)
        assert len(results) == 2
        assert results[0].sample_id == "AZ-XYZ"
        assert results[0].gene_symbol == "mcr-1"
