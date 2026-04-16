"""
Tests for the pipeline results loader.

Tests cover: manifest parsing, schema column mapping, type coercion,
file type inference, and the full load flow against a real DB.
"""

import gzip
import json
from unittest.mock import MagicMock, patch

from backend.pipeline_results_loader import (
    SCHEMA_COLUMN_MAP,
    LoaderResult,
    _build_sample_updates,
    _coerce_value,
    _infer_file_type,
    load_pipeline_results,
)


class TestInferFileType:
    def test_consensus_fasta(self):
        assert _infer_file_type("consensus/AZ-001.consensus.fa.gz") == "consensus_fasta"

    def test_assembly_fasta(self):
        assert _infer_file_type("assembly/AZ-001.assembly.fasta.gz") == "assembly_fasta"

    def test_vcf(self):
        assert _infer_file_type("variants/AZ-001.vcf.gz") == "variant_calls"

    def test_multiqc(self):
        assert _infer_file_type("multiqc/multiqc_report.html") == "multiqc_report"

    def test_bam(self):
        assert _infer_file_type("mapped/AZ-001.bam") == "alignment"

    def test_manifest(self):
        assert _infer_file_type("iridanext.output.json.gz") == "pipeline_manifest"

    def test_unknown(self):
        assert _infer_file_type("some/unknown/file.xyz") == "pipeline_output"

    def test_case_insensitive(self):
        assert _infer_file_type("SAMPLE.VCF.GZ") == "variant_calls"


class TestCoerceValue:
    def test_str(self):
        assert _coerce_value("BA.2.86", str) == "BA.2.86"

    def test_float(self):
        assert _coerce_value("99.7", float) == 99.7

    def test_int(self):
        assert _coerce_value("1250", int) == 1250

    def test_bool_true(self):
        assert _coerce_value("true", bool) is True
        assert _coerce_value("PASS", bool) is True
        assert _coerce_value("1", bool) is True

    def test_bool_false(self):
        assert _coerce_value("false", bool) is False
        assert _coerce_value("FAIL", bool) is False

    def test_list_already_list(self):
        assert _coerce_value(["mcr-1", "blaTEM-1"], list) == ["mcr-1", "blaTEM-1"]

    def test_list_semicolon_string(self):
        assert _coerce_value("mcr-1;blaTEM-1", list) == ["mcr-1", "blaTEM-1"]

    def test_list_comma_string(self):
        assert _coerce_value("mcr-1,blaTEM-1", list) == ["mcr-1", "blaTEM-1"]

    def test_none_returns_none(self):
        assert _coerce_value(None, str) is None

    def test_empty_string_returns_none(self):
        assert _coerce_value("", str) is None

    def test_bad_float_returns_none(self):
        assert _coerce_value("not-a-number", float) is None

    def test_no_coercion(self):
        assert _coerce_value({"key": "val"}, None) == {"key": "val"}


class TestBuildSampleUpdates:
    def test_maps_known_keys(self):
        metadata = {
            "pango_lineage": "BA.2.86",
            "coverage_depth": "1250.3",
            "genome_completeness": "99.7",
        }
        updates = _build_sample_updates(metadata)
        assert updates["pango_lineage"] == "BA.2.86"
        assert updates["coverage_depth"] == 1250.3
        assert updates["genome_completeness"] == 99.7

    def test_ignores_unknown_keys(self):
        metadata = {
            "pango_lineage": "BA.2.86",
            "some_unknown_tool_output": "value",
            "another_custom_field": "123",
        }
        updates = _build_sample_updates(metadata)
        assert "some_unknown_tool_output" not in updates
        assert "another_custom_field" not in updates
        assert "pango_lineage" in updates

    def test_excludes_none_values(self):
        metadata = {
            "pango_lineage": "BA.2.86",
            "coverage_depth": "",  # empty → None → excluded
        }
        updates = _build_sample_updates(metadata)
        assert "pango_lineage" in updates
        assert "coverage_depth" not in updates

    def test_amr_genes_list_coercion(self):
        metadata = {"amr_genes": "mcr-1;blaTEM-1"}
        updates = _build_sample_updates(metadata)
        assert updates["amr_genes"] == ["mcr-1", "blaTEM-1"]

    def test_empty_metadata(self):
        assert _build_sample_updates({}) == {}

    def test_all_unknown_keys(self):
        metadata = {"custom_a": "1", "custom_b": "2"}
        assert _build_sample_updates(metadata) == {}


class TestSchemaColumnMap:
    def test_has_pango_lineage(self):
        assert "pango_lineage" in SCHEMA_COLUMN_MAP

    def test_has_amr_genes(self):
        assert "amr_genes" in SCHEMA_COLUMN_MAP
        col, coercion = SCHEMA_COLUMN_MAP["amr_genes"]
        assert coercion is list

    def test_has_coverage_depth(self):
        assert "coverage_depth" in SCHEMA_COLUMN_MAP
        col, coercion = SCHEMA_COLUMN_MAP["coverage_depth"]
        assert coercion is float

    def test_has_mag_fields(self):
        assert "mag_completeness_pct" in SCHEMA_COLUMN_MAP
        assert "mag_contamination_pct" in SCHEMA_COLUMN_MAP
        assert "mag_strain_heterogeneity" in SCHEMA_COLUMN_MAP

    def test_has_tb_fields(self):
        assert "tb_lineage" in SCHEMA_COLUMN_MAP
        assert "tb_lineage_confidence" in SCHEMA_COLUMN_MAP

    def test_vadr_alerts_is_list(self):
        col, coercion = SCHEMA_COLUMN_MAP["vadr_alerts"]
        assert coercion is list


class TestLoaderResult:
    def test_success_when_no_errors(self):
        r = LoaderResult(run_id="run-001")
        assert r.success is True

    def test_failure_when_errors(self):
        r = LoaderResult(run_id="run-001", errors=["something failed"])
        assert r.success is False

    def test_default_empty_lists(self):
        r = LoaderResult(run_id="run-001")
        assert r.samples_updated == []
        assert r.errors == []
        assert r.files_registered == 0
        assert r.global_files_registered == 0


class TestReadManifest:
    """Test manifest download and parsing (mocked GCS)."""

    def _make_manifest(self, data: dict) -> bytes:
        return gzip.compress(json.dumps(data).encode())

    def test_parses_valid_manifest(self):
        from backend.pipeline_results_loader import _read_manifest

        manifest_data = {
            "files": {
                "global": [{"path": "multiqc/multiqc_report.html"}],
                "samples": {"AZ-001": [{"path": "consensus/AZ-001.consensus.fa.gz"}]},
            },
            "metadata": {
                "samples": {"AZ-001": {"pango_lineage": "BA.2.86", "coverage_depth": "1250.3"}}
            },
        }
        compressed = self._make_manifest(manifest_data)

        mock_client = MagicMock()
        mock_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=compressed))
        }

        with (
            patch("backend.storage._get_client", return_value=mock_client),
            patch("backend.config.get_settings"),
        ):
            result = _read_manifest("gs://jackpot-results/run-001/")

        assert result["files"]["global"][0]["path"] == "multiqc/multiqc_report.html"
        assert result["metadata"]["samples"]["AZ-001"]["pango_lineage"] == "BA.2.86"

    def test_normalises_trailing_slash(self):
        from backend.pipeline_results_loader import _read_manifest

        compressed = self._make_manifest(
            {"files": {"global": [], "samples": {}}, "metadata": {"samples": {}}}
        )
        mock_client = MagicMock()
        mock_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=compressed))
        }

        with (
            patch("backend.storage._get_client", return_value=mock_client),
            patch("backend.config.get_settings"),
        ):
            # Should work with or without trailing slash
            _read_manifest("gs://jackpot-results/run-001")
            call_args = mock_client.get_object.call_args
            assert call_args[1]["Key"] == "run-001/iridanext.output.json.gz"


class TestLoadPipelineResults:
    """Integration-style tests using mocked DB and GCS."""

    def _make_manifest(self, data: dict) -> bytes:
        return gzip.compress(json.dumps(data).encode())

    def test_empty_manifest_succeeds(self):
        manifest = {
            "files": {"global": [], "samples": {}},
            "metadata": {"samples": {}},
        }
        compressed = self._make_manifest(manifest)
        mock_client = MagicMock()
        mock_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=compressed))
        }

        with (
            patch("backend.storage._get_client", return_value=mock_client),
            patch("backend.config.get_settings"),
            patch("backend.database.execute_write"),
            patch("backend.database.execute_query"),
        ):
            result = load_pipeline_results(
                run_id="run-001",
                result_uri="gs://jackpot-results/run-001/",
                pipeline_name="nf-core/viralrecon",
                pipeline_version="2.6.0",
                launched_by_id=1,
                conn=MagicMock(),
            )
        assert result.success is True
        assert result.samples_updated == []

    def test_bad_manifest_uri_returns_error(self):
        mock_client = MagicMock()
        mock_client.get_object.side_effect = Exception("NoSuchKey")

        with (
            patch("backend.storage._get_client", return_value=mock_client),
            patch("backend.config.get_settings"),
        ):
            result = load_pipeline_results(
                run_id="run-bad",
                result_uri="gs://jackpot-results/run-bad/",
                pipeline_name="nf-core/viralrecon",
                pipeline_version="2.6.0",
                launched_by_id=1,
                conn=MagicMock(),
            )
        assert result.success is False
        assert len(result.errors) == 1
        assert "NoSuchKey" in result.errors[0]

    def test_registers_global_files(self):
        manifest = {
            "files": {
                "global": [{"path": "multiqc/multiqc_report.html"}],
                "samples": {},
            },
            "metadata": {"samples": {}},
        }
        compressed = self._make_manifest(manifest)
        mock_client = MagicMock()
        mock_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=compressed))
        }
        mock_write = MagicMock()

        with (
            patch("backend.storage._get_client", return_value=mock_client),
            patch("backend.config.get_settings"),
            patch("backend.database.execute_write", mock_write),
            patch("backend.database.execute_query"),
        ):
            result = load_pipeline_results(
                run_id="run-001",
                result_uri="gs://jackpot-results/run-001/",
                pipeline_name="nf-core/viralrecon",
                pipeline_version="2.6.0",
                launched_by_id=1,
                conn=MagicMock(),
            )

        assert result.global_files_registered == 1
        # Verify the URI was constructed correctly
        call_kwargs = mock_write.call_args_list[0][0][1]
        assert call_kwargs["uri"] == "gs://jackpot-results/run-001/multiqc/multiqc_report.html"
        assert call_kwargs["file_type"] == "multiqc_report"

    def test_skips_unknown_sample(self):
        manifest = {
            "files": {"global": [], "samples": {"UNKNOWN-999": []}},
            "metadata": {"samples": {"UNKNOWN-999": {"pango_lineage": "BA.2"}}},
        }
        compressed = self._make_manifest(manifest)
        mock_client = MagicMock()
        mock_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=compressed))
        }

        with (
            patch("backend.storage._get_client", return_value=mock_client),
            patch("backend.config.get_settings"),
            patch("backend.database.execute_write"),
            patch("backend.database.execute_query", return_value=[]),
        ):
            result = load_pipeline_results(
                run_id="run-001",
                result_uri="gs://jackpot-results/run-001/",
                pipeline_name="nf-core/viralrecon",
                pipeline_version="2.6.0",
                launched_by_id=1,
                conn=MagicMock(),
            )

        assert "UNKNOWN-999" not in result.samples_updated
        assert any("not found" in e for e in result.errors)
