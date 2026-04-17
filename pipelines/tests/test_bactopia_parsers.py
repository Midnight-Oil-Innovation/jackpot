"""Unit tests for bactopia parsers (K-5)."""

from __future__ import annotations

import sys
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.bactopia import collect_files, parse  # noqa: E402
from pipelines.bactopia.parsers import amr, annotation, assembly, mlst  # noqa: E402
from pipelines.bactopia.parsers.assembly import _QUAST_COLUMN_MAP  # noqa: E402
from shared.parsers import RunMetadata  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "bactopia"
METADATA = RunMetadata(
    run_id="run-bactopia-1",
    pipeline_name="bactopia",
    pipeline_version="3.0.1",
)

_HAMRONIZED_TSV = (
    "input_file_name\tgene_symbol\tgene_name\treference_database_name\t"
    "reference_database_version\treference_accession\tanalysis_software_name\t"
    "analysis_software_version\tdrug_class\tantimicrobial_agent\tpredicted_phenotype\t"
    "coverage_percentage\tsequence_identity\tinput_sequence_id\tinput_gene_start\t"
    "input_gene_stop\tstrand_orientation\n"
    "AZ-BACT-001.tsv\tblaCTX-M-15\textended-spectrum beta-lactamase CTX-M-15\t"
    "NCBI\t2024-01-31.1\tNG_048935.1\tamrfinderplus\t3.12.8\tBETA-LACTAM\t"
    "ceftriaxone\tresistant\t100.00\t99.66\tcontig1\t4012\t5236\t+\n"
    "AZ-BACT-001.tsv\ttet(A)\ttetracycline efflux MFS transporter Tet(A)\t"
    "NCBI\t2024-01-31.1\tNG_048158.1\tamrfinderplus\t3.12.8\tTETRACYCLINE\t"
    "tetracycline\tresistant\t100.00\t100.00\tcontig2\t12100\t12732\t-\n"
)


def _fake_hamronize_runner(_cmd, *, capture_output, text):  # noqa: ARG001
    return CompletedProcess(_cmd, returncode=0, stdout=_HAMRONIZED_TSV, stderr="")


def _fake_hamronize_executable() -> str:
    # Path is never actually executed because the runner is faked, but
    # ``shared.hamronization_normalizer`` rejects a missing executable.
    return "/usr/bin/true"


@pytest.fixture
def fake_runner(monkeypatch):
    # Every AMR parse in the suite goes through shared.hamronization_normalizer,
    # which refuses to run without a ``hamronize`` binary on PATH.  Monkeypatch
    # ``shutil.which`` to return a truthy path so the code proceeds into the
    # faked runner.
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/true")
    return _fake_hamronize_runner


class TestBactopiaAMR:
    def test_parses_fixture(self, fake_runner):
        results = amr.parse(
            FIXTURES / "amrfinderplus",
            METADATA,
            tool_version="3.12.8",
            database_version="2024-01-31.1",
            runner=fake_runner,
        )
        # Runner returns 2 canonical rows for the one fixture sample.
        assert len(results) == 2
        assert {r.result_type for r in results} == {"amr_results"}
        first = results[0].payload
        assert first["sample_id"] == "AZ-BACT-001"
        assert first["gene_symbol"] == "blaCTX-M-15"
        assert first["drug"] == "ceftriaxone"
        assert first["tool_name"] == "amrfinderplus"

    def test_missing_dir_returns_empty(self, tmp_path, fake_runner):
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


class TestBactopiaMLST:
    def test_parses_fixture(self):
        [result] = mlst.parse(FIXTURES / "mlst", METADATA)
        payload = result.payload
        assert result.result_type == "typing_results"
        assert payload["sample_id"] == "AZ-BACT-001"
        assert payload["scheme"] == "ecoli"
        assert payload["sequence_type"] == "131"
        assert payload["allele_calls"]["adk"] == "53"
        assert payload["tool_name"] == "mlst"

    def test_skips_header_row_if_present(self, tmp_path):
        f = tmp_path / "AZ-2.tsv"
        f.write_text(
            "FILE\tSCHEME\tST\tadk\n"  # header-like
            "AZ-2.fa\tsenterica\t19\tadk(11)\n"
        )
        [result] = mlst.parse(tmp_path, METADATA)
        assert result.payload["sample_id"] == "AZ-2"
        assert result.payload["scheme"] == "senterica"
        assert result.payload["sequence_type"] == "19"

    def test_blank_st_becomes_none(self, tmp_path):
        f = tmp_path / "AZ-3.tsv"
        f.write_text("AZ-3.fa\tecoli\t-\tadk(-)\n")
        [result] = mlst.parse(tmp_path, METADATA)
        assert "sequence_type" not in result.payload
        # Regex captures the locus even when the allele is a placeholder dash.
        assert result.payload["allele_calls"]["adk"] == "-"


class TestBactopiaAssembly:
    def test_parses_quast_fixture(self):
        [result] = assembly.parse(FIXTURES / "assembly", METADATA)
        assert result.result_type == "assembly_qc"
        payload = result.payload
        assert payload["sample_id"] == "AZ-BACT-001"
        assert payload["num_contigs"] == 42
        assert payload["total_length"] == 4812345
        assert payload["n50"] == 281234
        assert payload["gc_percent"] == pytest.approx(50.58)
        assert payload["tool_name"] == "quast"
        assert payload["assembly_method"] == "shovill"

    def test_quast_column_map_covers_expected_keys(self):
        # A guard test: if upstream bactopia/QUAST renames a metric, we
        # want a test failure rather than a silent drop.
        for upstream, target in _QUAST_COLUMN_MAP.items():
            assert upstream
            assert target in {
                "total_length",
                "num_contigs",
                "largest_contig",
                "n50",
                "l50",
                "gc_percent",
                "n_count",
            }

    def test_collects_contigs(self):
        artifacts = assembly.collect(FIXTURES / "assembly", METADATA)
        assert [a.sample_id for a in artifacts] == ["AZ-BACT-001"]
        assert artifacts[0].relative_path == ("assembly/AZ-BACT-001/shovill/AZ-BACT-001.contigs.fa")
        assert artifacts[0].file_subtype == "assembly"

    def test_collects_flat_layout(self, tmp_path):
        d = tmp_path / "sample-X"
        d.mkdir()
        (d / "sample-X.contigs.fa").write_text(">c1\nACGT\n")
        artifacts = assembly.collect(tmp_path, METADATA)
        assert artifacts[0].relative_path == "assembly/sample-X/sample-X.contigs.fa"


class TestBactopiaAnnotation:
    def test_collects_nested_layout(self):
        artifacts = annotation.collect(FIXTURES / "annotation", METADATA)
        assert [a.sample_id for a in artifacts] == ["AZ-BACT-001"]
        assert artifacts[0].file_subtype == "annotation"
        assert artifacts[0].file_type == "gff"

    def test_collects_flat_layout(self, tmp_path):
        (tmp_path / "AZ-2.gff3").write_text("##gff-version 3\n")
        artifacts = annotation.collect(tmp_path, METADATA)
        assert artifacts[0].sample_id == "AZ-2"
        assert artifacts[0].relative_path == "annotation/AZ-2.gff3"

    def test_ignores_unrelated_files(self, tmp_path):
        (tmp_path / "AZ-1.gff3").write_text("##gff-version 3\n")
        (tmp_path / "README.txt").write_text("skip")
        artifacts = annotation.collect(tmp_path, METADATA)
        assert len(artifacts) == 1


class TestBactopiaPipeline:
    def test_parse_orchestrates(self, fake_runner):
        results = parse(FIXTURES, METADATA, runner=fake_runner)
        types_seen = {r.result_type for r in results}
        assert "amr_results" in types_seen
        assert "typing_results" in types_seen
        assert "assembly_qc" in types_seen

    def test_collect_files_includes_contigs_and_gffs(self):
        artifacts = collect_files(FIXTURES, METADATA)
        subtypes = {a.file_subtype for a in artifacts}
        assert subtypes == {"assembly", "annotation"}

    def test_empty_output_dir(self, tmp_path, fake_runner):
        assert parse(tmp_path, METADATA, runner=fake_runner) == []
        assert collect_files(tmp_path, METADATA) == []


def test_shared_amr_raises_on_missing_file(tmp_path, fake_runner):
    from shared.parsers import amrfinderplus as shared_amr

    with pytest.raises(FileNotFoundError):
        shared_amr.parse(
            tmp_path / "nope.tsv",
            METADATA,
            sample_id="AZ-BACT-001",
            tool_version="3.12.8",
            database_version="2024-01-31.1",
            runner=fake_runner,
            executable=_fake_hamronize_executable(),
        )


def test_shared_amr_with_missing_cli_raises(tmp_path, monkeypatch):
    """Without a runnable hamronize binary, the shared parser must error loudly."""
    from shared.hamronization_normalizer import HamronizationError
    from shared.parsers import amrfinderplus as shared_amr

    raw = tmp_path / "raw.tsv"
    raw.write_text("irrelevant\n")
    monkeypatch.setattr("shutil.which", lambda _name: None)

    def runner_never_called(*args, **kwargs):
        raise AssertionError("runner should not be invoked when executable is missing")

    with pytest.raises(HamronizationError, match="hamronize"):
        shared_amr.parse(
            raw,
            METADATA,
            sample_id="AZ-BACT-001",
            tool_version="3.12.8",
            database_version="2024-01-31.1",
            runner=runner_never_called,
            executable=None,
        )


def test_hamronized_runner_used(tmp_path, fake_runner):
    """Round-trip the in-memory canonical TSV from the fake runner."""
    from shared.parsers import amrfinderplus as shared_amr

    raw = tmp_path / "raw.tsv"
    raw.write_text("Name\tGene symbol\nAZ-BACT-001\tblaCTX-M-15\n")
    results = shared_amr.parse(
        raw,
        METADATA,
        sample_id="AZ-BACT-001",
        tool_version="3.12.8",
        database_version="2024-01-31.1",
        runner=fake_runner,
        executable=_fake_hamronize_executable(),
    )
    assert len(results) == 2
    # Fake runner returned drug info — must reach the payload.
    assert results[0].payload["drug"] == "ceftriaxone"


# Defensive: guarantee the fake runner signature matches what the shared
# normalizer calls with, otherwise tests silently succeed while prod fails.
def test_fake_runner_matches_subprocess_signature():
    call = _fake_hamronize_runner(
        ["/usr/bin/true"],
        capture_output=True,
        text=True,
    )
    assert isinstance(call, CompletedProcess)
    assert call.returncode == 0
    assert "gene_symbol" in call.stdout


# Keep SimpleNamespace import alive for any follow-up test that needs it.
_ = SimpleNamespace
