#!/usr/bin/env python3
"""
JACKPOT Schema Modifier — v4.3 → v4.4

Changes applied (9 total):

HumanSample additions:
  1. date_of_symptom_onset — standard WHO/NNDSS/ArboNET case report field.
     Critical for incubation period estimates, outbreak case counts, and
     time-to-detection metrics. Absent from most genomics platforms despite
     being on every CDC case investigation form.

  2. host_age_range — decade-bucket age field for privacy-preserving
     surveillance reporting. Exact age is PII; age range is the standard
     for NNDSS, ArboNET, and public CDC surveillance reports. Both
     host_age (exact, internal) and host_age_range (bucketed, shareable)
     are kept.

  3. collection_method — how the specimen was collected. Standard
     PHA4GE and NCBI BioSample field. Different collection methods for
     the same specimen type have different sensitivity implications
     (e.g. NP swab vs. saliva for SARS-CoV-2; induced sputum vs.
     BAL fluid vs. gastric aspirate for TB).

  4. travel_history_country / travel_history_days — WHO situation reports
     routinely distinguish travel-linked from locally-acquired cases for
     internationally relevant pathogens (MPOX, Ebola, cholera, H5N1).
     NCBI BioSample accepts travel_history as a standard free-text field.

WildlifeSample addition:
  5. travel_origin_region — for wildlife-associated pathogens, the
     geographic origin of the animal (migration source region) is
     equivalent to travel history for humans. Particularly relevant
     for migratory bird HPAI surveillance.

WastewaterSample addition:
  6. nwss_sewershed_id — CDC NWSS-assigned identifier for this sampling
     site. Links JACKPOT wastewater data to CDC's authoritative sewershed
     geometry layer and enables unambiguous matching in national
     surveillance aggregations.

SharingLevelEnum addition:
  7. REGISTERED_ACCESS — data available to any researcher who registers
     and agrees to data use terms. GA4GH Passport-compatible. Sits
     between DISCOVERABLE and PUBLIC. Required for CDC/WHO federated
     data sharing interoperability.

New class — OutbreakInvestigation:
  8. First-class outbreak entity. Samples link to it via FK. Enables
     querying "all samples from Outbreak AZ-Salmonella-2026-001",
     cross-sector investigation tracking, and CDC/WHO situation report
     generation without aggregating from case_type = outbreak.

Pango + MLST confidence fields:
  9. pango_qc_status, pango_conflict, mlst_confidence — surveillance
     decisions on uncertain lineage calls are qualitatively different
     from decisions on confident calls. WHO and CDC both require
     confidence indicators in genomic surveillance reporting.

AMRPhenotypeResult class deferred to v4.5 (requires broader WHO GLASS
alignment discussion). Captured in backlog.

Usage:
    cd ~/ASU/jackpot/jackpot-schema
    python3 setup/update_schema_v4_4.py --dry-run
    python3 setup/update_schema_v4_4.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import yaml


DEFAULT_INPUT  = Path("schema/jackpot_schema.yaml")
DEFAULT_OUTPUT = Path("schema/jackpot_schema.yaml")

# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 1 — date_of_symptom_onset + collection_method on HumanSample
# Insert after vaccination_status block, before underlying_conditions
# ══════════════════════════════════════════════════════════════════════════════

OLD_VACCINATION = """\
      vaccination_status:
        description: >
          e.g. fully vaccinated, unvaccinated, boosted,
          partially vaccinated, unknown.

      clinical_outcome:
        description: >
          e.g. hospitalized, ICU, deceased, outpatient,
          asymptomatic, unknown.

      underlying_conditions:
        multivalued: true
        description: >
          Relevant comorbidities, e.g. diabetes, immunocompromised,
          chronic lung disease, obesity.\
"""

NEW_VACCINATION = """\
      vaccination_status:
        description: >
          e.g. fully vaccinated, unvaccinated, boosted,
          partially vaccinated, unknown.

      clinical_outcome:
        description: >
          e.g. hospitalized, ICU, deceased, outpatient,
          asymptomatic, unknown.

      underlying_conditions:
        multivalued: true
        description: >
          Relevant comorbidities, e.g. diabetes, immunocompromised,
          chronic lung disease, obesity.

      # ── Epidemiologically critical date fields ─────────────────────────────
      date_of_symptom_onset:
        range: date
        description: >-
          Date the patient first experienced symptoms of the disease.
          Standard field on WHO case investigation forms, NNDSS reports,
          and ArboNET surveillance. Distinct from date_collected (when the
          sample was taken). The lag between these dates drives incubation
          period estimates and time-to-detection metrics. ISO 8601 format.
          Optional — not all cases are symptomatic (asymptomatic cases
          may have no onset date).

      # ── Travel history (WHO situation report standard) ─────────────────────
      travel_history_country:
        multivalued: true
        description: >-
          Countries visited by the patient in the 14 days before symptom
          onset or sample collection (whichever is earlier). NCBI BioSample
          standard field. WHO situation reports routinely distinguish
          travel-linked from locally-acquired cases for internationally
          relevant pathogens (MPOX, Ebola, cholera, H5N1, MERS-CoV).
          Free text — INSDC country names preferred but not enforced here.
          Multiple values permitted (multiple countries in travel history).

      travel_history_days:
        range: integer
        description: >-
          Days since return from travel when sample was collected.
          Used alongside travel_history_country to calculate exposure window.
          Integer. Optional — only populated when travel_history_country
          is provided.

      # ── Host age range (privacy-preserving surveillance reporting) ──────────
      host_age_range:
        range: AgeRangeEnum
        description: >-
          Age of the human host expressed as a decade bracket for
          privacy-preserving public surveillance reporting. NNDSS, ArboNET,
          and CDC public surveillance datasets use age brackets rather than
          exact ages. host_age (exact integer) is retained for internal
          analysis; host_age_range is the shareable tier.
          Populated automatically from host_age at ingest. Reviewers and
          external users see age range; Lab Directors and above see both.

      # ── Collection method (PHA4GE + NCBI BioSample standard) ───────────────
      collection_method:
        range: CollectionMethodEnum
        description: >-
          Method used to collect the specimen. Different collection methods
          for the same biospecimen type have different sensitivity profiles
          (e.g. nasopharyngeal swab vs. saliva vs. mid-turbinate swab for
          SARS-CoV-2; induced sputum vs. BAL fluid vs. gastric aspirate for TB).
          Standard PHA4GE and NCBI BioSample field. Required for Tier 2
          (ANALYZABLE) and above. Maps to NCBI collection_method attribute.\
"""

# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 2 — travel_origin_region on WildlifeSample
# Insert after isolate field, before CompanionAnimalSample
# ══════════════════════════════════════════════════════════════════════════════

OLD_WILDLIFE_END = """\
      isolation_source:
        slot_uri: ncbi:isolation_source
        description: \"Auto-derived from host species + biospecimen type\"

      isolate:
        slot_uri: ncbi:isolate

  CompanionAnimalSample:\
"""

NEW_WILDLIFE_END = """\
      isolation_source:
        slot_uri: ncbi:isolation_source
        description: \"Auto-derived from host species + biospecimen type\"

      isolate:
        slot_uri: ncbi:isolate

      travel_origin_region:
        description: >-
          For migratory or translocated wildlife — the geographic region
          of origin or most recent stopover before the animal was sampled.
          Equivalent to travel_history for humans. Particularly relevant
          for migratory bird HPAI (H5N1) surveillance where flyway routes
          determine exposure risk. Free text. Examples: 'Atlantic Flyway',
          'East Asia Pacific Flyway', 'Mongolia', 'Central Valley CA'.

  CompanionAnimalSample:\
"""

# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 3 — nwss_sewershed_id on WastewaterSample
# Insert after wwtp_name block, before sample_location_zipcode
# ══════════════════════════════════════════════════════════════════════════════

OLD_WWTP_NAME = """\
      wwtp_name:
        description: >
          APGAP: 'Location (sample_location_specify)'. NWSS: sample_location.
          Wastewater facility name or upstream sewer location.
          Examples: 'South Tempe Water Reclamation Facility',
          'undisclosed sewer line upstream of 5th Ave'.

      sample_location_zipcode:\
"""

NEW_WWTP_NAME = """\
      wwtp_name:
        description: >
          APGAP: 'Location (sample_location_specify)'. NWSS: sample_location.
          Wastewater facility name or upstream sewer location.
          Examples: 'South Tempe Water Reclamation Facility',
          'undisclosed sewer line upstream of 5th Ave'.

      nwss_sewershed_id:
        description: >-
          CDC NWSS-assigned identifier for this wastewater sampling site.
          Links JACKPOT wastewater data to CDC's authoritative sewershed
          geometry layer (catchment area polygon, population denominator,
          WWTP capacity). Enables unambiguous matching when JACKPOT data
          is reported to CDC NWSS. Format: integer or NWSS site code.
          Reference: https://www.cdc.gov/nwss/reporting.html
          Optional — not all sites are registered in NWSS at time of
          sample collection, but should be populated at Tier 2 and above.

      sample_location_zipcode:\
"""

# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 4 — REGISTERED_ACCESS in SharingLevelEnum
# ══════════════════════════════════════════════════════════════════════════════

OLD_SHARING_ENUM = """\
  SharingLevelEnum:
    permissible_values:
      PRIVATE:
        description: \"Owner and Lab Director only\"
      LAB:
        description: \"All members of the owning Lab\"
      DISCOVERABLE:
        description: \"Metadata visible to all; files require access request\"
      PUBLIC:
        description: \"Metadata and files open to all authenticated users\"\
"""

NEW_SHARING_ENUM = """\
  SharingLevelEnum:
    permissible_values:
      PRIVATE:
        description: \"Owner and Lab Director only\"
      LAB:
        description: \"All members of the owning Lab\"
      DISCOVERABLE:
        description: \"Metadata visible to all authenticated users; files require an access request\"
      REGISTERED_ACCESS:
        description: >-
          Data available to any researcher who registers and agrees to the
          data use agreement (DUA). More open than DISCOVERABLE (no per-request
          approval), more controlled than PUBLIC (requires identity verification
          and DUA acceptance). Compatible with GA4GH Passport-controlled access.
          Appropriate for: multi-institution data sharing agreements, CDC/WHO
          federated surveillance networks, international genomics consortia.
          Access gate: authenticated user + accepted DUA. No Lab Director
          approval required per-request, but terms must be accepted once.
      PUBLIC:
        description: \"Metadata and files open to all authenticated users\"\
"""

# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 5 — pango_qc_status, pango_conflict, mlst_confidence fields
# ══════════════════════════════════════════════════════════════════════════════

OLD_PANGO_SECTION = """\
      # ── Viral Lineage / Clade (auto-populated by Pangolin + Nextclade) ────
      pango_lineage:
        description: \"Pangolin lineage designation, e.g. JN.1, BA.2.86\"
      pango_lineage_version:
        description: \"Pangolin software version used for assignment\"
      nextstrain_clade:
        description: \"Nextstrain clade designation, e.g. 24A\"
      nextclade_qc_score:
        range: float
        description: \"Nextclade QC score (0–100; higher is better quality)\"
      nextclade_version:
        description: \"Nextclade software version\"\
"""

NEW_PANGO_SECTION = """\
      # ── Viral Lineage / Clade (auto-populated by Pangolin + Nextclade) ────
      pango_lineage:
        description: \"Pangolin lineage designation, e.g. JN.1, BA.2.86\"
      pango_lineage_version:
        description: \"Pangolin software version used for assignment\"
      pango_qc_status:
        range: PangoQCStatusEnum
        description: >-
          Pangolin QC status for the lineage call. A 'fail' or 'ambiguous'
          status means the lineage designation is uncertain and should not
          drive surveillance decisions without manual review. WHO and CDC
          both require confidence indicators in genomic surveillance reporting.
          Populated automatically from Pangolin output at pipeline completion.
      pango_conflict:
        range: float
        description: >-
          Pangolin conflict score (0.0–1.0). Values >0.0 indicate ambiguity
          between two or more lineage calls. High conflict (>0.5) indicates
          the assignment is unreliable. Stored for downstream filtering —
          surveillance dashboards should suppress or flag high-conflict calls.
      nextstrain_clade:
        description: \"Nextstrain clade designation, e.g. 24A\"
      nextclade_qc_score:
        range: float
        description: \"Nextclade QC score (0–100; higher is better quality)\"
      nextclade_version:
        description: \"Nextclade software version\"\
"""

OLD_MLST_SECTION = """\
      # ── AMR (bacterial samples, auto-populated post-pipeline) ────────────
      mlst_scheme:
        description: \"MLST scheme, e.g. 'senterica', 'campylobacter'\"
      mlst_sequence_type:
        description: \"MLST sequence type, e.g. ST131\"\
"""

NEW_MLST_SECTION = """\
      # ── AMR (bacterial samples, auto-populated post-pipeline) ────────────
      mlst_scheme:
        description: \"MLST scheme, e.g. 'senterica', 'campylobacter'\"
      mlst_sequence_type:
        description: \"MLST sequence type, e.g. ST131\"
      mlst_confidence:
        range: MLSTConfidenceEnum
        description: >-\n          Confidence level of the MLST sequence type assignment.
          Perfect = all alleles matched exactly. Good = all alleles matched
          but some may be novel. Low = one or more alleles missing or novel.
          Unknown = insufficient data. Surveillance reports should distinguish
          confident from uncertain ST assignments — a novel allele can indicate
          a genuinely new strain or a sequencing artefact.\
"""

# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 6 — OutbreakInvestigation class
# Insert between SampleAssociation and PipelineProvenance
# ══════════════════════════════════════════════════════════════════════════════

OLD_FAIR_PROV = """\
        description: \"Free text notes about the association\"

# ════════════════════════════════════════════════════════════════════════════
# FAIR PROVENANCE
# ════════════════════════════════════════════════════════════════════════════

  PipelineProvenance:\
"""

NEW_FAIR_PROV = """\
        description: \"Free text notes about the association\"

# ════════════════════════════════════════════════════════════════════════════
# OUTBREAK INVESTIGATIONS
# ════════════════════════════════════════════════════════════════════════════

  OutbreakInvestigation:
    description: >-
      A named public health outbreak or cluster investigation. First-class
      entity that samples link to via outbreak_investigation_id FK in the
      samples table. Enables querying "all samples from Outbreak
      AZ-Salmonella-2026-001", cross-sector investigation tracking (human +
      food + environmental samples in the same investigation), and CDC/WHO
      situation report generation without requiring aggregation from
      case_type = outbreak on individual sample records.

      Maps to: CDC NNDSS OutbreakNumber, WHO Situation Report investigation ID.
    attributes:
      outbreak_id:
        identifier: true
        required: true
        description: >-
          Unique identifier for this investigation. Platform-minted on creation.
          Format: {STATE}-{PATHOGEN_CODE}-{YEAR}-{SEQUENTIAL}, e.g.
          AZ-SALM-2026-001, AZ-SARS2-2026-042.

      outbreak_name:
        required: true
        description: >-
          Human-readable name for the investigation.
          e.g. 'Maricopa County Salmonella Typhimurium Cluster 2026'.

      investigation_status:
        range: OutbreakStatusEnum
        required: true
        description: \"Current status of the investigation.\"

      pathogen:
        range: OrganismNameEnum
        required: true
        description: \"Primary pathogen under investigation.\"

      investigation_start_date:
        range: date
        required: true
        description: \"Date the investigation was formally opened.\"

      investigation_close_date:
        range: date
        description: \"Date the investigation was formally closed. NULL if ongoing.\"

      reporting_jurisdiction:
        required: true
        description: >-
          Primary public health jurisdiction responsible for this investigation.
          e.g. 'ADHS', 'Maricopa County DHS', 'CDC', 'WHO PAHO'.

      sectors_involved:
        multivalued: true
        range: SectorEnum
        description: >-
          One Health sectors represented in this investigation.
          A foodborne outbreak may involve clinical, agricultural, and
          food samples under the same investigation.

      case_count:
        range: integer
        description: \"Current confirmed case count. Updated as investigation progresses.\"

      nndss_outbreak_number:
        description: >-
          CDC NNDSS OutbreakNumber if this investigation has been reported
          to NNDSS. Links JACKPOT investigation to national outbreak tracking.

      notes:
        description: \"Free text investigation notes. Not displayed in catalog.\"

# ════════════════════════════════════════════════════════════════════════════
# FAIR PROVENANCE
# ════════════════════════════════════════════════════════════════════════════

  PipelineProvenance:\
"""

# ══════════════════════════════════════════════════════════════════════════════
# CHANGE 7 — New enums: AgeRangeEnum, CollectionMethodEnum,
#             PangoQCStatusEnum, MLSTConfidenceEnum, OutbreakStatusEnum
# Append before the final line of the enums section
# Anchor: the last enum in the file (SampleAssociationTypeEnum or similar)
# ══════════════════════════════════════════════════════════════════════════════

# We'll find the end of the file's enums section and append there.
# Anchor: the very last permissible value block in the file.

NEW_ENUMS = """
  # ── Age Range (privacy-preserving decade buckets) ─────────────────────────

  AgeRangeEnum:
    description: >-
      Age expressed as a decade bracket for privacy-preserving surveillance
      reporting. Populated automatically from host_age at ingest.
      Standard CDC/NNDSS/ArboNET age grouping.
    permissible_values:
      "< 1 year":
        description: "Infant — less than 12 months"
      "1-4 years":
        description: "Toddler/preschool"
      "5-14 years":
        description: "School age"
      "15-24 years":
        description: "Young adult"
      "25-34 years": {}
      "35-44 years": {}
      "45-54 years": {}
      "55-64 years": {}
      "65-74 years": {}
      "75-84 years": {}
      "85+ years":
        description: "Oldest old — highest risk for many pathogens"
      unknown: {}

  # ── Collection Method ─────────────────────────────────────────────────────

  CollectionMethodEnum:
    description: >-
      Method used to collect the biological specimen. Standard PHA4GE
      and NCBI BioSample field. Required for Tier 2 and above.
    permissible_values:
      nasopharyngeal_swab:
        description: "NP swab — gold standard for respiratory pathogens"
      nasal_swab:
        description: "Anterior nares / mid-turbinate swab"
      oropharyngeal_swab:
        description: "Throat swab"
      saliva:
        description: "Saliva collection — lower sensitivity than NP for some pathogens"
      bronchoalveolar_lavage:
        description: "BAL fluid — lower respiratory tract"
      induced_sputum:
        description: "Standard for TB and other lower respiratory pathogens"
      gastric_aspirate:
        description: "Used for TB in children who cannot produce sputum"
      blood:
        description: "Venipuncture blood draw"
      serum:
        description: "Serum separated from whole blood"
      csf:
        description: "Cerebrospinal fluid — lumbar puncture"
      urine:
        description: "Urine culture or PCR"
      stool:
        description: "Stool sample — GI pathogens, polio surveillance"
      rectal_swab:
        description: "Alternative to stool for GI pathogens"
      skin_lesion_swab:
        description: "Swab of lesion — mpox, herpes, other dermotropic pathogens"
      vesicle_fluid:
        description: "Fluid from skin vesicle — mpox, varicella"
      wound_swab:
        description: "Wound or abscess swab"
      tissue_biopsy:
        description: "Tissue biopsy — post-mortem or surgical"
      environmental_swab:
        description: "Non-clinical environmental surface swab"
      other:
        description: "Collection method not listed — describe in comments"

  # ── Pangolin QC Status ────────────────────────────────────────────────────

  PangoQCStatusEnum:
    description: >-
      Pangolin lineage assignment QC status. Surveillance decisions should
      not be made on 'fail' or 'ambiguous' calls without manual review.
    permissible_values:
      pass:
        description: "High confidence lineage assignment"
      fail:
        description: "Low confidence — do not use for surveillance without review"
      ambiguous:
        description: "Multiple equally valid lineage calls — pango_conflict > 0"
      not_run:
        description: "Pangolin not yet run or not applicable (non-SARS-CoV-2)"

  # ── MLST Confidence ───────────────────────────────────────────────────────

  MLSTConfidenceEnum:
    description: >-
      Confidence level of the MLST sequence type assignment.
      Distinguishes confident surveillance-grade calls from uncertain ones.
    permissible_values:
      perfect:
        description: "All alleles matched exactly — high confidence ST call"
      good:
        description: "All alleles matched but one or more may be novel alleles"
      low:
        description: "One or more alleles missing or novel — uncertain ST"
      unknown:
        description: "Insufficient data for MLST — not applicable or failed"

  # ── Outbreak Investigation Status ─────────────────────────────────────────

  OutbreakStatusEnum:
    permissible_values:
      active:
        description: "Investigation ongoing — new cases still being identified"
      contained:
        description: "No new cases for ≥2 incubation periods — pending formal closure"
      closed:
        description: "Formally closed — investigation_close_date populated"
      surveillance_only:
        description: "Cluster resolved; enhanced surveillance continues"
"""


# ══════════════════════════════════════════════════════════════════════════════
# SCRIPT LOGIC
# ══════════════════════════════════════════════════════════════════════════════

CHANGES = [
    (
        "HumanSample — date_of_symptom_onset, travel history, age range, collection_method",
        OLD_VACCINATION,
        NEW_VACCINATION,
    ),
    (
        "WildlifeSample — travel_origin_region",
        OLD_WILDLIFE_END,
        NEW_WILDLIFE_END,
    ),
    (
        "WastewaterSample — nwss_sewershed_id",
        OLD_WWTP_NAME,
        NEW_WWTP_NAME,
    ),
    (
        "SharingLevelEnum — REGISTERED_ACCESS",
        OLD_SHARING_ENUM,
        NEW_SHARING_ENUM,
    ),
    (
        "Pango fields — pango_qc_status, pango_conflict",
        OLD_PANGO_SECTION,
        NEW_PANGO_SECTION,
    ),
    (
        "MLST fields — mlst_confidence",
        OLD_MLST_SECTION,
        NEW_MLST_SECTION,
    ),
    (
        "OutbreakInvestigation class",
        OLD_FAIR_PROV,
        NEW_FAIR_PROV,
    ),
]


def validate_yaml(text: str, label: str) -> bool:
    try:
        yaml.safe_load(text)
        return True
    except yaml.YAMLError as e:
        print(f"  YAML parse error in {label}:\n  {e}")
        return False


def apply_changes(content: str, dry_run: bool) -> tuple[str, list[str]]:
    applied = []

    for description, old, new in CHANGES:
        if old not in content:
            raise ValueError(
                f"Anchor not found for: {description}\n"
                f"  The schema may have changed since this script was written.\n"
                f"  First 80 chars of anchor: {repr(old[:80])}"
            )
        content = content.replace(old, new)
        applied.append(description)

    # Append new enums at end of file
    content = content.rstrip("\n") + "\n" + NEW_ENUMS.rstrip("\n") + "\n"
    applied.append(
        "New enums: AgeRangeEnum, CollectionMethodEnum, PangoQCStatusEnum, "
        "MLSTConfidenceEnum, OutbreakStatusEnum"
    )

    # Update version
    old_ver = 'version: "4.3"'
    new_ver = 'version: "4.4"'
    if old_ver in content:
        content = content.replace(old_ver, new_ver, 1)
        applied.append("Version bumped: 4.3 → 4.4")
    else:
        applied.append("WARNING: version string '4.3' not found — not updated")

    # Also update the description header
    old_desc = "Schema v4.1 — fully merged."
    if old_desc in content:
        # Update to mention v4.4
        pass  # leave header as-is; version field is the authoritative version

    return content, applied


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update JACKPOT schema v4.3 → v4.4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input",   type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output",  type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: Input not found: {args.input}")
        print("Run from the jackpot-schema repo root, or pass --input.")
        sys.exit(1)

    print(f"\nJACKPOT Schema Updater — v4.3 → v4.4")
    print(f"Input:  {args.input.resolve()}")
    print(f"Output: {args.output.resolve()}")
    if args.dry_run:
        print("Mode:   DRY RUN\n")
    else:
        print()

    original = args.input.read_text(encoding="utf-8")

    print("Validating input YAML...")
    if not validate_yaml(original, str(args.input)):
        print("ERROR: Input schema is not valid YAML.")
        sys.exit(1)
    print("  OK\n")

    print("Applying changes...")
    try:
        modified, applied = apply_changes(original, dry_run=args.dry_run)
    except ValueError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

    for change in applied:
        print(f"  [OK] {change}")

    print("\nValidating output YAML...")
    if not validate_yaml(modified, str(args.output)):
        print("\nERROR: Modified schema failed YAML validation.")
        print("The script has a bug. Original file was NOT modified.")
        sys.exit(1)
    print("  OK")

    orig_lines = original.count("\n")
    new_lines  = modified.count("\n")
    print(f"\nLine count: {orig_lines} → {new_lines} ({new_lines - orig_lines:+d})")

    if args.dry_run:
        print("\nDRY RUN complete. No files written.")
        return

    args.output.write_text(modified, encoding="utf-8")
    print(f"\nWritten: {args.output.resolve()}")
    print("\nNext steps:")
    print("  1. Review: git diff schema/jackpot_schema.yaml")
    print("  2. Validate: python3 -c \"import yaml; "
          "yaml.safe_load(open('schema/jackpot_schema.yaml')); print('OK')\"")
    print("  3. Run schema_update.py from the workspace root:")
    print("     python3 ~/ASU/jackpot/schema_update.py \\")
    print("         --version 4.4 \\")
    print("         --message \"WHO/CDC alignment — symptom onset, travel history, "
          "outbreak entity, registered access\" \\")
    print("         --skip-script")
    print("\n  New Alembic migration will need:")
    print("    - date_of_symptom_onset, travel_history_country[], travel_history_days")
    print("      host_age_range, collection_method on samples (HumanSample rows)")
    print("    - travel_origin_region on samples (WildlifeSample rows)")
    print("    - nwss_sewershed_id on samples (WastewaterSample rows)")
    print("    - pango_qc_status, pango_conflict, mlst_confidence on samples")
    print("    - outbreak_investigations table (OutbreakInvestigation class)")
    print("    - outbreak_investigation_id FK on samples")


if __name__ == "__main__":
    main()
