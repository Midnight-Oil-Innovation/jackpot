"""Unit tests for tb-profiler parsers (K-5)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.tb_profiler import collect_files, parse  # noqa: E402
from pipelines.tb_profiler.parsers import drug_resistance, lineage  # noqa: E402
from pipelines.tb_profiler.parsers.lineage import TBProfilerParseError  # noqa: E402
from shared.parsers import RunMetadata  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "tb_profiler"
METADATA = RunMetadata(
    run_id="run-tb-1",
    pipeline_name="tb-profiler",
    pipeline_version="6.2.0",
)


class TestLineage:
    def test_parses_fixture(self):
        [result] = lineage.parse(FIXTURES / "results", METADATA)
        payload = result.payload
        assert result.result_type == "tb_typing_results"
        assert payload["sample_id"] == "AZ-TB-001"
        assert payload["main_lineage"] == "lineage4"
        assert payload["sub_lineage"] == "lineage4.9"
        assert payload["spoligotype"] == "777000377760771"
        assert payload["drug_resistance_profile"] == "MDR"
        assert payload["tbprofiler_version"] == "6.2.0"
        assert payload["tbprofiler_db_version"] == "2024-05-09"

    def test_who_susceptibility_map_populated(self):
        [result] = lineage.parse(FIXTURES / "results", METADATA)
        who = result.payload["who_drug_susceptibility"]
        assert "rifampicin" in who
        assert "isoniazid" in who
        assert who["rifampicin"]["predicted"] == "resistant"
        assert who["rifampicin"]["variants"][0]["gene"] == "rpoB"

    def test_exclude_drug_resistance(self, tmp_path):
        fixture = FIXTURES / "results" / "AZ-TB-001.results.json"
        data = json.loads(fixture.read_text())
        target = tmp_path / "t.results.json"
        target.write_text(json.dumps(data))
        result = lineage.parse_file(target, METADATA, include_drug_resistance=False)
        assert "who_drug_susceptibility" not in result.payload

    def test_missing_dir(self, tmp_path):
        assert lineage.parse(tmp_path / "nope", METADATA) == []

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            lineage.parse_file(tmp_path / "nope.json", METADATA)

    def test_falls_back_to_filename_when_id_absent(self, tmp_path):
        target = tmp_path / "SAMPLE-Y.results.json"
        target.write_text(json.dumps({"main_lin": "lineage2"}))
        result = lineage.parse_file(target, METADATA)
        assert result.payload["sample_id"] == "SAMPLE-Y"

    def test_invalid_json_raises(self, tmp_path):
        target = tmp_path / "x.results.json"
        target.write_text("{not json")
        with pytest.raises(TBProfilerParseError):
            lineage.parse_file(target, METADATA)


class TestDrugResistance:
    def test_builds_who_map(self):
        data = json.loads((FIXTURES / "results" / "AZ-TB-001.results.json").read_text())
        who = drug_resistance.build_who_susceptibility(data)
        assert set(who.keys()) == {"rifampicin", "isoniazid"}
        assert who["rifampicin"]["who_confidences"] == ["Assoc w R"]

    def test_empty_dr_variants_returns_none(self):
        assert drug_resistance.build_who_susceptibility({"dr_variants": []}) is None
        assert drug_resistance.build_who_susceptibility({}) is None

    def test_to_amr_results_mirrors(self):
        fixture = FIXTURES / "results" / "AZ-TB-001.results.json"
        data = json.loads(fixture.read_text())
        rows = drug_resistance.to_amr_results(fixture, data, METADATA)
        assert len(rows) == 2
        assert {r.payload["drug"] for r in rows} == {"rifampicin", "isoniazid"}
        for r in rows:
            assert r.result_type == "amr_results"
            assert r.payload["reference_database"] == "WHO_catalogue"
            assert r.payload["tool_name"] == "tb-profiler"
            assert r.payload["drug_class"] == "antimycobacterial"
            assert r.payload["reference_accession"] == "WHO-Catalogue/2024-05-09"

    def test_mirror_empty_for_no_variants(self, tmp_path):
        target = tmp_path / "x.results.json"
        payload = {"id": "AZ-TB-002", "dr_variants": []}
        target.write_text(json.dumps(payload))
        assert drug_resistance.to_amr_results(target, payload, METADATA) == []


class TestPipeline:
    def test_parse_emits_typing_and_amr_mirror(self):
        results = parse(FIXTURES, METADATA)
        types_seen = [r.result_type for r in results]
        assert types_seen.count("tb_typing_results") == 1
        assert types_seen.count("amr_results") == 2

    def test_collect_files_empty(self):
        assert collect_files(FIXTURES, METADATA) == []

    def test_empty_tree(self, tmp_path):
        assert parse(tmp_path, METADATA) == []
