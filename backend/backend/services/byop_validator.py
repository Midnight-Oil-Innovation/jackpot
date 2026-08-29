"""BYOP Stage 1 static validation.

Runs the six static checks from `docs/byop_and_eukaryotic_design.md` §5.2
against a parsed `jackpot-pipeline.yaml` manifest, before any container is
pulled or any sandbox is started (that is Stage 2, `byop_sandbox.py`).

Every external input arrives as an argument — the parsed manifest, the parsed
JSON Schema, and the three operator policy sets. The module performs no file
reads, no network calls, and no database access, so the whole battery is unit
testable without fixtures or mocks.

Failures are values, not exceptions: each check returns a `CheckResult` and
`validate_manifest` aggregates them into a `ValidationReport`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import jsonschema

__all__ = [
    "CheckResult",
    "ValidationReport",
    "check_schema_conformance",
    "check_engine_syntax",
    "check_container_references",
    "check_reference_data",
    "check_license",
    "check_operator_permissions",
    "validate_manifest",
]


@dataclass
class CheckResult:
    """Outcome of a single Stage 1 check."""

    check_name: str
    passed: bool
    message: str
    details: dict[str, Any] | None = None


@dataclass
class ValidationReport:
    """Aggregate Stage 1 outcome for one manifest."""

    manifest_id: str
    passed: bool
    checks: list[CheckResult] = field(default_factory=list)


def manifest_identifier(manifest: dict) -> str:
    """Best-effort human-readable id — `name@version`, or `unknown` if absent.

    Runs against manifests that have already failed schema conformance, so it
    never assumes the metadata block is well-formed.
    """
    metadata = manifest.get("metadata")
    if not isinstance(metadata, dict):
        return "unknown"
    name = metadata.get("name")
    version = metadata.get("version")
    if not isinstance(name, str) or not name:
        return "unknown"
    if isinstance(version, str) and version:
        return f"{name}@{version}"
    return name


def _engine_enum(schema: dict) -> list[str]:
    """Allowed `engine.type` values, read from the schema at runtime."""
    return list(
        schema.get("properties", {})
        .get("engine", {})
        .get("properties", {})
        .get("type", {})
        .get("enum", [])
    )


def _engine_required_fields(schema: dict) -> list[str]:
    """Fields the schema marks required inside the `engine` block."""
    return list(schema.get("properties", {}).get("engine", {}).get("required", []))


def _container_pattern(schema: dict) -> str:
    """Registry-reference pattern the schema enforces on `containers[].image`."""
    return (
        schema.get("properties", {})
        .get("containers", {})
        .get("items", {})
        .get("properties", {})
        .get("image", {})
        .get("pattern", "")
    )


def check_schema_conformance(manifest: dict, schema: dict) -> CheckResult:
    """Validate the manifest against the BYOP manifest JSON Schema (§5.2a)."""
    try:
        jsonschema.validate(instance=manifest, schema=schema)
    except jsonschema.ValidationError as exc:
        return CheckResult(
            check_name="schema_conformance",
            passed=False,
            message="Manifest does not conform to the BYOP manifest schema.",
            details={
                "error": exc.message,
                "path": "/".join(str(part) for part in exc.absolute_path),
            },
        )
    return CheckResult(
        check_name="schema_conformance",
        passed=True,
        message="Manifest conforms to the BYOP manifest schema.",
    )


def check_engine_syntax(manifest: dict, schema: dict) -> CheckResult:
    """Check the engine block declares a known engine and all required fields.

    Full DSL linting needs the engine runtime and belongs to Stage 2 — this is
    a declaration-level check only (§5.2b).
    """
    allowed = _engine_enum(schema)
    engine = manifest.get("engine")
    if not isinstance(engine, dict):
        return CheckResult(
            check_name="engine_syntax",
            passed=False,
            message="Manifest has no engine block.",
            details={"allowed_engines": allowed},
        )

    engine_type = engine.get("type")
    if engine_type not in allowed:
        return CheckResult(
            check_name="engine_syntax",
            passed=False,
            message=f"Unknown engine type: {engine_type!r}.",
            details={"engine_type": engine_type, "allowed_engines": allowed},
        )

    missing = [
        name
        for name in _engine_required_fields(schema)
        if not isinstance(engine.get(name), str) or not engine.get(name)
    ]
    if missing:
        return CheckResult(
            check_name="engine_syntax",
            passed=False,
            message=f"Engine block is missing required fields: {', '.join(sorted(missing))}.",
            details={"missing_fields": sorted(missing), "engine_type": engine_type},
        )

    return CheckResult(
        check_name="engine_syntax",
        passed=True,
        message=f"Engine block is well-formed for engine {engine_type!r}.",
        details={"engine_type": engine_type},
    )


def check_container_references(manifest: dict, schema: dict) -> CheckResult:
    """Check every declared container image is a syntactically valid reference.

    Presence and shape only — registry reachability and digest resolution are
    network operations and belong to Stage 2 (§5.2c).
    """
    pattern = _container_pattern(schema)
    containers = manifest.get("containers")
    if not isinstance(containers, list) or not containers:
        return CheckResult(
            check_name="container_references",
            passed=False,
            message="Manifest declares no containers.",
        )

    invalid: list[dict[str, Any]] = []
    for index, entry in enumerate(containers):
        image = entry.get("image") if isinstance(entry, dict) else None
        if not isinstance(image, str) or not image.strip():
            invalid.append({"index": index, "image": image, "reason": "missing_or_blank"})
        elif pattern and not re.fullmatch(pattern, image):
            invalid.append({"index": index, "image": image, "reason": "malformed_reference"})

    if invalid:
        return CheckResult(
            check_name="container_references",
            passed=False,
            message=f"{len(invalid)} container reference(s) are missing or malformed.",
            details={"invalid_containers": invalid},
        )

    return CheckResult(
        check_name="container_references",
        passed=True,
        message=f"All {len(containers)} container reference(s) are well-formed.",
    )


def check_reference_data(manifest: dict, available_references: set[str]) -> CheckResult:
    """Check every declared non-bundled reference dataset is available (§5.2d).

    A manifest with `reference_data.bundled: true` ships its own references and
    needs nothing from the operator's cache.
    """
    reference_data = manifest.get("reference_data")
    if not isinstance(reference_data, dict):
        return CheckResult(
            check_name="reference_data",
            passed=False,
            message="Manifest has no reference_data block.",
        )

    if reference_data.get("bundled") is True:
        return CheckResult(
            check_name="reference_data",
            passed=True,
            message="Reference data is bundled with the pipeline.",
        )

    sources = reference_data.get("sources")
    if not isinstance(sources, list) or not sources:
        return CheckResult(
            check_name="reference_data",
            passed=False,
            message="Manifest declares bundled=false but lists no reference sources.",
        )

    declared = [
        str(entry["name"]) for entry in sources if isinstance(entry, dict) and entry.get("name")
    ]
    missing = sorted({name for name in declared if name not in available_references})
    if missing:
        return CheckResult(
            check_name="reference_data",
            passed=False,
            message=f"{len(missing)} declared reference dataset(s) are not available.",
            details={"missing_references": missing, "declared_references": declared},
        )

    return CheckResult(
        check_name="reference_data",
        passed=True,
        message=f"All {len(declared)} declared reference dataset(s) are available.",
    )


def check_license(manifest: dict, allowed_licenses: set[str]) -> CheckResult:
    """Check the declared SPDX license against the operator policy (§5.2e)."""
    metadata = manifest.get("metadata")
    declared = metadata.get("license") if isinstance(metadata, dict) else None
    if not isinstance(declared, str) or not declared.strip():
        return CheckResult(
            check_name="license",
            passed=False,
            message="Manifest does not declare a license.",
            details={"allowed_licenses": sorted(allowed_licenses)},
        )

    if declared not in allowed_licenses:
        return CheckResult(
            check_name="license",
            passed=False,
            message=f"License {declared!r} is not permitted by operator policy.",
            details={"license": declared, "allowed_licenses": sorted(allowed_licenses)},
        )

    return CheckResult(
        check_name="license",
        passed=True,
        message=f"License {declared!r} is permitted by operator policy.",
        details={"license": declared},
    )


def required_permissions(manifest: dict) -> list[str]:
    """Capability tokens the manifest's permissions block asks the operator for.

    The manifest declares capabilities structurally (§2.1); the operator grants
    them as a flat token set, so the two are reconciled here. External-API
    access is tokenised per URL to keep egress allowlisting per-endpoint.
    """
    permissions = manifest.get("permissions")
    if not isinstance(permissions, dict):
        return []

    required: list[str] = []
    if permissions.get("can_read_metadata", True):
        required.append("read_metadata")
    if permissions.get("can_write_files_to"):
        required.append("write_files")
    if permissions.get("can_use_gpu"):
        required.append("use_gpu")
    for url in permissions.get("can_call_external_apis") or []:
        required.append(f"external_api:{url}")
    return required


def check_operator_permissions(manifest: dict, operator_permissions: set[str]) -> CheckResult:
    """Check every capability the manifest requests has been granted (§5.2f)."""
    required = required_permissions(manifest)
    missing = sorted({token for token in required if token not in operator_permissions})
    if missing:
        return CheckResult(
            check_name="operator_permissions",
            passed=False,
            message=f"{len(missing)} requested capability/capabilities are not granted.",
            details={"missing_permissions": missing, "required_permissions": required},
        )

    return CheckResult(
        check_name="operator_permissions",
        passed=True,
        message=f"All {len(required)} requested capability/capabilities are granted.",
        details={"required_permissions": required},
    )


def validate_manifest(
    manifest: dict,
    schema: dict,
    available_references: set[str],
    allowed_licenses: set[str],
    operator_permissions: set[str],
) -> ValidationReport:
    """Run the full Stage 1 battery and return a structured report.

    Never raises on a failing check — a rejected manifest is a report with
    `passed=False` and the failing `CheckResult`s. Only a malformed `schema`
    argument (which breaks jsonschema itself) propagates as an exception.
    """
    checks = [
        check_schema_conformance(manifest, schema),
        check_engine_syntax(manifest, schema),
        check_container_references(manifest, schema),
        check_reference_data(manifest, available_references),
        check_license(manifest, allowed_licenses),
        check_operator_permissions(manifest, operator_permissions),
    ]
    return ValidationReport(
        manifest_id=manifest_identifier(manifest),
        passed=all(result.passed for result in checks),
        checks=checks,
    )
