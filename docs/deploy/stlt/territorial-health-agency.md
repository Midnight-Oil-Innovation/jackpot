> **Status:** Reference — STLT deployment guide for territorial health agencies.

# Territorial health agency deployment

## Who this is for

The five U.S. territories with public-health agencies — American Samoa,
Guam, Northern Mariana Islands, Puerto Rico, U.S. Virgin Islands — and
the three Freely Associated States with cooperative agreements
(Federated States of Micronesia, Republic of the Marshall Islands,
Republic of Palau).

Most will run **Scenario B** (single org on cloud). The smallest may
prefer **Scenario A** (single lab on a laptop) for the first few years
and graduate to Scenario B once volume justifies the cloud spend.

## Fit rationale

Territorial health agencies typically have:

- A single lab (sometimes none, contracting out to a CDC lab or to
  Hawaii / California reference labs).
- Limited bioinformatics staff (often one person, occasionally
  shared with epidemiology).
- Internet connectivity that may be intermittent or low-bandwidth
  depending on the territory.
- Active partnerships with CDC's territorial-support programs and with
  regional public-health-lab consortia.

JACKPOT's value for this operator:

- Runs offline / low-bandwidth (Scenario A) or in a small cloud
  footprint (Scenario B) without needing per-seat SaaS contracts.
- Small enough to maintain with one person.
- Submission tooling for NCBI and GISAID without the operator having
  to build a submission workflow from scratch.
- Path to federation if the territory wants to peer with neighboring
  Pacific Island health departments or with a regional Center of
  Excellence.

## Install steps

1. **Decide A vs B.** If your sequencing volume is < 50 samples per
   month and your bioinformatics workflow is "one analyst on one
   workstation," start with Scenario A. If you have a lab IT team and
   need access from multiple workstations, go straight to Scenario B.

2. **Provision the cloud project (Scenario B only).** Smallest viable
   GCP/AWS/Azure footprint: a single Cloud SQL instance (db-f1-micro
   or equivalent), a single GCS bucket family, a single GKE node pool
   with one e2-medium node. The reference Terraform is sized for a
   state-scale deployment; territorial deployments can drop to about
   1/10 the resource budget.

3. **Run `jackpot init configure --scenario A`** (or `--scenario B`
   for a cloud territorial deployment) — shipped in P0e, see
   `docs/install/quickstart.md`. For Scenario A: the CLI emits a
   Docker Compose `.env.local` with `COMPOSE_PROFILES=laptop` (api +
   postgres + minio + ui), and `jackpot init secrets` generates a
   per-instance JWT signing key. For Scenario B: the CLI emits a
   Helm `values.local.yaml` overlay with `COMPOSE_PROFILES=single-org`
   for any local-dev runs alongside the cloud deploy.

4. **Configure NCBI submitter account.** Most territorial agencies
   submit to NCBI either directly under their own BioProject or via
   an arrangement with CDC. JACKPOT supports either.

5. **Seed reportable-organisms.** The territorial reportable-disease
   lists differ from continental U.S. lists — dengue, leptospirosis,
   typhoid, and several locally-relevant zoonoses are usually higher
   priority. The CSV import flow makes adapting the seed quick.

6. **Decide on Globus / data-transfer integration.** Territorial labs
   often partner with reference labs that transfer raw sequencing
   data via Globus or via shipped storage media. JACKPOT supports
   Globus endpoint registration; the operator-config YAML records the
   endpoint ID. Shipped media can be ingested via the standard CSV
   batch flow once the data is on local storage.

## Governance and data handling

- **Sharing-level default:** PRIVATE. Many territories have data-
  sharing arrangements with their CDC partners that require
  promotion-on-approval rather than auto-share.
- **Federation:** Off by default. The Pacific-region public-health-lab
  federation is forming as of 2026; consider enabling once that
  network is stable.
- **DLP gate:** ON. Particularly important for territorial deployments
  where small populations make any leaked metadata more identifying.
- **Audit log retention:** 7 years.

## Funding sources

| Source | Eligibility | Use | Fit |
|---|---|---|---|
| **ELC (territories)** | All territories | Lab capacity, surveillance | ✅ Direct fit — territorial allocations exist |
| **PHIG (territories)** | All territories | Infrastructure | ✅ Direct fit |
| **CDC cooperative agreements specific to FAS / territories** | FAS + territories | Various | ✅ Often the primary funding line |
| **PHEP** | Territories | Preparedness | ⚠️ Possible for response-readiness framing |
| **Wellcome / Gates / philanthropic** | Any | Open source infrastructure for low-resource settings | ⚠️ More likely for FAS than territories |
| **Territorial own funds** | Self | Anything appropriated | ✅ Variable by territory |

## Workforce considerations

- **Bioinformatics staff:** 0.5–1 FTE typical. JACKPOT's defaults are
  designed to minimize the operator's per-day work — the ingest gate,
  validator, and pipeline scheduler do most of the work without
  constant tuning.
- **IT operations:** 0.25–0.5 FTE for Scenario A (a workstation). 0.5–1
  FTE for Scenario B (managed cloud).
- **Coordination with CDC partner programs:** The platform exposes
  the metadata fields CDC partner programs need; the operator-side
  workflow for actually transmitting to CDC is unchanged.

## Common pitfalls

- **Underestimating bandwidth requirements for raw FASTQ transfer.**
  A single MinION run is ~5 GB; an Illumina NovaSeq run can be
  hundreds of GB. Plan for either local storage + media shipping or
  a Globus endpoint with adequate bandwidth.
- **Overprovisioning the cloud footprint.** Territorial volumes are
  small. Don't blindly copy a state-scale Terraform; right-size.
- **Forgetting to localize the reportable-organisms list.**
  Tropical-disease organisms relevant to your territory may not be
  in the continental U.S. default seed.
- **Pricing assumption mismatches.** GCP/AWS/Azure egress charges
  matter more for territorial deployments because the data often
  needs to flow off-island for collaboration. Estimate egress in your
  cost model.
