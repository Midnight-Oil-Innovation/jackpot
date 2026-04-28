from scripts.portal_to_tostadas import SOURCE_TYPE_PACKAGE, convert_sample


def minimal_sample(source_type="Human", **kwargs):
    base = {
        "sample_id": "EX-001",
        "source_type": source_type,
        "organism_name": "Severe acute respiratory syndrome coronavirus 2",
        "collection_location_country": "United States",
        "fastq_r1_uri": "gs://bucket/R1.fastq.gz",
    }
    base.update(kwargs)
    return base


def test_human_gets_correct_package():
    result = convert_sample(minimal_sample())
    assert result["biosample_attrs"]["package"] == SOURCE_TYPE_PACKAGE["Human"]


def test_wastewater_gets_correct_package():
    result = convert_sample(minimal_sample(source_type="Wastewater"))
    assert result["biosample_attrs"]["package"] == SOURCE_TYPE_PACKAGE["Wastewater"]


def test_geo_loc_name_combines_country_and_state():
    result = convert_sample(
        minimal_sample(
            collection_location_country="United States",
            collection_location_state="California",
        )
    )
    assert result["biosample_attrs"]["geo_loc_name"] == "United States: California"


def test_geo_loc_name_country_only():
    result = convert_sample(minimal_sample())
    assert result["biosample_attrs"]["geo_loc_name"] == "United States"


def test_sample_name_is_sample_id():
    result = convert_sample(minimal_sample())
    assert result["sample_name"] == "EX-001"


def test_missing_optional_fields_dont_crash():
    result = convert_sample(minimal_sample())
    assert result["fastq_r2"] == ""
    assert result["consensus_fasta"] == ""
