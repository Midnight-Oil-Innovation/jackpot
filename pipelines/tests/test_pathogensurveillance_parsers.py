"""Unit tests for nf-core/pathogensurveillance parsers (M-1)."""

from __future__ import annotations

import sys
from pathlib import Path
from subprocess import CompletedProcess

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.pathogensurveillance import collect_files, parse  # noqa: E402
from pipelines.pathogensurveillance.parsers import (  # noqa: E402
    amr,
    identification,
    mlst,
    phylogeny,
    reference_selection,
    report,
    variants,
)
from pipelines.pathogensurveillance.parsers.identification import (  # noqa: E402
    SendsketchParseError,
)
from shared.parsers import RunMetadata  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "pathogensurveillance"
METADATA = RunMetadata(
    run_id="run-psv-1",
    pipeline_name="nf-core/pathogensurveillance",
    pipeline_version="1.1.0",
)


_HAMRONIZED_TSV = (
    "input_file_name\tgene_symbol\tgene_name\treference_database_name\t"
    "reference_database_version\treference_accession\tanalysis_software_name\t"
    "analysis_software_version\tdrug_class\tantimicrobial_agent\tpredicted_phenotype\t"
    "coverage_percentage\tsequence_identity\tinput_sequence_id\tinput_gene_start\t"
    "input_gene_stop\tstrand_orientation\n"
    "AZ-PSV-001.tsv\tblaCTX-M-15\textended-spectrum beta-lactamase CTX-M-15\t"
    "NCBI\t2024-01-31.1\tNG_048935.1\tamrfinderplus\t3.12.8\tBETA-LACTAM\t"
    "ceftriaxone\tresistant\t100.00\t99.66\tcontig1\t4012\t5236\t+\n"
)


def _fake_hamronize_runner(cmd, *, capture_output, text):  # noqa: ARG001
    return CompletedProcess(cmd, returncode=0, stdout=_HAMRONIZED_TSV, stderr="")


@pytest.fixture
def fake_runner(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/true")
    return _fake_hamronize_runner


class TestSendsketchIdentification:
    def test_parses_top_hit(self):
        results = identification.parse(FIXTURES / "sendsketch", METADATA)
        by_sample = {r.payload["sample_id"]: r for r in results}
        # AZ-PSV-003 has no data rows → skipped (not an error).
        assert set(by_sample) == {"AZ-PSV-001", "AZ-PSV-002"}
        one = by_sample["AZ-PSV-001"].payload
        assert one["taxon_id"] == "562"
        assert one["taxon_name"] == "Escherichia coli"
        assert one["rank"] == "species"
        assert one["abundance_percent"] == pytest.approx(98.12)
        assert one["reference_database"] == "RefSeq"
        assert one["tool_name"] == "sendsketch"
        assert one["tool_version"] == "1.1.0"

    def test_top_hit_only(self):
        """E. coli fixture has two data rows; only the first must survive."""
        results = identification.parse(FIXTURES / "sendsketch", METADATA)
        e_coli_rows = [r for r in results if r.payload["sample_id"] == "AZ-PSV-001"]
        assert len(e_coli_rows) == 1
        assert e_coli_rows[0].payload["taxon_name"] == "Escherichia coli"

    def test_missing_dir(self, tmp_path):
        assert identification.parse(tmp_path / "nope", METADATA) == []

    def test_empty_hits_file_returns_nothing(self, tmp_path):
        d = tmp_path / "sendsketch"
        d.mkdir()
        (d / "AZ-4.sendsketch.txt").write_text(
            "Query: AZ-4.contigs.fa\tSketches: 1\tDB: RefSeq\n"
            "WKID\tKID\tANI\tComplt\tContam\tMatches\tUnique\tnoHit\tTaxID\t"
            "gSize\tgSeqs\ttaxName\n"
        )
        assert identification.parse(d, METADATA) == []

    def test_missing_header_raises(self, tmp_path):
        d = tmp_path / "sendsketch"
        d.mkdir()
        (d / "AZ-5.sendsketch.txt").write_text(
            "Query: AZ-5.contigs.fa\n"
            "WKID\tANI\tComplt\n"  # missing TaxID, taxName
            "98\t98\t99\n"
        )
        with pytest.raises(SendsketchParseError, match="TaxID"):
            identification.parse(d, METADATA)

    def test_ignores_unrelated_files(self, tmp_path):
        d = tmp_path / "sendsketch"
        d.mkdir()
        (d / "run.log").write_text("not a sendsketch")
        assert identification.parse(d, METADATA) == []


class TestAMR:
    def test_parses_fixture(self, fake_runner):
        results = amr.parse(
            FIXTURES / "amrfinderplus",
            METADATA,
            tool_version="3.12.8",
            database_version="2024-01-31.1",
            runner=fake_runner,
        )
        [r] = results
        assert r.result_type == "amr_results"
        assert r.payload["sample_id"] == "AZ-PSV-001"
        assert r.payload["gene_symbol"] == "blaCTX-M-15"
        assert r.payload["tool_name"] == "amrfinderplus"
        assert r.payload["drug"] == "ceftriaxone"

    def test_missing_dir(self, tmp_path, fake_runner):
        assert (
            amr.parse(
                tmp_path / "nope",
                METADATA,
                tool_version="3.12.8",
                database_version="2024-01-31.1",
                runner=fake_runner,
            )
            == []
        )


class TestMLST:
    def test_parses_both_fixtures(self):
        results = mlst.parse(FIXTURES / "mlst", METADATA)
        by_sample = {r.payload["sample_id"]: r.payload for r in results}
        assert set(by_sample) == {"AZ-PSV-001", "AZ-PSV-002"}
        assert by_sample["AZ-PSV-001"]["scheme"] == "ecoli"
        assert by_sample["AZ-PSV-001"]["sequence_type"] == "11"
        assert by_sample["AZ-PSV-001"]["allele_calls"]["gyrB"] == "4"
        assert by_sample["AZ-PSV-002"]["scheme"] == "saureus"
        assert by_sample["AZ-PSV-002"]["tool_name"] == "mlst"

    def test_missing_dir(self, tmp_path):
        assert mlst.parse(tmp_path / "nope", METADATA) == []


class TestVariants:
    def test_parses_plain_vcf(self):
        results = variants.parse(FIXTURES / "variants" / "graphtyper", METADATA)
        by_sample = {r.payload["sample_id"]: r.payload for r in results}
        first = by_sample["AZ-PSV-001"]
        assert first["variant_count"] == 5
        assert first["filtered_variant_count"] == 2  # two LowQual
        assert first["passed_variant_count"] == 3
        assert first["metric_group"] == "graphtyper_variants"
        assert first["source_file"].endswith("AZ-PSV-001.vcf")

    def test_parses_gzipped_vcf(self):
        results = variants.parse(FIXTURES / "variants" / "graphtyper", METADATA)
        payload = next(r.payload for r in results if r.payload["sample_id"] == "AZ-PSV-002")
        assert payload["variant_count"] == 2
        assert payload["passed_variant_count"] == 2
        assert payload["filtered_variant_count"] == 0
        assert payload["source_file"].endswith(".vcf.gz")

    def test_missing_dir(self, tmp_path):
        assert variants.parse(tmp_path / "nope", METADATA) == []

    def test_empty_vcf_zero_variants(self, tmp_path):
        d = tmp_path / "variants"
        d.mkdir()
        (d / "AZ-EMPTY.vcf").write_text(
            "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        )
        [r] = variants.parse(d, METADATA)
        assert r.payload["variant_count"] == 0
        assert r.payload["passed_variant_count"] == 0
        assert r.payload["filtered_variant_count"] == 0


class TestReferenceSelection:
    def test_layout_a_key_value(self):
        results = reference_selection.parse(FIXTURES / "reference_selection", METADATA)
        by_sample = {r.payload["sample_id"]: r.payload for r in results}
        a = by_sample["AZ-PSV-001"]
        assert a["metric_group"] == "reference_selection"
        assert a["reference_accession"] == "GCF_000005845.2"
        assert a["reference_name"] == "Escherichia coli K-12 MG1655"
        assert a["reference_source"] == "RefSeq"
        assert a["source_file"].startswith("reference_selection/")

    def test_layout_b_header_plus_row(self):
        results = reference_selection.parse(FIXTURES / "reference_selection", METADATA)
        b = next(r.payload for r in results if r.payload["sample_id"] == "AZ-PSV-002")
        assert b["reference_accession"] == "GCF_000013425.1"
        assert b["reference_name"] == "Staphylococcus aureus NCTC 8325"

    def test_missing_dir(self, tmp_path):
        assert reference_selection.parse(tmp_path / "nope", METADATA) == []

    def test_empty_file_yields_no_row(self, tmp_path):
        d = tmp_path / "reference_selection"
        d.mkdir()
        (d / "AZ-EMPTY.reference.tsv").write_text("")
        assert reference_selection.parse(d, METADATA) == []


class TestPhylogeny:
    def test_collects_three_trees(self):
        artifacts = phylogeny.collect(FIXTURES / "phylogeny", METADATA)
        subtypes = {a.file_subtype for a in artifacts}
        assert subtypes == {"core_tree", "busco_tree", "snp_tree"}
        assert {a.file_type for a in artifacts} == {"newick"}
        assert {a.sample_id for a in artifacts} == {"_run_"}
        for a in artifacts:
            assert a.relative_path.startswith("phylogeny/")

    def test_missing_dir(self, tmp_path):
        assert phylogeny.collect(tmp_path / "nope", METADATA) == []

    def test_flat_layout_name_hint(self, tmp_path):
        """A flat phylogeny dir with filename hints still resolves subtypes."""
        d = tmp_path / "phylogeny"
        d.mkdir()
        (d / "core_gene.treefile").write_text("(A:1,B:2);")
        (d / "busco.nwk").write_text("(A:1,B:2);")
        artifacts = phylogeny.collect(d, METADATA)
        subtypes = {a.file_subtype for a in artifacts}
        assert subtypes == {"core_tree", "busco_tree"}

    def test_unknown_tree_file_skipped(self, tmp_path):
        d = tmp_path / "phylogeny"
        d.mkdir()
        (d / "random.treefile").write_text("(A,B);")
        # No subtype can be resolved → silently skipped.
        assert phylogeny.collect(d, METADATA) == []


class TestReport:
    def test_collects_html(self):
        [artifact] = report.collect(FIXTURES / "report", METADATA)
        assert artifact.file_type == "html"
        assert artifact.file_subtype == "report"
        assert artifact.sample_id == "_run_"
        assert artifact.relative_path.startswith("report/")

    def test_missing_dir(self, tmp_path):
        assert report.collect(tmp_path / "nope", METADATA) == []

    def test_accepts_renamed_report(self, tmp_path):
        d = tmp_path / "report"
        d.mkdir()
        (d / "psv_report.html").write_text("<html></html>")
        [a] = report.collect(d, METADATA)
        assert a.file_subtype == "report"

    def test_ignores_unrelated_html(self, tmp_path):
        d = tmp_path / "report"
        d.mkdir()
        (d / "random.html").write_text("<html></html>")
        assert report.collect(d, METADATA) == []


class TestPipeline:
    def test_parse_orchestrates_all(self, fake_runner):
        results = parse(FIXTURES, METADATA, runner=fake_runner)
        types = [r.result_type for r in results]
        # 2 sendsketch + 1 amr + 2 mlst + 2 variants + 2 reference_selection = 9
        assert types.count("taxonomic_profile") == 2
        assert types.count("amr_results") == 1
        assert types.count("typing_results") == 2
        assert types.count("pipeline_metrics") == 4  # 2 variants + 2 reference_selection

    def test_collect_files_returns_trees_and_report(self):
        artifacts = collect_files(FIXTURES, METADATA)
        subtypes = {a.file_subtype for a in artifacts}
        assert subtypes == {"core_tree", "busco_tree", "snp_tree", "report"}

    def test_empty_tree(self, tmp_path, fake_runner):
        assert parse(tmp_path, METADATA, runner=fake_runner) == []
        assert collect_files(tmp_path, METADATA) == []


class TestVersionPinning:
    def test_only_1_1_0_supported(self):
        """The launcher reads SUPPORTED_PIPELINE_VERSIONS to emit a warning
        for out-of-range versions.  Keep this guard tight."""
        from pipelines.pathogensurveillance.parsers import SUPPORTED_PIPELINE_VERSIONS

        assert SUPPORTED_PIPELINE_VERSIONS == ["1.1.0"]


def test_shared_amr_parser_used():
    """pathogensurveillance must defer AMR work to the shared parser so
    the M-2 cross-pipeline AMR comparison stays valid."""
    from pipelines.pathogensurveillance.parsers import amr as psv_amr
    from shared.parsers import amrfinderplus as shared_amr

    assert psv_amr.shared_amr is shared_amr


def test_shared_mlst_parser_used():
    from pipelines.pathogensurveillance.parsers import mlst as psv_mlst
    from shared.parsers import mlst as shared_mlst

    assert psv_mlst.shared_mlst is shared_mlst
