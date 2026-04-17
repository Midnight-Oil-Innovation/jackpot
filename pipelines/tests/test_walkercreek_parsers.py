"""Unit tests for walkercreek parsers (J-5)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.walkercreek import collect_files, parse  # noqa: E402
from pipelines.walkercreek.parsers import consensus, irma  # noqa: E402
from pipelines.walkercreek.parsers.irma import IRMAParseError  # noqa: E402
from shared.parsers import RunMetadata  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "walkercreek"
METADATA = RunMetadata(
    run_id="run-walkercreek-1",
    pipeline_name="walkercreek",
    pipeline_version="1.1.4",
)


class TestIRMA:
    def test_parses_tsv_fixture(self):
        results = irma.parse(FIXTURES / "typing" / "typing_summary.tsv", METADATA)
        assert len(results) == 3
        assert {r.result_type for r in results} == {"typing_results"}
        first = results[0].payload
        assert first["sample_id"] == "AZ-FLU-001"
        assert first["scheme"] == "h3n2"
        assert first["sequence_type"] == "H3N2"
        assert first["clade"] == "3C.2a1b.2a.2a.1"
        assert first["tool_name"] == "irma"
        assert first["tool_version"] == "1.1.4"

    def test_accepts_csv(self, tmp_path):
        f = tmp_path / "typing.csv"
        f.write_text("sample_id,subtype,clade,irma_version,scheme\nAZ-1,H3N2,3C,1.0,h3n2\n")
        [result] = irma.parse(f, METADATA)
        assert result.payload["sample_id"] == "AZ-1"

    def test_missing_columns_raises(self, tmp_path):
        f = tmp_path / "typing.tsv"
        f.write_text("sample_id\tirma_version\nAZ-1\t1.0\n")
        with pytest.raises(IRMAParseError, match="subtype"):
            irma.parse(f, METADATA)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            irma.parse(tmp_path / "none.tsv", METADATA)

    def test_default_scheme_from_subtype(self, tmp_path):
        f = tmp_path / "t.tsv"
        f.write_text(
            "sample_id\tsubtype\nAZ-1\tH1N1pdm09\nAZ-2\tH3N2\nAZ-3\tRSV-B\nAZ-4\tUnknown\n"
        )
        results = irma.parse(f, METADATA)
        schemes = [r.payload["scheme"] for r in results]
        assert schemes == ["h1n1", "h3n2", "rsv", "irma"]

    def test_skips_blank_sample_row(self, tmp_path):
        f = tmp_path / "t.tsv"
        f.write_text("sample_id\tsubtype\n\tH3N2\nAZ-1\tH3N2\n")
        [result] = irma.parse(f, METADATA)
        assert result.payload["sample_id"] == "AZ-1"


class TestConsensus:
    def test_nested_layout(self):
        d = FIXTURES / "consensus"
        artifacts = consensus.collect(d, METADATA)
        by_sample: dict[str, list[str]] = {}
        for a in artifacts:
            by_sample.setdefault(a.sample_id, []).append(a.file_subtype)
        # Illumina-style AZ-FLU-001 has nested dir, Nanopore-style AZ-FLU-002 is flat
        assert sorted(by_sample["AZ-FLU-001"]) == ["segment_HA", "segment_NA"]
        assert sorted(by_sample["AZ-FLU-002"]) == ["segment_HA", "segment_NA"]
        # Relative paths keep consensus/ prefix (relative to output_dir)
        assert all(a.relative_path.startswith("consensus/") for a in artifacts)

    def test_returns_empty_for_missing(self, tmp_path):
        assert consensus.collect(tmp_path / "nope", METADATA) == []

    def test_ignores_files_without_segment(self, tmp_path):
        d = tmp_path / "consensus"
        d.mkdir()
        (d / "AZ-1_HA.fa").write_text(">x\nACGT\n")
        (d / "standalone.fa").write_text(">x\nACGT\n")  # no underscore -> skip
        (d / "README").write_text("ignore")
        artifacts = consensus.collect(d, METADATA)
        assert len(artifacts) == 1
        assert artifacts[0].sample_id == "AZ-1"
        assert artifacts[0].file_subtype == "segment_HA"

    def test_accepts_gzipped(self, tmp_path):
        d = tmp_path / "consensus"
        d.mkdir()
        (d / "AZ-1_HA.fa.gz").write_bytes(b"\x1f\x8b")
        artifacts = consensus.collect(d, METADATA)
        assert artifacts[0].file_subtype == "segment_HA"


class TestPipelineParse:
    def test_parses_full_fixture(self):
        results = parse(FIXTURES, METADATA)
        assert len(results) == 3
        assert {r.payload["sample_id"] for r in results} == {
            "AZ-FLU-001",
            "AZ-FLU-002",
            "AZ-RSV-001",
        }

    def test_collects_per_segment_files(self):
        files = collect_files(FIXTURES, METADATA)
        assert len(files) == 4
        assert {f.sample_id for f in files} == {"AZ-FLU-001", "AZ-FLU-002"}

    def test_empty_output_dir(self, tmp_path):
        assert parse(tmp_path, METADATA) == []
        assert collect_files(tmp_path, METADATA) == []
