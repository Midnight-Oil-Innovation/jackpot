# JACKPOT

**Pathogen genomics platform for genomic epidemiology, bioinformatics,
and public-health research.** AGPL-3.0. Multi-deployment-target by
design — one codebase, seven install scenarios.

This is the canonical monorepo at `Midnight-Oil-Innovation/jackpot`. It
holds the backend, the CLI, the schema, the pipeline parsers, the
infrastructure code, and the project's governance documents in one
place. As of P0d (April 2026) the repo replaced the previous
six-repo + git-submodule layout.

## What's in this repo

| Top-level | Contents | Maintainers |
|---|---|---|
| [`backend/`](./backend/) | FastAPI service (REST API + Streamlit researcher UI), validators, ingest gate, pipeline launch + result loaders, scheduler, storage abstraction. uv workspace member. | Project core |
| [`cli/`](./cli/) | `jackpot` CLI + Python SDK. Programmatic access to the API. uv workspace member. | Project core |
| [`schema/`](./schema/) | LinkML metadata schema (single source of truth for all sample metadata) + a thin Python helper exposing schema paths. uv workspace member. | Project core |
| [`pipelines/`](./pipelines/) | Nextflow pipelines + the `nf-jackpot` plugin + shared parsers (Cecret, viralrecon, walkercreek, bactopia, Grandeur, mycosnp, tb-profiler, mag, taxprofiler, pathogensurveillance). Has its own pyproject; not part of the workspace by design. | Project core |
| [`deploy/`](./deploy/) | Terraform (GCP) + Helm charts + deployment scripts for staging/production environments. | Project core + ops |
| [`docs/`](./docs/) | Product docs, architecture design documents, deploy guides, FHIR mapping, learnings/review log. | Project core |
| [`governance/`](./governance/) | Charter, COI policy, jurisdiction posture, benefits-sharing framework, grievance procedure, shutdown/portability plan, advisory board design, CARE Principles. | Project core + future advisory board |
| [`tests/`](./tests/) | Backend's integration tests against a real Postgres testcontainer. (CLI and pipelines have their own member-local tests.) | Project core |
| [`spec.md`](./spec.md), [`todo.md`](./todo.md) | Living project specification + rolling task list. | Project core |

## Deploy scenarios

JACKPOT supports seven install scenarios — see
[`spec.md §1`](./spec.md) for the full picture and
[`docs/deploy/stlt/`](./docs/deploy/stlt/) for STLT-tier specific
guides.

| Code | Scenario | Per-tier guide |
|---|---|---|
| **A** | Single academic lab on a laptop | (in P0e install/CLI work) |
| **B** | Single org on cloud (GCP / AWS / Azure) | (in P0e install/CLI work) |
| **C** | Multi-lab agency (typical state public-health department shape) | [state-health-department.md](./docs/deploy/stlt/state-health-department.md) |
| **D** | Hosted multi-tenant SaaS | (in P0c multi-tenancy work) |
| **E** | Federation member (peers with other JACKPOT instances) | [tribal-epidemiology-center.md](./docs/deploy/stlt/tribal-epidemiology-center.md) |
| **F** | CI / e2e test harness | (in `tests/` and `.github/workflows/`) |
| **T** | Tribal-sovereignty deployment (variant of A or E with sovereignty-aware defaults) | [tribal-authority.md](./docs/deploy/stlt/tribal-authority.md) |

Production code is **operator-agnostic** (Critical Rule 55 in
[`docs/CLAUDE.md`](./docs/CLAUDE.md)) — no organization names, email
domains, or infrastructure identifiers are hardcoded. The `jackpot
init` CLI is the only place where operator-specific values are learned
at install time.

## Operations runbooks

For deploying and operating a JACKPOT instance:

| Runbook | When to use it |
|---|---|
| [`docs/deploy/production-deploy.md`](./docs/deploy/production-deploy.md) | Every production deploy. Documents the GitHub Actions `production` environment approval gate, what an approver should verify, cancel + rollback procedures. |
| [`docs/deploy/pitr-restore-drill.md`](./docs/deploy/pitr-restore-drill.md) | Before going live with real data, then quarterly. Validates Cloud SQL point-in-time recovery is configured AND your team can execute it. |
| [`docs/staging_access.md`](./docs/staging_access.md) | Day-to-day staging environment access, troubleshooting, and the bootstrap Job pattern. |

## Governance

JACKPOT is licensed AGPL-3.0 and is committed to FAIR + CARE
principles. The full set of governance documents lives under
[`governance/`](./governance/):

- [`charter.md`](./governance/charter.md) — what the project is and is not
- [`coi-policy.md`](./governance/coi-policy.md) — maintainer disclosure expectations
- [`jurisdiction-and-data-residency.md`](./governance/jurisdiction-and-data-residency.md) — where operator data lives per scenario
- [`benefits-sharing-framework.md`](./governance/benefits-sharing-framework.md) — citation, collaboration, data-back defaults
- [`access-grievance-procedure.md`](./governance/access-grievance-procedure.md) — how to raise concerns
- [`platform-shutdown-data-portability-plan.md`](./governance/platform-shutdown-data-portability-plan.md) — what happens to operators if the maintainer steps away
- [`advisory-board.md`](./governance/advisory-board.md) — forward-looking governance design (board not yet constituted)
- [`care-principles-and-tribal-data-sovereignty.md`](./governance/care-principles-and-tribal-data-sovereignty.md) — Scenario T design and CARE → JACKPOT defaults mapping

## Development

The fastest path from `git clone` to a running stack is the
[10-minute quickstart guide](./docs/install/quickstart.md):

```bash
# Clone + workspace install
git clone git@github.com:Midnight-Oil-Innovation/jackpot.git
cd jackpot
uv sync

# Bootstrap a laptop instance (Scenario A)
uv run jackpot init configure --scenario A --instance-name local --no-gh
uv run jackpot init secrets --instance local
docker compose --env-file instances/local/.env.local up -d
uv run jackpot init bootstrap --instance local

# Test suite (Docker required for testcontainers)
uv run pytest
```

> **Heads-up:** `docker compose up` requires `COMPOSE_PROFILES` to be
> set, either via `--env-file instances/<name>/.env.local` (as above)
> or explicitly (`COMPOSE_PROFILES=laptop docker compose up`). Without
> it, every service in `docker-compose.yml` is profile-gated and the
> command silently brings nothing up.

For other scenarios:

```bash
# Show what jackpot init knows about each scenario
uv run jackpot init scenario-info F --json     # CI defaults
uv run jackpot init scenario-info T --json     # Tribal-sovereignty defaults

# Walk the 5-question detector to pick the right scenario for your operator
uv run jackpot init detect
```

See [`docs/architecture/jackpot-init-cli.md`](./docs/architecture/jackpot-init-cli.md)
for the design + the 9 architectural decisions that shape `jackpot init`,
and the [STLT-tier deploy guides](./docs/deploy/stlt/) for cloud
deployment specifics per operator type.

For the full developer guide, the 55 Critical Rules, the testing
philosophy, and the GCP production architecture, read
[`docs/CLAUDE.md`](./docs/CLAUDE.md). For the rolling task list and
the active sprint, read [`todo.md`](./todo.md). For the design
documents driving Phase 26 / 27 / 28 and the BYOP infrastructure work,
see:

- [`docs/jackpot_pathoplexus_loculus_overview.md`](./docs/jackpot_pathoplexus_loculus_overview.md) — Pathoplexus / Loculus + 8 peer platforms comparative analysis
- [`docs/jackpot_cdc_dmi_stlt_overview.md`](./docs/jackpot_cdc_dmi_stlt_overview.md) — CDC DMI / North Star + STLT operators + CARE Principles
- [`docs/jackpot_byop_and_eukaryotic_design.md`](./docs/jackpot_byop_and_eukaryotic_design.md) — BYOP infrastructure + eukaryotic pathogen support

## Layer-cake positioning

```text
┌──────────────────────────────────────────────────────────────┐
│  CASE-LEVEL EPIDEMIOLOGY                                     │
│  NBS, MAVEN, Trisano (state-specific)                        │
└────────────────────────────────▲─────────────────────────────┘
                                 │ ECR/ELR via TEFCA
┌────────────────────────────────┴─────────────────────────────┐
│  ELECTRONIC CASE / LAB REPORTING ROUTING (APHL AIMS)         │
└────────────────────────────────▲─────────────────────────────┘
                                 │ HL7 / FHIR
┌────────────────────────────────┴─────────────────────────────┐
│  PUBLIC HEALTH LABORATORY OPERATIONAL SYSTEMS (LIMS)         │
└────────────────────────────────▲─────────────────────────────┘
                                 │ specimen → sequencing
┌────────────────────────────────┴─────────────────────────────┐
│  ★ JACKPOT ★                                                 │
│  Pathogen genomics platform                                  │
└────────────────────────────────▲─────────────────────────────┘
                                 │ pipeline results
┌────────────────────────────────┴─────────────────────────────┐
│  DOWNSTREAM REPOSITORIES + ANALYSIS                          │
│  NCBI Pathogen Detection, GISAID/ENA, Pathoplexus,           │
│  Pathogenwatch, Nextstrain, GenSpectrum                      │
└──────────────────────────────────────────────────────────────┘
```

JACKPOT integrates with these systems; it does not replace them. See
[`docs/jackpot_cdc_dmi_stlt_overview.md §9`](./docs/jackpot_cdc_dmi_stlt_overview.md)
for the detail.

## License

[GNU Affero General Public License v3.0 or later](./LICENSE). The
license choice is strategic, not just legal — it joins JACKPOT to the
European pathogen-genomics open-source cluster (Loculus, GenSpectrum/
LAPIS, SILO) and closes the SaaS loophole that Apache 2.0 leaves
open. See [`spec.md §13`](./spec.md) for the full rationale.

## Contributing

Contribution mechanics, code of conduct, and review expectations live
in `CONTRIBUTING.md` (forthcoming, P0e). Until that lands, the
operating norm is: open an issue, open a PR, follow the conventional-
commit prefixes documented in [`docs/CLAUDE.md`](./docs/CLAUDE.md),
and run `uv run pytest` before requesting review. For substantive
governance or schema-shape questions, see
[`governance/access-grievance-procedure.md`](./governance/access-grievance-procedure.md)
for the right channel.
