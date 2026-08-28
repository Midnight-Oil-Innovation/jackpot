"""Stage 1 static-validation tests for BYOP manifests (B-BYOP-2)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from backend.services.byop_validator import (
    CheckResult,
    ValidationReport,
    check_container_references,
    check_engine_syntax,
    check_license,
    check_operator_permissions,
    check_reference_data,
    check_schema_conformance,
    validate_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schema" / "byop-pipeline-manifest.schema.json"


def details_of(result: CheckResult) -> dict:
    """Narrow the optional details dict — every assertion below needs it present."""
    assert result.details is not None
    return result.details


AVAILABLE_REFERENCES = {"M. tuberculosis H37Rv"}
ALLOWED_LICENSES = {"AGPL-3.0", "GPL-3.0", "MIT", "Apache-2.0"}
OPERATOR_PERMISSIONS = {
    "read_metadata",
    "write_files",
    "external_api:https://api.tbprofiler.org/lineages",
}


@pytest.fixture(scope="session")
def schema() -> dict:
    """The real checked-in manifest schema — not a stub."""
    return json.loads(SCHEMA_PATH.read_text())


def _valid_manifest() -> dict:
    return {
        "api_version": "jackpot.io/v1",
        "kind": "Pipeline",
        "metadata": {
            "name": "my-tb-typer",
            "display_name": "M. tuberculosis WGS Typer",
            "version": "1.2.3",
            "description": "Lineage assignment and drug-resistance prediction.",
            "authors": [{"name": "Jane Doe", "email": "jane@example.org"}],
            "license": "AGPL-3.0",
        },
        "engine": {
            "type": "nextflow",
            "version": ">=24.04.0",
            "entrypoint": "main.nf",
        },
        "applicability": {
            "organism_names": ["Mycobacterium tuberculosis"],
            "source_types": ["human"],
            "data_types": ["paired_end_short_read"],
            "surveillance_relevant_required": False,
        },
        "resources": {
            "cpu_min": 4,
            "memory_gb_min": 16,
            "storage_gb_estimate": 20,
            "walltime_minutes_estimate": 90,
            "gpu_required": False,
            "internet_required": False,
        },
        "reference_data": {
            "bundled": False,
            "sources": [
                {
                    "name": "M. tuberculosis H37Rv",
                    "url": "https://ftp.ensembl.org/pub/H37Rv.fa.gz",
                    "checksum": "sha256:" + "ab" * 32,
                }
            ],
        },
        "containers": [{"image": "quay.io/biocontainers/tb-profiler:5.0.1"}],
        "inputs": [
            {"name": "sample_id", "type": "string", "source": "jackpot.sample.id"},
            {"name": "r1_fastq", "type": "file", "source": "jackpot.sample.files.r1"},
        ],
        "outputs": {
            "results_directory": "${result_uri}/",
            "results_schema": "results.schema.json",
            "primary_result_file": "tb_profiler.results.json",
            "pipeline_results_parser": "tb_profiler_v5",
        },
        "permissions": {
            "can_read_metadata": True,
            "can_write_files_to": ["${result_uri}/"],
            "can_call_external_apis": ["https://api.tbprofiler.org/lineages"],
            "can_use_gpu": False,
        },
    }


@pytest.fixture
def manifest() -> dict:
    return _valid_manifest()


# --- schema conformance ------------------------------------------------------


def test_schema_conformance_passes_for_valid_manifest(manifest, schema):
    result = check_schema_conformance(manifest, schema)
    assert isinstance(result, CheckResult)
    assert result.check_name == "schema_conformance"
    assert result.passed is True


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda m: m.pop("kind"), id="missing_required_top_level_field"),
        pytest.param(lambda m: m["metadata"].pop("license"), id="missing_required_nested_field"),
        pytest.param(lambda m: m.__setitem__("containers", "not-a-list"), id="wrong_type"),
        pytest.param(
            lambda m: m["resources"].__setitem__("cpu_min", "four"), id="wrong_scalar_type"
        ),
    ],
)
def test_schema_conformance_fails_for_invalid_manifest(manifest, schema, mutate):
    mutate(manifest)
    result = check_schema_conformance(manifest, schema)
    assert result.check_name == "schema_conformance"
    assert result.passed is False
    assert result.details is not None
    assert details_of(result)["error"]


# --- engine syntax -----------------------------------------------------------


@pytest.mark.parametrize("engine_type", ["nextflow", "snakemake", "wdl", "manifest"])
def test_engine_syntax_accepts_every_schema_enum_value(manifest, schema, engine_type):
    manifest["engine"]["type"] = engine_type
    result = check_engine_syntax(manifest, schema)
    assert result.passed is True
    assert details_of(result)["engine_type"] == engine_type


def test_engine_syntax_enum_matches_schema(schema):
    enum = schema["properties"]["engine"]["properties"]["type"]["enum"]
    assert set(enum) == {"nextflow", "snakemake", "wdl", "manifest"}


@pytest.mark.parametrize(
    "mutate, expected_detail_key",
    [
        pytest.param(
            lambda m: m["engine"].__setitem__("type", "cromwell"),
            "allowed_engines",
            id="unknown_engine",
        ),
        pytest.param(
            lambda m: m["engine"].pop("entrypoint"), "missing_fields", id="missing_entrypoint"
        ),
        pytest.param(
            lambda m: m["engine"].__setitem__("version", ""), "missing_fields", id="blank_version"
        ),
    ],
)
def test_engine_syntax_failures(manifest, schema, mutate, expected_detail_key):
    mutate(manifest)
    result = check_engine_syntax(manifest, schema)
    assert result.passed is False
    assert expected_detail_key in details_of(result)


def test_engine_syntax_fails_when_engine_block_absent(manifest, schema):
    manifest.pop("engine")
    result = check_engine_syntax(manifest, schema)
    assert result.passed is False


# --- container references ----------------------------------------------------


@pytest.mark.parametrize(
    "image",
    [
        "quay.io/biocontainers/tb-profiler:5.0.1",
        "ghcr.io/example/pipeline:v1",
        "quay.io/biocontainers/snippy@sha256:" + "cd" * 32,
    ],
)
def test_container_references_accepts_well_formed_images(manifest, schema, image):
    manifest["containers"] = [{"image": image}]
    result = check_container_references(manifest, schema)
    assert result.passed is True


@pytest.mark.parametrize(
    "containers",
    [
        pytest.param([{"image": ""}], id="blank"),
        pytest.param([{"digest": "sha256:" + "ab" * 32}], id="missing_key"),
        pytest.param([{"image": "quay.io/biocontainers/tb-profiler"}], id="no_tag_or_digest"),
        pytest.param([{"image": "has spaces:1.0"}], id="illegal_characters"),
    ],
)
def test_container_references_rejects_bad_images(manifest, schema, containers):
    manifest["containers"] = containers
    result = check_container_references(manifest, schema)
    assert result.passed is False
    assert details_of(result)["invalid_containers"]


def test_container_references_fails_when_list_empty(manifest, schema):
    manifest["containers"] = []
    result = check_container_references(manifest, schema)
    assert result.passed is False


# --- reference data ----------------------------------------------------------


def test_reference_data_passes_when_all_declared_are_available(manifest):
    result = check_reference_data(manifest, AVAILABLE_REFERENCES)
    assert result.passed is True


def test_reference_data_passes_when_bundled(manifest):
    manifest["reference_data"] = {"bundled": True}
    result = check_reference_data(manifest, set())
    assert result.passed is True


def test_reference_data_reports_single_missing_reference(manifest):
    result = check_reference_data(manifest, set())
    assert result.passed is False
    assert details_of(result)["missing_references"] == ["M. tuberculosis H37Rv"]


def test_reference_data_reports_every_missing_reference(manifest):
    manifest["reference_data"]["sources"].append(
        {
            "name": "Plasmodium falciparum 3D7",
            "url": "https://example.org/3D7.fa.gz",
            "checksum": "sha256:" + "ef" * 32,
        }
    )
    result = check_reference_data(manifest, set())
    assert result.passed is False
    assert details_of(result)["missing_references"] == [
        "M. tuberculosis H37Rv",
        "Plasmodium falciparum 3D7",
    ]


def test_reference_data_fails_when_unbundled_with_no_sources(manifest):
    manifest["reference_data"] = {"bundled": False, "sources": []}
    result = check_reference_data(manifest, AVAILABLE_REFERENCES)
    assert result.passed is False


# --- license -----------------------------------------------------------------


@pytest.mark.parametrize("spdx", sorted(ALLOWED_LICENSES))
def test_license_accepts_allowlisted_identifiers(manifest, spdx):
    manifest["metadata"]["license"] = spdx
    result = check_license(manifest, ALLOWED_LICENSES)
    assert result.passed is True


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda m: m["metadata"].__setitem__("license", "BSL-1.1"), id="not_allowlisted"
        ),
        pytest.param(lambda m: m["metadata"].pop("license"), id="absent"),
        pytest.param(lambda m: m["metadata"].__setitem__("license", "   "), id="blank"),
    ],
)
def test_license_failures(manifest, mutate):
    mutate(manifest)
    result = check_license(manifest, ALLOWED_LICENSES)
    assert result.passed is False
    assert details_of(result)["allowed_licenses"] == sorted(ALLOWED_LICENSES)


# --- operator permissions ----------------------------------------------------


def test_operator_permissions_passes_when_all_granted(manifest):
    result = check_operator_permissions(manifest, OPERATOR_PERMISSIONS)
    assert result.passed is True


def test_operator_permissions_passes_when_nothing_requested(manifest):
    manifest["permissions"] = {"can_read_metadata": False, "can_write_files_to": []}
    result = check_operator_permissions(manifest, OPERATOR_PERMISSIONS)
    assert result.passed is True
    assert details_of(result)["required_permissions"] == []


@pytest.mark.parametrize(
    "mutate, expected_missing",
    [
        pytest.param(
            lambda m: m["permissions"].__setitem__("can_use_gpu", True),
            ["use_gpu"],
            id="gpu_not_granted",
        ),
        pytest.param(
            lambda m: m["permissions"]["can_call_external_apis"].append("https://evil.example/x"),
            ["external_api:https://evil.example/x"],
            id="egress_not_allowlisted",
        ),
    ],
)
def test_operator_permissions_lists_missing_capabilities(manifest, mutate, expected_missing):
    mutate(manifest)
    result = check_operator_permissions(manifest, OPERATOR_PERMISSIONS)
    assert result.passed is False
    assert details_of(result)["missing_permissions"] == expected_missing


def test_operator_permissions_lists_all_missing_capabilities(manifest):
    result = check_operator_permissions(manifest, set())
    assert result.passed is False
    assert details_of(result)["missing_permissions"] == [
        "external_api:https://api.tbprofiler.org/lineages",
        "read_metadata",
        "write_files",
    ]


# --- validate_manifest integration -------------------------------------------


def test_validate_manifest_passes_end_to_end(manifest, schema):
    report = validate_manifest(
        manifest,
        schema,
        AVAILABLE_REFERENCES,
        ALLOWED_LICENSES,
        OPERATOR_PERMISSIONS,
    )
    assert isinstance(report, ValidationReport)
    assert report.manifest_id == "my-tb-typer@1.2.3"
    assert report.passed is True
    assert len(report.checks) == 6
    assert all(result.passed for result in report.checks)


def test_validate_manifest_reports_exactly_the_two_failing_checks(manifest, schema):
    manifest["metadata"]["license"] = "BSL-1.1"
    manifest["permissions"]["can_use_gpu"] = True

    report = validate_manifest(
        manifest,
        schema,
        AVAILABLE_REFERENCES,
        ALLOWED_LICENSES,
        OPERATOR_PERMISSIONS,
    )
    assert report.passed is False
    failed = {result.check_name for result in report.checks if not result.passed}
    assert failed == {"license", "operator_permissions"}


def test_validate_manifest_does_not_mutate_the_manifest(manifest, schema):
    before = copy.deepcopy(manifest)
    validate_manifest(manifest, schema, AVAILABLE_REFERENCES, ALLOWED_LICENSES, set())
    assert manifest == before


def test_validate_manifest_handles_structurally_broken_manifest(schema):
    report = validate_manifest({}, schema, set(), ALLOWED_LICENSES, set())
    assert report.manifest_id == "unknown"
    assert report.passed is False
    assert len(report.checks) == 6
