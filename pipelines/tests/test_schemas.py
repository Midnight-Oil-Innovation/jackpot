"""Round-trip validation for the shared result schemas."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.schemas import (  # noqa: E402
    MAGQC,
    RESULT_SCHEMAS,
    AMRResult,
    AssemblyQC,
    NextcladeResult,
    PangolinResult,
    TaxonomicProfile,
    TBTypingResult,
    TypingResult,
    WastewaterLineageAbundance,
)


class TestRegistryMapping:
    def test_all_nine_result_types_present(self):
        expected = {
            "amr_results",
            "typing_results",
            "pangolin_results",
            "nextclade_results",
            "tb_typing_results",
            "assembly_qc",
            "mag_qc",
            "taxonomic_profile",
            "wastewater_lineage_abundance",
        }
        assert set(RESULT_SCHEMAS.keys()) == expected

    def test_registry_maps_to_classes(self):
        assert RESULT_SCHEMAS["pangolin_results"] is PangolinResult
        assert RESULT_SCHEMAS["amr_results"] is AMRResult
        assert RESULT_SCHEMAS["mag_qc"] is MAGQC


class TestAMRResult:
    def test_minimum_valid(self):
        obj = AMRResult(sample_id="EX-1", gene_symbol="mcr-1", tool_name="amrfinderplus")
        assert obj.sample_id == "EX-1"
        assert obj.reference_database is None

    def test_rejects_out_of_range_identity(self):
        with pytest.raises(ValueError):
            AMRResult(
                sample_id="EX-1",
                gene_symbol="mcr-1",
                tool_name="amrfinderplus",
                identity_percent=120,
            )

    def test_rejects_extra_fields(self):
        with pytest.raises(ValueError):
            AMRResult(
                sample_id="EX-1",
                gene_symbol="mcr-1",
                tool_name="amrfinderplus",
                unknown_field="x",
            )


class TestPangolin:
    def test_minimum_valid(self):
        obj = PangolinResult(
            sample_id="EX-1",
            lineage="BA.2.86",
            pangolin_version="4.3.1",
        )
        assert obj.lineage == "BA.2.86"


class TestNextclade:
    def test_requires_version(self):
        with pytest.raises(ValueError):
            NextcladeResult(sample_id="EX-1")


class TestTyping:
    def test_minimum_valid(self):
        obj = TypingResult(
            sample_id="EX-1",
            scheme="mlst_senterica",
            tool_name="mlst",
        )
        assert obj.scheme == "mlst_senterica"


class TestTBTyping:
    def test_minimum_valid(self):
        obj = TBTypingResult(sample_id="EX-1", tbprofiler_version="5.0")
        assert obj.main_lineage is None


class TestAssemblyQC:
    def test_percent_bounds(self):
        with pytest.raises(ValueError):
            AssemblyQC(
                sample_id="EX-1",
                tool_name="QUAST",
                genome_completeness=110,
            )


class TestMAGQC:
    def test_requires_bin_id(self):
        with pytest.raises(ValueError):
            MAGQC(sample_id="EX-1", tool_name="CheckM2")


class TestTaxonomicProfile:
    def test_requires_taxon_id(self):
        with pytest.raises(ValueError):
            TaxonomicProfile(sample_id="EX-1", tool_name="kraken2")


class TestWastewater:
    def test_abundance_bounds(self):
        with pytest.raises(ValueError):
            WastewaterLineageAbundance(
                sample_id="EX-WW-1",
                lineage="BA.2",
                abundance=1.5,
                tool_name="freyja",
            )

    def test_minimum_valid(self):
        obj = WastewaterLineageAbundance(
            sample_id="EX-WW-1",
            lineage="BA.2",
            abundance=0.33,
            tool_name="freyja",
        )
        assert obj.abundance == pytest.approx(0.33)
