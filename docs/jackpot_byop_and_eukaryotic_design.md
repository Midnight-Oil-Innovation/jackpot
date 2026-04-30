# JACKPOT — BYOP and Eukaryotic Pathogen Pipelines

**Status:** Design document · 2026-04-29
**Scope:** (1) Multi-engine BYOP architecture (Nextflow, Snakemake, WDL, manifest-wrapped scripts) sourced from public/private Git, tar.gz uploads, or Docker images, with static-validation + sandbox-dry-run gating. (2) Full-parity eukaryotic pathogen support across 8 priority pathogen groups — schema, parsers, pipelines, dashboards.

---

## 0. Executive summary

BYOP today is "register a Nextflow pipeline URL, hope it runs." The redesign turns it into a real platform feature: four supported engines, four source types, two-stage gating (static checks then sandbox dry-run), and a uniform `pipeline_results` shape that downstream code doesn't have to special-case by engine.

The eukaryotic additions exercise BYOP as the first set of non-trivial pipelines that aren't already in the curated zoo. They land alongside the existing bacterial/viral coverage with the same depth: schema fields, organism enum entries, parsers per pipeline, dashboard widgets, AMR-equivalent (drug-resistance) tracking where biology supports it.

The two halves combine into a coherent "JACKPOT does everything bacterial/viral plus everything eukaryotic-parasitic plus arbitrary user pipelines" story, all with the same `pipeline_results` ingestion, the same audit log, the same DLP and scrubber gates, and the same federation rules.

---

## Part I — BYOP architecture

## 1. The four engines

### 1.1 Coverage matrix

| Engine | Manifest format | Container model | Resume support | Maturity in public health |
|---|---|---|---|---|
| **Nextflow** | `.nf` scripts + `nextflow.config` + `nextflow_schema.json` | Per-process containers | Native (`-resume`) | Highest — nf-core has 100+ pipelines |
| **Snakemake** | `Snakefile` + `config.yaml` + per-rule conda/container | Per-rule containers or conda envs | Native (`--rerun-incomplete`) | High — Loculus uses it for ingest |
| **WDL** | `workflow.wdl` + `inputs.json` | Per-task `runtime { docker }` | Cromwell engine: yes, miniwdl: limited | Lower in pathogen genomics; common in clinical |
| **Manifest-wrapped scripts** | `jackpot-pipeline.yaml` + Bash/Python scripts | One Docker image declared in manifest | None — restart-from-scratch | New — JACKPOT-specific |

The fourth engine (manifest-wrapped scripts) needs its own definition since it doesn't exist yet — see §3.

### 1.2 Why all four

Different communities default to different engines. Forcing everyone onto Nextflow excludes Snakemake-native shops (a lot of academic labs in Europe), WDL-native shops (Broad Institute and clinical genomics shops), and the long tail of "I have a Bash script that works, I don't want to learn a workflow language." Accepting all four means JACKPOT is the integration layer, not the workflow-engine police.

### 1.3 Common abstractions across engines

Despite different syntaxes, all four engines share the same conceptual lifecycle:

```text
register → validate → dry-run → activate → launch (per sample) →
events stream in → results parsed → results stored
```

JACKPOT provides the validation, dry-run, launch, event collection, parsing, and storage. The pipeline author provides the workflow definition and a `pipeline_results.schema.json` that tells JACKPOT how to interpret outputs.

---

## 2. The pipeline manifest — `jackpot-pipeline.yaml`

Every BYOP pipeline, regardless of engine, is required to ship a `jackpot-pipeline.yaml` at the repository root (or tar.gz top level, or as a sidecar to a Docker image reference). This is JACKPOT's contract — engine-specific workflow files are read as needed but the manifest is the source of truth for everything JACKPOT needs to know.

### 2.1 Manifest schema

```yaml
# jackpot-pipeline.yaml
api_version: jackpot.io/v1                  # required; must be jackpot.io/v1
kind: Pipeline                               # required

metadata:
  name: my-tb-typer                          # required; lowercase-hyphen-only
  display_name: "M. tuberculosis WGS Typer"  # required; human-readable
  version: "1.2.3"                           # required; semver
  description: |                             # required; markdown supported
    Lineage assignment, drug-resistance prediction, and SNP-distance
    nearest-neighbour calling for Mycobacterium tuberculosis isolates.
  authors:                                   # required; min 1
    - name: "Jane Doe"
      email: "jane@example.org"              # optional
      orcid: "0000-0001-2345-6789"           # optional
  license: "AGPL-3.0"                        # required; SPDX identifier
  homepage: "https://github.com/example/my-tb-typer"  # optional
  citation: |                                # optional but recommended
    Doe J et al. (2026). Title. J Open Source Software.
    DOI: 10.21105/joss.NNNNN

engine:
  type: nextflow                             # required: nextflow|snakemake|wdl|manifest
  version: ">=24.04.0"                       # required; engine version constraint
  entrypoint: main.nf                        # required path within the pipeline
  config: nextflow.config                    # optional, engine-specific
  schema: nextflow_schema.json               # optional, for parameter validation

# Organism applicability — JACKPOT enforces this
applicability:
  organism_names:                            # required; from OrganismNameEnum
    - "Mycobacterium tuberculosis"
    - "Mycobacterium tuberculosis complex"
  source_types:                              # required; from SourceTypeEnum
    - human
    - livestock
  data_types:                                # required; what the pipeline consumes
    - paired_end_short_read                  # FASTQ R1/R2
    - long_read                              # ONT/PacBio
    - assembly                               # FASTA
  surveillance_relevant_required: false      # if true, only surveillance-relevant samples can launch this

# Resource declarations — used for sandbox dry-run sizing and launch quota
resources:
  cpu_min: 4                                 # required; minimum CPUs the pipeline needs
  cpu_max: 32                                # optional; ceiling — pipeline won't benefit beyond this
  memory_gb_min: 16                          # required
  memory_gb_max: 64                          # optional
  storage_gb_estimate: 20                    # required; per-sample working storage
  walltime_minutes_estimate: 90              # required; typical per-sample runtime
  gpu_required: false                        # required
  internet_required: false                   # required; if true, pipeline pulls reference at runtime
                                             # (Scenario T defaults reject internet_required=true)

# Reference data declarations
reference_data:
  bundled: false                             # required; true = ships with pipeline, false = pulled at runtime
  sources:                                   # required if bundled=false
    - name: "M. tuberculosis H37Rv"
      url: "https://ftp.ensembl.org/pub/.../H37Rv.fa.gz"
      checksum: "sha256:abc123..."           # required for non-bundled; integrity check
      cached_locally_at: "/refs/Mtb/H37Rv.fa.gz"  # JACKPOT-internal cache path

# Container declarations
containers:
  - image: "quay.io/biocontainers/tb-profiler:5.0.1"
    digest: "sha256:def456..."               # optional but strongly recommended
  - image: "quay.io/biocontainers/snippy:4.6.0"
    digest: "sha256:789abc..."

# Inputs — what JACKPOT passes to the pipeline at launch
inputs:
  - name: sample_id                          # required for every pipeline
    type: string
    source: jackpot.sample.id                # tells JACKPOT how to populate
  - name: r1_fastq
    type: file
    source: jackpot.sample.files.r1
    required_when: "data_type == 'paired_end_short_read'"
  - name: r2_fastq
    type: file
    source: jackpot.sample.files.r2
    required_when: "data_type == 'paired_end_short_read'"
  - name: assembly_fasta
    type: file
    source: jackpot.sample.files.assembly
    required_when: "data_type == 'assembly'"

# Outputs — what JACKPOT expects to ingest
outputs:
  results_directory: "${result_uri}/"        # required; URI prefix for all outputs
  results_schema: results.schema.json        # required path to the pipeline_results JSON Schema
  primary_result_file: "tb_profiler.results.json"  # required; the file the parser will read
  multiqc_report: "multiqc_report.html"      # optional; standard pattern
  pipeline_results_parser: "tb_profiler_v5"  # required; references parser registered in JACKPOT

# Permissions — what JACKPOT capabilities the pipeline needs
permissions:
  can_read_metadata: true                    # default true; needs sample metadata
  can_write_files_to:                        # required; JACKPOT enforces this
    - "${result_uri}/"
  can_call_external_apis:                    # default empty
    - "https://api.tbprofiler.org/lineages"  # explicit allowlist
  can_use_gpu: false                         # default false

# Cost estimation (advisory only)
cost:
  cpu_cost_per_run_usd: 0.40                 # operator-configurable per cloud
  storage_cost_per_run_usd: 0.05
  estimated_total_per_sample_usd: 0.45
```

### 2.2 What JACKPOT does with each section

| Section | JACKPOT use |
|---|---|
| `metadata` | Pipeline catalog UI; audit log; citation generation |
| `engine` | Selects launcher (`backend/services/pipeline_launcher.py` dispatches by engine type) |
| `applicability` | Filters which samples can launch the pipeline; UI hides incompatible pipelines |
| `resources` | Sandbox dry-run sizing; per-instance launch quota enforcement |
| `reference_data` | Pre-pull and cache references; integrity check via checksum |
| `containers` | Pre-pull images; digest-pinning enforcement at launch |
| `inputs` | Populates engine-specific input formats (Nextflow params, Snakemake config, WDL inputs.json) |
| `outputs` | Parser registration; result-file location; MultiQC integration |
| `permissions` | Sandbox isolation; egress allowlist; GPU node selection |
| `cost` | Operator-facing cost estimation in launch UI |

### 2.3 Schema location

Stored in the JACKPOT repo under `schema/byop-pipeline-manifest.schema.json` — a JSON Schema file that's checked into version control and used by the static validator (§5.2).

---

## 3. Engine-specific notes

### 3.1 Nextflow (existing path, hardened)

Today's BYOP register-a-Nextflow-URL flow is closest to the new design. Changes required:

- The `nextflow_schema.json` becomes optional metadata, not the manifest. The new `jackpot-pipeline.yaml` is required.
- The pipeline's existing `nextflow_schema.json` is still consulted for parameter introspection — JACKPOT auto-populates the launch UI's parameter form from it.
- `-weblog` flag is auto-injected at launch by JACKPOT, pointing at `/api/v1/pipelines/events`.
- Resume support is enabled by default (`-resume` flag with a JACKPOT-managed work directory in operator-controlled storage).

### 3.2 Snakemake

Snakemake's idioms differ from Nextflow's:

- Entry point is a `Snakefile` rather than a `main.nf`.
- Configuration is `config.yaml` (YAML, not Groovy DSL).
- Per-rule containers via `singularity:` or `container:` directive; per-rule conda envs via `conda:` directive. JACKPOT's launcher resolves both — preferring container over conda when both are present.
- No native event/weblog system. JACKPOT emits events from a wrapping launcher script that polls the Snakemake `--report` JSON and streams events to `/api/v1/pipelines/events` on a 30-second cadence plus on terminal state.
- Resume via `--rerun-incomplete --keep-going` with JACKPOT-managed work directory.

Implementation lives in `backend/services/snakemake_launcher.py`.

### 3.3 WDL

WDL is the workflow language for Cromwell (Broad) and miniwdl. Pattern:

- Entry point is a `.wdl` file with one `workflow` block; multiple `task` blocks each declaring `runtime { docker: "..." }`.
- Inputs are JSON (`inputs.json`), populated by JACKPOT from the manifest's `inputs` declarations.
- JACKPOT supports both Cromwell (heavyweight, full features) and miniwdl (lightweight, simpler) as launcher backends. Operator configures which is preferred via `JACKPOT_WDL_BACKEND` env var.
- Cromwell's metadata API provides events JACKPOT can poll. miniwdl emits structured logs JACKPOT parses.

Implementation lives in `backend/services/wdl_launcher.py`.

### 3.4 Manifest-wrapped scripts

The fourth engine is JACKPOT-specific. The use case: someone has a working Bash or Python script and wants it in the platform without learning a workflow language.

Manifest specifies:

```yaml
engine:
  type: manifest
  version: "1.0"                 # JACKPOT manifest engine version
  entrypoint: run.sh             # the script to invoke
  shell: bash                    # bash | python | sh
  args:                          # how arguments are passed
    - "--sample-id"
    - "${inputs.sample_id}"
    - "--r1"
    - "${inputs.r1_fastq}"
    - "--r2"
    - "${inputs.r2_fastq}"
    - "--out"
    - "${outputs.results_directory}"
```

The script runs inside a single declared container (the first one in `containers:`). No multi-step, no parallelization, no resume. Restart-from-scratch on failure.

Why include this engine: the fastest possible BYOP path for someone with a working script. They're trading workflow-engine features (parallelization, resume, container-per-step) for simplicity. The manifest engine is ideal for:

- Single-step pipelines (run one tool, write one output)
- "Glue" pipelines that wrap a single command-line tool
- Initial prototypes that may later get rewritten as Nextflow/Snakemake/WDL

JACKPOT's launcher (`backend/services/manifest_launcher.py`) is essentially a Docker run wrapper with structured timing and exit-code event emission.

### 3.5 What JACKPOT *won't* do for any engine

To keep the platform tractable:

- **No engine version translation.** Operator must run a recent enough engine version. JACKPOT errors on `engine.version` mismatch.
- **No automatic conda environment building from `requirements.txt`.** Operators must use containers or pre-built conda envs.
- **No DAG visualization in JACKPOT UI.** Engine-specific tools (Nextflow tower, Snakemake report, Cromwell timing diagram) handle this; JACKPOT just links to them.
- **No cross-engine pipeline composition.** A pipeline is one engine, top to bottom.

---

## 4. The four source types

### 4.1 Public Git URL

```yaml
# UI: paste a URL
source:
  type: git
  url: https://github.com/example/my-tb-typer
  ref: v1.2.3                # tag, branch, or commit SHA
```

JACKPOT does `git clone --depth 1 --branch <ref>` into a working directory, reads the manifest, validates, runs sandbox dry-run, registers.

Reference handling: any `ref` accepted by Git. Tags strongly preferred. Branch names accepted but flagged in UI ("you're tracking a moving branch — pin to a tag for reproducibility"). Commit SHAs accepted and treated as immutable.

### 4.2 Private Git with deploy keys

```yaml
source:
  type: git
  url: git@github.com:private/my-tb-typer.git
  ref: v1.2.3
  deploy_key_secret: gcp-sm://jackpot-staging/byop-deploy-key-tb-typer
```

JACKPOT supports per-pipeline deploy keys stored in operator's Secret Manager (GCP SM, AWS Secrets, Azure Key Vault, MinIO encrypted blob). Keys never appear in JACKPOT's database; they're referenced by URI and resolved at clone time.

UI flow for adding a private pipeline:

1. User pastes Git URL + ref
2. JACKPOT generates an SSH keypair locally (in the user's browser session, via WebCrypto)
3. Public key displayed for the user to add as a deploy key on their repo
4. Private key uploaded to operator's secret manager via JACKPOT's secret-write API (audited)
5. JACKPOT clones using the deploy key

### 4.3 Uploaded tar.gz

```yaml
source:
  type: tarball
  uploaded_uri: gs://jackpot-byop-uploads/abc123-my-tb-typer-1.2.3.tar.gz
  sha256: "deadbeef..."
```

User uploads via the standard JACKPOT signed-URL ingest path (same machinery as sample uploads). Tarball is checksummed, extracted to a working directory, manifest read, validation runs.

Tarball constraints (enforced):

- Must be `.tar.gz` (no zip, no bare tar, no 7z)
- Maximum 500 MB compressed (operator-configurable)
- Must contain `jackpot-pipeline.yaml` at the top level
- No symlinks pointing outside the tarball
- No setuid/setgid bits on extracted files

### 4.4 Docker image reference

```yaml
source:
  type: docker
  image: "quay.io/example/my-tb-typer-bundle:1.2.3"
  digest: "sha256:abc..."          # required for docker source
  manifest_path: "/jackpot-pipeline.yaml"  # path inside the image
```

For pre-built pipeline containers. JACKPOT pulls the image, copies out the manifest from the declared path, validates. The same image is then used as the pipeline's primary container at launch.

This source type is restricted to the `manifest` engine (single-container pipelines) — you can't ship a Nextflow pipeline with multiple per-step containers as a single Docker image.

### 4.5 Source-type comparison

| Source | Reproducibility | Privacy | Update path | Best for |
|---|---|---|---|---|
| Public Git | High (with tag) | None | Re-register at new ref | Open-source pipelines |
| Private Git | High (with tag) | High | Re-register at new ref | Internal lab pipelines |
| Uploaded tar.gz | High (immutable) | High | Upload new version | Air-gapped or sensitive pipelines |
| Docker image | Highest (digest-pinned) | High | Push new tag | Single-step "glue" pipelines |

---

## 5. The two-stage gating system

### 5.1 Why two stages

A trust-the-user model lets a malicious or buggy pipeline read random files, exfiltrate data, or wedge a node. A static-checks-only model misses runtime problems (the manifest claims `cpu_min: 4` but the actual workflow OOMs at 32 GB). A sandbox-only model misses easy structural bugs that should fail in milliseconds.

Two-stage gating runs static checks in seconds, then a sandbox dry-run in minutes. Both must pass before the pipeline activates.

### 5.2 Stage 1 — static validation

Lives in `backend/services/byop_validator.py`. Runs immediately after source resolution, before any container pull.

#### 5.2a Manifest schema validation

- Manifest parses as YAML
- Validates against `schema/byop-pipeline-manifest.schema.json`
- All required fields present
- All enums (engine.type, applicability.source_types, etc.) match valid values

#### 5.2b Engine-specific structural checks

| Check | Nextflow | Snakemake | WDL | Manifest |
|---|---|---|---|---|
| Entrypoint file exists | `main.nf` | `Snakefile` | `*.wdl` | Script file |
| Engine syntax parses | `nextflow inspect` | `snakemake --lint --dry-run -n` | `miniwdl check` | bash -n / python -c |
| Containers referenced | All `container` directives | All `singularity:` / `container:` | All `runtime { docker }` | First in `containers[]` |
| `nextflow_schema.json` valid | Optional but checked if present | N/A | N/A | N/A |

#### 5.2c Container resolution

Every container in `containers:` is checked:

- Image registry is reachable (operator-allowlisted registries: docker.io, quay.io, ghcr.io, gcr.io, public.ecr.aws, plus operator-configured private registries)
- Image tag exists
- If `digest:` is provided, it matches the resolved manifest digest
- Image is pullable with the operator's configured pull credentials

Operator can block specific registries via `JACKPOT_BYOP_ALLOWED_REGISTRIES` env var. Default allowlist excludes private Docker Hub repos (rate-limit risk) and unknown registries.

#### 5.2d Reference data resolution

For `bundled: false` references:

- URL is reachable (HTTP HEAD request)
- Checksum (`sha256:`) is present
- If reference data is already in JACKPOT's cache (under `${JACKPOT_REFDATA_CACHE}/`), the cached checksum matches

#### 5.2e License compatibility

Manifest declares `license:` as SPDX identifier. JACKPOT checks against the operator's allowed-license policy:

- Operator default: any OSI-approved license
- Scenario T default: AGPL-3.0, GPL-3.0, MIT, Apache-2.0 (avoiding licenses with sovereignty issues)
- Operator-configurable via `JACKPOT_BYOP_ALLOWED_LICENSES`

#### 5.2f Permissions sanity

- `permissions.can_call_external_apis` is checked against operator's egress allowlist; blocked URLs cause registration failure
- `permissions.can_use_gpu: true` is rejected if the operator's deployment has no GPU nodes
- `resources.internet_required: true` is rejected on Scenario T deployments (sovereignty default)

#### 5.2g Static stage outcome

- Pass: pipeline moves to Stage 2 (sandbox dry-run)
- Fail: registration rejected with structured error pointing to the failing field

### 5.3 Stage 2 — sandbox dry-run

Lives in `backend/services/byop_sandbox.py`. Runs after Stage 1 passes.

#### 5.3a What "dry-run" means per engine

| Engine | Dry-run mechanic |
|---|---|
| Nextflow | `nextflow run <entrypoint> -profile test --outdir <sandbox> -stub-run` |
| Snakemake | `snakemake --use-conda --use-singularity -n --cores 1 --config <test-inputs>` |
| WDL | `miniwdl run --dir <sandbox> --input test_inputs.json --task-only-resources <entrypoint>` (or Cromwell with similar dry-run flags) |
| Manifest | Run the script with `JACKPOT_DRY_RUN=1` env var; pipeline author checks this in their script and skips real work. Falls back to running with a 60-second hard timeout if not honored. |

#### 5.3b Sandbox isolation

The dry-run executes in an isolated environment:

- Dedicated Kubernetes namespace (`jackpot-byop-sandbox-<pipeline-id>`) for cloud deployments
- Dedicated Docker network (`jackpot-byop-<pipeline-id>`) for laptop/local deployments
- Egress restricted to operator-declared allowlist
- Filesystem restricted to sandbox working directory
- No access to JACKPOT's database, secrets, or sample storage
- 5-minute hard wall-clock timeout (configurable via `JACKPOT_BYOP_SANDBOX_TIMEOUT_SECONDS`)
- Resource caps: 2 CPU, 4 GB RAM, 10 GB storage (the dry-run isn't supposed to do real work)

The sandbox is *more restrictive* than a real pipeline run because it's untrusted code being evaluated. Once a pipeline is activated, real runs get the resources declared in `manifest.resources`.

#### 5.3c Test inputs

Each engine type ships with a small synthetic test input that JACKPOT provides:

- 10K paired-end FASTQ reads simulated from a generic genome
- 1K-base FASTA assembly
- Minimal metadata for the sample (organism = first value in `applicability.organism_names`)

Test inputs live in `backend/test_data/byop_sandbox/` and are mounted into the dry-run sandbox.

#### 5.3d What gets validated

- Pipeline starts without error
- Pipeline reads its declared inputs
- Pipeline writes to its declared output directory
- Pipeline produces a parseable `primary_result_file` (matches `outputs.results_schema`)
- No filesystem writes outside `${result_uri}/`
- No network calls outside `permissions.can_call_external_apis`
- Exit code 0
- Total walltime under operator's threshold (`JACKPOT_BYOP_SANDBOX_TIMEOUT_SECONDS`)

#### 5.3e Sandbox stage outcome

- Pass: pipeline activates and appears in the launchable catalog
- Fail: registration rejected with structured error including the sandbox's stdout/stderr (truncated to 10 KB)
- Timeout: registration rejected with timeout error
- Resource overrun: registration rejected — pipeline declared `cpu_min: 4` but actually wanted 16

### 5.4 Re-validation triggers

A registered pipeline is re-validated automatically when:

- Source `ref` changes (operator updates the registration)
- Manifest version changes
- Operator updates `JACKPOT_BYOP_ALLOWED_REGISTRIES` or `JACKPOT_BYOP_ALLOWED_LICENSES`
- Quarterly background validation job runs (configurable cadence; default 90 days) to catch silently-broken upstream containers or moved Git refs

Failed re-validation transitions the pipeline to `DEACTIVATED` state with a notification to its registrar; existing `pipeline_results` rows from prior runs remain (immutability).

---

## 6. Pipeline lifecycle states

```text
SUBMITTED          User registered; static validation queued
  ↓
VALIDATING         Stage 1 running
  ↓
SANDBOX_PENDING    Stage 1 passed; Stage 2 queued
  ↓
SANDBOX_RUNNING    Stage 2 running
  ↓
ACTIVE             Both stages passed; appears in catalog
  ↓
DEACTIVATED        Re-validation failed OR registrar deactivated OR
                   registry pulled the source
  ↓
ARCHIVED           Pipeline + all its pipeline_results retained for
                   audit but no longer launchable
```

Failure terminal states (no transition to ACTIVE):

```text
VALIDATION_FAILED  Stage 1 failed
SANDBOX_FAILED     Stage 2 failed
SANDBOX_TIMEOUT    Stage 2 exceeded operator timeout
```

State transitions are logged to the audit log with the structured failure reason.

---

## 7. Schema additions for BYOP

`schema/jackpot_schema.yaml` additions:

```yaml
# New table: byop_pipelines
byop_pipelines:
  is_a: NamedThing
  attributes:
    id:
      identifier: true
      range: integer
    name:
      required: true
      range: string
      description: lowercase-hyphen-only name from manifest
    display_name:
      required: true
      range: string
    version:
      required: true
      range: string
      description: semver from manifest
    description:
      range: string
    engine_type:
      required: true
      range: PipelineEngineEnum
    engine_version:
      required: true
      range: string
    source_type:
      required: true
      range: PipelineSourceTypeEnum
    source_url:
      range: string
      description: Git URL or registry URL
    source_ref:
      range: string
      description: Git tag/branch/commit
    source_uploaded_uri:
      range: string
      description: For tarball source type
    source_sha256:
      range: string
      description: Tarball checksum
    docker_image:
      range: string
    docker_digest:
      range: string
    manifest_yaml:
      required: true
      range: string
      description: Full manifest content as text for audit
    applicable_organisms:
      multivalued: true
      range: OrganismNameEnum
    applicable_source_types:
      multivalued: true
      range: SourceTypeEnum
    applicable_data_types:
      multivalued: true
      range: DataTypeEnum
    pipeline_status:
      required: true
      range: PipelineStatusEnum
    validation_log:
      range: string
      description: Static validation output (truncated)
    sandbox_log:
      range: string
      description: Sandbox dry-run output (truncated)
    registered_by_user_id:
      required: true
      range: User
    registered_at:
      required: true
      range: datetime
    activated_at:
      range: datetime
    deactivated_at:
      range: datetime
    last_validated_at:
      range: datetime
    license_spdx:
      required: true
      range: string
    citation:
      range: string
    cost_estimate_usd:
      range: float

PipelineEngineEnum:
  permissible_values:
    nextflow:
    snakemake:
    wdl:
    manifest:

PipelineSourceTypeEnum:
  permissible_values:
    git:
    git_private:
    tarball:
    docker:

PipelineStatusEnum:
  permissible_values:
    SUBMITTED:
    VALIDATING:
    SANDBOX_PENDING:
    SANDBOX_RUNNING:
    ACTIVE:
    DEACTIVATED:
    ARCHIVED:
    VALIDATION_FAILED:
    SANDBOX_FAILED:
    SANDBOX_TIMEOUT:

DataTypeEnum:
  permissible_values:
    paired_end_short_read:
    single_end_short_read:
    long_read:
    assembly:
    raw_signal:
    metagenomic:
```

`pipeline_results` table gains:

```yaml
pipeline_results:
  attributes:
    # ... existing fields
    byop_pipeline_id:
      range: byop_pipelines
      description: Set if this run was a BYOP pipeline; null for curated zoo
    byop_pipeline_version:
      range: string
      description: Snapshot of byop_pipelines.version at launch time
```

---

## 8. API surface

`backend/routers/byop.py`:

```text
POST   /api/v1/byop/pipelines                  Register new pipeline
GET    /api/v1/byop/pipelines                  List (paginated, filterable by status/engine/organism)
GET    /api/v1/byop/pipelines/{id}             Get pipeline details
PATCH  /api/v1/byop/pipelines/{id}             Update (only certain fields — display_name, description, etc.)
POST   /api/v1/byop/pipelines/{id}/revalidate  Trigger re-validation
POST   /api/v1/byop/pipelines/{id}/deactivate  Move to DEACTIVATED
DELETE /api/v1/byop/pipelines/{id}             Move to ARCHIVED (no hard delete)
GET    /api/v1/byop/pipelines/{id}/manifest    Get the manifest YAML
GET    /api/v1/byop/pipelines/{id}/validation  Get validation/sandbox logs
GET    /api/v1/byop/manifest-schema            Get the JSON Schema for jackpot-pipeline.yaml
GET    /api/v1/byop/test-data                  Get sandbox test inputs (operator can verify)
```

Existing `/api/v1/pipelines/launch` accepts `byop_pipeline_id` alongside curated `pipeline_zoo_id` — single launch endpoint, dispatches by pipeline source.

---

## 9. Streamlit UI changes

Existing pages get BYOP-aware:

- **Pipelines page** — adds a "BYOP" tab alongside "Pipeline Zoo." Shows registered BYOP pipelines with status badge.
- **New page: BYOP Registration** — wizard for registering a new pipeline. Step 1: source type. Step 2: source details. Step 3: manifest preview. Step 4: validation status (live updates). Step 5: sandbox status. Step 6: activated.
- **Sample detail page** — pipeline-launch dropdown shows BYOP pipelines whose `applicability.organism_names` matches the sample's organism.
- **Pipeline-results display** — uses the BYOP pipeline's parser; renders MultiQC report if `outputs.multiqc_report` is declared.

Auth model:

- Bioinformatician role: can register, run, view all BYOP pipelines
- Researcher role: can run ACTIVE BYOP pipelines on their own samples; cannot register
- Lab Director: can deactivate BYOP pipelines registered in their lab
- Platform Admin: can deactivate any BYOP pipeline; can configure registry/license allowlists

---

## 10. Telemetry and operator visibility

For each BYOP pipeline, JACKPOT tracks:

- Total runs
- Success rate
- Mean walltime
- Mean memory peak
- Cost per run (in USD, based on operator's per-resource costs)
- Most recent failures with truncated error logs

Surfaced in the BYOP catalog UI so operators can spot pipelines that "register fine but fail in production." If a BYOP pipeline's success rate drops below an operator-configured threshold (default 50%), the platform admin is notified and the pipeline is auto-deactivated pending review.

---

## Part II — Eukaryotic pathogen pipelines

## 11. Pathogen scope and biology context

Eight pathogen groups. For each, the reference genomes, typing schemes, and surveillance-relevant features differ — JACKPOT needs to handle them with the same depth as bacterial coverage.

### 11.1 *Plasmodium* (malaria)

- **Species:** *P. falciparum* (most virulent), *P. vivax* (most widespread), plus *P. malariae*, *P. ovale curtisi*, *P. ovale wallikeri*, *P. knowlesi* (zoonotic)
- **Reference genomes:** *P. falciparum* 3D7 (PlasmoDB), *P. vivax* P01 (PlasmoDB)
- **Genome size:** ~23 Mb
- **Chromosomes:** 14
- **Surveillance focus:** drug resistance markers (`pfk13` for artemisinin, `pfdhfr`/`pfdhps` for SP, `pfcrt`/`pfmdr1` for chloroquine/lumefantrine), parasite genetic diversity (MOI — multiplicity of infection), HRP2/HRP3 deletions (RDT escape)
- **Typing scheme:** SNP-barcode (e.g., the 24-SNP barcode from Daniels et al. 2008 for *P. falciparum*), microsatellite-based typing, whole-genome SNP analysis
- **Workflow tools:** [MalariaGEN's `pf7` resource](https://www.malariagen.net/), `Pf-HRP2/3 deletion typer`, `artemisinin_resistance_caller`, the Sanger pipeline
- **Sample types:** dried blood spots most common; whole blood, RDT cards
- **Sequencing:** Illumina short-read most common; some ONT for long-read; MalariaGEN amplicon panels
- **Relevant existing pipelines:** `nf-core/sarek` (general somatic; not malaria-specific), MalariaGEN Sanger pipeline (not on nf-core), `mippy` (amplicon-based)

### 11.2 *Leishmania* (leishmaniasis)

- **Species:** *L. donovani* (visceral, fatal if untreated), *L. major* (cutaneous), *L. infantum*, *L. tropica*, *L. amazonensis*, *L. braziliensis*
- **Reference genomes:** *L. donovani* BPK282A1 (TriTrypDB), *L. major* Friedlin (TriTrypDB)
- **Genome size:** ~32-35 Mb
- **Chromosomes:** 36 (most species; *L. mexicana* complex has different counts)
- **Surveillance focus:** species discrimination (differential treatment), drug resistance (antimony, miltefosine, paromomycin), strain typing for outbreak attribution, HIV co-infection cases
- **Typing scheme:** MLST (LmjMLST), SNP-based phylogeny, kDNA minicircle analysis, whole-genome SNP
- **Workflow tools:** `Leishmania-typer`, custom mapping pipelines using `bwa-mem` + `samtools` + `gatk`, `LeishGEDIT` (CRISPR-Cas9 tool but has typing utilities)
- **Sample types:** skin lesion biopsies, bone marrow aspirate, blood, lymph node aspirate
- **Sequencing:** Illumina, increasingly ONT
- **Relevant existing pipelines:** TriTrypDB pipelines (web-only), no canonical nf-core pipeline

### 11.3 *Trypanosoma* (Chagas, sleeping sickness)

- **Species:** *T. cruzi* (Chagas — Americas), *T. brucei gambiense* (West African sleeping sickness), *T. brucei rhodesiense* (East African sleeping sickness), *T. congolense* and *T. vivax* (livestock)
- **Reference genomes:** *T. cruzi* CL Brener, *T. brucei* TREU927 (TriTrypDB)
- **Genome size:** ~26-55 Mb (T. cruzi has high heterozygosity and aneuploidy)
- **Chromosomes:** 11 megabase chromosomes + intermediate + minichromosomes (T. brucei); T. cruzi has 41 chromosome pairs in CL Brener
- **Surveillance focus:** discrete typing units (DTUs — TcI through TcVI for *T. cruzi*; key for Chagas treatment outcomes), drug resistance, vector-pathogen-host triangulation
- **Typing scheme:** DTU assignment for *T. cruzi* (multiple PCR-based methods + WGS), MLST for *T. brucei*, isoenzyme typing (legacy)
- **Workflow tools:** `TcrustDB`, `TrypanoGEN` resources, custom mapping pipelines
- **Sample types:** blood (acute Chagas), tissue (chronic Chagas), CSF (sleeping sickness late stage), lymph node aspirate
- **Sequencing:** Illumina mostly; some PacBio for the highly repetitive *T. cruzi* genome
- **Relevant existing pipelines:** No canonical; mostly bespoke

### 11.4 *Schistosoma* (schistosomiasis)

- **Species:** *S. mansoni* (intestinal), *S. haematobium* (urinary), *S. japonicum* (Asian intestinal), plus *S. mekongi*, *S. intercalatum*, *S. guineensis*
- **Reference genomes:** *S. mansoni* v9 (WormBase ParaSite), *S. haematobium* (Schisto_haematobium_v3), *S. japonicum* (SjapanSir)
- **Genome size:** ~363-399 Mb (large, repetitive)
- **Chromosomes:** 8 (7 autosomes + ZW sex chromosomes; female heterogamety)
- **Surveillance focus:** praziquantel resistance (emerging concern), hybrid species detection (S. haematobium × S. bovis hybrids in Europe and Africa), population genetic structure for transmission tracking
- **Typing scheme:** mitochondrial cox1 and nad1 barcoding (most common), microsatellite panels, whole-genome SNP, Internal Transcribed Spacer (ITS) for hybrid detection
- **Workflow tools:** `WormBase ParaSite` tools, `cox1_barcode_assigner`, `schisto_hybrid_caller`
- **Sample types:** miracidia (from feces/urine — preserved on Whatman cards is the field standard), adult worms, eggs
- **Sequencing:** Illumina; ONT for long-read assembly
- **Relevant existing pipelines:** `nf-core/createtaxdb` (general), no schisto-specific nf-core; SCAN (Schistosomiasis Collection at Natural History Museum) pipelines

### 11.5 Soil-transmitted helminths (STH)

- **Species:** *Ascaris lumbricoides* (roundworm), *Trichuris trichiura* (whipworm), *Necator americanus* and *Ancylostoma duodenale* (hookworms), *Strongyloides stercoralis*
- **Reference genomes:** *A. lumbricoides* (and *A. suum* — pig roundworm, near-identical genome), *T. trichiura* (TT_v1), *N. americanus* (Necam_v2), *S. stercoralis* (Sstrong_v3)
- **Genome size:** *Ascaris* ~270 Mb, *Trichuris* ~80 Mb, *Necator* ~230 Mb, *Strongyloides* ~50 Mb
- **Surveillance focus:** drug resistance (benzimidazole — single nucleotide polymorphisms in β-tubulin isotype 1 gene at codons 167, 198, 200), species/strain attribution, zoonotic transmission (*A. suum* ↔ *A. lumbricoides*), morantel/levamisole resistance in hookworms
- **Typing scheme:** ITS2 barcoding (species ID), β-tubulin SNP genotyping (resistance), whole-genome SNP for population structure
- **Workflow tools:** `nemabiome` (amplicon-based, Tasmania), `WormCat`, `WormBase ParaSite` tools
- **Sample types:** stool (for eggs/larvae), adult worms (rare in clinical samples)
- **Sequencing:** Illumina amplicon (most common in surveillance), PCR-based for resistance markers, occasional WGS
- **Relevant existing pipelines:** `nemabiome` (R package + analysis pipeline; for amplicon data)

### 11.6 *Wuchereria*/*Brugia* (lymphatic filariasis)

- **Species:** *Wuchereria bancrofti* (most common), *Brugia malayi*, *Brugia timori*
- **Reference genomes:** *Brugia malayi* (Brugia_malayi_4.0 — well-characterized; was the first parasitic nematode genome sequenced), *Wuchereria bancrofti* draft genomes; *B. timori* draft
- **Genome size:** *B. malayi* ~95 Mb, *W. bancrofti* ~81 Mb
- **Surveillance focus:** elimination program monitoring (MDA — Mass Drug Administration with ivermectin/DEC/albendazole), ivermectin resistance markers, *Wolbachia* endosymbiont status (basis for doxycycline therapy), residual transmission detection
- **Typing scheme:** mitochondrial cox1 barcoding, *Wolbachia* surface protein (wsp) typing for endosymbiont strain, microfilarial WGS where available
- **Workflow tools:** `BrugiaSeq` resources, `Wolbachia_typer`
- **Sample types:** blood (microfilariae — collected at night because of nocturnal periodicity), adult worms (rare)
- **Sequencing:** Illumina; ONT showing promise for microfilarial WGS from low-input samples
- **Relevant existing pipelines:** No nf-core; mostly bespoke

### 11.7 *Cryptosporidium*, *Giardia* (waterborne protozoa)

- **Species:** *Cryptosporidium parvum* (zoonotic), *C. hominis* (anthroponotic), *C. meleagridis*, plus rare species; *Giardia intestinalis* (= *G. duodenalis*, = *G. lamblia*) has 8 assemblages (A through H), with assemblages A and B causing most human disease
- **Reference genomes:** *C. parvum* IOWA-ATCC, *C. hominis* TU502, *G. intestinalis* assemblage A WB (CryptoDB and GiardiaDB)
- **Genome size:** *Cryptosporidium* ~9 Mb (small for a eukaryote), *Giardia* ~12 Mb
- **Surveillance focus:** outbreak attribution (water source, daycare cluster), species/assemblage discrimination (treatment differs), nitazoxanide resistance (rare but emerging), zoonotic transmission tracking
- **Typing scheme:** GP60 (gp60) gene subtyping (for *Cryptosporidium*; gold standard for outbreak typing), 18S rRNA/ITS for species ID, whole-genome SNP, beta-giardin typing (for *Giardia*)
- **Workflow tools:** `CryptoDB` and `GiardiaDB` resources, `GP60_subtyper`, `WGS_outbreak_caller`
- **Sample types:** stool (the only routine sample), water concentrates (for environmental surveillance)
- **Sequencing:** Illumina, increasingly ONT for portable outbreak response
- **Relevant existing pipelines:** No canonical nf-core; PHE/CDC have internal pipelines (closed)

### 11.8 *Toxoplasma*, *Entamoeba*

- **Species:** *Toxoplasma gondii* (cosmopolitan), *Entamoeba histolytica* (vs harmless *E. dispar* — must distinguish for treatment)
- **Reference genomes:** *T. gondii* ME49 (ToxoDB), *E. histolytica* HM-1:IMSS (AmoebaDB)
- **Genome size:** *Toxoplasma* ~65 Mb, *Entamoeba* ~24 Mb
- **Surveillance focus:** *T. gondii* — clonal lineage assignment (Type I/II/III + atypical strains; explains differential virulence and outbreak source), congenital toxoplasmosis. *E. histolytica* — discrimination from *E. dispar* (most "histolytica" in microscopy is actually dispar; treatment unnecessary), drug resistance to metronidazole
- **Typing scheme:** *T. gondii* — multilocus genotyping (15-marker MLST), restriction fragment length polymorphism (RFLP — legacy), whole-genome SNP. *E. histolytica* — SREHP and chitinase typing for outbreak work
- **Workflow tools:** `ToxoDB` resources, `Toxo_typer`, `Eh_vs_Ed_discriminator`
- **Sample types:** *T. gondii* — placenta (congenital), CSF (immunocompromised), blood, ocular fluid; *Entamoeba* — stool (most common), abscess aspirate (amebic liver abscess)
- **Sequencing:** Illumina mostly
- **Relevant existing pipelines:** No canonical nf-core; ToxoDB pipelines are web-only

---

## 12. Schema additions for eukaryotic pathogens

### 12.1 OrganismNameEnum additions

The default reference list from `OrganismNameEnum` (62 entries currently) gets ~25 additions:

```yaml
OrganismNameEnum:
  permissible_values:
    # ... existing 62 values ...

    # Plasmodium
    Plasmodium falciparum:
    Plasmodium vivax:
    Plasmodium malariae:
    Plasmodium ovale curtisi:
    Plasmodium ovale wallikeri:
    Plasmodium knowlesi:

    # Leishmania
    Leishmania donovani:
    Leishmania major:
    Leishmania infantum:
    Leishmania tropica:
    Leishmania braziliensis:
    Leishmania mexicana:

    # Trypanosoma
    Trypanosoma cruzi:
    Trypanosoma brucei gambiense:
    Trypanosoma brucei rhodesiense:
    Trypanosoma congolense:
    Trypanosoma vivax:

    # Schistosoma
    Schistosoma mansoni:
    Schistosoma haematobium:
    Schistosoma japonicum:
    Schistosoma mekongi:
    Schistosoma intercalatum:

    # Soil-transmitted helminths
    Ascaris lumbricoides:
    Ascaris suum:
    Trichuris trichiura:
    Necator americanus:
    Ancylostoma duodenale:
    Ancylostoma ceylanicum:
    Strongyloides stercoralis:

    # Filarial nematodes
    Wuchereria bancrofti:
    Brugia malayi:
    Brugia timori:

    # Waterborne protozoa
    Cryptosporidium parvum:
    Cryptosporidium hominis:
    Cryptosporidium meleagridis:
    Giardia intestinalis:

    # Other protozoa
    Toxoplasma gondii:
    Entamoeba histolytica:
    Entamoeba dispar:
```

Same Critical Rule 55 applies — these are *default* values seeded by `jackpot init`, not hardcoded. Operators can add/remove via Platform Admin UI.

### 12.2 New schema fields specific to eukaryotic pathogens

Most eukaryotic-specific information goes in `samples` as new optional fields, plus pipeline-result JSONB blobs. New `samples` columns:

```yaml
samples:
  attributes:
    # ... existing fields ...

    # Eukaryotic-specific metadata
    parasite_developmental_stage:           # ring, trophozoite, schizont, gametocyte, etc.
      range: ParasiteDevelopmentalStageEnum
    sample_preservation_method:             # whatman_card, dried_blood_spot, ethanol, frozen
      range: SamplePreservationMethodEnum
    parasitemia_percent:                    # for blood-borne; key for downstream assembly
      range: float
    multiplicity_of_infection:              # MOI; for Plasmodium typing
      range: integer
    coinfection_organisms:                  # multiple Plasmodium species, etc.
      multivalued: true
      range: OrganismNameEnum

ParasiteDevelopmentalStageEnum:
  permissible_values:
    ring:
    trophozoite:
    schizont:
    gametocyte:
    sporozoite:
    merozoite:
    cyst:
    trophozoite_amoebic:
    egg:
    miracidium:
    cercaria:
    adult:
    larva_l1:
    larva_l2:
    larva_l3:
    microfilaria:
    bradyzoite:
    tachyzoite:

SamplePreservationMethodEnum:
  permissible_values:
    fresh:
    frozen_minus_20:
    frozen_minus_80:
    ethanol_70:
    ethanol_95:
    rnalater:
    whatman_card:
    dried_blood_spot:
    formalin_fixed_paraffin_embedded:
    nucleic_acid_only:
```

### 12.3 New pipeline-results tables

Following the existing pattern (`pangolin_results`, `nextclade_results`, etc.) the eukaryotic pipelines get dedicated typed result tables. One per major typing/resistance pipeline. Examples:

```yaml
plasmodium_drug_resistance_results:
  attributes:
    sample_id:
      range: samples
    pfk13_mutations:
      multivalued: true
      range: string
      description: "e.g., F446I, R561H, C580Y"
    pfdhfr_mutations:
      multivalued: true
      range: string
    pfdhps_mutations:
      multivalued: true
      range: string
    pfcrt_codon_76:
      range: string
      description: "K (sensitive) or T (resistant)"
    pfmdr1_mutations:
      multivalued: true
      range: string
    artemisinin_resistance_call:
      range: ResistanceCallEnum
    sp_resistance_call:
      range: ResistanceCallEnum
    chloroquine_resistance_call:
      range: ResistanceCallEnum
    hrp2_deletion_detected:
      range: boolean
    hrp3_deletion_detected:
      range: boolean
    pipeline_version:
      range: string

leishmania_typing_results:
  attributes:
    sample_id:
      range: samples
    species_call:
      range: OrganismNameEnum
    mlst_profile:
      range: string
    drug_resistance_calls:
      range: dict
      description: "JSON: tool → resistant/susceptible per drug"

trypanosoma_typing_results:
  attributes:
    sample_id:
      range: samples
    dtu_call:
      range: TcDTUEnum
    drug_resistance_calls:
      range: dict

TcDTUEnum:
  permissible_values:
    TcI:
    TcII:
    TcIII:
    TcIV:
    TcV:
    TcVI:
    TcBat:

schistosoma_typing_results:
  attributes:
    sample_id:
      range: samples
    species_call:
      range: OrganismNameEnum
    cox1_haplotype:
      range: string
    nad1_haplotype:
      range: string
    its_genotype:
      range: string
    hybrid_detected:
      range: boolean
    parental_species_calls:
      multivalued: true
      range: OrganismNameEnum
    pzq_resistance_indicator:
      range: ResistanceCallEnum

helminth_drug_resistance_results:
  attributes:
    sample_id:
      range: samples
    species_call:
      range: OrganismNameEnum
    its2_barcode:
      range: string
    btub_codon_167:
      range: string
    btub_codon_198:
      range: string
    btub_codon_200:
      range: string
    benzimidazole_resistance_call:
      range: ResistanceCallEnum
    morantel_resistance_call:
      range: ResistanceCallEnum

filarial_typing_results:
  attributes:
    sample_id:
      range: samples
    species_call:
      range: OrganismNameEnum
    cox1_barcode:
      range: string
    wolbachia_status:
      range: WolbachiaStatusEnum
    wolbachia_supergroup:
      range: string
    ivermectin_resistance_call:
      range: ResistanceCallEnum

WolbachiaStatusEnum:
  permissible_values:
    present:
    absent:
    unknown:

cryptogiardia_typing_results:
  attributes:
    sample_id:
      range: samples
    species_call:
      range: OrganismNameEnum
    gp60_subtype:
      range: string
      description: "e.g., IIaA15G2R1; key for outbreak attribution"
    giardia_assemblage:
      range: GiardiaAssemblageEnum
    snp_outbreak_cluster_id:
      range: string

GiardiaAssemblageEnum:
  permissible_values:
    A:
    B:
    C:
    D:
    E:
    F:
    G:
    H:

toxo_entamoeba_typing_results:
  attributes:
    sample_id:
      range: samples
    species_call:
      range: OrganismNameEnum
    toxo_clonal_lineage:
      range: ToxoClonalLineageEnum
    toxo_15_marker_profile:
      range: string
    eh_vs_ed_call:
      range: EhVsEdEnum
    eh_metronidazole_resistance_indicator:
      range: ResistanceCallEnum

ToxoClonalLineageEnum:
  permissible_values:
    Type_I:
    Type_II:
    Type_III:
    Atypical:
    Recombinant:

EhVsEdEnum:
  permissible_values:
    histolytica:
    dispar:
    moshkovskii:
    inconclusive:

ResistanceCallEnum:
  permissible_values:
    susceptible:
    intermediate:
    resistant:
    inconclusive:
```

These tables follow the same immutable, append-only pattern as existing pipeline-results tables — every pipeline run gets a new INSERT, with `pipeline_version` fielded for reprocessing semantics.

---

## 13. Default eukaryotic pipelines for the zoo

For each pathogen group, JACKPOT ships at least one default pipeline. These are reference implementations operators can use immediately or fork.

| Pathogen group | Pipeline name | Engine | Source | Inputs | Outputs |
|---|---|---|---|---|---|
| *Plasmodium* | `jackpot-plasmodium-typer` | Nextflow | New, JACKPOT-authored | FASTQ | Drug resistance + lineage + HRP deletions |
| *Plasmodium* (amplicon) | `jackpot-plasmodium-mippy` | Nextflow | Wraps existing `mippy` | FASTQ amplicon | Allele frequencies |
| *Leishmania* | `jackpot-leishmania-typer` | Nextflow | New | FASTQ | Species + MLST + drug resistance |
| *Trypanosoma* | `jackpot-trypanosoma-dtu-caller` | Nextflow | New | FASTQ | DTU + drug resistance |
| *Schistosoma* | `jackpot-schistosoma-barcode` | Snakemake | Wraps cox1/nad1/ITS markers | FASTQ or amplicon | Species + hybrid status |
| Soil-transmitted helminths | `jackpot-sth-nemabiome` | Nextflow | Wraps `nemabiome` | FASTQ amplicon | Species + β-tubulin SNPs |
| Soil-transmitted helminths | `jackpot-sth-wgs` | Nextflow | New | FASTQ WGS | Full SNP + resistance + population |
| Filarial nematodes | `jackpot-filarial-typer` | Nextflow | New | FASTQ | Species + Wolbachia + resistance |
| *Cryptosporidium*/*Giardia* | `jackpot-cryptogiardia-typer` | Nextflow | New | FASTQ | Species + GP60 + assemblage + cluster |
| *Toxoplasma*/*Entamoeba* | `jackpot-toxo-entamoeba-typer` | Nextflow | New | FASTQ | Lineage/discrimination |

All default pipelines are AGPL-3.0, hosted under `Midnight-Oil-Innovation/jackpot-pipelines-eukaryotic` (single repo, one subdirectory per pipeline), and registered as curated zoo entries in `jackpot init`.

Initial implementations can lean heavily on existing community tooling:

- *Plasmodium*: `tb-profiler`-pattern wrapping `bcftools` for SNP calling against `pfk13`, `pfdhfr`, `pfdhps`, `pfcrt`, `pfmdr1` reference loci
- *Leishmania*, *Trypanosoma*: bwa-mem mapping + GATK variant calling against TriTrypDB references; species call via Mash distance
- *Schistosoma*: amplicon mapping against cox1, nad1, ITS reference databases
- Soil-transmitted helminths: existing `nemabiome` for amplicon, custom WGS pipeline
- Filarial: bwa-mem + GATK against *Brugia malayi* reference; *Wolbachia* status via mapping subset
- *Cryptosporidium*/*Giardia*: amplicon GP60 subtyping pipeline + WGS option for SNP clustering
- *Toxoplasma*/*Entamoeba*: 15-marker MLST + species discrimination

These pipelines are *Level 1* zoo entries (curated launch catalog) and follow the same registration path as bacterial/viral defaults.

---

## 14. Dashboard additions

Each pathogen group gets a dashboard page in the Streamlit researcher view, mirroring the existing patterns:

- **Malaria dashboard** — drug resistance prevalence by region/year; `pfk13` SNP frequency; HRP2/HRP3 deletion prevalence; MOI distribution
- **Leishmania dashboard** — species distribution; drug resistance trends; HIV co-infection cases
- **Trypanosoma dashboard** — DTU geographic distribution; treatment-outcome correlation
- **Schistosoma dashboard** — hybrid detection map; PZQ resistance indicators; cox1 haplotype trees
- **STH dashboard** — β-tubulin SNP prevalence; species map
- **Filarial dashboard** — elimination program tracking; ivermectin resistance; *Wolbachia* status
- **Crypto/Giardia dashboard** — outbreak cluster map; GP60 subtype trends; assemblage distribution
- **Toxo/Entamoeba dashboard** — lineage geographic distribution; *E. histolytica* vs *E. dispar* differential

These pages follow the Phase 25 admin/dashboard pattern and link from the main researcher dashboard.

---

## 15. Validation tier and surveillance-relevant logic

The existing `validator.py` tier-aware logic and `compute_surveillance_relevant()` need eukaryotic-aware extensions:

- New tier-2 fields: `parasite_developmental_stage`, `sample_preservation_method`
- New tier-3 fields: `parasitemia_percent`, `multiplicity_of_infection`, `coinfection_organisms`
- Surveillance-relevance rules expanded: any sample with organism in the eukaryotic-pathogen subset of `OrganismNameEnum` is `surveillance_relevant=TRUE` by default (operators can override per their reportable-disease list)

---

## 16. Interaction with the existing two-PII-gate architecture

### 16.1 SRA Human Scrubber

Eukaryotic samples present an interesting case: the host is human (in clinical samples) or animal (in zoonotic surveillance). The scrubber currently removes human reads. For:

- *Plasmodium* in human blood: scrubber works as-is — removes human reads, leaves parasite reads
- *Leishmania* in human tissue: scrubber works as-is
- *Trypanosoma* in human blood/CSF: scrubber works as-is
- *Schistosoma* miracidia: pre-purified, minimal host contamination — scrubber is safe but does little
- Helminths: same — typically pre-purified
- Filaria from blood: scrubber works
- *Crypto*/*Giardia* from stool: scrubber removes human gut shedding contamination
- *Toxo*/*Entamoeba* from clinical: scrubber works

For non-human-host samples (animal hosts in zoonotic surveillance — *Trypanosoma congolense* in cattle, *Schistosoma* in snails, etc.), the scrubber as-is doesn't help (it scrubs *human* reads only, not bovine, ovine, or molluscan).

This is the same gap the bacterial/viral side has for non-human-host samples. A future enhancement could replace the scrubber with a multi-host scrubber (e.g., `hostile` from Sanger, which supports human/mouse/rat/cow/sheep). Tracked as a future backlog item but not part of this design.

### 16.2 GCP DLP

The metadata DLP gate works the same way for eukaryotic samples — it scans free-text fields for PII regardless of organism. No changes needed.

---

## 17. Backlog items

Per existing convention, B-XXX-prefixed items grouped by source:

### N. BYOP architecture

```text
[ ] B-BYOP-1   Implement jackpot-pipeline.yaml manifest schema. Create
               schema/byop-pipeline-manifest.schema.json. Document under
               docs/byop/manifest.md. Effort: 1-2 sessions.
               Phase: P1.

[ ] B-BYOP-2   Implement backend/services/byop_validator.py — Stage 1
               static validation (manifest schema, engine syntax,
               container resolution, reference data, license, permissions).
               Effort: 3-4 sessions. Phase: P1.

[ ] B-BYOP-3   Implement backend/services/byop_sandbox.py — Stage 2
               sandbox dry-run with Kubernetes-namespace and
               Docker-network isolation. Effort: 1 week. Phase: P1.

[ ] B-BYOP-4   Implement backend/routers/byop.py — full CRUD API plus
               revalidate/deactivate/archive endpoints. Effort: 2-3
               sessions. Phase: P1.

[ ] B-BYOP-5   Implement engine launchers per engine type:
               nextflow_launcher.py (existing, harden), snakemake_launcher.py
               (new), wdl_launcher.py (new), manifest_launcher.py (new).
               Effort: 2-3 sessions per launcher. Phase: P1.

[ ] B-BYOP-6   Implement backend/services/byop_quarterly_revalidation.py
               background job for upstream-rot detection. Effort: 1 session.
               Phase: P1.

[ ] B-BYOP-7   Implement Streamlit BYOP registration wizard (new page).
               Effort: 2-3 sessions. Phase: P1.

[ ] B-BYOP-8   Implement Streamlit BYOP catalog tab on the Pipelines page.
               Effort: 1-2 sessions. Phase: P1.

[ ] B-BYOP-9   Schema migration for byop_pipelines table and pipeline_results
               foreign key additions. Effort: 1 session. Phase: P0b
               (Schema v5.0).

[ ] B-BYOP-10  Implement BYOP telemetry — aggregated success rate, walltime,
               cost per pipeline. Effort: 1-2 sessions. Phase: P1.
```

### O. Eukaryotic pathogen schema and infrastructure

```text
[ ] B-EUK-1    Schema migration: OrganismNameEnum additions (~25 species),
               new ParasiteDevelopmentalStageEnum, new
               SamplePreservationMethodEnum, new samples columns
               (parasite_developmental_stage, sample_preservation_method,
               parasitemia_percent, multiplicity_of_infection,
               coinfection_organisms). Effort: 1 session.
               Phase: P0b.

[ ] B-EUK-2    Schema migration: new pipeline-result tables —
               plasmodium_drug_resistance_results, leishmania_typing_results,
               trypanosoma_typing_results, schistosoma_typing_results,
               helminth_drug_resistance_results, filarial_typing_results,
               cryptogiardia_typing_results, toxo_entamoeba_typing_results,
               plus supporting enums (TcDTUEnum, GiardiaAssemblageEnum,
               ToxoClonalLineageEnum, EhVsEdEnum, WolbachiaStatusEnum,
               ResistanceCallEnum). Effort: 1-2 sessions.
               Phase: P0b.

[ ] B-EUK-3    Update validator.py for eukaryotic-aware tier rules:
               new tier-2 fields (developmental stage, preservation method),
               new tier-3 fields (parasitemia, MOI, coinfection).
               Update compute_surveillance_relevant() to include eukaryotic
               pathogens by default. Effort: 1 session.
               Phase: with B-EUK-1 / B-EUK-2.
```

### P. Eukaryotic pathogen pipelines (per group)

```text
[ ] B-EUK-PLAS-1  jackpot-plasmodium-typer pipeline (Nextflow). Drug
                  resistance loci genotyping + HRP deletion detection.
                  Repo: Midnight-Oil-Innovation/jackpot-pipelines-eukaryotic.
                  Effort: 1-2 weeks. Phase: P1+.

[ ] B-EUK-PLAS-2  jackpot-plasmodium-mippy pipeline (Nextflow). Wraps
                  existing mippy for amplicon-based surveillance.
                  Effort: 3-5 sessions. Phase: P1+.

[ ] B-EUK-LEIS-1  jackpot-leishmania-typer pipeline. Species + MLST +
                  drug resistance. Effort: 1-2 weeks. Phase: P1+.

[ ] B-EUK-TRYP-1  jackpot-trypanosoma-dtu-caller pipeline. DTU assignment
                  for T. cruzi + drug resistance for T. brucei spp.
                  Effort: 1-2 weeks. Phase: P1+.

[ ] B-EUK-SCHI-1  jackpot-schistosoma-barcode pipeline (Snakemake). cox1/
                  nad1/ITS markers + hybrid detection. Effort: 1 week.
                  Phase: P1+.

[ ] B-EUK-STH-1   jackpot-sth-nemabiome pipeline. Wraps existing
                  nemabiome amplicon analysis. Effort: 3-5 sessions.
                  Phase: P1+.

[ ] B-EUK-STH-2   jackpot-sth-wgs pipeline. WGS-based SNP + resistance
                  for soil-transmitted helminths. Effort: 1-2 weeks.
                  Phase: P1+.

[ ] B-EUK-FILA-1  jackpot-filarial-typer pipeline. Species + Wolbachia
                  + ivermectin resistance. Effort: 1-2 weeks. Phase: P1+.

[ ] B-EUK-CRYP-1  jackpot-cryptogiardia-typer pipeline. GP60 subtyping +
                  Giardia assemblage + outbreak SNP clustering.
                  Effort: 1-2 weeks. Phase: P1+.

[ ] B-EUK-TOXO-1  jackpot-toxo-entamoeba-typer pipeline. Toxo lineage +
                  E. histolytica vs E. dispar discrimination.
                  Effort: 1 week. Phase: P1+.
```

### Q. Eukaryotic dashboards

```text
[ ] B-EUK-DASH-1  Streamlit dashboard pages for the 8 pathogen groups
                  (one page each). Patterns per Section 14. Effort: 2-3
                  sessions per dashboard, ~3 weeks total.
                  Phase: P1+ (after relevant pipelines exist).
```

### R. Eukaryotic parsers

```text
[ ] B-EUK-PARSE-1 Implement pipeline_results parsers for each new
                  pipeline-result table — one parser per typing pipeline
                  (8 parsers). Follow existing pattern in
                  backend/parsers/. Effort: 1 session per parser.
                  Phase: with each pipeline above.
```

Total: 10 BYOP items + 3 schema items + 10 pipeline items + 1 dashboard package + 8 parsers = **32 backlog items**.

These naturally form a new Phase 28 — "BYOP and Eukaryotic Pathogen Coverage."

---

## 18. Phasing and dependency graph

The order matters because some items block others:

```text
P0b Schema v5.0
  ├── B-BYOP-9  byop_pipelines table + pipeline_results FK
  ├── B-EUK-1   OrganismNameEnum + samples columns
  └── B-EUK-2   pipeline-result tables + enums
       └── B-EUK-3  validator updates

P1 (Operator-type configurability)
  ├── B-BYOP-1  manifest schema definition
  ├── B-BYOP-2  static validator
  ├── B-BYOP-3  sandbox
  ├── B-BYOP-4  router
  ├── B-BYOP-5  engine launchers (4 parallel)
  ├── B-BYOP-6  quarterly revalidation
  ├── B-BYOP-7  registration wizard UI
  ├── B-BYOP-8  catalog tab UI
  └── B-BYOP-10 telemetry

P1+ (after BYOP infra is real, eukaryotic pipelines fold in)
  ├── B-EUK-PLAS-1, B-EUK-PLAS-2     # malaria (priority)
  ├── B-EUK-LEIS-1                    # leishmaniasis
  ├── B-EUK-TRYP-1                    # trypanosomiasis
  ├── B-EUK-SCHI-1                    # schistosomiasis
  ├── B-EUK-STH-1, B-EUK-STH-2        # soil-transmitted helminths
  ├── B-EUK-FILA-1                    # filarial nematodes
  ├── B-EUK-CRYP-1                    # crypto/giardia
  ├── B-EUK-TOXO-1                    # toxo/entamoeba
  ├── B-EUK-PARSE-1 (per pipeline)    # parsers
  └── B-EUK-DASH-1                    # dashboards
```

Schema work in P0b is the gating step — both BYOP infrastructure and eukaryotic schema land there. Everything else is post-P0b.

The 8 eukaryotic pipelines can be built in parallel by independent developers/contractors; each is its own ~1-2 week project. The first ones to ship first are *Plasmodium* (highest global disease burden, most active surveillance community, largest existing tooling base) and *Cryptosporidium*/*Giardia* (US-relevant via waterborne outbreaks, GP60 typing has clear outbreak utility).

---

## 19. What this design intentionally doesn't do

To keep scope tractable:

- **Doesn't try to build a workflow IDE.** Operators register pipelines; they don't author them in JACKPOT.
- **Doesn't validate biological correctness.** A pipeline that calls every sample resistant will activate fine — JACKPOT only validates structural/operational correctness.
- **Doesn't unify outputs across engines beyond `pipeline_results` JSONB blob and parser registration.** Each pipeline declares its output shape; JACKPOT just stores and serves.
- **Doesn't provide cross-pipeline result comparison out of the box.** That's downstream analytics work; pipeline-result tables enable it but don't include it.
- **Doesn't ship reference genomes for eukaryotic organisms.** Each pipeline declares its references via `reference_data:`; JACKPOT pulls from the declared sources at install time. (For Scenario A laptop deploys, reference bundles can be pre-pulled.)
- **Doesn't replace TriTrypDB, PlasmoDB, ToxoDB, CryptoDB, etc.** These are the canonical eukaryotic-pathogen databases; JACKPOT pipelines pull references from them and link to them in the dashboard.

---

## 20. Cross-references

| Topic | Where developed |
|---|---|
| BYOP pre-design (vague stretch goal) | `spec.md` Phase 25 |
| Pipeline-zoo pattern | `jackpot_architecture.md` |
| `pipeline_results_loader.py` (existing immutable append-only loader) | Memory + project knowledge |
| Two PII gates | `jackpot_pathoplexus_loculus_overview.md` §9 |
| Critical Rule 55 (operator-agnostic production code) | `CLAUDE.md` |
| Validation tier system | `validator.py` |

---

## 21. Glossary additions

| Term | Definition |
|---|---|
| **BYOP** | Bring Your Own Pipeline — JACKPOT's mechanism for operator-registered workflows |
| **DTU** | Discrete Typing Unit (for *Trypanosoma cruzi*; TcI through TcVI) |
| **GP60** | Glycoprotein 60; canonical *Cryptosporidium* outbreak typing locus |
| **HRP2/HRP3** | Histidine-rich proteins 2 and 3; *P. falciparum* RDT targets, deletion = RDT escape |
| **MOI** | Multiplicity of infection; number of distinct *Plasmodium* genotypes per infection |
| **PlasmoDB**, **TriTrypDB**, **ToxoDB**, **CryptoDB**, **GiardiaDB** | Canonical eukaryotic pathogen databases (VEuPathDB family) |
| **STH** | Soil-transmitted helminths |
| **WormBase ParaSite** | Genome database for parasitic worms |

---

*End of design document. Companion to `jackpot_pathoplexus_loculus_overview.md` (peer-platform comparative analysis) and `jackpot_cdc_dmi_stlt_overview.md` (US public-health-data ecosystem alignment).*
