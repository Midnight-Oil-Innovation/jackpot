"""
Tests for backend/template_generator.py

Covers:
- CSV generation for all 12 source types
- Tier filtering (PRELIMINARY/ANALYZABLE/SUBMITTABLE)
- Metagenomics overlay
- Companion enums JSON
- Field classification logic
- Edge cases
"""

import csv
import io
import json

import pytest

from backend.template_generator import (
    ANALYZABLE_FIELDS,
    METAGENOMICS_FIELDS,
    PRELIMINARY_FIELDS,
    SOURCE_TYPE_CLASS,
    SUBMITTABLE_FIELDS,
    SYSTEM_COMPUTED,
    TemplateTier,
    _classify_field_tier,
    _snake_to_label,
    generate_companion_enums_json,
    generate_csv_template,
)

# ── Helpers ────────────────────────────────────────────────────────────────


def _parse_csv(csv_string: str) -> list[list[str]]:
    """Parse a CSV string into a list of rows."""
    reader = csv.reader(io.StringIO(csv_string))
    return list(reader)


def _get_field_names(csv_string: str) -> list[str]:
    """Extract field names (row 1) from a CSV template."""
    rows = _parse_csv(csv_string)
    return rows[0] if rows else []


def _get_tier_tags(csv_string: str) -> dict[str, str]:
    """Extract field_name → tier_tag mapping from rows 1 and 3."""
    rows = _parse_csv(csv_string)
    if len(rows) < 3:
        return {}
    return dict(zip(rows[0], rows[2], strict=False))


# ── Basic generation tests ────────────────────────────────────────────────


class TestCSVGeneration:
    """Tests for generate_csv_template()."""

    def test_generates_nonempty_csv(self):
        result = generate_csv_template("human", TemplateTier.ANALYZABLE)
        assert len(result) > 0

    def test_csv_has_five_header_rows_plus_data(self):
        result = generate_csv_template("human", TemplateTier.ANALYZABLE)
        rows = _parse_csv(result)
        # 5 header rows + 1 example + 10 empty = 16 minimum
        assert len(rows) >= 6  # 5 headers + at least 1 data row

    def test_row_1_is_snake_case_field_names(self):
        result = generate_csv_template("human", TemplateTier.ANALYZABLE)
        field_names = _get_field_names(result)
        for name in field_names:
            assert name == name.lower().replace(" ", "_"), f"Field name '{name}' is not snake_case"

    def test_row_2_is_human_readable_labels(self):
        result = generate_csv_template("human", TemplateTier.ANALYZABLE)
        rows = _parse_csv(result)
        labels = rows[1]
        # Labels should be Title Case, not snake_case
        for label in labels:
            assert (
                label[0].isupper() or label == ""
            ), f"Label '{label}' does not start with uppercase"

    def test_row_3_has_valid_tier_tags(self):
        result = generate_csv_template("human", TemplateTier.SUBMITTABLE)
        rows = _parse_csv(result)
        valid_tags = {"REQUIRED", "ANALYZABLE", "SUBMITTABLE", "OPTIONAL"}
        for tag in rows[2]:
            assert tag in valid_tags, f"Invalid tier tag: '{tag}'"

    def test_row_4_has_validation_hints(self):
        result = generate_csv_template("human", TemplateTier.ANALYZABLE)
        rows = _parse_csv(result)
        hints = rows[3]
        # Every column should have some hint text
        for hint in hints:
            assert len(hint) > 0, "Validation hint should not be empty"

    def test_row_5_has_example_data(self):
        result = generate_csv_template("human", TemplateTier.ANALYZABLE)
        rows = _parse_csv(result)
        example = rows[4]
        # At least some cells should have example values
        non_empty = [v for v in example if v.strip()]
        assert len(non_empty) > 5, "Example row should have pre-filled values"

    def test_no_system_computed_fields_in_template(self):
        result = generate_csv_template("human", TemplateTier.SUBMITTABLE)
        field_names = set(_get_field_names(result))
        leaked = field_names & SYSTEM_COMPUTED
        assert leaked == set(), f"System-computed fields should not appear in templates: {leaked}"


# ── Source type coverage ──────────────────────────────────────────────────


class TestAllSourceTypes:
    """Every source type should produce a valid template."""

    @pytest.mark.parametrize("source_type", list(SOURCE_TYPE_CLASS.keys()))
    def test_generates_csv_for_source_type(self, source_type):
        result = generate_csv_template(source_type, TemplateTier.ANALYZABLE)
        assert len(result) > 0
        rows = _parse_csv(result)
        assert len(rows) >= 6  # 5 headers + at least 1 data row

    @pytest.mark.parametrize("source_type", list(SOURCE_TYPE_CLASS.keys()))
    def test_sample_id_always_present(self, source_type):
        fields = _get_field_names(generate_csv_template(source_type, TemplateTier.PRELIMINARY))
        assert "sample_id" in fields

    @pytest.mark.parametrize("source_type", list(SOURCE_TYPE_CLASS.keys()))
    def test_organism_name_always_present(self, source_type):
        fields = _get_field_names(generate_csv_template(source_type, TemplateTier.PRELIMINARY))
        assert "organism_name" in fields

    @pytest.mark.parametrize("source_type", list(SOURCE_TYPE_CLASS.keys()))
    def test_source_type_always_present(self, source_type):
        fields = _get_field_names(generate_csv_template(source_type, TemplateTier.PRELIMINARY))
        assert "source_type" in fields


# ── Tier filtering ────────────────────────────────────────────────────────


class TestTierFiltering:
    """Tier selection controls which columns appear."""

    def test_preliminary_has_fewer_columns_than_analyzable(self):
        prelim = _get_field_names(generate_csv_template("human", TemplateTier.PRELIMINARY))
        analyz = _get_field_names(generate_csv_template("human", TemplateTier.ANALYZABLE))
        assert len(prelim) < len(analyz), (
            f"PRELIMINARY ({len(prelim)} cols) should have fewer columns "
            f"than ANALYZABLE ({len(analyz)} cols)"
        )

    def test_analyzable_has_fewer_columns_than_submittable(self):
        analyz = _get_field_names(generate_csv_template("human", TemplateTier.ANALYZABLE))
        submit = _get_field_names(generate_csv_template("human", TemplateTier.SUBMITTABLE))
        assert len(analyz) < len(submit), (
            f"ANALYZABLE ({len(analyz)} cols) should have fewer columns "
            f"than SUBMITTABLE ({len(submit)} cols)"
        )

    def test_preliminary_excludes_analyzable_fields(self):
        fields = _get_field_names(generate_csv_template("human", TemplateTier.PRELIMINARY))
        for af in ANALYZABLE_FIELDS:
            assert (
                af not in fields
            ), f"ANALYZABLE field '{af}' should not be in PRELIMINARY template"

    def test_preliminary_excludes_submittable_fields(self):
        fields = _get_field_names(generate_csv_template("human", TemplateTier.PRELIMINARY))
        for sf in SUBMITTABLE_FIELDS:
            if sf not in PRELIMINARY_FIELDS:
                assert (
                    sf not in fields
                ), f"SUBMITTABLE field '{sf}' should not be in PRELIMINARY template"

    def test_analyzable_excludes_submittable_only_fields(self):
        fields = _get_field_names(generate_csv_template("human", TemplateTier.ANALYZABLE))
        # originating_lab and submitting_lab are SUBMITTABLE-only
        assert "originating_lab" not in fields
        assert "submitting_lab" not in fields

    def test_submittable_includes_all_required_fields(self):
        fields = _get_field_names(generate_csv_template("human", TemplateTier.SUBMITTABLE))
        for pf in PRELIMINARY_FIELDS:
            assert pf in fields, f"PRELIMINARY field '{pf}' missing from SUBMITTABLE"
        for af in ANALYZABLE_FIELDS:
            assert af in fields, f"ANALYZABLE field '{af}' missing from SUBMITTABLE"
        for sf in SUBMITTABLE_FIELDS:
            assert sf in fields, f"SUBMITTABLE field '{sf}' missing from SUBMITTABLE"

    def test_submittable_human_includes_host_age_sex(self):
        fields = _get_field_names(generate_csv_template("human", TemplateTier.SUBMITTABLE))
        assert "host_age" in fields
        assert "host_sex" in fields

    def test_submittable_nonhuman_host_age_is_optional(self):
        tags = _get_tier_tags(generate_csv_template("wastewater", TemplateTier.SUBMITTABLE))
        if "host_age" in tags:
            assert tags["host_age"] == "OPTIONAL"
        if "host_sex" in tags:
            assert tags["host_sex"] == "OPTIONAL"


# ── Metagenomics overlay ──────────────────────────────────────────────────


class TestMetagenomicsOverlay:
    """Metagenomics flag adds MAG-specific fields."""

    def test_metagenomics_adds_target_organisms(self):
        fields = _get_field_names(
            generate_csv_template("wastewater", TemplateTier.ANALYZABLE, metagenomics=True)
        )
        assert "target_organisms" in fields

    def test_metagenomics_adds_assembly_type(self):
        fields = _get_field_names(
            generate_csv_template("soil", TemplateTier.ANALYZABLE, metagenomics=True)
        )
        assert "assembly_type" in fields

    def test_metagenomics_adds_mag_fields(self):
        fields = _get_field_names(
            generate_csv_template("human", TemplateTier.SUBMITTABLE, metagenomics=True)
        )
        for mf in METAGENOMICS_FIELDS:
            assert mf in fields, f"Metagenomics field '{mf}' missing"

    def test_without_metagenomics_no_mag_fields(self):
        fields = _get_field_names(
            generate_csv_template("human", TemplateTier.SUBMITTABLE, metagenomics=False)
        )
        assert "mag_completeness_pct" not in fields
        assert "mag_contamination_pct" not in fields

    def test_metagenomics_example_row_prefills_organism(self):
        result = generate_csv_template("wastewater", TemplateTier.ANALYZABLE, metagenomics=True)
        rows = _parse_csv(result)
        field_names = rows[0]
        example = rows[4]
        idx = field_names.index("organism_name")
        assert example[idx] == "metagenome"

    @pytest.mark.parametrize("source_type", list(SOURCE_TYPE_CLASS.keys()))
    def test_metagenomics_works_with_every_source_type(self, source_type):
        result = generate_csv_template(source_type, TemplateTier.ANALYZABLE, metagenomics=True)
        fields = _get_field_names(result)
        assert "target_organisms" in fields


# ── Companion enums JSON ──────────────────────────────────────────────────


class TestCompanionEnums:
    """Tests for generate_companion_enums_json()."""

    def test_returns_dict(self):
        result = generate_companion_enums_json("human", TemplateTier.ANALYZABLE)
        assert isinstance(result, dict)

    def test_organism_name_has_values(self):
        result = generate_companion_enums_json("human", TemplateTier.ANALYZABLE)
        assert "organism_name" in result
        assert len(result["organism_name"]["values"]) > 0

    def test_each_entry_has_required_keys(self):
        result = generate_companion_enums_json("human", TemplateTier.SUBMITTABLE)
        for field_name, entry in result.items():
            assert "label" in entry, f"{field_name} missing 'label'"
            assert "values" in entry, f"{field_name} missing 'values'"
            assert "required_at_tier" in entry, f"{field_name} missing 'required_at_tier'"

    def test_enums_json_serializable(self):
        result = generate_companion_enums_json("human", TemplateTier.SUBMITTABLE)
        # Should not raise
        serialized = json.dumps(result)
        assert len(serialized) > 0


# ── Field classification ──────────────────────────────────────────────────


class TestFieldClassification:
    """Tests for _classify_field_tier()."""

    def test_sample_id_is_required(self):
        assert _classify_field_tier("sample_id", "human") == "REQUIRED"

    def test_organism_name_is_required(self):
        assert _classify_field_tier("organism_name", "human") == "REQUIRED"

    def test_collection_location_state_is_analyzable(self):
        assert _classify_field_tier("collection_location_state", "human") == "ANALYZABLE"

    def test_originating_lab_is_submittable(self):
        assert _classify_field_tier("originating_lab", "human") == "SUBMITTABLE"

    def test_host_age_is_submittable_for_human(self):
        assert _classify_field_tier("host_age", "human") == "SUBMITTABLE"

    def test_host_age_is_optional_for_wastewater(self):
        assert _classify_field_tier("host_age", "wastewater") == "OPTIONAL"

    def test_host_sex_is_optional_for_soil(self):
        assert _classify_field_tier("host_sex", "soil") == "OPTIONAL"

    def test_unknown_field_is_optional(self):
        assert _classify_field_tier("some_random_field", "human") == "OPTIONAL"


# ── Utility functions ─────────────────────────────────────────────────────


class TestUtilities:
    """Tests for helper functions."""

    def test_snake_to_label(self):
        assert _snake_to_label("sample_id") == "Sample Id"
        assert _snake_to_label("collection_location_country") == "Collection Location Country"
        assert _snake_to_label("organism_name") == "Organism Name"

    def test_snake_to_label_single_word(self):
        assert _snake_to_label("sector") == "Sector"


# ── Consistency checks ────────────────────────────────────────────────────


class TestConsistency:
    """Cross-source-type consistency checks."""

    def test_all_source_types_share_base_required_fields(self):
        """Every source type at PRELIMINARY should have the same base fields."""
        base_fields_per_type = {}
        for st in SOURCE_TYPE_CLASS:
            fields = _get_field_names(generate_csv_template(st, TemplateTier.PRELIMINARY))
            base_fields_per_type[st] = set(fields) & set(PRELIMINARY_FIELDS)

        reference = base_fields_per_type["human"]
        for st, fields in base_fields_per_type.items():
            assert fields == reference, (
                f"Source type '{st}' has different PRELIMINARY base fields "
                f"than 'human'. Diff: {fields.symmetric_difference(reference)}"
            )

    def test_column_order_stable_across_tiers(self):
        """Fields present in PRELIMINARY should appear in the same order
        in ANALYZABLE and SUBMITTABLE templates."""
        prelim = _get_field_names(generate_csv_template("human", TemplateTier.PRELIMINARY))
        submit = _get_field_names(generate_csv_template("human", TemplateTier.SUBMITTABLE))
        # Every PRELIMINARY field should appear in SUBMITTABLE
        for pf in prelim:
            assert pf in submit, f"PRELIMINARY field '{pf}' missing from SUBMITTABLE"

        # Order should be preserved (PRELIMINARY fields appear first in SUBMITTABLE)
        prelim_positions = [submit.index(f) for f in prelim if f in submit]
        assert prelim_positions == sorted(
            prelim_positions
        ), "PRELIMINARY field order is not preserved in SUBMITTABLE template"
