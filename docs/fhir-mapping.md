# JACKPOT — FHIR-translatable data model

## Purpose

JACKPOT does not currently expose a FHIR API. It probably should not for
the foreseeable future — building a FHIR endpoint speculatively, before
an actual operator needs to integrate with TEFCA / a state HIE / an EHR,
risks shipping a contract that doesn't fit the eventual use case.

But the *data model* is FHIR-translatable today. Documenting that
translation now means:

1. When an operator does need FHIR, the mapping work is mostly
   already done.
2. Grant narratives that reference FHIR/TEFCA alignment can do so
   honestly.
3. Schema changes that would break FHIR translatability get caught
   during review (point at this doc).

This doc maps the JACKPOT LinkML schema's relevant entities to FHIR R5
resources. Implementation of the actual translation is Phase 27 backlog
item B-DMI-2.

## Mapping table

| JACKPOT entity | FHIR R5 resource | Translation notes |
|---|---|---|
| `Sample` (the union of `HumanSample`, `EnvironmentalSample`, `Isolate`, etc.) | [`Specimen`](https://hl7.org/fhir/R5/specimen.html) + [`MolecularSequence`](https://hl7.org/fhir/R5/molecularsequence.html) | `Specimen` carries the source-side metadata (collection date, location, source type). `MolecularSequence` carries the actual sequencing details and references to the FASTQ files. |
| `pipeline_results` | [`Observation`](https://hl7.org/fhir/R5/observation.html) + [`Provenance`](https://hl7.org/fhir/R5/provenance.html) | `Observation` carries the result value (typing, AMR profile, cluster assignment). `Provenance` carries which pipeline+version+parameters produced it. Multiple `Observation` resources per sample, one `Provenance` per pipeline run. |
| `sequencing_lab` | [`Organization`](https://hl7.org/fhir/R5/organization.html) | Standard FHIR Organization, with `type` slice = "lab" and an identifier from the operator's namespace. |
| `organizations` (the JACKPOT operator's own org/agency rows) | [`Organization`](https://hl7.org/fhir/R5/organization.html) | Same resource type, different `type` slice. |
| `labs` (sub-units within the operator) | [`Organization`](https://hl7.org/fhir/R5/organization.html) with `partOf` reference | `partOf` references the parent `organizations` Organization. |
| `users` (Platform Admin, Lab Director, etc.) | [`Practitioner`](https://hl7.org/fhir/R5/practitioner.html) + [`PractitionerRole`](https://hl7.org/fhir/R5/practitionerrole.html) | Practitioner carries the identity; PractitionerRole carries which lab and which JACKPOT permission group. |
| `audit_log` entries | [`AuditEvent`](https://hl7.org/fhir/R5/auditevent.html) | Direct mapping; JACKPOT's audit-log shape (action + actor + target + timestamp) translates cleanly. |
| `projects` (Seqera-derived org/lab/project hierarchy) | [`ResearchStudy`](https://hl7.org/fhir/R5/researchstudy.html) | One ResearchStudy per project. Useful for grant-tracked or IRB-tracked projects. |

## Resources JACKPOT does NOT map to

These are deliberate omissions, not gaps:

- **`Patient`.** JACKPOT does not store patient identifiers. The DLP
  free-text scanner (Critical Rule 43) actively prevents PII from
  reaching the database. JACKPOT's `external_case_id` field is the
  operator-issued anonymized case identifier or exemption code, not a
  patient identifier. Translating to FHIR `Patient` would imply
  patient-level data that JACKPOT explicitly does not hold.

- **`Practitioner` for clinical providers.** JACKPOT users are
  laboratory and analytical staff, not the clinicians who collected
  the original specimen. The collecting clinician is referenced
  abstractly via `collection_facility` (mapped to `Organization`,
  not `Practitioner`).

- **`Encounter`.** JACKPOT operates at the specimen-and-sequencing
  layer, not the clinical encounter layer. Encounter context is
  upstream of JACKPOT (in the originating clinical system) and may
  be referenced indirectly via `external_case_id` joining to NBS / an
  EHR system, but JACKPOT does not store encounter resources.

- **`Condition`.** Diagnosis is upstream of JACKPOT. JACKPOT's
  `host_disease` field captures the operator-reported indication for
  sequencing, not a clinical diagnosis. If clinical diagnosis is
  needed, it is pulled from the upstream case-management system at
  query time, not stored in JACKPOT.

- **`DiagnosticReport`.** JACKPOT emits typing / AMR / cluster
  results that look diagnostic-report-shaped, but the actual clinical
  diagnostic report happens at the clinical lab (CLIA-regulated)
  layer, not at the genomics-layer JACKPOT lives in. Mapping JACKPOT
  results to `DiagnosticReport` would imply CLIA equivalence that the
  platform does not assert.

The "no Patient, no Practitioner-as-clinician" boundary is a
sovereignty and PII protection. It is a feature, not a limitation.

## Field-level mapping (Specimen example)

For the most-frequent translation case, JACKPOT `HumanSample` →
FHIR `Specimen`, the field-level mapping is:

| JACKPOT field | FHIR Specimen path | Notes |
|---|---|---|
| `sample_id` | `Specimen.identifier[0].value` | System = the operator's namespace |
| `external_case_id` | `Specimen.identifier[1].value` | System = the operator's case-namespace; absent for non-Human samples |
| `date_collected` | `Specimen.collection.collectedDateTime` | Full or partial date precision per FHIR spec |
| `collection_facility` | `Specimen.collection.collector.display` | Could be promoted to `Specimen.collection.collector` reference if the operator maintains a `collection_facility` Organization registry |
| `collection_location_country` + `collection_location_state` | `Specimen.collection.bodySite.text` (no — wrong path) → custom `Specimen.extension` for geographic origin | FHIR doesn't have a clean "geographic source" slot for non-clinical specimen; use a profile-defined extension |
| `biospecimen_type` | `Specimen.type` | Mapped to a SNOMED CT or LOINC code |
| `source_type` | `Specimen.subject` (omitted — see "no Patient" above) plus a custom `Specimen.extension` for `JACKPOT_source_type` | JACKPOT keeps source-type as a structured field; FHIR `Specimen.subject` would point at a Patient that JACKPOT doesn't hold |
| `host_age` (if HumanSample) | omitted in FHIR translation | Aggregate-only in JACKPOT exports; not translated to per-Specimen |
| `host_sex` (if HumanSample) | omitted in FHIR translation | Same |
| `organism_name` | (target organism is sequenced FROM the specimen, not OF the specimen) → `MolecularSequence.referenceSeq.referenceSeqId` or a custom `JACKPOT_target_organism` extension | FHIR `Specimen` is about the host material; the pathogen identity belongs on `MolecularSequence` |
| `sequencing_platform` | `MolecularSequence.observedSeq.platform` (custom extension; FHIR R5 doesn't have a clean platform slot) | |
| `type_of_experiment` | (handled at MolecularSequence + Observation level) | |
| `quality_status` (PRELIMINARY / ANALYZABLE / SUBMITTABLE) | `Specimen.status` is too narrow (available/unavailable/unsatisfactory) → custom extension | JACKPOT's tier is a richer concept than FHIR Specimen.status |

The exhaustive field-level mapping for all JACKPOT entities × FHIR
resources is left to the implementation phase (B-DMI-2). This document
captures the mapping at the resource-and-headline-field level so that
the implementation can fill in the rest without architectural
surprises.

## Implementation choices to make later

When B-DMI-2 actually lands a FHIR endpoint, several decisions need
review:

- **Profile selection.** US Core? Genomics Reporting IG? A custom
  profile for JACKPOT? Probably the latter, with extensions
  documented as a profile.
- **Read-only vs read-write.** JACKPOT's first FHIR exposure should
  almost certainly be read-only (`GET /fhir/Specimen/{id}`,
  `GET /fhir/MolecularSequence/{id}`, `GET /fhir/Observation?subject=
  Specimen/{id}`). Write would imply JACKPOT accepting samples via
  FHIR ingest, which is a substantial scope.
- **Authentication.** SMART on FHIR? OAuth2 with operator-issued
  client credentials? Federation contract with the requesting
  system? All viable; defer until an operator names one.
- **Bulk export.** FHIR Bulk Data Access ($export) is the obvious
  pattern for surveillance-reporting use cases. Worth designing for
  even if not implementing initially.
- **Versioning.** FHIR R5 is current as of 2026; the Genomics
  Reporting IG is on R5 in its 2026 publication. Pin to R5; provide
  R4-compatible translation only if explicitly needed.

## Why this doc exists separately from the LinkML schema

The LinkML schema is the source of truth for what JACKPOT stores. The
FHIR mapping is one of *many* possible export contracts (others:
NCBI BioSample/SRA XML, GISAID metadata, TOSTADAS, Pathoplexus
submission, Pathogenwatch import). Each export contract gets its own
mapping document so that schema changes can be cross-checked against
all known export contracts before they land.

The LinkML → FHIR translation is intentionally documented here in
prose rather than encoded as a LinkML mapping (which LinkML supports)
because the mapping involves slot-level decisions (extensions vs
profiles, omitted resources, custom typing) that don't fit cleanly
into a declarative mapping syntax. Once B-DMI-2 implements the
actual translation, the implementation can codify whatever subset
of this fits in a generated form.

## Related

- `docs/jackpot_cdc_dmi_stlt_overview.md §5` — the broader
  TEFCA/FHIR positioning rationale.
- LinkML mapping configs at `schema/schema/mapping_configs/` — the
  inbound mapping (CSV → JACKPOT). FHIR is part of the outbound
  story.
- HL7 FHIR R5: https://hl7.org/fhir/R5/
- HL7 Genomics Reporting Implementation Guide:
  https://hl7.org/fhir/uv/genomics-reporting/
