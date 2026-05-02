# State Health Department deployment

## Who this is for

State public-health departments that operate (or contract with) a public-
health laboratory and want pathogen-genomics infrastructure that:

- Stays inside the state's IT estate.
- Integrates with the state's existing case-management system (NBS,
  MAVEN, Trisano) without replacing it.
- Supports multiple labs across the state under a single deployment.
- Submits data to NCBI BioSample/SRA and (for SARS-CoV-2) GISAID
  using the state's existing submitter accounts.

Most state health departments will run **Scenario C** (multi-lab
agency). The few smaller-state departments that operate a single lab
(no satellite labs) may instead run **Scenario B** (single org on
cloud).

## Fit rationale

A state health department typically has:

- One central public-health lab and 2–10 sentinel/regional labs that
  feed into it. The org/lab/project hierarchy in JACKPOT was designed
  for exactly this shape.
- Active NCBI submitter accounts (BioProject + BioSample + SRA) under
  the state's name.
- An IT department that can manage cloud infrastructure (typically
  GCP, AWS, or Azure depending on the state's existing cloud
  contract).
- An epidemiology team that lives in NBS or MAVEN; bioinformatics
  staff who live in JACKPOT-equivalent tooling today (often a mix of
  Excel + Nextflow + ad-hoc scripts).

JACKPOT's value proposition for this operator:

- Replaces ad-hoc bioinformatics tooling with a structured platform
  that all sentinel labs can submit to.
- Provides the brokering machinery for NCBI/GISAID submission so each
  lab doesn't reinvent the workflow.
- Adds the access-control + audit layer that state-level IT and
  epidemiology auditing requires.
- Supports federation if the state wants to peer with neighboring
  states' instances or with a regional Center of Excellence.

## Install steps

1. **Provision the cloud project.** GCP project, Cloud SQL Postgres,
   GCS buckets, Artifact Registry, GKE cluster (or whatever your
   state's cloud allows). The reference Terraform under
   `deploy/terraform/` is GCP-specific; AWS/Azure equivalents are
   community-contributable.

2. **Run `jackpot init configure --scenario C`** (shipped in P0e — see
   `docs/install/quickstart.md`). The CLI prompts for your state
   name, the contact email for platform-admin notifications, and the
   public API URL. Then `jackpot init secrets --instance <name>` to
   generate the JWT signing key, and `jackpot init bootstrap --instance
   <name>` to apply alembic + seed.sql + smoke-test `/health`.

3. **Apply the Terraform / Helm.** The deploy/ subtree of this
   monorepo is where your IT team gets started. The reference
   configuration deploys to a GKE cluster with Workload Identity for
   GCP authentication.

4. **Configure your NCBI submitter accounts** in the operator-config
   YAML. The platform reads the BioProject ID, the SRA submission
   credential reference (Secret Manager / ASM / Key Vault path), and
   the GISAID credential reference. Production code never sees the
   credentials directly — it asks the operator's secret manager.

5. **Seed your reportable-organisms list.** The 62-value default set
   that ships with the platform is a starting point. Your state's
   reportable-disease list almost certainly differs. The `jackpot init`
   flow imports a CSV; the admin UI lets Platform Admins add/remove
   values without code changes.

6. **Migrate or onboard sentinel labs.** Each sentinel lab gets a
   `Lab` row in your deployment, a `Lab Director` user, and any
   collaborators they need. The `lab_membership` table controls
   per-lab access; the `sequencing_lab_assignments` table controls
   which sentinel labs can submit data on behalf of which JACKPOT labs.

7. **Configure the integration with NBS / MAVEN / Trisano** if your
   state needs sample → case linkage. JACKPOT does not have a built-in
   case-management connector today (Phase 27 backlog item B-DMI-2 is
   the FHIR ingest router that would enable this); the typical
   interim pattern is to push specimen IDs to the state's case system
   via the system's own ETL, with an annual export from JACKPOT.

## Governance and data handling

- **Sample sharing-level default:** PRIVATE. Promotion to CONSORTIUM
  or PUBLIC is per-sample, requires Lab Director or Platform Admin
  approval (configurable in the admin UI).
- **Audit log retention:** 7 years (matches CLIA + state public-health
  retention norms). Configurable longer; do not configure shorter
  without consulting your state's records-management officer.
- **DLP gate:** ON by default (Critical Rule 43). Free-text metadata
  fields are scanned for PII before DB commit. Do not disable.
- **Federation:** Off by default. Enable if you have a peering
  arrangement with another state, a regional Center of Excellence, or
  CDC.
- **Submission to NCBI/GISAID:** Per-sample, with the state's
  submitter accounts. The platform packages the submission; your
  authorized submitter approves and releases.

## Funding sources

| Source | Eligibility | Use | Fit |
|---|---|---|---|
| **ELC (Epidemiology and Laboratory Capacity)** | States, large LHDs, territories | Lab capacity, surveillance, staff | ✅ Direct fit for state-deployed JACKPOT |
| **PHIG (Public Health Infrastructure Grant)** | All STLT | Foundational capabilities, IT infrastructure | ✅ Direct fit; the IC Program (paused) was PHIG-funded |
| **PHEP (Public Health Emergency Preparedness)** | State + LHD | Preparedness exercises, response systems | ⚠️ Possible for response-readiness framing |
| **DMI cooperative agreements** | All STLT | Data modernization specifically | ✅ Currently in limbo but historically the most direct fit |
| **State own funds** | Self | Anything the state appropriates | ✅ The cleanest path; depends on appropriations |

## Workforce considerations

- **Bioinformatics staff:** 1–2 FTE for a small-state deployment, 3–5
  for a large-state deployment. Existing public-health-lab
  bioinformaticians can run JACKPOT after a few weeks of ramp; no
  specialized JACKPOT-specific certification is needed.
- **IT operations:** 0.5–1 FTE for a managed-cloud deployment (Cloud
  SQL + GKE + Cloud Scheduler all reduce ops burden). Closer to 1–2
  FTE for an on-prem deployment.
- **Epidemiology liaison:** 0.25 FTE — someone who knows both NBS and
  the genomics workflow and can bridge them.

## Common pitfalls

- **Trying to use JACKPOT as the case-management system.** It isn't.
  Keep NBS / MAVEN / Trisano as the case-management system; integrate
  via specimen-ID joins.
- **Skipping the operator-side benefits-sharing policy.** The
  governance/benefits-sharing-framework.md is project-side defaults;
  your state should publish its own deployment-local
  `docs/operator-benefits-sharing.md` for the labs you serve.
- **Hardcoding the central-lab name in custom code.** Use the
  `organizations` and `labs` tables; do not fork the codebase to add
  state-specific constants. Critical Rule 55 applies.
- **Treating the federation feature as discovery.** Federation is
  signed-message exchange between peers you've explicitly approved.
  It is not a search engine; it is not a publication channel. If you
  want public discovery, submit to NCBI.
- **Letting the DLP gate get disabled "for testing" and forgetting to
  re-enable.** Don't.
