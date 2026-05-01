# `jackpot init` CLI — design

**Status:** P0e B.1 design checkpoint. Not yet implemented.
**Author:** P0e session, 2026-05-01.
**Reviewers required before B.2 implementation:** Glen.

## Purpose

`jackpot init` is the operator-bootstrap CLI. It turns a freshly-cloned
`Midnight-Oil-Innovation/jackpot` into a configured deployment for one
of the 7 install scenarios. It is the **single, named, version-
controlled point** at which operator-specific values enter the system,
satisfying Critical Rule 55 (production code is operator-agnostic).

It replaces:

- The deleted `backend/setup/write_files*.py` scaffold scripts (which
  emitted operator-coupled files at install time)
- The hardcoded operator strings in `deploy/helm/jackpot-api/values-staging.yaml`
  (now templated, awaiting `jackpot init` to fill them per-instance)
- The hardcoded `assertion.repository_owner == 'linuxprophet'` WIF
  attribute in `deploy/scripts/bootstrap_project.sh` (now a CLI arg)
- The "edit values.yaml then docker compose up" tribal knowledge in
  the README

## Non-goals

- **Not a deployment orchestrator.** `jackpot init` produces config; it
  does not run `terraform apply`, `helm upgrade`, or `docker compose up`
  on the operator's behalf. Those remain explicit operator actions.
- **Not a secret manager.** It generates secrets locally (JWT signing
  key, etc.) but does not push them to GCP Secret Manager — that's a
  separate `terraform apply` step the operator runs after seeing what
  was generated.
- **Not a continuous-config tool.** Run-once at install. For ongoing
  config drift, operators edit their gitignored local config files
  directly or rerun `jackpot init reconfigure`.

## 1. Command structure

`jackpot init` is a Click subcommand of the existing `jackpot` CLI
(installed via `cli/pyproject.toml` `[project.scripts]`). Subcommand
layout:

```
jackpot init                  # entrypoint — runs detect → configure → bootstrap
jackpot init detect           # ask scenario-detector questions, propose scenario
jackpot init configure        # generate .env.local + values.local.yaml + secrets
jackpot init bootstrap        # apply the generated config to the local stack
jackpot init validate         # run /health smoke tests against the configured stack
jackpot init reconfigure      # rerun configure preserving existing secrets
```

The default `jackpot init` (no subcommand) runs `detect → configure →
bootstrap → validate` in sequence, prompting between each step. Each
subcommand is independently runnable for cases where an operator wants
to skip or rerun a phase.

**Why subcommands rather than a monolithic init?** The 7 scenarios
have different needs. Scenario F (CI) wants `jackpot init detect
--scenario F --non-interactive` and skip everything else. Scenario T
(Tribal) wants the operator to read every prompt carefully. Splitting
the phases lets each scenario use what fits.

## 2. Scenario detector flow (B-STLT-4)

`jackpot init detect` asks a small number of questions and proposes a
scenario. Operators can override the proposal.

### Question set

```
1. Operator type
   [a] Academic researcher / single bioinformatician
   [b] Single public-health organization (no federation, no SaaS)
   [c] Multi-lab agency (state health department, city public health)
   [d] Hosted SaaS provider serving multiple tenants
   [e] Federation member (peers with other JACKPOT instances)
   [f] CI / automated test environment
   [t] Tribal nation, Tribal Epidemiology Center, or Indigenous-data-
       sovereignty deployment
   [?] Help me decide

2. Deployment target
   [1] Laptop / on-prem (Docker Compose; no cloud)
   [2] Cloud single-org (GCP/AWS/Azure managed)
   [3] Cloud multi-tenant (Kubernetes-native, multi-region)

3. Federation participation
   [n] Off — this instance does not peer with others
   [m] Member — receives data from peers; may push data to peers
   [h] Hub — coordinates a federation; routes between members

4. PII handling defaults
   [d] Full DLP — Cloud DLP scanner runs on every metadata write
   [s] Scrubber-only — strip identifiers at ingest, no DLP scanning
   [o] Off — operator certifies they do not handle PII (rare; CI/research only)

5. Authentication method
   [g] Google OAuth (recommended for cloud deployments)
   [s] SSO (Okta, Auth0; production multi-tenant only)
   [m] Mock auth — single dev user (laptop / CI only)
```

### Scenario inference

Detector applies a deterministic mapping from `(operator_type,
deployment_target, federation, auth)` to a scenario:

| If operator answers... | Scenario inferred |
|---|---|
| operator=a, target=1, auth=m | A (laptop) |
| operator=b, target=2, auth=g | B (single-org cloud) |
| operator=c, target=2 or 3, auth=g | C (multi-lab agency) |
| operator=d, target=3, auth=s | D (hosted SaaS) |
| operator=e, federation in {m, h} | E (federation member) |
| operator=f, auth=m, dlp=o | F (CI test) |
| operator=t (any combination) | T (Tribal-sovereignty) |

If answers are inconsistent (e.g. "tribal" + "SaaS multi-tenant" — a
cross-tenant Tribal hub is unusual but not impossible), the detector
proposes the closest match and asks the operator to confirm or
override.

Detector outputs to stdout: the inferred scenario, the question-by-
question answer log, and a one-paragraph rationale. The operator can
accept, override (`--scenario X` flag), or rerun with different
answers.

## 3. Scenario → defaults mapping

Each scenario maps to a `ScenarioDefaults` Pydantic model with named
fields for every install-time knob. The full registry lives at
`cli/jackpot/init/scenarios.py`. Sketch:

```python
class ScenarioDefaults(BaseModel):
    # — Backend behaviour —
    deletion_on_request: bool         # CARE Authority-to-Control
    auto_publish_to_insdc: bool       # NCBI/GenBank auto-submission
    federation_enabled: bool
    dlp_enabled: bool
    scheduler_enabled: bool

    # — Compose / Helm shape —
    compose_profile: Literal["laptop", "single-org", "multi-tenant", "ci"]
    replica_count: int
    storage_backend: Literal["local", "minio", "gcs", "s3"]
    pipeline_executor: Literal["local", "gcp_batch", "aws_batch", "k8s_jobs"]

    # — Auth shape —
    auth_method: Literal["mock", "oauth", "sso"]
    oauth_provider: Literal["google", None]

    # — Database —
    database_engine: Literal["postgres-local", "cloud-sql", "rds-postgres"]
    database_pitr_enabled: bool
    database_backup_retention_days: int

    # — Federation —
    federation_role: Literal["off", "member", "hub", None]
    federation_peers: list[str]       # initial peer list (URLs)

    # — Governance flags —
    care_principles_enforced: bool    # extra audit-log events
    consent_workflow_enabled: bool

    # — Operator metadata (these are ASKED, not defaulted) —
    host_organization_name: str       # required at install time
    host_organization_email: str      # required at install time
    deployment_url: str               # for cloud scenarios
    cors_origins: list[str]
```

### Scenario A (laptop) defaults

```python
ScenarioDefaults(
    deletion_on_request=False,        # local-only; no consent flow
    auto_publish_to_insdc=False,
    federation_enabled=False,
    dlp_enabled=False,
    scheduler_enabled=True,
    compose_profile="laptop",
    replica_count=1,
    storage_backend="minio",
    pipeline_executor="local",
    auth_method="mock",
    oauth_provider=None,
    database_engine="postgres-local",
    database_pitr_enabled=False,
    database_backup_retention_days=0,
    federation_role="off",
    federation_peers=[],
    care_principles_enforced=False,
    consent_workflow_enabled=False,
)
```

### Scenario B (single-org cloud) defaults

Same as A but: `replica_count=2`, `storage_backend="gcs"`,
`pipeline_executor="gcp_batch"`, `auth_method="oauth"`,
`oauth_provider="google"`, `database_engine="cloud-sql"`,
`database_pitr_enabled=True`, `database_backup_retention_days=14`,
`dlp_enabled=True`.

### Scenario C (multi-lab agency) defaults

Same as B but: `replica_count=3`, `database_backup_retention_days=30`,
prompts for additional `lab_count` and `default_lab_director_email`
(seed data the operator can later edit).

### Scenario D (hosted SaaS) defaults

Same as C but: `compose_profile="multi-tenant"`, `auth_method="sso"`,
multi-tenancy middleware enabled (P0c gate must be lifted before this
scenario is bootstrap-able), `replica_count=5`, billing module enabled
(once 7 stub routers from review_log item 17 ship).

### Scenario E (federation member) defaults

Same as B (or C if multi-lab) but: `federation_enabled=True`,
`federation_role="member"` (operator chooses "hub" if running a TEC),
prompts for initial peer list, generates federation-peer keypair.

### Scenario F (CI test) defaults

```python
ScenarioDefaults(
    deletion_on_request=False,
    auto_publish_to_insdc=False,
    federation_enabled=False,
    dlp_enabled=False,
    scheduler_enabled=False,         # no APScheduler in CI
    compose_profile="ci",
    replica_count=1,
    storage_backend="local",         # filesystem; no MinIO container needed
    pipeline_executor="local",
    auth_method="mock",
    oauth_provider=None,
    database_engine="postgres-local",
    database_pitr_enabled=False,
    database_backup_retention_days=0,
    federation_role="off",
    federation_peers=[],
    care_principles_enforced=False,
    consent_workflow_enabled=False,
    host_organization_name="CI Test Org",
    host_organization_email="ci@example.org",
    deployment_url="http://localhost:8000",
    cors_origins=["http://localhost:8501"],
)
```

CI deploy must work with `jackpot init --scenario F --non-interactive`
and zero further input. This is the reproducible-tests-from-fresh-
clone path.

### Scenario T (Tribal-sovereignty) defaults

```python
ScenarioDefaults(
    deletion_on_request=True,         # CARE Authority-to-Control — REQUIRED
    auto_publish_to_insdc=False,      # explicit per-sample approval only
    federation_enabled=False,         # off by default; opt-in only
    dlp_enabled=True,                 # PII handling on
    scheduler_enabled=True,
    compose_profile="laptop",         # or "single-org"; operator picks
    replica_count=1,
    storage_backend="local",          # default to on-prem; operator can switch
    pipeline_executor="local",
    auth_method="oauth",
    oauth_provider="google",
    database_engine="postgres-local",
    database_pitr_enabled=True,       # data integrity matters
    database_backup_retention_days=30,
    federation_role="off",            # operator opts in if applicable
    federation_peers=[],
    care_principles_enforced=True,    # extra audit-log events for consent
    consent_workflow_enabled=True,
)
```

The Scenario T defaults specifically address the four CARE Principles:
- **C**ollective benefit: federation off-by-default until operator
  decides who they trust
- **A**uthority to control: `deletion_on_request=True` enables the
  tombstone-and-vacuum path described in `jackpot_cdc_dmi_stlt_overview.md` §7
- **R**esponsibility: extra audit log events tag every consent grant /
  withdrawal / derivation
- **E**thics: no auto-publish to INSDC; explicit per-sample approval

## 4. Output artifacts

`jackpot init configure` writes to a per-instance directory rather than
overwriting repo files. Default path: `instances/<instance-name>/`
where instance-name is `local` for laptop, `staging`/`production` for
cloud, or operator-supplied via `--instance-name`.

```
instances/<name>/
├── jackpot.toml            Resolved scenario + operator config
├── .env.local              Local-dev env vars (gitignored)
├── values.local.yaml       Helm values overrides (gitignored)
├── seed.sql                Operator-customized seed data (DROP+REINSERT after alembic)
├── secrets/
│   ├── jwt-signing-key     Generated 32-byte hex
│   └── README.md           Lists what other secrets the operator must
│                           create in Secret Manager / vault
└── README.md               How to use this instance directory
```

`instances/` itself is in `.gitignore`. Operators commit their own
instance configs to a private branch or out-of-band repo.

For Scenario F (CI), `jackpot init --scenario F` writes to
`instances/ci/` and the CI workflow checks it in (so CI runs are
reproducible). Operators should NOT commit `instances/local/` or
`instances/staging/`.

## 5. Rerun semantics

`jackpot init` detects existing `instances/<name>/jackpot.toml` and
offers three paths:

1. **Reuse** (default if non-interactive): exit 0, do nothing.
2. **Reconfigure**: rerun `configure` preserving the existing
   `secrets/` directory and the operator-supplied identity values
   (host_organization_name, deployment_url). Useful for changing
   replica counts or adding federation peers.
3. **Reset**: delete `instances/<name>/` and start fresh. Requires an
   explicit `--reset --i-mean-it` flag because secrets get regenerated.

`jackpot init reconfigure` skips the detector and goes straight to the
configure phase, reading scenario from the existing `jackpot.toml`.

## 6. Scenario T defaults — design rationale

The sovereignty-aware defaults must be *defaults*, not options the
operator has to discover. A Tribal IT staffer running `jackpot init`
should not need to read the CARE Principles primer to enable basic
consent-aware behaviour — it should be on out of the box.

Specifically:

- `deletion_on_request=True` triggers the schema column
  `samples.deletion_status` (added in P0b/c) and enables the tombstone-
  and-vacuum job. **Note: the schema column doesn't yet exist** — P0b
  must land before Scenario T is fully bootstrap-able. `jackpot init
  --scenario T` should warn that "Tribal sovereignty deletion paths
  require P0b schema additions; some features will be unavailable
  until the schema migration runs."
- `auto_publish_to_insdc=False` requires the operator to explicitly
  approve each sample for INSDC submission. Adds a column to the
  pre-publish UI flow.
- `federation_enabled=False` keeps the federation router unavailable
  until the operator opts in via `jackpot init reconfigure --enable-
  federation`.
- `consent_workflow_enabled=True` adds a "consent grant" record at
  sample creation (existing user-supplied), and a "consent withdrawal"
  workflow that triggers the deletion path.

These defaults are operator-overrideable, but the defaults match the
guidance in `governance/care-principles-and-tribal-data-sovereignty.md`
and the design in `jackpot_cdc_dmi_stlt_overview.md` §7.

## 7. Scenario F (CI test) — design rationale

Must be runnable by GitHub Actions with one command and no operator
input. Specifically:

```bash
git clone https://github.com/Midnight-Oil-Innovation/jackpot
cd jackpot
uv sync
uv run jackpot init --scenario F --non-interactive
docker compose up -d
uv run pytest
```

That's the entire CI bootstrap. The `instances/ci/` directory ships in
the repo (not gitignored for the `ci/` subdirectory) so CI is
reproducible; the rest of `instances/` is gitignored.

The Scenario F defaults turn off everything the test suite doesn't
need:
- No DLP scanning (slow, requires GCP creds)
- No NCBI/GISAID submission paths (out of scope for unit + integration
  tests)
- No federation
- No scheduler (tests control time via freezegun)
- Filesystem storage (no MinIO container — fewer Docker layers)
- Mock auth (no OAuth flow needed)

## 8. Implementation skeleton

`cli/jackpot/init/` (new package):

```
cli/jackpot/init/
├── __init__.py
├── scenarios.py        ScenarioDefaults Pydantic model + 7-scenario registry
├── detector.py         Scenario detector (B-STLT-4): question logic
├── writers.py          Emits .env.local, values.local.yaml, seed.sql
├── secrets.py          Generates JWT signing key + lists vault entries needed
├── validator.py        Runs post-bootstrap /health + sanity checks
└── prompts.py          Reusable click.prompt wrappers with consistent UX
```

`cli/jackpot/cli/init.py` (new module):

```python
import click
from jackpot.init import scenarios, detector, writers, secrets, validator

@click.group()
def init():
    """Bootstrap a JACKPOT instance for a chosen install scenario."""

@init.command()
@click.option("--scenario", type=click.Choice([s.code for s in scenarios.ALL]))
@click.option("--non-interactive", is_flag=True)
@click.option("--instance-name", default="local")
def detect_cmd(scenario, non_interactive, instance_name):
    ...

@init.command("configure")
def configure_cmd(...):
    ...

# etc.

# Wired up from cli/jackpot/cli/main.py:
# cli.add_command(init)
```

## 9. Tests

Each scenario gets at least one end-to-end test that runs `jackpot
init --scenario X --non-interactive` and asserts:

- `instances/X/jackpot.toml` exists with the right scenario marker
- `instances/X/.env.local` exists and contains all env vars the
  scenario requires (no hardcoded fallback values)
- `instances/X/values.local.yaml` exists and contains operator-
  specific values from the scenario defaults

For the bootstrap path (Scenario A and F), additional tests:
- `docker compose up -d` succeeds (CI only — uses testcontainers
  pattern from existing `tests/conftest.py`)
- `curl http://localhost:8000/health` returns 200
- The seeded admin user can log in (mock auth)

The B-STLT-4 detector gets unit tests for each branch of its question
logic (trial answers → expected scenario inference).

Coverage target for `cli/jackpot/init/`: 85%+.

## 10. Documentation

After implementation:

- New: `docs/install/quickstart.md` — "your first 10 minutes with
  JACKPOT" using `jackpot init --scenario A`
- Update: each `docs/deploy/stlt/*.md` to reference `jackpot init
  --scenario <X>` as the standard install path
- Update: `README.md` "Development" section to use `jackpot init`
  rather than the manual edit-values + docker compose dance
- New: `cli/jackpot/init/README.md` developer-facing docs for adding a
  new scenario or a new question to the detector

## 11. Phasing within P0e

`jackpot init` lands in this order:

1. **B.2.1** — `cli/jackpot/init/scenarios.py` registry only. No CLI
   wiring yet. Tests for the 7-scenario data structure.
2. **B.2.2** — `cli/jackpot/init/detector.py` + `cli/jackpot/cli/init.py
   detect_cmd`. The CLI starts to do something visible.
3. **B.2.3** — `cli/jackpot/init/writers.py` + `configure_cmd`.
   Operators can now generate config files.
4. **B.2.4** — `cli/jackpot/init/secrets.py` + secret generation.
5. **B.2.5** — `cli/jackpot/init/validator.py` + `bootstrap_cmd` +
   `validate_cmd`. End-to-end bootstrap works for Scenario A.
6. **B.2.6** — Wire `bootstrap_cmd` for Scenarios B, C, F. Skip D
   (gated on P0c multi-tenancy), E (gated on federation router which
   doesn't exist), T (gated on P0b sovereignty schema).
7. **B.3** — Tests.
8. **B.4** — Documentation.

## 12. Open questions for review

The following are unresolved design points that need Glen's input
before implementation begins:

1. **Instance directory location.** `instances/<name>/` at repo root,
   or `~/.jackpot/instances/<name>/` (XDG-style)? Repo root is more
   discoverable and lets the CI path work cleanly; XDG is more
   conventional for CLI tools.

2. **Compose profile mechanism.** Does the existing `docker-compose.yml`
   need a `profiles:` section so we can `docker compose --profile
   laptop up` vs `--profile ci up`? Or do we generate per-scenario
   compose files in `instances/<name>/docker-compose.yml`? Generating
   feels closer to the per-instance config pattern but means the canonical
   compose file diverges across scenarios.

3. **Reading from existing values-staging.yaml.** Phase A landed the
   workflow plumbing operator vars from `${{ vars.* }}` for staging.
   Should `jackpot init configure` understand existing GitHub Actions
   environment vars (read via `gh api` or required vars file)? Or is
   the operator expected to type them in fresh during init? Type-in is
   simpler; gh-API integration is more powerful but pulls in a `gh`
   CLI dependency.

4. **The `instances/ci/` commit-or-don't decision.** If `instances/ci/`
   ships in the repo, contributors get reproducible CI. But it pins
   the CI scenario to F forever; switching CI to a different scenario
   later means a repo edit. The flexibility may not matter — F is the
   right CI scenario indefinitely.

5. **Federation peer keypair generation.** Scenario E needs operator
   keypairs for signing federation messages. Generated locally (less
   trust, easier ops) or via a centralized federation-CA (more trust,
   harder ops)? Could defer to a Phase E follow-up but Scenario E's
   bootstrap path becomes incomplete without it.

6. **Migration → seed data interaction.** Per A.3, the baseline
   migration now seeds operator-agnostic Example Org / Example Lab.
   Should `jackpot init` immediately overwrite those with operator-
   specific values via UPDATE, or generate `seed.sql` for the
   operator to apply via `psql`, or just leave the example values in
   place and let the operator rename via the UI later? The "leave it
   for UI" path is simplest for operators but means the seeded admin
   user is `admin@example.org` until they rename.

Glen's call on each before B.2 begins.
