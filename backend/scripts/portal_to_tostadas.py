#!/usr/bin/env python3
"""
Convert JACKPOT sample metadata JSON to TOSTADAS config.yaml.
Maps portal schema fields to NCBI BioSample attribute names.

Usage:
    python3 portal_to_tostadas.py \
        --input submission_metadata.json \
        --output tostadas_config/
"""

import argparse
import json
from pathlib import Path

import yaml

BIOSAMPLE_FIELD_MAP: dict[str, str] = {
    "organism_name": "organism",
    "strain": "strain",
    "isolate": "isolate",
    "serotype": "serotype",
    "date_collected": "collection_date",
    "collection_location_country": "geo_loc_name",
    "host_species": "host",
    "host_age": "host_age",
    "host_sex": "host_sex",
    "sequencing_platform": "sequencing_platform",
    "library_preparation_method": "library_strategy",
    "env_broad_scale": "env_broad_scale",
    "env_local_scale": "env_local_scale",
    "env_medium": "env_medium",
    "pango_lineage": "lineage",
}

SOURCE_TYPE_PACKAGE: dict[str, str] = {
    "Human": "MIMS.me.human-associated.6.0",
    "Wildlife": "MIMS.me.animal-associated.6.0",
    "CompanionAnimal": "MIMS.me.animal-associated.6.0",
    "Livestock": "MIMS.me.animal-associated.6.0",
    "Wastewater": "MIMS.me.wastewater.6.0",
    "Water": "MIMS.me.water.6.0",
    "Air": "MIMS.me.air.6.0",
    "Soil": "MIMS.me.soil.6.0",
    "Surface": "MIMS.me.built_environment.6.0",
}


def convert_sample(sample: dict) -> dict:
    biosample: dict = {}
    for portal_field, ncbi_attr in BIOSAMPLE_FIELD_MAP.items():
        val = sample.get(portal_field)
        if val:
            biosample[ncbi_attr] = str(val)

    country = sample.get("collection_location_country", "")
    state = sample.get("collection_location_state", "")
    biosample["geo_loc_name"] = f"{country}: {state}" if state else country
    biosample["package"] = SOURCE_TYPE_PACKAGE.get(sample.get("source_type", ""), "Generic.1.0")

    return {
        "sample_name": sample["sample_id"],
        "bioproject": sample.get("bioproject_accession", ""),
        "biosample_attrs": biosample,
        "fastq_r1": sample["fastq_r1_uri"],
        "fastq_r2": sample.get("fastq_r2_uri", ""),
        "consensus_fasta": sample.get("consensus_fasta_uri", ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    samples = data.get("samples", [data])
    converted = [convert_sample(s) for s in samples]
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "submission": {
            "submission_name": data.get("submission_name", "jackpot_submission"),
            "samples": converted,
        }
    }
    with open(output_dir / "config.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    print(f"Generated TOSTADAS config for {len(converted)} samples → {output_dir}")


if __name__ == "__main__":
    main()
