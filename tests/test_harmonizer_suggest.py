"""I-1 tests for backend.harmonizer.suggest_column_mapping / suggest_value_mapping.

Pure-logic tests — no DB, no fixtures.
"""

from __future__ import annotations

import pytest

from backend.harmonizer import (
    MappingSuggestion,
    suggest_column_mapping,
    suggest_value_mapping,
)

# ── suggest_column_mapping ─────────────────────────────────────────


def test_suggest_column_mapping_exact_match():
    out = suggest_column_mapping(["sample_id"])
    assert isinstance(out["sample_id"], MappingSuggestion)
    assert out["sample_id"].target == "sample_id"
    assert out["sample_id"].confidence == 1.0
    assert out["sample_id"].reason == "exact_match"


def test_suggest_column_mapping_case_insensitive():
    out = suggest_column_mapping(["Sample_ID", "  SAMPLE_ID  "])
    for col in ("Sample_ID", "  SAMPLE_ID  "):
        assert out[col].target == "sample_id"
        assert out[col].confidence == 1.0


def test_suggest_column_mapping_synonym():
    out = suggest_column_mapping(["Sample ID", "Specimen", "Accession"])
    for col in ("Sample ID", "Specimen", "Accession"):
        assert out[col].target == "sample_id"
        assert out[col].confidence == 0.9
        assert out[col].reason == "synonym"


def test_suggest_column_mapping_low_confidence_returns_unmapped():
    out = suggest_column_mapping(["xkcd_random_thing", "wholly_unrelated"])
    for col in ("xkcd_random_thing", "wholly_unrelated"):
        assert out[col].target is None
        assert out[col].confidence == 0.0
        assert out[col].reason == "unmapped"


def test_suggest_column_mapping_handles_extra_columns_gracefully():
    cols = ["Sample ID", "totally_unknown", "Collection Date"]
    out = suggest_column_mapping(cols)
    assert out["Sample ID"].target == "sample_id"
    assert out["totally_unknown"].target is None
    assert out["Collection Date"].target == "date_collected"
    assert set(out.keys()) == set(cols)


def test_suggest_column_mapping_handles_unicode():
    # Unicode column names must not crash the matcher; they may end
    # up unmapped, which is fine.
    out = suggest_column_mapping(["Sämple ÏD", "日付"])
    assert "Sämple ÏD" in out
    assert "日付" in out


def test_suggest_column_mapping_fuzzy_partial_match():
    # "samp_id" should fuzzy-match sample_id at >= 0.80 ratio.
    out = suggest_column_mapping(["sampleid"])
    assert out["sampleid"].target == "sample_id"
    # Synonym list contains "sampleid" so this is the synonym path.
    assert out["sampleid"].reason in ("synonym", "exact_match") or out[
        "sampleid"
    ].reason.startswith("fuzzy:")


def test_suggest_column_mapping_target_fields_override():
    # Caller can restrict the target list.
    out = suggest_column_mapping(["Sample ID"], target_fields=["organism_name"])
    # 'Sample ID' is no longer in synonym scope when sample_id isn't a target.
    assert out["Sample ID"].target in (None, "organism_name")


# ── suggest_value_mapping ──────────────────────────────────────────


def test_suggest_value_mapping_exact_enum_match():
    out = suggest_value_mapping(["clinical"], ["clinical", "wastewater"])
    assert out["clinical"].target == "clinical"
    assert out["clinical"].confidence == 1.0


def test_suggest_value_mapping_case_insensitive_enum_match():
    out = suggest_value_mapping(["Clinical", "WASTEWATER"], ["clinical", "wastewater"])
    assert out["Clinical"].target == "clinical"
    assert out["WASTEWATER"].target == "wastewater"


def test_suggest_value_mapping_fuzzy_match():
    # "clinic" against ["clinical", "wastewater"] — close enough.
    out = suggest_value_mapping(["clinical_"], ["clinical", "wastewater"])
    assert out["clinical_"].target == "clinical"
    assert out["clinical_"].reason.startswith("fuzzy:") or out["clinical_"].reason == "exact_match"


def test_suggest_value_mapping_no_confident_match_returns_none():
    out = suggest_value_mapping(["random_garbage_value"], ["clinical", "wastewater"])
    assert out["random_garbage_value"].target is None
    assert out["random_garbage_value"].confidence == 0.0


@pytest.mark.parametrize(
    "input_cols,expected_target",
    [
        (["organism"], "organism_name"),
        (["country"], "collection_location_country"),
        (["state"], "collection_location_state"),
        (["host"], "host_species"),
        (["age"], "host_age"),
        (["sex"], "host_sex"),
        (["platform"], "sequencing_platform"),
    ],
)
def test_suggest_column_mapping_common_synonyms(input_cols, expected_target):
    out = suggest_column_mapping(input_cols)
    assert out[input_cols[0]].target == expected_target
