"""
JACKPOT CSV column harmonizer.

Maps raw CSV column names to JACKPOT schema field names using a
mapping_config YAML file. Called by the batch ingest router before
validate_sample().

Mapping config format (see schema/mapping_configs/asu_human_v1.yaml):
    source_format: asu_human_v1
    target_class: HumanSample
    column_mappings:
      "Raw Column Name": schema_field_name
    file_detection:
      files_column: "FASTQ files"
      separator: ";"
      auto_detect_pairs: true
"""

from pathlib import Path
from typing import Any

import yaml

_MAPPING_DIR = Path("schema/schema/mapping_configs")
_cache: dict[str, dict] = {}


def load_mapping(mapping_name: str) -> dict:
    """
    Load a mapping config YAML by name (without .yaml extension).
    Results are cached in memory for the process lifetime.

    Example: load_mapping("asu_human_v1")
    """
    if mapping_name in _cache:
        return _cache[mapping_name]

    path = _MAPPING_DIR / f"{mapping_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Mapping config '{mapping_name}' not found at {path}. "
            f"Available: {[p.stem for p in _MAPPING_DIR.glob('*.yaml')]}"
        )
    with open(path) as f:
        config = yaml.safe_load(f)
    _cache[mapping_name] = config
    return config


def harmonize_row(raw: dict[str, Any], mapping: dict) -> dict[str, Any]:
    """
    Apply a mapping config to a single CSV row dict.

    Returns a new dict with JACKPOT schema field names as keys.
    Fields already using schema names pass through unchanged.
    Unknown columns are preserved with their original names.
    """
    column_map: dict[str, str] = mapping.get("column_mappings", {})
    result: dict[str, Any] = {}

    for raw_key, value in raw.items():
        # Skip empty values
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        # Map to schema field name if a mapping exists, else keep as-is
        schema_key = column_map.get(raw_key, raw_key)
        result[schema_key] = value.strip() if isinstance(value, str) else value

    return result


def harmonize_csv(
    rows: list[dict[str, Any]],
    mapping_name: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Harmonize all rows in a CSV using a named mapping config.

    Returns (harmonized_rows, warnings).
    Warnings are generated for unknown columns not in the mapping.
    """
    mapping = load_mapping(mapping_name)
    column_map: dict[str, str] = mapping.get("column_mappings", {})
    harmonized: list[dict[str, Any]] = []
    warnings: list[str] = []

    if rows:
        unknown = [k for k in rows[0] if k not in column_map and k not in column_map.values()]
        if unknown:
            warnings.append(
                f"Unknown columns not in mapping '{mapping_name}': "
                f"{unknown}. They will be passed through unchanged."
            )

    for row in rows:
        harmonized.append(harmonize_row(row, mapping))

    return harmonized, warnings
