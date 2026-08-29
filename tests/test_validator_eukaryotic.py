"""Eukaryotic-aware tier rules and surveillance relevance (B-EUK-3).

P0b (`c871b28bbdab`) landed the eukaryotic columns — parasite_developmental_stage,
sample_preservation_method, parasitemia_percent, multiplicity_of_infection,
coinfection_organisms — but validator.py never learned about them, so no
eukaryotic sample could reach a tier on those fields. These tests cover the
logic that closes that gap, per `docs/byop_and_eukaryotic_design.md` §15.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.validator import (
    EUKARYOTIC_PATHOGEN_GENERA,
    TIER2_REQUIRED_EUKARYOTIC,
    TIER3_REQUIRED_EUKARYOTIC,
    compute_surveillance_relevant,
    is_eukaryotic_pathogen,
    validate_sample,
)

# A sample carrying every tier-2 and tier-3 field a eukaryotic sample needs.
EUKARYOTIC_EXTRAS = {
    "parasite_developmental_stage": "trophozoite",
    "sample_preservation_method": "EDTA_whole_blood",
    "parasitemia_percent": 2.5,
    "multiplicity_of_infection": 1,
    "coinfection_organisms": ["Plasmodium vivax"],
}


def _eukaryotic_sample(valid_human_sample: dict, **overrides) -> dict:
    return {
        **valid_human_sample,
        "organism_name": "Plasmodium falciparum",
        "host_age": 34,
        "host_sex": "female",
        "collection_location_county": "Maricopa",
        "originating_lab": "Example Lab",
        "submitting_lab": "Example Lab",
        **overrides,
    }


# ── genus matching ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "organism",
    [
        "Plasmodium falciparum",
        "Leishmania donovani",
        "Trypanosoma cruzi",
        "Schistosoma mansoni",
        "Cryptosporidium parvum",
        "Giardia duodenalis",
        "Entamoeba histolytica",
        "Toxoplasma gondii",
        "Brugia malayi",
        "Ancylostoma duodenale",
    ],
)
def test_eukaryotic_organisms_are_recognised(organism):
    assert is_eukaryotic_pathogen(organism)


@pytest.mark.parametrize(
    "organism",
    [
        "Severe acute respiratory syndrome coronavirus 2",
        "Salmonella enterica",
        "Mycobacterium tuberculosis",
        "Candida auris",  # a eukaryote, but a fungus — not in the parasite set
        "metagenome",
        "novel pathogen",
    ],
)
def test_non_eukaryotic_organisms_are_not_recognised(organism):
    assert not is_eukaryotic_pathogen(organism)


@pytest.mark.parametrize("junk", [None, "", "   ", 42, [], {"a": 1}])
def test_junk_organism_values_are_false_not_an_error(junk):
    """validate_sample runs before the enum check has necessarily passed."""
    assert is_eukaryotic_pathogen(junk) is False


def test_genus_match_covers_species_not_yet_in_the_enum():
    """A new Plasmodium species is covered the day it is added to the schema."""
    assert is_eukaryotic_pathogen("Plasmodium fictitious")


# ── the schema pin: the tripwire for the heuristic ─────────────────────────


def _eukaryotic_enum_values() -> list[str]:
    """Organism names inside the eukaryotic block of jackpot_schema.yaml.

    The block is delimited by its banner comment and runs to the end of the
    enum. Values are two-space-indented keys under permissible_values.
    """
    from jackpot_schema import SCHEMA_YAML_PATH

    lines = Path(SCHEMA_YAML_PATH).read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if "Eukaryotic pathogens (P0b" in line)
    indent = len(lines[start]) - len(lines[start].lstrip())

    values: list[str] = []
    for line in lines[start + 1 :]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        current = len(line) - len(line.lstrip())
        if current < indent:  # dedent out of the enum block
            break
        if current == indent and re.fullmatch(r"[A-Z][^:]*:", line.strip()):
            values.append(line.strip()[:-1])
    return values


def test_schema_pin_every_eukaryotic_enum_value_has_a_known_genus():
    """Adding a new eukaryotic genus to the schema must fail until it is
    added to EUKARYOTIC_PATHOGEN_GENERA.

    The genus set approximates a schema enum. That is only safe while the two
    agree, so this test is the tripwire — without it the heuristic silently
    stops classifying a whole genus (e.g. Babesia) as eukaryotic.
    """
    values = _eukaryotic_enum_values()
    assert len(values) >= 38, f"expected the eukaryotic block, parsed only {values}"

    unknown = sorted({v.split()[0] for v in values} - set(EUKARYOTIC_PATHOGEN_GENERA))
    assert not unknown, (
        f"eukaryotic genera in jackpot_schema.yaml but not in "
        f"EUKARYOTIC_PATHOGEN_GENERA: {unknown}. Add them to backend/validator.py."
    )


def test_schema_pin_catches_every_value_via_the_public_helper():
    for organism in _eukaryotic_enum_values():
        assert is_eukaryotic_pathogen(organism), f"{organism} not recognised"


# ── tier rules ─────────────────────────────────────────────────────────────


def test_eukaryotic_sample_with_all_fields_reaches_tier_3(valid_human_sample):
    result = validate_sample(_eukaryotic_sample(valid_human_sample, **EUKARYOTIC_EXTRAS))
    assert result.valid, result.errors
    assert result.tier == 3, (result.tier2_missing, result.tier3_missing)


@pytest.mark.parametrize("field", TIER2_REQUIRED_EUKARYOTIC)
def test_missing_eukaryotic_tier2_field_blocks_analyzable(valid_human_sample, field):
    data = _eukaryotic_sample(valid_human_sample, **EUKARYOTIC_EXTRAS)
    del data[field]
    result = validate_sample(data)
    assert field in result.tier2_missing
    assert result.tier == 1


@pytest.mark.parametrize("field", TIER3_REQUIRED_EUKARYOTIC)
def test_missing_eukaryotic_tier3_field_blocks_submittable(valid_human_sample, field):
    data = _eukaryotic_sample(valid_human_sample, **EUKARYOTIC_EXTRAS)
    del data[field]
    result = validate_sample(data)
    assert field in result.tier3_missing
    assert result.tier == 2


def test_coinfection_organisms_is_not_required_for_submittable(valid_human_sample):
    """A monoinfection must be able to reach SUBMITTABLE.

    byop design §15 lists coinfection_organisms as a tier-3 field, but
    _is_absent() treats [] as missing and CSV ingest collapses an empty cell
    to [], so "screened, no coinfection" is indistinguishable from "not
    recorded". Requiring it would force submitters to invent a value. Making
    it required again needs a "screened, none found" sentinel — a schema
    decision deferred to Phase 28.
    """
    data = _eukaryotic_sample(valid_human_sample, **EUKARYOTIC_EXTRAS)
    del data["coinfection_organisms"]
    result = validate_sample(data)
    assert result.tier == 3, (result.tier2_missing, result.tier3_missing)
    assert "coinfection_organisms" not in result.tier3_missing


@pytest.mark.parametrize("empty", [[], None])
def test_explicitly_empty_coinfection_still_reaches_submittable(valid_human_sample, empty):
    data = _eukaryotic_sample(valid_human_sample, **EUKARYOTIC_EXTRAS)
    data["coinfection_organisms"] = empty
    result = validate_sample(data)
    assert result.tier == 3, (result.tier2_missing, result.tier3_missing)


def test_coinfection_organisms_is_still_accepted_when_present(valid_human_sample):
    """Dropping it from the tier gate must not make it invalid to supply."""
    data = _eukaryotic_sample(valid_human_sample, **EUKARYOTIC_EXTRAS)
    data["coinfection_organisms"] = ["Plasmodium vivax", "Plasmodium malariae"]
    result = validate_sample(data)
    assert result.valid, result.errors
    assert result.tier == 3


def test_non_eukaryotic_sample_is_unaffected_by_the_new_fields(valid_human_sample):
    """The regression that matters: a bacterial or viral sample must not be
    stranded at PRELIMINARY for lacking a developmental stage."""
    data = {
        **valid_human_sample,
        "host_age": 34,
        "host_sex": "female",
        "collection_location_county": "Maricopa",
        "originating_lab": "Example Lab",
        "submitting_lab": "Example Lab",
    }
    result = validate_sample(data)
    assert result.tier == 3, (result.tier2_missing, result.tier3_missing)
    for field in TIER2_REQUIRED_EUKARYOTIC + TIER3_REQUIRED_EUKARYOTIC:
        assert field not in result.tier2_missing
        assert field not in result.tier3_missing


# ── surveillance relevance ─────────────────────────────────────────────────


def test_eukaryotic_organism_is_surveillance_relevant_without_being_reportable():
    """The default reportable set predates eukaryotic support, so keying off
    it alone would silently drop malaria out of surveillance."""
    assert compute_surveillance_relevant("Plasmodium falciparum", None, set()) is True


def test_non_eukaryotic_unreportable_organism_stays_false():
    assert compute_surveillance_relevant("Escherichia coli", None, {"Salmonella enterica"}) is False


def test_reportable_organism_still_wins():
    reportable = {"Salmonella enterica"}
    assert compute_surveillance_relevant("Salmonella enterica", None, reportable) is True


def test_metagenome_behaviour_is_unchanged():
    assert compute_surveillance_relevant("metagenome", None, set()) is True
    assert compute_surveillance_relevant("metagenome", ["Salmonella enterica"], set()) is False
    reportable = {"Salmonella enterica"}
    assert compute_surveillance_relevant("metagenome", ["Salmonella enterica"], reportable) is True
