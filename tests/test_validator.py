from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from backend.validator import validate_sample


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
        "adhs_medsis_id",
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
