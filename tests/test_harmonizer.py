"""Tests for backend.harmonizer — CSV column harmonization.

Phase 22 review action item 15: harmonizer.py was at 0% coverage
(no tests at all). P0e D closes the gap with happy-path + the
security-relevant path-traversal rejection branches.
"""

import pytest

from backend.harmonizer import _cache, harmonize_csv, harmonize_row, load_mapping


@pytest.fixture(autouse=True)
def clear_mapping_cache():
    """The harmonizer caches mappings in a module-global. Clear between
    tests so a load_mapping in one test doesn't leak into another."""
    _cache.clear()
    yield
    _cache.clear()


# ── load_mapping ────────────────────────────────────────────────────────


class TestLoadMapping:
    def test_loads_known_mapping(self):
        mapping = load_mapping("example_human_v1")
        assert "column_mappings" in mapping
        assert isinstance(mapping["column_mappings"], dict)

    def test_caches_subsequent_loads(self):
        first = load_mapping("example_human_v1")
        second = load_mapping("example_human_v1")
        # Same dict instance — cached, not re-parsed.
        assert first is second

    def test_unknown_mapping_raises(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            load_mapping("does_not_exist")

    def test_path_traversal_with_slash_rejected(self):
        with pytest.raises(ValueError, match="Invalid mapping_name"):
            load_mapping("../etc/passwd")

    def test_path_traversal_with_backslash_rejected(self):
        with pytest.raises(ValueError, match="Invalid mapping_name"):
            load_mapping("subdir\\file")

    def test_dotfile_prefix_rejected(self):
        with pytest.raises(ValueError, match="Invalid mapping_name"):
            load_mapping(".secret")


# ── harmonize_row ───────────────────────────────────────────────────────


class TestHarmonizeRow:
    def test_renames_columns_per_mapping(self):
        mapping = {
            "column_mappings": {
                "Sample ID": "sample_id",
                "Organism": "organism_name",
            }
        }
        result = harmonize_row(
            {"Sample ID": "EX-001", "Organism": "Salmonella enterica"},
            mapping,
        )
        assert result == {
            "sample_id": "EX-001",
            "organism_name": "Salmonella enterica",
        }

    def test_unmapped_columns_pass_through(self):
        mapping = {"column_mappings": {"Known": "schema_known"}}
        result = harmonize_row(
            {"Known": "x", "UnknownColumn": "y"},
            mapping,
        )
        assert result == {"schema_known": "x", "UnknownColumn": "y"}

    def test_strips_whitespace_from_string_values(self):
        mapping = {"column_mappings": {"Org": "organism_name"}}
        result = harmonize_row({"Org": "  Salmonella  "}, mapping)
        assert result == {"organism_name": "Salmonella"}

    def test_empty_string_values_skipped(self):
        mapping = {"column_mappings": {"Org": "organism_name"}}
        result = harmonize_row({"Org": ""}, mapping)
        assert result == {}

    def test_whitespace_only_value_skipped(self):
        mapping = {"column_mappings": {"Org": "organism_name"}}
        result = harmonize_row({"Org": "   "}, mapping)
        assert result == {}

    def test_none_values_skipped(self):
        mapping = {"column_mappings": {"Org": "organism_name"}}
        result = harmonize_row({"Org": None}, mapping)
        assert result == {}

    def test_non_string_values_pass_through_unchanged(self):
        mapping = {"column_mappings": {"Count": "sample_count"}}
        result = harmonize_row({"Count": 42}, mapping)
        assert result == {"sample_count": 42}

    def test_empty_mapping_passes_all_keys_through(self):
        mapping = {"column_mappings": {}}
        result = harmonize_row({"a": "1", "b": "2"}, mapping)
        assert result == {"a": "1", "b": "2"}


# ── harmonize_csv ───────────────────────────────────────────────────────


class TestHarmonizeCsv:
    def test_harmonizes_all_rows(self):
        rows = [
            {"Sample ID": "EX-001", "Organism": "Salmonella"},
            {"Sample ID": "EX-002", "Organism": "Listeria"},
        ]
        # Use a real mapping that exists in schema/mapping_configs/.
        harmonized, warnings = harmonize_csv(rows, "example_human_v1")
        assert len(harmonized) == 2
        # The example_human_v1 mapping doesn't necessarily map "Sample ID"
        # to anything; the key behaviour is that BOTH rows got processed.
        assert all(isinstance(row, dict) for row in harmonized)

    def test_warns_about_unknown_columns(self):
        rows = [
            {
                "TotallyMadeUpColumn": "x",
                "AnotherInvented": "y",
            }
        ]
        harmonized, warnings = harmonize_csv(rows, "example_human_v1")
        assert len(warnings) == 1
        assert "TotallyMadeUpColumn" in warnings[0]
        assert "AnotherInvented" in warnings[0]
        assert "example_human_v1" in warnings[0]

    def test_no_warning_when_all_columns_recognised_or_target_names(self):
        # Use schema target names directly — they're in column_mappings.values()
        # so the unknown-detection skips them.
        mapping = load_mapping("example_human_v1")
        target_field = next(iter(mapping["column_mappings"].values()))

        rows = [{target_field: "value"}]
        harmonized, warnings = harmonize_csv(rows, "example_human_v1")
        assert warnings == []

    def test_empty_rows_returns_empty(self):
        harmonized, warnings = harmonize_csv([], "example_human_v1")
        assert harmonized == []
        assert warnings == []

    def test_unknown_mapping_raises(self):
        with pytest.raises(FileNotFoundError):
            harmonize_csv([{"x": "y"}], "no_such_mapping")
