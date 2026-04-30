"""
M-2: Shared AMR normalization invariant — cross-pipeline validator.

Three JACKPOT pipelines call AMRFinderPlus and emit ``amr_results``:

* ``pipelines.bactopia.parsers.amr``
* ``pipelines.grandeur.parsers.amr``
* ``pipelines.pathogensurveillance.parsers.amr``

All three **must** route through ``shared.parsers.amrfinderplus``, which
pipes the raw tool output through the hAMRonization CLI and parses the
canonical TSV.  The JACKPOT surveillance guarantee is that an AMR hit
reported for sample X shows up identically in cross-pipeline searches
regardless of which pipeline produced it — so the canonical AMRResult
payload must match **field-for-field** when the three parsers are given
matched input (same hamronized output).

This test asserts that invariant.  It also guards against a future
change that silently introduces a parallel AMR path in one of the three
pipelines (e.g. a parser that reads the raw AMRFinderPlus TSV directly
without hamronizing): such a change would almost certainly break the
canonical comparison because the column mapping differs, and we catch
it here at test time.

The test uses an in-process faked hamronize runner (same pattern as
``test_bactopia_parsers.py``) so CI does not need the hamronize binary.
"""

from __future__ import annotations

import sys
from pathlib import Path
from subprocess import CompletedProcess

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.bactopia.parsers import amr as bactopia_amr  # noqa: E402
from pipelines.grandeur.parsers import amr as grandeur_amr  # noqa: E402
from pipelines.pathogensurveillance.parsers import amr as psv_amr  # noqa: E402
from shared.parsers import RunMetadata  # noqa: E402
from shared.parsers import amrfinderplus as shared_amr  # noqa: E402

METADATA = RunMetadata(
    run_id="run-amr-invariant-1",
    pipeline_name="cross-pipeline-amr",
    pipeline_version="3.12.8",
)

# Canonical hAMRonization output for a synthetic two-gene hit.  Each of
# the three parsers gets this exact TSV back when they invoke the
# hamronize CLI, so the emitted AMRResult payloads are expected to be
# identical (modulo the sample_id, which is derived from the input
# filename — we write all three fixtures under a common sample_id so
# even that lines up).
CANONICAL_TSV = (
    "input_file_name\tgene_symbol\tgene_name\treference_database_name\t"
    "reference_database_version\treference_accession\tanalysis_software_name\t"
    "analysis_software_version\tdrug_class\tantimicrobial_agent\tpredicted_phenotype\t"
    "coverage_percentage\tsequence_identity\tinput_sequence_id\tinput_gene_start\t"
    "input_gene_stop\tstrand_orientation\n"
    "AZ-XP-001.tsv\tblaCTX-M-15\textended-spectrum beta-lactamase CTX-M-15\t"
    "NCBI\t2024-01-31.1\tNG_048935.1\tamrfinderplus\t3.12.8\tBETA-LACTAM\t"
    "ceftriaxone\tresistant\t100.00\t99.66\tcontig1\t4012\t5236\t+\n"
    "AZ-XP-001.tsv\ttet(A)\ttetracycline efflux MFS transporter Tet(A)\t"
    "NCBI\t2024-01-31.1\tNG_048158.1\tamrfinderplus\t3.12.8\tTETRACYCLINE\t"
    "tetracycline\tresistant\t100.00\t100.00\tcontig2\t12100\t12732\t-\n"
)


def _runner(cmd, *, capture_output, text):  # noqa: ARG001
    return CompletedProcess(cmd, returncode=0, stdout=CANONICAL_TSV, stderr="")


@pytest.fixture
def raw_amr_tree(tmp_path, monkeypatch):
    """Stage one matching ``AZ-XP-001.tsv`` under each pipeline's AMR layout.

    The raw content is identical across the three pipelines — all we
    actually need is a file that exists; the hamronize runner is faked,
    so the file's contents never drive the parsed output.
    """
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/true")
    raw = "placeholder\n"
    for layout in ("bactopia", "grandeur", "psv"):
        d = tmp_path / layout / "amrfinderplus"
        d.mkdir(parents=True)
        (d / "AZ-XP-001.tsv").write_text(raw)
    return tmp_path


def _payloads(results) -> list[dict]:
    """Stable-ordered payload list for equality comparison."""
    return sorted(
        (r.payload for r in results),
        key=lambda p: (p["sample_id"], p["gene_symbol"], p.get("contig_id", "")),
    )


class TestAMRNormalizationInvariant:
    def test_all_three_pipelines_emit_identical_payloads(self, raw_amr_tree):
        common = dict(
            metadata=METADATA,
            tool_version="3.12.8",
            database_version="2024-01-31.1",
            runner=_runner,
        )
        b = bactopia_amr.parse(raw_amr_tree / "bactopia" / "amrfinderplus", **common)
        g = grandeur_amr.parse(raw_amr_tree / "grandeur" / "amrfinderplus", **common)
        p = psv_amr.parse(raw_amr_tree / "psv" / "amrfinderplus", **common)

        bp = _payloads(b)
        gp = _payloads(g)
        pp = _payloads(p)

        # Every pipeline emits exactly two canonical rows for the shared fixture.
        assert len(bp) == len(gp) == len(pp) == 2

        # Field-for-field equivalence across the three pipelines.
        assert bp == gp, "bactopia vs. Grandeur AMR payloads diverged"
        assert gp == pp, "Grandeur vs. pathogensurveillance AMR payloads diverged"

    def test_all_three_pipelines_share_the_same_shared_parser(self):
        """Guard against a fork of the shared AMR parser.  A diverging
        pipeline-local parser would bypass hAMRonization and silently
        change the canonical payload."""
        assert bactopia_amr.shared_amr is shared_amr
        assert grandeur_amr.shared_amr is shared_amr
        assert psv_amr.shared_amr is shared_amr

    def test_canonical_fields_present_on_every_row(self, raw_amr_tree):
        results = bactopia_amr.parse(
            raw_amr_tree / "bactopia" / "amrfinderplus",
            metadata=METADATA,
            tool_version="3.12.8",
            database_version="2024-01-31.1",
            runner=_runner,
        )
        required = {"sample_id", "gene_symbol", "tool_name", "reference_database"}
        for r in results:
            missing = required - r.payload.keys()
            assert not missing, f"Missing canonical AMR fields: {missing}"

    def test_sample_id_derived_from_filename(self, raw_amr_tree):
        """Every pipeline derives sample_id from the per-sample AMR TSV
        filename, not from the hamronized TSV content.  This keeps the
        sample_id bound to the file the wrapper staged."""
        common = dict(
            metadata=METADATA,
            tool_version="3.12.8",
            database_version="2024-01-31.1",
            runner=_runner,
        )
        for parser, sub in (
            (bactopia_amr, "bactopia"),
            (grandeur_amr, "grandeur"),
            (psv_amr, "psv"),
        ):
            results = parser.parse(raw_amr_tree / sub / "amrfinderplus", **common)
            sample_ids = {r.payload["sample_id"] for r in results}
            assert sample_ids == {"AZ-XP-001"}

    def test_tool_name_is_amrfinderplus_everywhere(self, raw_amr_tree):
        common = dict(
            metadata=METADATA,
            tool_version="3.12.8",
            database_version="2024-01-31.1",
            runner=_runner,
        )
        for parser, sub in (
            (bactopia_amr, "bactopia"),
            (grandeur_amr, "grandeur"),
            (psv_amr, "psv"),
        ):
            results = parser.parse(raw_amr_tree / sub / "amrfinderplus", **common)
            assert {r.payload["tool_name"] for r in results} == {"amrfinderplus"}
