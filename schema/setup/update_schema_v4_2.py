#!/usr/bin/env python3
"""
JACKPOT Schema Modifier — v4.1 → v4.2

Changes applied:
  1. Move case_id from HumanSample up to BaseSample
  2. Add case_source_system to BaseSample
  3. Add case_type to BaseSample
  4. Add CaseTypeEnum
  5. Add sector to BaseSample
  6. Add SectorEnum
  7. Add surveillance_relevant and related override fields to BaseSample
  8. Add target_organisms to BaseSample (for metagenomics)
  9. Add SurveillanceOverrideCategoryEnum
  10. Add quality_status to BaseSample
  11. Add QualityStatusEnum
  12. Add date_collected_precision to BaseSample
  13. Add DatePrecisionEnum
  14. Add read_type to BaseSample
  15. Add ReadTypeEnum
  16. Add assembly_type to BaseSample
  17. Add AssemblyTypeEnum + MAG QC fields
  18. Add originating_lab, submitting_lab, data_generator to BaseSample
  19. Add ena_accession to BaseSample
  20. Add data_use_terms, embargo_release_date, citation_request to BaseSample
  21. Add DataUseTermsEnum
  22. Add date_received_lab, date_sequence_uploaded, date_lineage_assigned,
      date_phenotype_reported to BaseSample (turnaround tracking)

Usage:
    cd ~/jackpot/jackpot-schema
    python3 ~/path/to/update_schema_v4_2.py

    # Dry run (print what would change, don't write):
    python3 ~/path/to/update_schema_v4_2.py --dry-run

    # Custom input/output paths:
    python3 ~/path/to/update_schema_v4_2.py \
        --input schema/jackpot_schema.yaml \
        --output schema/jackpot_schema.yaml
"""

import argparse
import sys
from pathlib import Path

import yaml

# ── Paths ──────────────────────────────────────────────────────────────────

DEFAULT_INPUT = Path("schema/jackpot_schema.yaml")
DEFAULT_OUTPUT = Path("schema/jackpot_schema.yaml")


# ── New YAML blocks ────────────────────────────────────────────────────────
# Each block is the exact YAML text to insert, with correct indentation.
# Anchored to a specific existing line so insertion is position-independent.

NEW_BASEAMPLE_FIELDS = """\
      # ── Case Linkage (cross-sector epidemiological grouping) ──────────────
      case_id:
        description: >-
          Generic public health case identifier. Links samples across sectors
          (human, animal, environmental) that share an epidemiological
          connection. The host operator may use a system-specific
          field (e.g. adhs_medsis_id for HumanSample under MEDSIS-style
          systems). Other jurisdictions use this field:
          CalREDIE (CA), ECLRS (NY), NEDSS (CDC), etc.
          Nullable — not all samples belong to a named case.

      case_source_system:
        description: >-
          The surveillance system that issued the case_id.
          Examples: MEDSIS-style systems, CalREDIE, ECLRS, NEDSS, ESSENCE.
          Free text — not a controlled vocabulary since system names
          vary by jurisdiction and evolve over time.

      case_type:
        range: CaseTypeEnum
        description: >-
          Classification of the epidemiological event this sample is
          associated with. Only meaningful when case_id is populated.

      # ── One Health Sector ─────────────────────────────────────────────────
      sector:
        range: SectorEnum
        required: true
        description: >-
          One Health sector classification. Determines surveillance network
          routing and tiered access control rules. Distinct from source_type
          which describes the physical sample material.

      # ── Surveillance Relevance ────────────────────────────────────────────
      surveillance_relevant:
        range: boolean
        required: true
        description: >-
          Whether host-operator public health oversight access applies to this sample.
          Computed at ingest from organism_name against the reportable_organisms
          table. TRUE if organism is reportable, FALSE otherwise.
          For metagenomic samples (organism_name = metagenome): TRUE if any
          target_organism is reportable, or TRUE by default if no targets
          specified (conservative). Can be overridden — see
          surveillance_relevant_override.

      surveillance_relevant_override:
        range: boolean
        description: >-
          TRUE if surveillance_relevant was manually overridden from its
          organism-driven default. Triggers audit logging. TRUE → FALSE
          overrides require governance board approval (status tracked via
          surveillance_override_pending). FALSE → TRUE overrides are
          self-declared by Lab Director.

      surveillance_override_pending:
        range: boolean
        description: >-
          TRUE when a TRUE → FALSE override has been submitted but not yet
          approved by the governance board. surveillance_relevant stays TRUE
          until approval. Cleared when override is approved or denied.

      surveillance_override_category:
        range: SurveillanceOverrideCategoryEnum
        description: >-
          Classification of the override reason. Determines whether governance
          board approval is required.

      surveillance_override_reason:
        description: >-
          Required when surveillance_relevant_override is TRUE. Justification
          for the override, reviewed by governance board for TRUE → FALSE
          changes.

      surveillance_override_approved_by_id:
        range: integer
        description: >-
          User ID of the governance board member who approved a TRUE → FALSE
          override. NULL for FALSE → TRUE overrides (no approval required)
          and for non-overridden samples.

      surveillance_override_date:
        range: date
        description: "Date the override was approved by the governance board."

      # ── Metagenomic Targeting ─────────────────────────────────────────────
      target_organisms:
        multivalued: true
        range: OrganismNameEnum
        description: >-
          For metagenomic samples (organism_name = metagenome) — the
          pathogen(s) the lab is specifically targeting or monitoring for.
          Used to compute surveillance_relevant when organism_name is
          'metagenome'. If empty (untargeted metagenomics),
          surveillance_relevant defaults to TRUE conservatively.
          Not applicable to isolate or consensus genome samples.

      # ── Data Quality Tier ─────────────────────────────────────────────────
      quality_status:
        range: QualityStatusEnum
        required: true
        description: >-
          Metadata completeness tier achieved at ingest. Determines which
          platform features are available for this sample. PRELIMINARY = Tier 1
          (ingestible, immediately available for pipeline runs). ANALYZABLE =
          Tier 2 (eligible for time-series and geographic analyses).
          SUBMITTABLE = Tier 3 (meets full NCBI/GISAID/NWSS requirements).
          QC_FAILED = failed QC checks, retained for audit but excluded from
          analyses. RETRACTED = previously released data withdrawn.

      # ── Date Precision ────────────────────────────────────────────────────
      date_collected_precision:
        range: DatePrecisionEnum
        description: >-
          Precision of date_collected. When only a year or year-month is
          known, set this field and store date_collected as YYYY-01-01 or
          YYYY-MM-01 respectively. Epiweek computation is suppressed when
          precision is year or month. Displayed to analysts so they understand
          the resolution of time-series data.

      # ── Sequencing Read Type ──────────────────────────────────────────────
      read_type:
        range: ReadTypeEnum
        description: >-
          Sequencing read length/technology category. Determines pipeline
          compatibility and QC expectations. Distinct from sequencing_platform
          (which captures the instrument make). A hybrid assembly uses both
          short_read and long_read inputs for the same sample.

      # ── Assembly Type ─────────────────────────────────────────────────────
      assembly_type:
        range: AssemblyTypeEnum
        description: >-
          Distinguishes isolate assemblies from metagenome-assembled genomes
          (MAGs) and other assembly strategies. Drives QC threshold selection
          and pipeline routing. MAG-specific QC fields (mag_completeness_pct,
          mag_contamination_pct, etc.) are only meaningful when assembly_type
          is mag or sag.

      mag_completeness_pct:
        range: float
        description: >-
          CheckM2 completeness percentage. Only applicable when
          assembly_type = mag or sag. Range: [0, 100].

      mag_contamination_pct:
        range: float
        description: >-
          CheckM2 contamination percentage. Only applicable when
          assembly_type = mag or sag. Range: [0, 100].

      mag_strain_heterogeneity_pct:
        range: float
        description: >-
          CheckM2 strain heterogeneity percentage. Indicates within-bin
          strain diversity. Only applicable when assembly_type = mag.

      mag_bin_size_bp:
        range: integer
        description: >-
          MAG bin size in base pairs. Only applicable when assembly_type = mag.

      # ── Provenance and Attribution (WHO Principle 6) ──────────────────────
      originating_lab:
        description: >-
          Lab that collected the original sample. Maps to GISAID
          "Originating lab" and NCBI BioSample originating_lab.
          Required for WHO Principle 6 attribution. May differ from
          sequencing_lab (who sequenced it) and submitting_lab (who
          uploaded to JACKPOT).

      submitting_lab:
        description: >-
          Lab that submitted data to JACKPOT. May differ from
          originating_lab and sequencing_lab. Required for WHO Principle 6
          credit tracking.

      data_generator:
        description: >-
          Individual or organization that generated the sequence data.
          Used for attribution in publications per WHO Principle 6.
          Format: "Name, Institution" or ORCID URI.

      # ── ENA Accession (international interoperability) ────────────────────
      ena_accession:
        description: >-
          European Nucleotide Archive run accession (ERR prefix).
          ENA and NCBI SRA mirror each other but submitting labs in
          Europe and Asia may submit via ENA. Required for WHO Principle 9
          interoperability with non-US partners.

      # ── Data Use Terms (WHO Principles 6 and 8) ──────────────────────────
      data_use_terms:
        range: DataUseTermsEnum
        description: >-
          Conditions under which this data may be used, per WHO Principle 8
          ("as open as possible, as closed as necessary"). Defaults to the
          organization's policy. Overrides sharing_level for external
          data use agreements.

      embargo_release_date:
        range: date
        description: >-
          Date after which data_use_terms = embargo data becomes openly
          accessible. Only meaningful when data_use_terms = embargo.

      citation_request:
        description: >-
          Free-text citation request from originating lab. Surfaced to
          data users when they access or download this sample's data.
          Per WHO Principle 6 — users should invite originating labs to
          participate in research and publications.

      # ── Turnaround Time Tracking (Rockefeller benchmarks) ─────────────────
      date_received_lab:
        range: date
        description: >-
          Date sample received at sequencing lab. Start of the turnaround
          clock. Rockefeller benchmark: ≤10 days from receipt to consensus
          genome upload.

      date_sequence_uploaded:
        range: date
        description: >-
          Date consensus genome uploaded to JACKPOT. Rockefeller target:
          ≤10 days from date_received_lab.

      date_lineage_assigned:
        range: date
        description: >-
          Date lineage or sequence type assignment completed (Pangolin,
          MLST, cgMLST). Rockefeller target: ≤48 hours from
          date_sequence_uploaded.

      date_phenotype_reported:
        range: date
        description: >-
          Date phenotypic threat assessment (AMR profile, virulence) reported.
          Rockefeller target: ≤21 days from date_sequence_uploaded.

"""

NEW_ENUMS = """\
  # ── Case Linkage ──────────────────────────────────────────────────────────

  CaseTypeEnum:
    permissible_values:
      outbreak:
        description: "Part of a named outbreak investigation"
      cluster:
        description: "Genomic or epidemiological cluster, not yet a named outbreak"
      sporadic:
        description: "Single case with no known epidemiological links"
      surveillance:
        description: "Routine surveillance — no specific case being investigated"
      contact_investigation:
        description: "Sample collected as part of contact tracing"
      sentinel:
        description: "Sentinel surveillance site sample"

  # ── One Health Sector ─────────────────────────────────────────────────────

  SectorEnum:
    permissible_values:
      clinical:
        description: "Human clinical diagnosis or treatment context"
      veterinary:
        description: "Animal health — companion, livestock, or zoo animals"
      agricultural:
        description: "Food production — crops, produce, food processing"
      environmental:
        description: "Environmental monitoring — water, soil, air, surfaces"
      wastewater:
        description: "Community-level wastewater surveillance (NWSS)"
      wildlife:
        description: "Wild animal surveillance"
      research:
        description: "Research sample not part of active public health surveillance"

  # ── Surveillance Override Category ────────────────────────────────────────

  SurveillanceOverrideCategoryEnum:
    permissible_values:
      reportable_organism_exception:
        description: >-
          Reportable organism present but sample is outside surveillance scope.
          Requires governance board approval (TRUE → FALSE override).
      untargeted_metagenome_research:
        description: >-
          Untargeted metagenome conservatively flagged TRUE, but sample is
          confirmed research-only with no surveillance purpose.
          Lab Director self-approval permitted.
      voluntary_opt_in:
        description: >-
          Non-reportable organism or research sample voluntarily brought
          under surveillance oversight (FALSE → TRUE override).
          No approval required.

  # ── Metadata Quality Tier ─────────────────────────────────────────────────

  QualityStatusEnum:
    permissible_values:
      PRELIMINARY:
        description: >-
          Tier 1 — minimum viable metadata present. Sample is immediately
          ingested and available for pipeline runs and basic search.
          May lack date precision, geographic detail, or source-type fields.
      ANALYZABLE:
        description: >-
          Tier 2 — sufficient metadata for epidemiological analysis including
          time-series (date to at least month precision) and geographic
          aggregation. Eligible for MMWR epiweek computation.
      SUBMITTABLE:
        description: >-
          Tier 3 — meets full NCBI BioSample, GISAID, and NWSS requirements.
          All required fields present, dates to full ISO 8601 day precision,
          all source-type-specific fields populated. Automated submission
          workflows enabled.
      QC_FAILED:
        description: >-
          Failed automated or manual QC checks. Retained in the system for
          audit purposes but excluded from analyses and not shown in the
          catalog by default.
      UNDER_REVIEW:
        description: >-
          Flagged for human review — automated QC result is inconclusive.
          Excluded from analyses pending review outcome.
      RETRACTED:
        description: >-
          Previously released data that has been withdrawn by the submitting
          lab or Platform Admin. Not shown in catalog; audit record preserved.

  # ── Date Precision ────────────────────────────────────────────────────────

  DatePrecisionEnum:
    permissible_values:
      day:
        description: >-
          Full ISO 8601 date known (YYYY-MM-DD). Default when date is entered
          in full. Required for Tier 3 (SUBMITTABLE) quality status.
      month:
        description: >-
          Only year and month known. Store date_collected as YYYY-MM-01.
          Epiweek computation uses mid-month estimate with warning.
          Sufficient for Tier 2 (ANALYZABLE) monthly aggregation.
      year:
        description: >-
          Only year known. Store date_collected as YYYY-01-01.
          Epiweek computation suppressed. Sufficient for Tier 1 (PRELIMINARY)
          annual surveillance counts.

  # ── Read Type ─────────────────────────────────────────────────────────────

  ReadTypeEnum:
    permissible_values:
      short_read:
        description: "Illumina or Ion Torrent — reads <1000bp"
      long_read:
        description: "ONT or PacBio — reads >1000bp, typically 10–100kb"
      hybrid:
        description: >-
          Combined short and long read data for the same sample.
          Used for hybrid assembly pipelines (e.g. Unicycler, Dragonflye).
      ultra_long:
        description: "ONT ultra-long reads >100kb — used for complete chromosome assembly"

  # ── Assembly Type ─────────────────────────────────────────────────────────

  AssemblyTypeEnum:
    permissible_values:
      isolate:
        description: >-
          Single organism isolate — standard WGS assembly from pure culture.
          Coverage depth and genome completeness QC apply.
      mag:
        description: >-
          Metagenome-assembled genome — binned from metagenomic data.
          CheckM2 completeness and contamination QC apply instead of
          coverage/VADR metrics.
      sag:
        description: >-
          Single-amplified genome — from single-cell genomics.
          Lower completeness expected; CheckM2 QC applies.
      consensus:
        description: >-
          Amplicon or reference-guided consensus genome (e.g. SARS-CoV-2
          ARTIC protocol). VADR and Nextclade QC apply.
      metatranscriptome:
        description: "RNA-based metagenomic assembly — transcriptome from community."

  # ── Data Use Terms ────────────────────────────────────────────────────────

  DataUseTermsEnum:
    permissible_values:
      open_access:
        description: >-
          No restrictions — submitter does not retain rights. Data may be
          freely used, shared, and republished with attribution.
      controlled_access:
        description: >-
          Access subject to a Data Use Agreement (DUA). Submitter protections
          apply. Users must agree to DUA terms before accessing data.
      restricted:
        description: >-
          Internal use only — not for external sharing. Overrides sharing_level
          for external requests.
      embargo:
        description: >-
          Under publication embargo. Data is accessible internally but
          embargo_release_date controls when external access is permitted.

"""


# ── Anchor strings for insertion ───────────────────────────────────────────
# These are unique strings in the current schema that we anchor insertions to.

# New BaseSample fields go just before the cross-sample linkage section
BASEAMPLE_INSERT_ANCHOR = "      # ── Cross-sample Linkage"

# case_id removal anchor in HumanSample
HUMANSAMPLE_CASEID_START = (
    "      case_id:\n"
    "        description: >\n"
    "          Generic public health case identifier for non-MEDSIS sources\n"
    "          (e.g. CDC NEDSS case ID, county health department ID).\n"
)

# New enums go just before the SharingLevelEnum section
ENUM_INSERT_ANCHOR = "  # ── Sharing and Access"


# ── Helpers ────────────────────────────────────────────────────────────────


def validate_yaml(text: str, path: str) -> bool:
    """Return True if text parses as valid YAML."""
    try:
        yaml.safe_load(text)
        return True
    except yaml.YAMLError as e:
        print(f"YAML parse error in {path}:\n{e}")
        return False


def apply_changes(content: str) -> tuple[str, list[str]]:
    """
    Apply all schema changes to content string.
    Returns (modified_content, list_of_applied_changes).
    Raises ValueError if an anchor is not found.
    """
    applied = []

    # ── 1. Insert new BaseSample fields ────────────────────────────────────
    if BASEAMPLE_INSERT_ANCHOR not in content:
        raise ValueError(
            f"Anchor not found in schema:\n  '{BASEAMPLE_INSERT_ANCHOR}'\n"
            "The schema may have changed. Update the anchor string."
        )
    content = content.replace(
        BASEAMPLE_INSERT_ANCHOR,
        NEW_BASEAMPLE_FIELDS + BASEAMPLE_INSERT_ANCHOR,
    )
    applied.append(
        "Inserted new BaseSample fields (case_id, sector, "
        "surveillance_relevant, quality_status, read_type, "
        "assembly_type, provenance, turnaround, etc.)"
    )

    # ── 2. Remove case_id from HumanSample ─────────────────────────────────
    if HUMANSAMPLE_CASEID_START not in content:
        raise ValueError(
            f"HumanSample case_id block not found. "
            "It may have already been removed or the text has changed.\n"
            f"Looking for:\n{HUMANSAMPLE_CASEID_START}"
        )
    content = content.replace(HUMANSAMPLE_CASEID_START, "")
    applied.append("Removed case_id from HumanSample (moved to BaseSample)")

    # ── 3. Insert new enums ─────────────────────────────────────────────────
    if ENUM_INSERT_ANCHOR not in content:
        raise ValueError(
            f"Anchor not found in schema:\n  '{ENUM_INSERT_ANCHOR}'\n"
            "The schema may have changed. Update the anchor string."
        )
    content = content.replace(
        ENUM_INSERT_ANCHOR,
        NEW_ENUMS + ENUM_INSERT_ANCHOR,
    )
    applied.append(
        "Inserted new enums: CaseTypeEnum, SectorEnum, "
        "SurveillanceOverrideCategoryEnum, QualityStatusEnum, "
        "DatePrecisionEnum, ReadTypeEnum, AssemblyTypeEnum, "
        "DataUseTermsEnum"
    )

    # ── 4. Update schema version in header ─────────────────────────────────
    old_version = 'version: "4.1"'
    new_version = 'version: "4.2"'
    if old_version in content:
        content = content.replace(old_version, new_version, 1)
        applied.append("Updated schema version: 4.1 → 4.2")
    else:
        applied.append("WARNING: version string '4.1' not found — schema version not updated")

    return content, applied


# ── Main ───────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Update JACKPOT schema from v4.1 to v4.2")
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

    print("\nJACKPOT Schema Updater — v4.1 → v4.2")
    print(f"Input:  {args.input.resolve()}")
    print(f"Output: {args.output.resolve()}")
    if args.dry_run:
        print("Mode:   DRY RUN (no files will be written)\n")
    else:
        print()

    original = args.input.read_text(encoding="utf-8")

    # Validate input parses cleanly
    print("Validating input YAML...")
    if not validate_yaml(original, str(args.input)):
        print("ERROR: Input schema is not valid YAML. Fix errors before running.")
        sys.exit(1)
    print("  OK\n")

    # Apply changes
    print("Applying changes...")
    try:
        modified, applied = apply_changes(original)
    except ValueError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

    for change in applied:
        print(f"  [OK] {change}")

    # Validate output parses cleanly
    print("\nValidating output YAML...")
    if not validate_yaml(modified, str(args.output)):
        print("\nERROR: Modified schema failed YAML validation.")
        print("The script has a bug. The original file was NOT modified.")
        sys.exit(1)
    print("  OK")

    # Count lines
    orig_lines = original.count("\n")
    new_lines = modified.count("\n")
    print(f"\nLine count: {orig_lines} → {new_lines} (+{new_lines - orig_lines})")

    if args.dry_run:
        print("\nDRY RUN complete. No files written.")
        return

    # Write output
    args.output.write_text(modified, encoding="utf-8")
    print(f"\nWritten: {args.output.resolve()}")
    print("\nNext steps:")
    print("  1. Review the diff:  git diff schema/jackpot_schema.yaml")
    print(
        '  2. Validate YAML:    python3 -c "import yaml; '
        "yaml.safe_load(open('schema/jackpot_schema.yaml'))\""
    )
    print("  3. Regenerate models (from jackpot-backend/):")
    print(
        "       uv run gen-pydantic schema/schema/jackpot_schema.yaml > backend/models_generated.py"
    )
    print(
        "       uv run gen-json-schema schema/schema/jackpot_schema.yaml "
        "> schema/schema/jackpot_schema.json"
    )
    print("  4. Create Alembic migration:")
    print('       uv run alembic revision -m "schema_v4_2_case_sector_surveillance_quality"')
    print("  5. Commit jackpot-schema, then update submodule pointer in jackpot-backend")


if __name__ == "__main__":
    main()
