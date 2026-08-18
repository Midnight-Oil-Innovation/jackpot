> **Status:** Superseded — archived (directory convention). Historical; do not cite as current.

Comprehensive inventory of everything we've discussed as potential additions to JACKPOT. Organized by domain so you can see what clusters together.

## ML and modeling infrastructure

**New tables:**

- **`model_artifacts`** — model_id, version, training_data_hash, training_pipeline_run_id, validation_metrics (JSONB), artifact_uri (GCS/MinIO path), created_at, status enum (`active` / `deprecated` / `retired`), replacement_model_id. Immutable append-only.
- **`model_evaluations`** — model_id, evaluation_dataset_id, metrics (JSONB), evaluated_at. Append-only. Each row records a single evaluation of a model against a specific held-out dataset.
- **`inference_runs`** — model_id, input_data_query, output_pipeline_results_ids, run_at. Append-only. Records every batch scoring or real-time inference event.
- **`embeddings`** — sample_id, model_id, embedding (pgvector type or JSONB float array), created_at. Stores foundation model embeddings computed at ingest. Enables downstream anomaly detection without re-running the foundation model.

**New pipeline category:**

- **`analytics` / `modeling` pipeline type** — distinct from existing `bioinformatics` pipelines. Same Nextflow infrastructure, same pipeline_results pattern, but tagged so the catalog and UI can distinguish them.

**New Nextflow pipelines:**

- **Embedding pipeline at ingest** — runs after viralrecon or equivalent, passes consensus sequences through a chosen foundation model (Nucleotide Transformer, Evo, HyenaDNA, DNABERT-2, or ESM-2), writes embeddings to the `embeddings` table.
- **Batch anomaly scan pipeline** — scheduled Nextflow workflow or APScheduler job. Queries recent samples, scores them against an active anomaly detection model (Isolation Forest on embeddings), writes results to `pipeline_results` and alerts to `notifications`.
- **Lineage growth anomaly pipeline** — daily MLR or Bayesian fit on lineage frequencies, flags lineages with growth coefficient exceeding threshold. Writes to `notifications`.
- **AMR fingerprint anomaly pipeline** — Isolation Forest on hAMRonization output vectors, flags samples in unusual regions of the AMR fingerprint space.
- **UShER placement outlier scoring pipeline** — runs on every sample at ingest, writes parsimony scores and placement uncertainty to `pipeline_results`; downstream scheduled job flags high-parsimony samples.
- **Training pipeline** — runs model training as a Nextflow workflow, outputs versioned model artifacts to GCS, writes `model_artifacts` row with training data hash and validation metrics.
- **Drift monitoring pipeline** — scheduled job using `alibi-detect` to compare current embedding/lineage/AMR distributions to training-time distributions, triggers retraining workflow when drift exceeds threshold.

**Aggregated alerting:**

- **Unified anomaly view or query** — combines lineage growth, AMR, UShER, and embedding-based detectors into a single "current anomalies" view in Streamlit, with multi-detector weighting.

## Federation infrastructure

**Layer 1 (federated summary statistics, v1):**

- **Summary stats publishing service** — APScheduler job in each cell that periodically computes and publishes summary statistics (lineage frequency vectors, AMR fingerprint distributions, embedding centroids and covariances) to a federation coordinator.
- **Federation coordinator service** — receives summary stats from member cells, aggregates them into federation-level statistics, pushes federation-level results back to members. Could be hosted by a designated cell or a neutral party.
- **Hierarchical Bayesian modeling code for lineage growth coefficients** — federated meta-analysis pattern using numpyro or PyMC, takes per-cell coefficients and produces a global posterior with cell-specific deviations.
- **Federation audit trail** — extensions to the existing audit_log to capture every summary stat exchange, with cryptographic verification.

**Layer 2 (true federated learning with Flower, v2):**

- **Flower (`flwr`) client service** — runs in each JACKPOT cell, executes local training rounds on cell-private data, exchanges model updates (LoRA adapters preferred) with the federation server.
- **Flower server service** — orchestrates training rounds, aggregates client updates via FedAvg or Byzantine-robust alternatives (Krum, Trimmed Mean, Median, Bulyan, FLTrust).
- **LoRA adapter management** — versioning, storage, and lifecycle management for low-rank adapters trained per cell and federation-wide. Uses `peft` from Hugging Face.
- **Federation round orchestration via Nextflow** — wraps Flower training rounds in the existing Nextflow pattern so they appear in pipeline_runs with full audit.

**Layer 3 (privacy hardening, future):**

- **Differential privacy via Opacus** — DP-SGD plug-in for PyTorch model training in Flower clients, with privacy budget accounting.
- **Secure aggregation protocol** — Bonawitz et al. 2017 cryptographic protocol, supported natively by Flower.
- **Trusted execution environment for aggregator** — GCP Confidential Computing for the Flower server, optional hardening.

## Schema additions for Health Observatory use cases

**New sample type extensions:**

- **`dairy_bulk_tank` subclass under Food source type** — or new sample type — for H5N1 bulk milk surveillance. Fields for collection point, herd size, processing status, storage temperature.
- **Air filter sampling protocol fields on AirSample** — filter type (e.g., polycarbonate, polysulfone), sampling duration, flow volume, post-collection processing (e.g., fungal culture vs direct DNA extraction). Needed for *Coccidioides* surveillance specifically.

**New table:**

- **`external_data_sources`** — registers approved external data sources (NOAA weather stations, ASIIS vaccination registry, Arizona open data portals, NWSS, NHSN HRD). Fields for source_name, base_url, identifier_pattern, last_validated_at, contact_email, license, allowed_use. Then `sample_associations` and `metadata_tags` can reference these with confidence rather than relying on free-text URLs.

**Pipeline result type schemas:**

- **Valley fever LSTM extension result type** — strain-resolved forecaster output with confidence intervals, geographic resolution, time horizon, model_id reference.
- **ML forecasting result types** — generic schema for anomaly scores, lineage growth coefficients, AMR pattern probabilities, federated model inference outputs.
- **Drug-of-abuse wastewater detection result type** — if Tempe's broader pathogen+drug panel gets ingested, the drug detection time series needs a structured schema.

## Schema additions from earlier roadmap (already planned)

- **Schema v5.0** — major version that consolidates the additions above plus the existing P0b roadmap items.
- **ICTV-aligned taxonomy refactor** — controlled vocabulary alignment with ICTV (International Committee on Taxonomy of Viruses) for virus taxonomy, motivated by the Varsani / Cenote-Taker 3 collaboration angle.
- **US states controlled vocabulary** — for `collection_location_state` when country is "United States" (already in your Month 2 plan).
- **Multi-tenancy middleware** — P0c, separate from schema but affects how all tables are queried.

## COVID-19 demo infrastructure

**Data ingest scripts:**

- **`fetch_demo_data.py`** — pulls NCBI Virus SARS-CoV-2 metadata, NWSS wastewater metric data, NWSS concentration data, HHS historical hospital data, NHSN HRD current hospital data for Arizona, all via Socrata APIs. Full script delivered in chat.
- **NCBI Datasets CLI wrapper** — commands for pulling actual FASTA sequences with metadata, scoped to Arizona for the demo period.
- **Tempe Open Data fetcher** — pulls Tempe's publicly-published wastewater feeds (SARS-CoV-2, influenza, RSV, mpox, norovirus, opioids) via the ArcGIS Hub REST API. Tempe-specific because the catchment includes the ASU campus.
- **COVID-19 Forecast Hub data fetcher (offered, not delivered)** — for benchmarking JACKPOT's forecasts against historical submissions. The reichlab/covid19-forecast-hub repo or its successor.
- **CoV-Spectrum LAPIS API fetcher (offered, not delivered)** — lineage frequency time series for comparison.

**Demo dataset construction:**

- Arizona-scoped SARS-CoV-2 sequence subset (NCBI Virus, 2021-01 through 2023-06)
- Pango lineage assignments via Pangolin or Nextclade
- Maricopa County wastewater data from NWSS
- Arizona hospitalization data from HHS legacy + NHSN HRD current, stitched at the methodology change
- Held-out future period (2023-07 through 2023-12) for forecast evaluation
- Partitioned by simulated cell of origin (geographic by Census region, or lab-effect by sampling profile)

## Sol cluster federation simulation infrastructure

- **JACKPOT Apptainer (.sif) container builds** — for FastAPI, PostgreSQL, and MinIO components, built for Sol's container environment.
- **SLURM submission script for federation simulation** — single allocation, multi-node cell instantiation, hostname-based cell IDs, scratch-directory data isolation per cell. Full script delivered in chat.
- **Linux `tc` (traffic control) commands for WAN simulation** — netem-based delay, jitter, and packet loss configuration per cell interface to simulate realistic federation conditions (80ms ± 10ms latency, 0.01% loss, 1 Gbps cap).
- **Globus DTN integration** — using Sol's Globus endpoint as the transport layer for inter-cell data movement, more realistic than direct TCP.
- **Three architectural shapes documented:**
  - Shape 1: Single SLURM allocation, multiple cells per node
  - Shape 2: Two-allocation cross-datacenter (exploiting Sol's 4-mile DC split for real latency)
  - Shape 3: Single allocation with `tc`-simulated WAN conditions (most realistic)

## Testing infrastructure

**Test data generators:**

- **Custom SIR generator** — takes (N, R0, gamma, T_max), produces daily case count time series with known parameters for backtest of R(t) estimation.
- **FAVITES wrapper** — Nextflow-wrapped Moshiri FAVITES, takes (transmission_rate, recovery_rate, mutation_rate, sample_fraction), produces transmission trees + simulated sequences + sample metadata.
- **Dawg wrapper** — Reed Cartwright's sequence-evolution-only simulator for synthetic FASTA data with biologically accurate indel models.
- **Custom metadata generator** — generates valid sample metadata using the JACKPOT schema's controlled vocabularies (Faker for personal-identifier-like fields, constrained sampling from enums for the rest).
- **Hypothesis property-test data infrastructure** — automated random generation against schema constraints for the invariant tests.

**Test types:**

- **Property-based tests using Hypothesis** — invariants like probabilities summing to 1, SIR conservation laws, non-negativity, deterministic reproducibility with seeds.
- **Backtest / replay tests for time-aware anomaly detection** — historical data replayed in chronological order, no time leakage enforced via `WHERE created_at <= replay_timestamp`.
- **Sensitivity analysis and calibration recovery tests** — forward-simulate from known parameters, verify the fitted model recovers them.
- **Numerical / property tests for epi models** — conservation laws, positivity, boundary conditions (R0 = 0 → no outbreak; R0 = ∞ → full attack rate).
- **Model evaluation tests against held-out data** — load model + versioned test dataset, assert metrics exceed documented thresholds. Becomes release gate.

**Benchmark dataset infrastructure:**

- **`test-fixtures` GCS bucket** — versioned benchmark datasets with content hashing and strict access controls.
- **Benchmark dataset versioning** — datasets referenced by hash in `model_evaluations` for full reproducibility.
- **CI subset for per-commit testing** — stripped-down (small N, short T) version of the test suite; full evaluation suite runs nightly.

## P0 bug fixes (already documented in userMemories, not new from this chat but in scope)

- **`log_audit()` and `create_notification()` `db_conn` forwarding** — both accept `db_conn` but never forward it to `execute_write()`, causing audit/notification writes to auto-commit in separate transactions.
- **`_handle_workflow_complete()` `execute_query(..., conn=conn)`** — calls `execute_query` with a `conn=` parameter that the signature doesn't accept; will throw TypeError when Nextflow posts `workflow.complete`.
- **`jackpot-api-config` ConfigMap CORS_ORIGINS format** — still contains the old string value instead of the JSON array format required by pydantic-settings for `list[str]`. Fix: `kubectl -n jackpot delete configmap jackpot-api-config` then `gh workflow run deploy-staging.yml`.

## Operator-side infrastructure not in JACKPOT itself

These came up in the ASU coalition discussions and would be deployed alongside JACKPOT for specific use cases but live outside the JACKPOT repo:

- **`jackpot init` CLI** — already in your P0e roadmap, for per-operator bootstrap of operator-specific configuration.
- **Presidio DLP scanner backend** — for Scenario A laptop deployments where GCP Cloud DLP isn't available. Deferred per the userMemories notes.
- **Decision Theater visualization layer** — separate frontend that consumes JACKPOT data and renders to the Drum, not part of JACKPOT itself.

## Open architectural decisions

A few things came up where the design space was discussed but no specific addition was committed:

- **Presidio vs other DLP backend choice** — deferred to a future phase per userMemories.
- **Choice of foundation model** for the embedding pipeline (Nucleotide Transformer, Evo, HyenaDNA, DNABERT-2, ESM-2) — each has different tradeoffs in license, model size, embedding quality, and compute requirements.
- **Choice between ONNX, TorchScript, or PyTorch pickle** for portable model serialization.
- **Aggregator hosting model for federation** — designated cell, neutral third party, rotating role.
- **Compute budget and approval for GPU access** on Sol or GCP for the foundation model embedding pipeline.

## Quick summary by count

- New database tables: **4** (`model_artifacts`, `model_evaluations`, `inference_runs`, `embeddings`, `external_data_sources`) — actually 5
- New pipeline types: **7** (embedding, batch anomaly scan, lineage growth, AMR fingerprint, UShER placement, training, drift monitoring)
- New federation services: **5** (summary stats publisher, federation coordinator, Flower client, Flower server, LoRA adapter manager)
- New schema additions: **3** (dairy_bulk_tank, air filter protocol fields, ICTV taxonomy refactor)
- New result type schemas: **3+** (Valley fever LSTM, generic ML forecasting, drug-of-abuse wastewater)
- New scripts/utilities: **6** (fetch_demo_data, NCBI Datasets wrapper, Tempe data fetcher, Forecast Hub fetcher, LAPIS fetcher, SLURM federation script)
- New test generators: **5** (SIR, FAVITES, Dawg, metadata, Hypothesis)
- Documented P0 bug fixes: **3**

Want me to convert any of these into actual `todo.md` entries with priority/phase markers, or expand the schema definitions for any specific table into a Pydantic/LinkML draft?
