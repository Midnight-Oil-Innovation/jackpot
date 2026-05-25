# JACKPOT — Project Charter

## Mission

JACKPOT is open-source pathogen genomics infrastructure for public-health
laboratories, public-health agencies, Tribal authorities, and academic
research groups. It exists to make it cheap, safe, and sovereignty-respecting
for any operator to ingest, validate, analyze, and share pathogen sequencing
data without surrendering control of that data to a centralized platform.

## What JACKPOT is

JACKPOT is a **multi-deployment-target software platform** licensed under
AGPL-3.0. It runs on a laptop, in a single organization's cloud account, in
a multi-lab health-agency installation, as a hosted SaaS, as a federation
member exchanging data with peer instances, in CI test environments, and in
Tribal-sovereignty deployments with sovereignty-aware defaults. The platform
is deliberately operator-agnostic — production code knows nothing about any
specific institution; the `jackpot init` CLI is the only place where
operator names and infrastructure identifiers enter the system.

The seven install scenarios are documented in `spec.md §1` and the per-tier
deploy guides under `docs/deploy/`.

## What JACKPOT is not

JACKPOT is not a hosted service. The reference deployment that the project
maintainers run is for testing and demonstration only; it is not a
production data store for anyone else's samples.

JACKPOT is not a replacement for case-management systems (NBS, MAVEN,
analysis platforms (NCBI Pathogen Detection, Pathoplexus, Pathogenwatch,
Nextstrain, GenSpectrum). JACKPOT integrates with these systems through
documented contracts; it does not try to absorb their scope. See
`docs/jackpot_cdc_dmi_stlt_overview.md §9` for the layer-cake positioning.

JACKPOT is not a credentialed broker. It does not hold submitter accounts
on behalf of operators for NCBI BioSample/SRA, GISAID, or Pathoplexus —
each operator brings their own credentials. The platform exposes the
brokering machinery (templates, validation, packaging) but the relationship
with the destination repository belongs to the operator.

## Who JACKPOT is for

- **Public-health labs** (state, local, territorial, Tribal) doing routine
  pathogen surveillance.
- **Tribal Epidemiology Centers** acting as federation hubs for member
  Tribes that want sovereignty-preserving data sharing.
- **Tribal authorities** running sovereignty-respecting deployments with
  CARE-Principles-aligned defaults.
- **Academic and research labs** doing one-off or programmatic genomic
  epidemiology work that needs more than ad-hoc Excel + Nextflow.
- **Single-org operators** that want pathogen-surveillance capability
  without paying the overhead of a multi-tenant SaaS contract.

## Stewardship

JACKPOT is currently maintained by Midnight-Oil-Innovation. The project
welcomes contributions from any operator running JACKPOT in production and
from the broader pathogen-genomics community. Contribution mechanics, code
of conduct, and review expectations live in `CONTRIBUTING.md` (forthcoming).

The project commits to forward-compatibility for AGPL-licensed forks: any
operator running JACKPOT can fork the codebase and keep running indefinitely
even if upstream stops maintaining the project. The shutdown-and-portability
plan is documented separately
(`governance/platform-shutdown-data-portability-plan.md`).

## Funding posture

JACKPOT does not solicit operator-side funding to use the software. The
software is, and will remain, free under AGPL-3.0. The project may accept
grant funding from public-health funders, philanthropic sources, or
research foundations to support development; any such funding will be
disclosed publicly.

Operators paying for JACKPOT support, hosting, or customization from
third-party vendors (including the project maintainers in any commercial
capacity) is encouraged — that is the AGPL business model in action — but
no operator is obligated to pay anyone to run JACKPOT.

## Conflicts of interest

The project maintainers' commercial entities, current public-health
contracts, and other relationships that could influence project direction
are disclosed in `governance/coi-policy.md`. Any decision to add a feature
that disproportionately benefits a single operator must be reviewable in the
public-issue tracker with the rationale documented.

## Governance evolution

This is a single-maintainer project today. As JACKPOT grows past a handful
of production deployments, it should add an advisory board that includes
representatives from active operator-types: at minimum a state-health
representative, a Tribal-sovereignty representative, an academic-research
representative, and a federation-member representative. The composition,
selection process, and decision scope are documented in
`governance/advisory-board.md`.

## CARE Principles

JACKPOT formally commits to the CARE Principles for Indigenous Data
Governance (Collective Benefit, Authority to Control, Responsibility,
Ethics) alongside FAIR. The mapping from each CARE principle to specific
JACKPOT architectural decisions is documented in
`governance/care-principles-and-tribal-data-sovereignty.md`.
