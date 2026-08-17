"""
JACKPOT CSV column harmonizer.

Maps raw CSV column names to JACKPOT schema field names using a
mapping_config YAML file. Called by the batch ingest router before
validate_sample().

Mapping config format (see schema/schema/mapping_configs/example_human_v1.yaml):
    source_format: example_human_v1
    target_class: HumanSample
    column_mappings:
      "Raw Column Name": schema_field_name
    file_detection:
      files_column: "FASTQ files"
      separator: ";"
      auto_detect_pairs: true

I-1 also exposes ``suggest_column_mapping`` and ``suggest_value_mapping`` —
similarity-based suggestion helpers used by the spreadsheet importer
wizard. Both take user-supplied strings and propose JACKPOT-canonical
matches with a confidence score; the wizard always shows the suggestion
to the user and never auto-applies it without explicit confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

import yaml
from jackpot_schema import MAPPING_CONFIGS_DIR as _MAPPING_DIR

_cache: dict[str, dict] = {}


# I-1 — synonym table for suggest_column_mapping. Operator-agnostic
# generic field names only (no institutional names like
# ADHS_MEDSIS_ID). Add a new key here to teach the wizard a new alias.
COLUMN_NAME_SYNONYMS: dict[str, list[str]] = {
    "sample_id": [
        "sample id",
        "sampleid",
        "sample-id",
        "specimen",
        "specimen id",
        "specimenid",
        "accession",
        "id",
        "isolate id",
    ],
    "date_collected": [
        "collection date",
        "date collected",
        "sample date",
        "collected",
        "date",
        "collected on",
        "collection",
    ],
    "date_sequenced": [
        "sequenced",
        "sequence date",
        "sequencing date",
        "run date",
    ],
    "source_type": [
        "source",
        "source type",
        "sample source",
        "specimen type",
        "sample type",
    ],
    "sector": [
        "domain",
        "one health sector",
        "one-health sector",
    ],
    "organism_name": [
        "organism",
        "pathogen",
        "species",
        "taxon",
        "scientific name",
    ],
    "collection_location_country": [
        "country",
        "location country",
        "geo country",
        "collection country",
    ],
    "collection_location_state": [
        "state",
        "province",
        "region",
        "collection state",
    ],
    "collection_location_county": [
        "county",
        "collection county",
    ],
    "host_species": [
        "host",
        "host organism",
        "host species",
    ],
    "host_age": [
        "age",
        "patient age",
        "host age",
    ],
    "host_sex": [
        "sex",
        "patient sex",
        "host sex",
        "gender",
    ],
    "isolation_source": [
        "isolation source",
        "isolation",
        "source material",
    ],
    "biospecimen_type": [
        "specimen type",
        "biospecimen",
        "specimen material",
    ],
    "sequencing_platform": [
        "platform",
        "sequencer",
        "instrument platform",
    ],
    "sequencing_instrument": [
        "instrument",
        "instrument model",
        "sequencer model",
    ],
    "sequencing_lab": [
        "lab",
        "laboratory",
        "sequencing laboratory",
        "facility",
    ],
    "type_of_experiment": [
        "experiment",
        "experiment type",
        "assay",
    ],
    "library_preparation_method": [
        "library prep",
        "library preparation",
        "prep method",
    ],
    "nucleic_acid_extraction_method": [
        "extraction",
        "extraction method",
        "nucleic acid extraction",
    ],
    "external_case_id": [
        "case id",
        "patient id",
        "subject id",
        "case number",
    ],
}


# Confidence threshold for fuzzy matches; below this we return None to
# signal "not confident enough — ask the user." Tuned conservatively;
# the user can always override an unmapped column manually.
_FUZZY_CONFIDENCE_THRESHOLD: float = 0.80


@dataclass(frozen=True)
class MappingSuggestion:
    """A suggested target field for a single source column or value.

    Attributes:
        target: the proposed JACKPOT-canonical name (field name for
            column suggestions, enum value for value suggestions). None
            when no confident match is available.
        confidence: 0.0–1.0 score. 1.0 = exact match; 0.9 = synonym
            match; 0.0 = unmapped.
        reason: short human-readable label, e.g. ``"exact_match"``,
            ``"synonym"``, ``"fuzzy:0.86"``, ``"unmapped"``.
    """

    target: str | None
    confidence: float
    reason: str


def _normalize(value: str) -> str:
    return value.strip().lower()


def _exact_column_match(norm: str, target_lower: dict[str, str]) -> str | None:
    return target_lower.get(norm)


def _synonym_column_match(norm: str, target_set: set[str]) -> str | None:
    for canonical, syns in COLUMN_NAME_SYNONYMS.items():
        if canonical not in target_set:
            continue
        if any(_normalize(s) == norm for s in syns):
            return canonical
    return None


def _fuzzy_column_match(norm: str, target_fields: list[str]) -> tuple[str | None, float]:
    """Best fuzzy score across canonical target field names and their synonyms."""
    best_target: str | None = None
    best_score: float = 0.0
    for canonical in target_fields:
        score = SequenceMatcher(None, norm, _normalize(canonical)).ratio()
        if score > best_score:
            best_score = score
            best_target = canonical
        for syn in COLUMN_NAME_SYNONYMS.get(canonical, []):
            score = SequenceMatcher(None, norm, _normalize(syn)).ratio()
            if score > best_score:
                best_score = score
                best_target = canonical
    return best_target, best_score


def suggest_column_mapping(
    spreadsheet_columns: list[str],
    target_fields: list[str] | None = None,
) -> dict[str, MappingSuggestion]:
    """Suggest JACKPOT field names for an arbitrary spreadsheet's columns.

    I-1. The importer wizard calls this once per session at the column-
    mapping step (step 3). Each spreadsheet column gets a suggestion
    with a confidence score the UI surfaces alongside the user's
    eventual choice. Suggestions are never auto-applied.

    Algorithm (highest confidence wins):

    1. Exact match (case-insensitive, trimmed) against any JACKPOT
       canonical field name → ``confidence=1.0``, ``reason='exact_match'``.
    2. Match against any value in :data:`COLUMN_NAME_SYNONYMS` →
       ``confidence=0.9``, ``reason='synonym'``.
    3. Fuzzy match via :class:`difflib.SequenceMatcher` against
       canonical names + synonym values, taking the best score above
       :data:`_FUZZY_CONFIDENCE_THRESHOLD` →
       ``confidence=score``, ``reason='fuzzy:0.NN'``.
    4. Otherwise ``target=None``, ``confidence=0.0``, ``reason='unmapped'``.

    Args:
        spreadsheet_columns: column names exactly as they appear in the
            user's spreadsheet (preserves case, whitespace).
        target_fields: optional override for the canonical JACKPOT field
            list. Defaults to the keys of :data:`COLUMN_NAME_SYNONYMS`.

    Returns:
        ``{spreadsheet_column: MappingSuggestion, ...}`` — one entry per
        input column. Order is preserved.
    """
    if target_fields is None:
        target_fields = list(COLUMN_NAME_SYNONYMS.keys())

    target_set = set(target_fields)
    target_lower = {_normalize(f): f for f in target_fields}

    out: dict[str, MappingSuggestion] = {}
    for raw in spreadsheet_columns:
        norm = _normalize(raw)

        exact = _exact_column_match(norm, target_lower)
        if exact is not None:
            out[raw] = MappingSuggestion(target=exact, confidence=1.0, reason="exact_match")
            continue

        synonym_hit = _synonym_column_match(norm, target_set)
        if synonym_hit is not None:
            out[raw] = MappingSuggestion(target=synonym_hit, confidence=0.9, reason="synonym")
            continue

        best_target, best_score = _fuzzy_column_match(norm, target_fields)
        if best_score >= _FUZZY_CONFIDENCE_THRESHOLD and best_target is not None:
            out[raw] = MappingSuggestion(
                target=best_target,
                confidence=best_score,
                reason=f"fuzzy:{best_score:.2f}",
            )
            continue

        out[raw] = MappingSuggestion(
            target=None,
            confidence=0.0,
            reason="unmapped",
        )
    return out


def suggest_value_mapping(
    spreadsheet_values: list[str],
    enum_values: list[str],
) -> dict[str, MappingSuggestion]:
    """Suggest enum values for free-text strings found in a spreadsheet.

    I-1. The importer wizard calls this once per enum field at the
    value-normalization step (step 4). For each unique value present in
    the spreadsheet column, propose the closest enum value with a
    confidence score. Returns ``MappingSuggestion`` per input value.

    Algorithm matches :func:`suggest_column_mapping`: exact → synonym
    (skipped here, no synonym table for values) → fuzzy →
    ``unmapped``. Synonym tables for enum values can be added per-enum
    in a follow-up.

    Args:
        spreadsheet_values: unique values seen in the user's column.
        enum_values: the JACKPOT-canonical enum members for the field.

    Returns:
        ``{spreadsheet_value: MappingSuggestion, ...}`` — one entry per
        input value, with the suggested target enum member and a
        confidence score. ``target=None`` when no confident match
        exists; the wizard surfaces the unmapped values for the user to
        decide.
    """
    enum_lower = {_normalize(v): v for v in enum_values}
    out: dict[str, MappingSuggestion] = {}
    for raw in spreadsheet_values:
        norm = _normalize(raw)
        if norm in enum_lower:
            out[raw] = MappingSuggestion(
                target=enum_lower[norm],
                confidence=1.0,
                reason="exact_match",
            )
            continue
        best: str | None = None
        best_score: float = 0.0
        for enum in enum_values:
            score = SequenceMatcher(None, norm, _normalize(enum)).ratio()
            if score > best_score:
                best_score = score
                best = enum
        if best_score >= _FUZZY_CONFIDENCE_THRESHOLD and best is not None:
            out[raw] = MappingSuggestion(
                target=best,
                confidence=best_score,
                reason=f"fuzzy:{best_score:.2f}",
            )
            continue
        out[raw] = MappingSuggestion(
            target=None,
            confidence=0.0,
            reason="unmapped",
        )
    return out


def load_mapping(mapping_name: str) -> dict:
    """
    Load a mapping config YAML by name (without .yaml extension).
    Results are cached in memory for the process lifetime.

    Example: load_mapping("example_human_v1")
    """
    if mapping_name in _cache:
        return _cache[mapping_name]

    # Reject any mapping_name that would escape the configs directory
    # via path-segment trickery. Names are flat identifiers; anything
    # else (slashes, parents, leading dots) is rejected as invalid.
    if "/" in mapping_name or "\\" in mapping_name or mapping_name.startswith("."):
        raise ValueError(f"Invalid mapping_name: {mapping_name!r}")

    path = (_MAPPING_DIR / f"{mapping_name}.yaml").resolve()
    if not path.is_relative_to(_MAPPING_DIR.resolve()):
        raise ValueError(f"Invalid mapping_name: {mapping_name!r}")

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
