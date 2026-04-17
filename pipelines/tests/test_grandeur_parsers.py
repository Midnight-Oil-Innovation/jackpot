"""Unit tests for Grandeur parsers (K-5)."""

from __future__ import annotations

import sys
from pathlib import Path
from subprocess import CompletedProcess

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.grandeur import collect_files, parse  # noqa: E402
from pipelines.grandeur.parsers import amr, blast, kraken2, mlst  # noqa: E402
from shared.parsers import RunMetadata  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "grandeur"
METADATA = RunMetadata(
    run_id="run-grandeur-1",
    pipeline_name="grandeur",
    pipeline_version="4.2.0",
)


def _runner(_cmd, *, capture_output, text):  # noqa: ARG001
    # Only reached when the canonical file is absent; the canonical shortcut
    # in Grandeur's parser means the fixture doesn't hit this path.  We
    # return something sane in case a test deliberately deletes the
    # canonical file.
    return CompletedProcess(_cmd, returncode=0, stdout="", stderr="")


class TestGrandeurAMRShortcut:
    def test_parses_canonical_directly(self):
        results = amr.parse(
            FIXTURES / "amrfinderplus",
            METADATA,
            tool_version="3.12.8",
            database_version="2024-01-31.1",
            runner=_runner,
        )
        # Two rows in the canonical fixture, no CLI round-trip.
        assert len(results) == 2
        first = results[0].payload
        assert first["gene_symbol"] == "blaCTX-M-15"
        assert first["drug"] == "ceftriaxone"
        assert first["reference_database"] == "NCBI Reference Gene Database"

    def test_canonical_takes_priority_over_raw(self, tmp_path):
        # Both raw and canonical exist; only canonical should be parsed.
        d = tmp_path / "amrfinderplus"
        d.mkdir()
        (d / "AZ-1.tsv").write_text("Name\tGene symbol\nAZ-1\tblaCTX\n")
        (d / "AZ-1.hamronized.tsv").write_text(
            "gene_symbol\tanalysis_software_name\nblaCTX-M-15\tamrfinderplus\n"
        )

        def runner_never_called(*args, **kwargs):
            raise AssertionError("CLI runner must not be called when canonical exists")

        results = amr.parse(
            d,
            METADATA,
            tool_version="3.12.8",
            database_version="2024-01-31.1",
            runner=runner_never_called,
        )
        assert len(results) == 1
        assert results[0].payload["sample_id"] == "AZ-1"

    def test_falls_back_to_runner_when_only_raw(self, tmp_path):
        d = tmp_path / "amrfinderplus"
        d.mkdir()
        (d / "AZ-2.tsv").write_text("irrelevant\n")
        canonical = (
            "gene_symbol\tanalysis_software_name\tantimicrobial_agent\n"
            "aac(6')-Iaa\tamrfinderplus\tgentamicin\n"
        )
        import shutil

        original_which = shutil.which
        shutil.which = lambda _name: "/usr/bin/true"  # type: ignore[assignment]

        def runner(_cmd, *, capture_output, text):  # noqa: ARG001
            return CompletedProcess(_cmd, returncode=0, stdout=canonical, stderr="")

        try:
            results = amr.parse(
                d,
                METADATA,
                tool_version="3.12.8",
                database_version="2024-01-31.1",
                runner=runner,
            )
        finally:
            shutil.which = original_which  # type: ignore[assignment]
        assert len(results) == 1
        assert results[0].payload["gene_symbol"] == "aac(6')-Iaa"
        assert results[0].payload["drug"] == "gentamicin"


class TestGrandeurMLST:
    def test_parses_fixture(self):
        [result] = mlst.parse(FIXTURES / "mlst", METADATA)
        payload = result.payload
        assert payload["sample_id"] == "AZ-GRD-001"
        assert payload["scheme"] == "senterica"
        assert payload["sequence_type"] == "11"
        assert payload["allele_calls"]["aroC"] == "10"


class TestGrandeurKraken2:
    def test_top_hit_only(self):
        [result] = kraken2.parse(FIXTURES / "kraken2", METADATA)
        payload = result.payload
        assert payload["sample_id"] == "AZ-GRD-001"
        assert payload["taxon_name"] == "Salmonella enterica"
        assert payload["rank"] == "S"
        assert payload["taxon_id"] == "28901"
        assert payload["abundance_percent"] == pytest.approx(97.80)
        assert payload["reference_database"] == "kraken2_standard"

    def test_top_only_when_no_species(self, tmp_path):
        d = tmp_path / "kraken2"
        d.mkdir()
        (d / "AZ-3_report.txt").write_text(
            " 50.00\t100\t100\tG\t1\tGenusHit\n 40.00\t80\t80\tG\t2\tOtherGenus\n"
        )
        [result] = kraken2.parse(d, METADATA)
        # No species rows → fall back to top of any rank.
        assert result.payload["taxon_name"] == "GenusHit"

    def test_ignores_empty_report(self, tmp_path):
        d = tmp_path / "kraken2"
        d.mkdir()
        (d / "AZ-4_report.txt").write_text("")
        assert kraken2.parse(d, METADATA) == []


class TestGrandeurBlast:
    def test_summary_fixture(self):
        [result] = blast.parse(FIXTURES / "blast", METADATA)
        payload = result.payload
        assert result.result_type == "pipeline_metrics"
        assert payload["sample_id"] == "AZ-GRD-001"
        assert payload["total_hits"] == 3
        assert payload["top_subject"] == "NC_003197.2"
        assert payload["top_identity_percent"] == pytest.approx(99.87)

    def test_handles_malformed_row(self, tmp_path):
        d = tmp_path / "blast"
        d.mkdir()
        (d / "AZ-5_blast.tsv").write_text("contig\tshort\n")
        results = blast.parse(d, METADATA)
        # A single malformed row yields a summary with zero hits but still
        # emits a ParsedResult per sample file.
        assert len(results) == 1
        assert results[0].payload["total_hits"] == 0


class TestGrandeurPipeline:
    def test_parse_full_tree(self):
        results = parse(FIXTURES, METADATA, runner=_runner)
        types_seen = {r.result_type for r in results}
        assert {
            "amr_results",
            "typing_results",
            "taxonomic_profile",
            "pipeline_metrics",
        } <= types_seen

    def test_collect_files_is_empty(self):
        assert collect_files(FIXTURES, METADATA) == []

    def test_empty_tree(self, tmp_path):
        assert parse(tmp_path, METADATA, runner=_runner) == []
