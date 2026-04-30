"""Unit tests for nf-core/mag parsers (L-3)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.mag import collect_files, parse  # noqa: E402
from pipelines.mag.parsers import bin_registry, checkm2, gtdbtk  # noqa: E402
from pipelines.mag.parsers.checkm2 import CheckM2ParseError  # noqa: E402
from pipelines.mag.parsers.gtdbtk import GTDBTkParseError  # noqa: E402
from shared.parsers import RunMetadata  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "mag"
METADATA = RunMetadata(
    run_id="run-mag-1",
    pipeline_name="nf-core/mag",
    pipeline_version="3.0.3",
)


class TestCheckM2:
    def test_parses_fixture(self):
        results = checkm2.parse(FIXTURES, METADATA)
        # 3 bins in the fixture, one row each.
        assert len(results) == 3
        assert {r.result_type for r in results} == {"mag_qc"}
        first = results[0].payload
        assert first["sample_id"] == "AZ-META-001"
        assert first["bin_id"] == "AZ-META-001.MEGAHIT-MetaBAT2.1"
        assert first["completeness_percent"] == pytest.approx(98.42)
        assert first["contamination_percent"] == pytest.approx(1.23)
        assert first["num_contigs"] == 58
        assert first["n50"] == 145212
        assert first["bin_size_bp"] == 4876523
        assert first["gc_percent"] == pytest.approx(50.61)
        assert first["tool_name"] == "checkm2"

    def test_two_bins_map_to_same_parent(self):
        results = checkm2.parse(FIXTURES, METADATA)
        parents = {r.payload["sample_id"] for r in results}
        assert parents == {"AZ-META-001", "AZ-META-002"}
        # AZ-META-001 has two bins → one parent, two distinct bin_ids.
        one = [r for r in results if r.payload["sample_id"] == "AZ-META-001"]
        assert len(one) == 2
        assert {r.payload["bin_id"] for r in one} == {
            "AZ-META-001.MEGAHIT-MetaBAT2.1",
            "AZ-META-001.MEGAHIT-MetaBAT2.2",
        }

    def test_strain_heterogeneity_absent(self):
        results = checkm2.parse(FIXTURES, METADATA)
        for r in results:
            # CheckM2 doesn't emit strain heterogeneity; parser must leave it off.
            assert "strain_heterogeneity" not in r.payload

    def test_missing_output_returns_empty(self, tmp_path):
        assert checkm2.parse(tmp_path / "nope", METADATA) == []

    def test_missing_name_column_raises(self, tmp_path):
        bad = tmp_path / "CheckM2" / "checkm2_quality_report.tsv"
        bad.parent.mkdir(parents=True)
        bad.write_text("Completeness\tContamination\n98.0\t1.0\n")
        with pytest.raises(CheckM2ParseError, match="Name"):
            checkm2.parse(tmp_path, METADATA)

    def test_custom_resolver_overrides_prefix(self):
        def underscore_resolver(name: str) -> str:
            return name.split("_", 1)[0]

        results = checkm2.parse(FIXTURES, METADATA, sample_id_resolver=underscore_resolver)
        # Bin names have no '_', so underscore resolver returns the full name —
        # every bin becomes its own parent.  This asserts the resolver is hooked up.
        assert all(r.payload["sample_id"] == r.payload["bin_id"] for r in results)

    def test_blank_row_skipped(self, tmp_path):
        report = tmp_path / "CheckM2" / "checkm2_quality_report.tsv"
        report.parent.mkdir(parents=True)
        report.write_text(
            "Name\tCompleteness\tContamination\tGenome_Size\tTotal_Contigs\tContig_N50\tGC_Content\n"
            "\t98.0\t1.0\t1000\t10\t500\t50.0\n"
            "AZ-1.bin.1\t50.0\t2.0\t-\t5\t100\tN/A\n"
        )
        results = checkm2.parse(tmp_path, METADATA)
        assert len(results) == 1
        payload = results[0].payload
        # "-" and "N/A" should drop cleanly (not force a ValidationError).
        assert "bin_size_bp" not in payload
        assert "gc_percent" not in payload


class TestGTDBTk:
    def test_parses_fixture(self):
        results = gtdbtk.parse(FIXTURES, METADATA)
        # 4 rows in the fixture but the Unclassified row is dropped.
        assert len(results) == 3
        assert {r.result_type for r in results} == {"taxonomic_profile"}
        first = results[0].payload
        # sample_id on a TaxonomicProfile row is the bin_id (derived sample).
        assert first["sample_id"] == "AZ-META-001.MEGAHIT-MetaBAT2.1"
        assert first["taxon_name"] == "Streptococcus pneumoniae"
        assert first["rank"] == "species"
        assert first["reference_database"] == "GTDB"
        assert first["tool_name"] == "gtdbtk"
        assert first["lineage"].startswith("d__Bacteria")

    def test_empty_species_falls_back_to_genus(self):
        results = gtdbtk.parse(FIXTURES, METADATA)
        bin2 = next(
            r for r in results if r.payload["sample_id"] == "AZ-META-001.MEGAHIT-MetaBAT2.2"
        )
        assert bin2.payload["rank"] == "genus"
        assert bin2.payload["taxon_name"] == "Escherichia"

    def test_unclassified_row_skipped(self):
        results = gtdbtk.parse(FIXTURES, METADATA)
        bins = {r.payload["sample_id"] for r in results}
        assert "AZ-META-003.bin.1" not in bins

    def test_missing_dir(self, tmp_path):
        assert gtdbtk.parse(tmp_path / "nope", METADATA) == []

    def test_missing_required_columns_raises(self, tmp_path):
        bad_dir = tmp_path / "Taxonomy" / "GTDB-Tk"
        bad_dir.mkdir(parents=True)
        (bad_dir / "gtdbtk.bac120.summary.tsv").write_text(
            "classification\nd__Bacteria;s__E. coli\n"
        )
        with pytest.raises(GTDBTkParseError, match="required columns"):
            gtdbtk.parse(tmp_path, METADATA)


class TestBinRegistry:
    def test_collects_all_bin_fastas(self):
        artifacts = bin_registry.collect(FIXTURES, METADATA)
        # 3 bin FASTAs in the fixture across two binners.
        assert len(artifacts) == 3
        assert {a.file_subtype for a in artifacts} == {"mag_bin"}
        assert {a.file_type for a in artifacts} == {"fasta"}
        ids = {a.sample_id for a in artifacts}
        assert ids == {
            "AZ-META-001.MEGAHIT-MetaBAT2.1",
            "AZ-META-001.MEGAHIT-MetaBAT2.2",
            "AZ-META-002.MEGAHIT-DASTool.1",
        }

    def test_uses_bin_id_as_sample_id(self):
        """The bin FASTA's sample_id must match MAGQC.bin_id so the backend
        can wire it to the derived sample row."""
        artifacts = bin_registry.collect(FIXTURES, METADATA)
        checkm_bins = {r.payload["bin_id"] for r in checkm2.parse(FIXTURES, METADATA)}
        artifact_ids = {a.sample_id for a in artifacts}
        assert artifact_ids == checkm_bins

    def test_relative_path_is_rooted_at_output_dir(self):
        artifacts = bin_registry.collect(FIXTURES, METADATA)
        for a in artifacts:
            assert a.relative_path.startswith("GenomeBinning/")

    def test_skips_primary_assembly_contigs(self, tmp_path):
        d = tmp_path / "Assembly" / "MEGAHIT"
        d.mkdir(parents=True)
        (d / "AZ-1.contigs.fa").write_text(">contig\nACGT\n")
        # Also put a legit bin so the collector has something to return.
        bins = tmp_path / "GenomeBinning" / "MetaBAT2" / "bins"
        bins.mkdir(parents=True)
        (bins / "AZ-1.bin.1.fa").write_text(">b\nACGT\n")
        artifacts = bin_registry.collect(tmp_path, METADATA)
        assert len(artifacts) == 1
        assert artifacts[0].sample_id == "AZ-1.bin.1"

    def test_missing_dir(self, tmp_path):
        assert bin_registry.collect(tmp_path / "nope", METADATA) == []


class TestPipeline:
    def test_parse_orchestrates(self):
        results = parse(FIXTURES, METADATA)
        types_seen = {r.result_type for r in results}
        assert "mag_qc" in types_seen
        assert "taxonomic_profile" in types_seen

    def test_collect_files_returns_bins(self):
        artifacts = collect_files(FIXTURES, METADATA)
        assert len(artifacts) == 3
        assert {a.file_subtype for a in artifacts} == {"mag_bin"}

    def test_empty_tree(self, tmp_path):
        assert parse(tmp_path, METADATA) == []
        assert collect_files(tmp_path, METADATA) == []
