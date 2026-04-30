"""
M-4: End-to-end integration test — every wrapped pipeline against
     its canonical fixture tree.

This test is the "does the whole world still agree" guard for the
jackpot-nf package.  It walks every pipeline wrapper in
``pipelines/``, calls ``parse()`` against the fixture directory for
that wrapper, and asserts:

1. The call returns a non-empty ``list[ParsedResult]``.
2. Every payload ``result_type`` is one of the known set (either a
   Pydantic-backed ``amr_results`` / ``typing_results`` / etc., or a
   recognised JSONB metric group like ``pipeline_metrics`` /
   ``sample_files``).
3. For every payload whose ``result_type`` maps to a Pydantic class
   in :data:`shared.schemas.RESULT_SCHEMAS`, the payload validates
   against that schema — the backend registration endpoint will
   reject payloads that fail this check, so this is the earliest we
   can catch a parser-schema drift.
4. ``collect_files()`` returns well-formed FileArtifact objects
   (even if empty).

Why it's ``@pytest.mark.integration`` and skipped in CI:

* It loads every fixture + every parser in a single test run, so
  it is noticeably slower than the unit suite.
* It also imports the hamronization-normalizer runner fake — the
  per-pipeline unit tests exercise that path exhaustively; here we
  only need the end-to-end happy path.

The CI configuration runs this explicitly via
``pytest -m integration tests/test_pipeline_integration_e2e.py``
in the ``nf-integration`` job, so the coverage is still enforced —
just not in the fast-feedback default run.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.parsers import FileArtifact, ParsedResult, RunMetadata  # noqa: E402
from shared.schemas import RESULT_SCHEMAS  # noqa: E402

FIXTURE_ROOT = Path(__file__).parent / "fixtures"

# Result-type identifiers the parsers are allowed to emit.  The
# registration endpoint only accepts these; anything else is a bug.
# Canonical schemas come from RESULT_SCHEMAS; the metrics bucket is
# JSONB-only (intentionally schemaless per spec).
_ALLOWED_RESULT_TYPES: set[str] = set(RESULT_SCHEMAS) | {
    "pipeline_metrics",
    "sample_files",
}

# Canonical hAMRonization output reused for every AMR-producing pipeline.
# We don't run the real hamronize binary in this test — the fake runner
# returns this exact TSV, parameterised by the per-pipeline sample ID so
# the downstream parsers derive a sensible sample_id from the filename.
_CANONICAL_HAMRONIZED_TSV = (
    "input_file_name\tgene_symbol\tgene_name\treference_database_name\t"
    "reference_database_version\treference_accession\tanalysis_software_name\t"
    "analysis_software_version\tdrug_class\tantimicrobial_agent\t"
    "predicted_phenotype\tcoverage_percentage\tsequence_identity\t"
    "input_sequence_id\tinput_gene_start\tinput_gene_stop\tstrand_orientation\n"
    "{sample}.tsv\tblaCTX-M-15\textended-spectrum beta-lactamase CTX-M-15\t"
    "NCBI\t2024-01-31.1\tNG_048935.1\tamrfinderplus\t3.12.8\tBETA-LACTAM\t"
    "ceftriaxone\tresistant\t100.00\t99.66\tcontig1\t4012\t5236\t+\n"
)


def _build_hamronize_runner(sample_id_from_cmd: Callable[[list[str]], str]):
    """Return a ``subprocess.run``-compatible stand-in.

    The real hamronize CLI reads a raw AMRFinderPlus TSV and writes a
    canonical TSV to stdout; our replacement fakes that step by
    returning :data:`_CANONICAL_HAMRONIZED_TSV` with the sample_id
    interpolated from the command line so the downstream parser lifts
    a realistic ``input_file_name``.
    """

    def _runner(cmd, *, capture_output, text):  # noqa: ARG001
        sample = sample_id_from_cmd(cmd)
        return CompletedProcess(
            cmd,
            returncode=0,
            stdout=_CANONICAL_HAMRONIZED_TSV.format(sample=sample),
            stderr="",
        )

    return _runner


def _sample_from_cmd_tail(cmd: list[str]) -> str:
    """Pull ``<sample>.tsv`` off the end of the hamronize command and
    strip the suffix.  The hamronize CLI accepts the input path as
    its final positional argument."""
    for token in reversed(cmd):
        t = str(token)
        if t.endswith(".tsv") and not t.startswith("-"):
            return Path(t).stem
    return "UNKNOWN"


@pytest.fixture
def hamronize_runner(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/true")
    return _build_hamronize_runner(_sample_from_cmd_tail)


@dataclass(frozen=True)
class PipelineCase:
    """One row of the integration matrix.

    Attributes:
        wrapper: Python module name under ``pipelines/``.
        fixture_subdir: Directory under ``tests/fixtures/`` to pass
            as the parser's ``output_dir``.
        upstream_name: Human-readable pipeline identifier — used
            only for the ``RunMetadata.pipeline_name``.
        pipeline_version: A known-good version string from the
            wrapper's ``SUPPORTED_PIPELINE_VERSIONS``.
        uses_hamronize: If True, the parser needs an injected
            hamronize runner fixture.
        expects_results: If True, the fixture tree must produce at
            least one ``ParsedResult`` — catches accidental fixture
            regressions where a subdirectory gets renamed and the
            parser silently emits nothing.
    """

    wrapper: str
    fixture_subdir: str
    upstream_name: str
    pipeline_version: str
    uses_hamronize: bool = False
    expects_results: bool = True


# Keep this list in sync with the nf/README.md parser version
# matrix.  Adding a new wrapper here without a fixture under
# tests/fixtures/<subdir>/ will fail the assertion below.
_PIPELINE_CASES: list[PipelineCase] = [
    PipelineCase("cecret", "cecret", "UPHL-BioNGS/Cecret", "3.66"),
    PipelineCase("viralrecon", "viralrecon", "nf-core/viralrecon", "2.7.0"),
    PipelineCase("walkercreek", "walkercreek", "UPHL-BioNGS/walkercreek", "1.2"),
    PipelineCase("bactopia", "bactopia", "bactopia/bactopia", "3.1.0", uses_hamronize=True),
    PipelineCase("grandeur", "grandeur", "UPHL-BioNGS/Grandeur", "4.2.0", uses_hamronize=True),
    PipelineCase("mycosnp", "mycosnp", "CDCgov/mycosnp-nf", "2.1"),
    PipelineCase("tb_profiler", "tb_profiler", "jodyphelan/tb-profiler", "6.2.0"),
    PipelineCase("mag", "mag", "nf-core/mag", "3.1.0"),
    PipelineCase("taxprofiler", "taxprofiler", "nf-core/taxprofiler", "1.2.0"),
    PipelineCase(
        "pathogensurveillance",
        "pathogensurveillance",
        "nf-core/pathogensurveillance",
        "1.1.0",
        uses_hamronize=True,
    ),
]


def _import_wrapper(wrapper: str) -> tuple[Callable, Callable, list[str]]:
    """Return (parse, collect_files, SUPPORTED_PIPELINE_VERSIONS) for a wrapper."""
    module = __import__(f"pipelines.{wrapper}", fromlist=["parse", "collect_files"])
    return module.parse, module.collect_files, module.SUPPORTED_PIPELINE_VERSIONS


def _invoke(
    case: PipelineCase,
    metadata: RunMetadata,
    runner: Callable | None,
) -> tuple[list[ParsedResult], list[FileArtifact]]:
    """Call ``parse`` and ``collect_files`` for a case with the right kwargs."""
    parse_fn, collect_fn, _ = _import_wrapper(case.wrapper)
    fixture_dir = FIXTURE_ROOT / case.fixture_subdir
    if case.uses_hamronize:
        parsed = parse_fn(fixture_dir, metadata, runner=runner)
    else:
        parsed = parse_fn(fixture_dir, metadata)
    files = collect_fn(fixture_dir, metadata)
    return parsed, files


def _validate_against_schema(payload: dict[str, Any], result_type: str) -> None:
    """Raise AssertionError if payload doesn't match its Pydantic schema."""
    schema = RESULT_SCHEMAS.get(result_type)
    if schema is None:
        return  # JSONB-only result type — no schema to check.
    try:
        schema.model_validate(payload)
    except ValidationError as exc:
        raise AssertionError(
            f"{result_type} payload failed {schema.__name__} validation: {exc}"
        ) from exc


@pytest.mark.integration
class TestEndToEndPipelineIntegration:
    """One full parse + collect + validate pass per wrapped pipeline.

    The class is decorated with ``@pytest.mark.integration`` so the
    default CI ``pytest -q`` run skips it. The slower
    ``pytest -m integration`` job executes it explicitly.
    """

    @pytest.mark.parametrize(
        "case",
        _PIPELINE_CASES,
        ids=[c.wrapper for c in _PIPELINE_CASES],
    )
    def test_parse_produces_valid_payloads(self, case: PipelineCase, hamronize_runner):
        fixture_dir = FIXTURE_ROOT / case.fixture_subdir
        assert fixture_dir.exists(), (
            f"{case.wrapper}: missing fixture dir {fixture_dir} — update "
            "tests/fixtures/ or the PipelineCase matrix"
        )

        metadata = RunMetadata(
            run_id=f"run-e2e-{case.wrapper}",
            pipeline_name=case.upstream_name,
            pipeline_version=case.pipeline_version,
        )

        parsed, files = _invoke(
            case,
            metadata,
            runner=hamronize_runner if case.uses_hamronize else None,
        )

        if case.expects_results:
            assert len(parsed) >= 1, (
                f"{case.wrapper}: parse produced no results against the "
                f"canonical fixture tree — probable fixture/parser drift"
            )

        # Surface-level invariant: no unknown result types reach the
        # transport layer. The backend only accepts _ALLOWED_RESULT_TYPES.
        seen_types = {r.result_type for r in parsed}
        unknown = seen_types - _ALLOWED_RESULT_TYPES
        assert not unknown, (
            f"{case.wrapper}: emitted unknown result_type(s) "
            f"{unknown}. Allowed: {sorted(_ALLOWED_RESULT_TYPES)}"
        )

        for r in parsed:
            assert isinstance(r, ParsedResult), (
                f"{case.wrapper}: parse() yielded a non-ParsedResult: {type(r).__name__}"
            )
            assert isinstance(r.payload, dict) and "sample_id" in r.payload, (
                f"{case.wrapper}: payload missing sample_id — {r.payload!r}"
            )
            _validate_against_schema(r.payload, r.result_type)

        for f in files:
            assert isinstance(f, FileArtifact), (
                f"{case.wrapper}: collect_files() yielded a non-FileArtifact: {type(f).__name__}"
            )

    def test_every_wrapper_is_covered(self):
        """Matrix completeness guard: every directory under pipelines/
        that looks like a wrapper must appear in _PIPELINE_CASES, and
        every entry in _PIPELINE_CASES must have a fixture directory."""
        pipelines_dir = Path(__file__).parent.parent / "pipelines"
        wrappers_on_disk = {
            p.name
            for p in pipelines_dir.iterdir()
            if p.is_dir()
            and (p / "parsers" / "__init__.py").exists()
            and not p.name.startswith("_")
        }
        wrappers_in_matrix = {c.wrapper for c in _PIPELINE_CASES}
        missing_from_matrix = wrappers_on_disk - wrappers_in_matrix
        assert not missing_from_matrix, (
            "Wrappers on disk but not in the integration matrix: "
            f"{sorted(missing_from_matrix)} — add a PipelineCase entry"
        )
        missing_fixtures = {
            c.wrapper for c in _PIPELINE_CASES if not (FIXTURE_ROOT / c.fixture_subdir).exists()
        }
        assert not missing_fixtures, (
            "PipelineCase entries without fixture dirs: "
            f"{sorted(missing_fixtures)} — add tests/fixtures/<name>/"
        )
