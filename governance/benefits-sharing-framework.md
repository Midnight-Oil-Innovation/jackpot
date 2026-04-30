# JACKPOT — Benefits-Sharing Framework

## What "benefits sharing" means here

In pathogen-genomics infrastructure, "benefits sharing" is the question of
who gets credit, citations, downstream-use rights, and follow-on funding
when sequence data flows from the lab that generated it through analysis
platforms to the broader research and public-health community.

JACKPOT is not the data; JACKPOT is the platform. The benefits-sharing
question for the *platform* is narrower than the benefits-sharing question
for the *data*, but the platform's defaults shape the data's downstream
trajectory. This document establishes the project's defaults and the
operator-configurable knobs.

## Three levels of benefit

1. **Citation benefit.** When an operator's data feeds an analysis,
   publication, or surveillance bulletin, the originating operator
   should be cited.

2. **Collaboration benefit.** When an outside researcher wants to do
   secondary analysis of data the operator generated, the operator
   should know it's happening and have the option to collaborate.

3. **Data-back-to-source benefit.** When external analysis reveals new
   information about a sample (improved typing, AMR profile, cluster
   assignment, novel-organism detection), the originating operator
   should receive that updated information back automatically, not have
   to harvest it from a paper.

The platform supports all three; the operator's sharing-level
configuration determines which apply per sample.

## Defaults by scenario

| Scenario | Citation | Collaboration | Data-back |
|---|---|---|---|
| A — Single academic lab | Required for any external sharing | Opt-in | Opt-in |
| B — Single org on cloud | Required for any external sharing | Opt-in | Opt-in |
| C — Multi-lab agency | Required, with state attribution | Opt-in per lab | On by default for federation peers |
| D — Hosted SaaS | Per tenant policy (set by operator) | Per tenant policy | Per tenant policy |
| E — Federation member | Required, with peer attribution | On by default | On by default |
| F — CI / e2e test | N/A (synthetic data) | N/A | N/A |
| T — Tribal-sovereignty | Required, with explicit Tribe attribution | OFF by default; explicit per-sample approval | OFF by default; explicit per-sample approval |

The Scenario T defaults reflect the CARE-Principles framework: the
serving Tribe controls when collaboration and data-back arrangements
apply. See `governance/care-principles-and-tribal-data-sovereignty.md`
for the full reasoning.

## Citation mechanics

When an operator publishes sample data via JACKPOT — to a public
repository (NCBI BioSample/SRA, GISAID, Pathoplexus), to a federation
peer, or to a downstream analysis platform — the platform attaches a
citation block to the sample's metadata containing:

- Operator entity (organization name, lab name as applicable)
- Originating sequencing-lab entity
- Submission date
- A persistent identifier for the operator's contribution (the JACKPOT
  internal sample ID at minimum; a DOI if the operator has a DOI
  registry integration configured)

Downstream analysts who use the data are expected to honor the citation.
The platform makes this easy by emitting BibTeX, RIS, and
citation-style-language JSON forms on request.

## Collaboration mechanics

For operators with collaboration-enabled defaults, the platform exposes
two channels:

- **Sample access requests** (`POST /api/v1/sample-access/`). An outside
  researcher can request analytic access to specific samples; the
  originating operator approves or denies in the admin UI; if approved,
  the requester gets time-bounded read access (default 90 days,
  operator-configurable).

- **Per-sample contact disclosure.** Samples flagged for collaboration
  expose the originating-lab contact email in their metadata view.
  Researchers can reach out directly without going through the
  access-request workflow.

For operators with collaboration off (default for Scenario T), neither
channel is exposed. The operator can still share samples with specific
peers via federation, but the platform does not advertise samples for
discovery.

## Data-back mechanics

When pipeline results are computed downstream of a sample (typing,
AMR, cluster assignment, novel-organism detection), the result can flow
back to the originating operator in two ways:

- **Federation back-pressure.** A federation peer that runs a pipeline
  on a shared sample emits the result back to the originating instance
  via the federation protocol. The originating operator sees the
  result attached to their sample as if they had run the pipeline
  themselves.

- **External-result import.** An operator can subscribe to NCBI Pathogen
  Detection cluster updates, GenSpectrum mutation calls, or
  Pathogenwatch typing results for samples they originated. The
  platform polls these sources and imports the result on a schedule.

For Scenario T deployments, both data-back channels are off by default.
The Tribal authority decides per-sample whether to subscribe.

## What the platform never does

- Aggregate operator data across instances for project-side analytics.
- Publish operator data to any public repository without explicit
  per-sample approval from the operator.
- Use operator data for training models, building reference datasets,
  or any other purpose that benefits the project without benefiting the
  originating operator.
- Treat any operator's data as "the project's data" by virtue of having
  passed through JACKPOT-the-software.

## Operator-side benefits-sharing policies

Operators are encouraged to publish their own benefits-sharing policies
covering their relationships with the *originators* of their samples (the
patients, the environment, the wildlife). The platform supports
operator-defined consent and benefit-sharing flags on samples, but the
content of those policies is the operator's responsibility.

For Scenario T, the project recommends operators consult with their
Tribal Research Review Board (or equivalent) and document the resulting
policies under the operator's deployment-local
`docs/operator-benefits-sharing.md` file.
