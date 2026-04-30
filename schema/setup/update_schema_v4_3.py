#!/usr/bin/env python3
"""
JACKPOT Schema Modifier — v4.2 → v4.3

Changes applied:
  1. Update collection_location_country description — clarify INSDC country
     name requirement for BioSample/TOSTADAS submissions. Add soft validation
     note (warning at Tier 2, required at Tier 3).
  2. Update collection_location_state description — remove US-centric
     framing, clarify this field accepts any sub-national administrative
     division (state, province, estado, canton, prefecture, etc.).
  3. Update collection_location_county description — minor clarification,
     already internationally neutral.
  4. Update collection_location_zipcode description — remove US ZIP-only
     framing and 5-digit numeric validation note. Field is free text,
     format varies by country, optional.
  5. Add collection_location_city — new field for city/municipality of
     collection. Required by BioSample geo_loc_name construction in
     portal_to_tostadas.py (format: Country:State:City).

Usage:
    cd ~/jackpot/jackpot-schema
    python3 ~/path/to/update_schema_v4_3.py --dry-run
    python3 ~/path/to/update_schema_v4_3.py

    Custom paths:
    python3 ~/path/to/update_schema_v4_3.py \\
        --input schema/jackpot_schema.yaml \\
        --output schema/jackpot_schema.yaml
"""

import argparse
import sys
from pathlib import Path

import yaml

DEFAULT_INPUT = Path("schema/jackpot_schema.yaml")
DEFAULT_OUTPUT = Path("schema/jackpot_schema.yaml")


# ── Change 1: collection_location_country ─────────────────────────────────

OLD_COUNTRY = """\
      collection_location_country:
        slot_uri: genepio:0001181
        required: true
        description: "Country of sample collection"\
"""

NEW_COUNTRY = """\
      collection_location_country:
        slot_uri: genepio:0001181
        required: true
        description: >-
          Country of sample collection. Free text — no controlled vocabulary
          enforced at Tier 1 or Tier 2. At Tier 3 (SUBMITTABLE), must match
          an INSDC-approved country name for BioSample submission via TOSTADAS
          (e.g. "USA" not "United States", "United Kingdom" not "UK").
          INSDC country list: https://www.insdc.org/submitting-standards/country-qualifier-vocabulary/
          portal_to_tostadas.py validates against the INSDC list before
          constructing the geo_loc_name field (format: Country:State:City).\
"""


# ── Change 2: collection_location_state ───────────────────────────────────

OLD_STATE = """\
      collection_location_state:
        slot_uri: genepio:0001182
        description: "US state or equivalent administrative region"\
"""

NEW_STATE = """\
      collection_location_state:
        slot_uri: genepio:0001182
        description: >-
          Sub-national administrative region of sample collection. Accepts
          any equivalent administrative division regardless of country:
          US state, Canadian province, Mexican estado, Australian state,
          Brazilian estado, UK county/nation, German Bundesland, Japanese
          prefecture, etc. Free text — not a controlled vocabulary since
          administrative divisions vary by country. Used in NCBI BioSample
          geo_loc_name construction (Country:State:City).\
"""


# ── Change 3: collection_location_county ──────────────────────────────────

OLD_COUNTY = """\
      collection_location_county:
        description: "County or equivalent sub-state region"\
"""

NEW_COUNTY = """\
      collection_location_county:
        description: >-
          County, district, or equivalent sub-state administrative region of
          sample collection. US county, UK district, French département,
          Australian local government area, etc. Free text. Optional — not
          all countries use a county-level administrative division.\
"""


# ── Change 4: collection_location_zipcode ─────────────────────────────────

OLD_ZIPCODE = """\
      collection_location_zipcode:
        description: >
          APGAP: 'Zip code'. US ZIP code of collection location.
          Validation: 5-digit numeric format.\
"""

NEW_ZIPCODE = """\
      collection_location_zipcode:
        description: >-
          Postal code of collection location. Format varies by country and
          is not validated — free text. Examples: US ZIP (85004), UK postcode
          (SW1A 1AA), Canadian postal code (A1A 1A1), Australian postcode (2000),
          German Postleitzahl (10115). Optional — many countries do not use
          postal codes, and postal codes are not used in NCBI BioSample
          geo_loc_name construction.\
"""


# ── Change 5: insert collection_location_city after zipcode ───────────────
# Anchor: the geo_lat field that immediately follows zipcode

CITY_INSERT_ANCHOR = """\
      geo_lat:
        range: float
        description: "Decimal latitude (WGS84), e.g. 33.4484"\
"""

NEW_CITY_PLUS_ANCHOR = """\
      collection_location_city:
        description: >-
          City, town, municipality, or village of sample collection. Free text.
          Used in NCBI BioSample geo_loc_name construction alongside
          collection_location_country and collection_location_state:
          format is "Country:State:City" (e.g. "USA:California:San Diego").
          Optional — omitted from geo_loc_name if not provided.

      geo_lat:
        range: float
        description: "Decimal latitude (WGS84), e.g. 33.4484"\
"""


def validate_yaml(text: str, path: str) -> bool:
    try:
        yaml.safe_load(text)
        return True
    except yaml.YAMLError as e:
        print(f"YAML parse error in {path}:\n{e}")
        return False


def apply_changes(content: str) -> tuple[str, list[str]]:
    applied = []

    # 1. collection_location_country
    if OLD_COUNTRY not in content:
        raise ValueError(
            "Anchor not found: collection_location_country block.\n"
            "The schema may have changed. Check the anchor string."
        )
    content = content.replace(OLD_COUNTRY, NEW_COUNTRY)
    applied.append(
        "Updated collection_location_country — INSDC requirement "
        "for Tier 3 / TOSTADAS, geo_loc_name construction noted"
    )

    # 2. collection_location_state
    if OLD_STATE not in content:
        raise ValueError(
            "Anchor not found: collection_location_state block.\n"
            "The schema may have changed. Check the anchor string."
        )
    content = content.replace(OLD_STATE, NEW_STATE)
    applied.append(
        "Updated collection_location_state — removed US-centric "
        "framing, now accepts any sub-national administrative division"
    )

    # 3. collection_location_county
    if OLD_COUNTY not in content:
        raise ValueError(
            "Anchor not found: collection_location_county block.\n"
            "The schema may have changed. Check the anchor string."
        )
    content = content.replace(OLD_COUNTY, NEW_COUNTY)
    applied.append(
        "Updated collection_location_county — internationally neutral, " "explicitly optional"
    )

    # 4. collection_location_zipcode
    if OLD_ZIPCODE not in content:
        raise ValueError(
            "Anchor not found: collection_location_zipcode block.\n"
            "The schema may have changed. Check the anchor string."
        )
    content = content.replace(OLD_ZIPCODE, NEW_ZIPCODE)
    applied.append(
        "Updated collection_location_zipcode — removed US ZIP-only "
        "framing and 5-digit numeric validation, now free text international"
    )

    # 5. Insert collection_location_city before geo_lat
    if CITY_INSERT_ANCHOR not in content:
        raise ValueError(
            "Anchor not found: geo_lat block (insertion point for city field).\n"
            "The schema may have changed. Check the anchor string."
        )
    content = content.replace(CITY_INSERT_ANCHOR, NEW_CITY_PLUS_ANCHOR)
    applied.append(
        "Added collection_location_city — new field for NCBI "
        "geo_loc_name construction (Country:State:City)"
    )

    # 6. Update schema version
    old_version = 'version: "4.2"'
    new_version = 'version: "4.3"'
    if old_version in content:
        content = content.replace(old_version, new_version, 1)
        applied.append("Updated schema version: 4.2 → 4.3")
    else:
        applied.append("WARNING: version string '4.2' not found — " "schema version not updated")

    return content, applied


def main() -> None:
    parser = argparse.ArgumentParser(description="Update JACKPOT schema from v4.2 to v4.3")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input schema YAML (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output schema YAML (default: same as input)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print what would change without writing the file"
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: Input file not found: {args.input}")
        print("Run this script from the jackpot-schema repo root, or pass --input.")
        sys.exit(1)

    print("\nJACKPOT Schema Updater — v4.2 → v4.3")
    print(f"Input:  {args.input.resolve()}")
    print(f"Output: {args.output.resolve()}")
    if args.dry_run:
        print("Mode:   DRY RUN (no files will be written)\n")
    else:
        print()

    original = args.input.read_text(encoding="utf-8")

    print("Validating input YAML...")
    if not validate_yaml(original, str(args.input)):
        print("ERROR: Input schema is not valid YAML. Fix errors before running.")
        sys.exit(1)
    print("  OK\n")

    print("Applying changes...")
    try:
        modified, applied = apply_changes(original)
    except ValueError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

    for change in applied:
        print(f"  [OK] {change}")

    print("\nValidating output YAML...")
    if not validate_yaml(modified, str(args.output)):
        print("\nERROR: Modified schema failed YAML validation.")
        print("The script has a bug. The original file was NOT modified.")
        sys.exit(1)
    print("  OK")

    orig_lines = original.count("\n")
    new_lines = modified.count("\n")
    print(f"\nLine count: {orig_lines} → {new_lines} ({new_lines - orig_lines:+d})")

    if args.dry_run:
        print("\nDRY RUN complete. No files written.")
        return

    args.output.write_text(modified, encoding="utf-8")
    print(f"\nWritten: {args.output.resolve()}")
    print("\nNext steps:")
    print("  1. Review the diff:  git diff schema/jackpot_schema.yaml")
    print(
        '  2. Validate YAML:    python3 -c "import yaml; '
        "yaml.safe_load(open('schema/jackpot_schema.yaml')); print('OK')\""
    )
    print("  3. Regenerate models (from jackpot-backend/):")
    print(
        "       uv run gen-pydantic --pydantic-version 2 "
        "schema/schema/jackpot_schema.yaml > backend/models_generated.py"
    )
    print("       # Apply boolean keyword patch (Critical Rule 20)")
    print(
        "       uv run gen-json-schema schema/schema/jackpot_schema.yaml "
        "> schema/schema/jackpot_schema.json"
    )
    print("  4. Update portal_to_tostadas.py — add collection_location_city")
    print("     to geo_loc_name construction logic")
    print("  5. Update validator.py — add INSDC country name soft warning")
    print("     at Tier 2 and hard requirement at Tier 3")
    print("  6. Commit jackpot-schema, then update submodule pointer " "in jackpot-backend")


if __name__ == "__main__":
    main()
