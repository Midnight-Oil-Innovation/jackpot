from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from backend.validator import ValidationResult, compute_quality_status, validate_sample


def test_valid_human_sample_passes(valid_human_sample):
    result = validate_sample(valid_human_sample)
    assert result.valid, f"Expected valid but got errors: {result.errors}"


@pytest.mark.parametrize(
    "missing_field",
    [
        "sample_id",
        "organism_name",
        "source_type",
        "date_collected",
        "collection_location_country",
        "sequencing_platform",
        "external_case_id",
    ],
)
def test_missing_required_field_fails(valid_human_sample, missing_field):
    data = {k: v for k, v in valid_human_sample.items() if k != missing_field}
    result = validate_sample(data)
    assert not result.valid
    assert any(missing_field in e for e in result.errors)


@pytest.mark.parametrize("bad_source", ["human", "HUMAN", "clinical", ""])
def test_invalid_source_type_fails(valid_human_sample, bad_source):
    result = validate_sample({**valid_human_sample, "source_type": bad_source})
    assert not result.valid


@pytest.mark.parametrize(
    "platform",
    [
        "Illumina",
        "Oxford_Nanopore",
        "PacBio",
        "Ion_Torrent",
        "Other",
    ],
)
def test_all_valid_platforms_pass(valid_human_sample, platform):
    result = validate_sample({**valid_human_sample, "sequencing_platform": platform})
    assert result.valid


@pytest.mark.parametrize("bad_sharing", ["private", "open", "shared", ""])
def test_invalid_sharing_level_fails(valid_human_sample, bad_sharing):
    result = validate_sample({**valid_human_sample, "sharing_level": bad_sharing})
    assert not result.valid


@pytest.mark.parametrize("good_sharing", ["PRIVATE", "LAB", "DISCOVERABLE", "PUBLIC"])
def test_all_sharing_levels_pass(valid_human_sample, good_sharing):
    result = validate_sample({**valid_human_sample, "sharing_level": good_sharing})
    assert result.valid


def test_future_date_fails(valid_human_sample):
    future = (date.today() + timedelta(days=10)).isoformat()
    result = validate_sample({**valid_human_sample, "date_collected": future})
    assert not result.valid
    assert any("future" in e for e in result.errors)


def test_old_date_warns(valid_human_sample):
    old = "2015-01-01"
    result = validate_sample({**valid_human_sample, "date_collected": old})
    assert result.valid
    assert any("5 years" in w for w in result.warnings)


def test_invalid_vadr_status_fails(valid_human_sample):
    result = validate_sample({**valid_human_sample, "vadr_status": "UNKNOWN"})
    assert not result.valid


@pytest.mark.parametrize("vadr", ["PASS", "FAIL", "SKIP", "PENDING"])
def test_valid_vadr_statuses_pass(valid_human_sample, vadr):
    result = validate_sample({**valid_human_sample, "vadr_status": vadr})
    assert result.valid


def test_host_age_out_of_range_errors(valid_human_sample):
    result = validate_sample({**valid_human_sample, "host_age": 200})
    assert not result.valid


@given(st.text(min_size=0, max_size=200))
def test_any_organism_name_never_crashes(organism_name):
    result = validate_sample({"organism_name": organism_name, "source_type": "Human"})
    assert isinstance(result.valid, bool)
    assert isinstance(result.errors, list)


"""
ADDITIONAL test cases for compute_quality_status() tier logic.

Add these tests to the EXISTING tests/test_validator.py file.
Paste at the bottom of the file, after the existing test functions.

These tests verify:
1. Year-only dates can reach SUBMITTABLE (NCBI/GISAID accept year-only)
2. SUBMITTABLE checks field presence, not date precision
3. ANALYZABLE still requires month-or-better date precision
4. host_age/host_sex only required for HumanSample at SUBMITTABLE
"""


# ── Helper ────────────────────────────────────────────────────────────────


def _run(data: dict) -> str:
    """Run validate_sample on data and return the quality status string."""
    return compute_quality_status(validate_sample(data))


def _invalid_result() -> ValidationResult:
    """A failing validation result (errors present)."""
    return ValidationResult(valid=False, errors=["missing required field"], warnings=[])


def _full_human_data(**overrides) -> dict:
    """A sample dict with all Tier 1 + Tier 2 + Tier 3 fields for HumanSample."""
    data = {
        # Tier 1 — BASE_REQUIRED
        "sample_id": "EXAMPLE-TEST-001",
        "organism_name": "Salmonella enterica",
        "source_type": "Human",
        "date_collected": "2024-06-15",
        "collection_location_country": "United States",
        "sequencing_platform": "Illumina",
        "type_of_experiment": "WGS",
        # Tier 1 — SOURCE_REQUIRED (Human)
        "external_case_id": "CASE-12345",
        "biospecimen_type": "blood",
        "reason_for_collection": ["clinical"],
        "host_disease": ["salmonellosis"],
        # Tier 2 — TIER2_REQUIRED
        "sequencing_lab": "Example Sequencing Lab",
        "collection_facility": "Example Medical Center",
        "library_preparation_method": "Nextera XT",
        "nucleic_acid_extraction_method": ["QIAamp"],
        "date_sequenced": "2024-06-20",
        "collection_location_state": "California",
        # Tier 3 — TIER3_REQUIRED
        "originating_lab": "Example Clinical Lab",
        "submitting_lab": "Example Sequencing Lab",
        "collection_location_county": "San Diego",
        "purpose_for_collection": ["clinical"],
        "sequencing_protocol": "https://www.protocols.io/view/nextera-xt",
        # Tier 3 — TIER3_REQUIRED_HUMAN
        "host_age": 45,
        "host_sex": "Male",
        "date_collected_precision": "day",
    }
    data.update(overrides)
    return data


def _full_wastewater_data(**overrides) -> dict:
    """A sample dict with all Tier 1 + Tier 2 + Tier 3 fields for WastewaterSample."""
    data = {
        # Tier 1 — BASE_REQUIRED
        "sample_id": "EXAMPLE-WW-001",
        "organism_name": "metagenome",
        "source_type": "Wastewater",
        "date_collected": "2024-06-15",
        "collection_location_country": "United States",
        "sequencing_platform": "Illumina",
        "type_of_experiment": "shotgun_DNA_sequencing",
        # Tier 1 — SOURCE_REQUIRED (Wastewater)
        "population_served": 250000,
        "sample_type": "grab",
        "sample_matrix": "raw_wastewater",
        "pretreatment": ["none"],
        "concentration_method": "ultracentrifugation",
        "flow_rate_mgd": 42.5,
        # Tier 2 — TIER2_REQUIRED
        "sequencing_lab": "Example Sequencing Lab",
        "collection_facility": "Example Water Reclamation Facility",
        "library_preparation_method": "Nextera XT",
        "nucleic_acid_extraction_method": ["QIAamp PowerWater"],
        "date_sequenced": "2024-06-20",
        "collection_location_state": "California",
        # Tier 3 — TIER3_REQUIRED
        "originating_lab": "Example WWTP Lab",
        "submitting_lab": "Example Sequencing Lab",
        "collection_location_county": "San Diego",
        "purpose_for_collection": ["surveillance"],
        "sequencing_protocol": "https://www.protocols.io/view/nwss-ww",
        "date_collected_precision": "day",
    }
    data.update(overrides)
    return data


# ── SUBMITTABLE tier tests ────────────────────────────────────────────────


class TestComputeQualityStatusSubmittable:
    def test_full_human_data_is_submittable(self):
        result = _run(_full_human_data())
        assert result == "SUBMITTABLE"

    def test_year_only_human_still_submittable(self):
        """NCBI and GISAID accept year-only collection dates."""
        data = _full_human_data(date_collected_precision="year")
        result = _run(data)
        assert result == "SUBMITTABLE"

    def test_month_only_human_still_submittable(self):
        data = _full_human_data(date_collected_precision="month")
        result = _run(data)
        assert result == "SUBMITTABLE"

    def test_wastewater_submittable_without_host_age_sex(self):
        """Non-human source types don't need host_age or host_sex."""
        result = _run(_full_wastewater_data())
        assert result == "SUBMITTABLE"

    def test_wastewater_year_only_still_submittable(self):
        data = _full_wastewater_data(date_collected_precision="year")
        result = _run(data)
        assert result == "SUBMITTABLE"

    def test_missing_originating_lab_not_submittable(self):
        data = _full_human_data()
        del data["originating_lab"]
        result = _run(data)
        assert result != "SUBMITTABLE"

    def test_missing_county_not_submittable(self):
        data = _full_human_data()
        del data["collection_location_county"]
        result = _run(data)
        assert result != "SUBMITTABLE"

    def test_human_missing_host_age_not_submittable(self):
        data = _full_human_data()
        del data["host_age"]
        result = _run(data)
        assert result != "SUBMITTABLE"

    def test_human_missing_host_sex_not_submittable(self):
        data = _full_human_data()
        del data["host_sex"]
        result = _run(data)
        assert result != "SUBMITTABLE"


# ── ANALYZABLE tier tests ─────────────────────────────────────────────────


class TestComputeQualityStatusAnalyzable:
    def _tier2_human(self, **overrides) -> dict:
        """Full Tier 1 + Tier 2 human sample — missing Tier 3 fields."""
        data = _full_human_data()
        # Remove Tier 3 fields so we land at ANALYZABLE not SUBMITTABLE
        for f in [
            "originating_lab",
            "submitting_lab",
            "collection_location_county",
            "purpose_for_collection",
            "sequencing_protocol",
            "host_age",
            "host_sex",
        ]:
            data.pop(f, None)
        data.update(overrides)
        return data

    def test_state_plus_month_is_analyzable(self):
        result = _run(self._tier2_human(date_collected_precision="month"))
        assert result == "ANALYZABLE"

    def test_state_plus_day_is_analyzable(self):
        result = _run(self._tier2_human(date_collected_precision="day"))
        assert result == "ANALYZABLE"

    def test_state_plus_year_is_preliminary_not_analyzable(self):
        """Year-only precision blocks ANALYZABLE — time-series needs month+."""
        result = _run(self._tier2_human(date_collected_precision="year"))
        assert result == "PRELIMINARY"

    def test_no_state_is_preliminary(self):
        data = self._tier2_human()
        data.pop("collection_location_state", None)
        result = _run(data)
        assert result == "PRELIMINARY"


# ── PRELIMINARY tier tests ────────────────────────────────────────────────


class TestComputeQualityStatusPreliminary:
    def test_invalid_validation_is_always_preliminary(self):
        result = compute_quality_status(_invalid_result())
        assert result == "PRELIMINARY"

    def test_empty_data_is_preliminary(self):
        result = _run({})
        assert result == "PRELIMINARY"

    def test_year_only_no_state_is_preliminary(self):
        data = {"date_collected_precision": "year"}
        result = _run(data)
        assert result == "PRELIMINARY"
