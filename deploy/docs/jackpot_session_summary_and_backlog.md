# JACKPOT Session Summary & Backlog

**Document version:** 2.3 **Last updated:** 2026-04-19 **Sessions covered:** Session 1 (March–April 2026 consolidated), Session 2 (2026-04-10), Session 3 (2026-04-10), Session 4 (2026-04-12), Session 5 (2026-04-15 — diagrams), Session 6 (2026-04-16 — code audit), Session 5 (2026-04-16 — Claude Code autonomous setup + validator rewrite), Session 5 (2026-04-17 → 2026-04-19 — GCP staging deploy + Streamlit UI local debug)

------

# Session 1 — March–April 2026 (Consolidated)

## What we covered

This session spanned platform architecture, data governance, external platform analysis, schema evolution, UX information architecture, workspace design, data lifecycle, metadata tooling, upload mechanisms, TB typing, external database search integration, Globus architecture (deposit-first with university subscription), external sequencing lab access, BaseSpace transition path, pre-coding CLAUDE.md additions, GCP production architecture clarification, local dev stack topology (Docker Compose + minikube hybrid), Nextflow GCP Batch execution model, GKE autoscaling architecture, caching architecture (why JACKPOT avoids Celery/Redis as general-purpose tools), disaster recovery and backup architecture, Streamlit migration strategy (why it works for the prototype and when/how to migrate to React), and LLM support assistant architecture (RAG pattern for site orientation, how-to guidance, and data-specific support). Key outputs: schema modification script (v4.1 → v4.2), prioritized to-do list, updated feature backlog, updated CLAUDE.md.

------

## Topics discussed

### 1. Diagrams and mental models (MM14, MM15)

Built MM14 (Testing with pytest) and MM15 (GitHub CI Pipeline) as standalone HTML files. Produced the data standards explorer (interactive HTML mapping PHA4GE, GA4GH, FAIR, MIxS, NCBI, GISAID, MMWR, NWSS to specific schema fields).

### 2. CLAUDE.md update

Added Critical Rules 13–15 (jose jwt import, lazy engine pattern, stub router pattern), current baseline (95 tests, 63.96% coverage), and local dev role-switching procedure.

### 3. Role renaming — lab_admin → lab_director, org_admin → platform_admin

Full blast-radius rename executed: frontend pages, db/init.sql, backend/auth/guards.py, tests, write_files_2.py, CLAUDE.md, and Alembic migration a7fd1fcccb77 renaming is_lab_admin → is_lab_director on lab_membership. All hooks passing, merged to development.

### 4. Platform analysis — Pathogenwatch, EnteroBase, Data-flo, GHRU

- **Pathogenwatch/AMRsearch**: Docker + FASTA + NCBI taxid → S/I/R with paarsnp suppressor-aware algorithm. Directly adoptable.
- **GHRU assembly pipeline**: MIT-licensed Nextflow. First zoo candidate.
- **Data-flo**: Adaptor model reference for future visual pipeline builder.
- **EnteroBase**: 1.7M strains, cgMLST + HierCC. JACKPOT should store cgST and HierCC for Salmonella, E. coli, and M. tuberculosis. TB database now hosted at DSMZ (enterobase.dsmz.de) — separate API endpoint needed for TB federation.

### 5. Pipeline zoo design

Four-level spectrum. Month 2 = Level 1 (curated launch catalog). Level 3 (visual builder) = Year 2. Initial six pipelines: GHRU assembly, nf-core/viralrecon, nf-core/mag, nf-core/taxprofiler, nf-core/funcscan, tb-profiler. All Nextflow-first. Seqera Platform monitoring deferred — stays in JACKPOT.

nf-core/mag is a Month 2 zoo pipeline. The Year 2 "metagenomic pipeline path" is the JACKPOT-native orchestration layer that chains mag + taxprofiler

- funcscan together with MAG-to-sample linkage, cross-pipeline result aggregation, and surveillance_relevant recomputation across the chain. These are distinct — nf-core/mag running standalone in the zoo requires none of that orchestration.

### 6. Pipeline telemetry and execution tracking

pipeline_runs + pipeline_tasks + pipeline_events + pipeline_restarts tables. Nextflow -weblog POSTs events to POST /api/v1/pipelines/events. work_dir stored per run for -resume support. Background job handles auto-approve, expiry. Four-tab monitoring UI: Overview/Tasks/Events/Files.

### 7. Pipeline result storage and sharing

Two-tier: structured metrics in pipeline_results (JSONB), raw files in GCS jackpot-results bucket registered in pipeline_files. MultiQC served via presigned URL in iframe. Microreact export from datasets.

### 8. One Health and global standards review

Black et al. (2020): case→sample→sequence hierarchy. Djordjevic et al. (2024): hAMRonization, long-read metagenomics, MAG QC. Struelens et al. (2024): three data tiers, ONT clinical-grade accuracy. Rockefeller Foundation: turnaround benchmarks (10-day upload, 48h lineage, 21-day phenotype). WHO Guiding Principles (2022): open as possible/closed as necessary, interoperability, attribution.

### 9. Schema v4.2 — 22 changes

Produced update_schema_v4_2.py. All changes applied and validated. 1923 → 2326 lines (+403). Key changes: case_id moved to BaseSample, case_source_system + CaseTypeEnum added, sector + SectorEnum, surveillance_relevant + override fields, target_organisms for metagenomics, SurveillanceOverrideCategoryEnum, quality_status + QualityStatusEnum, date_collected_precision + DatePrecisionEnum, read_type + ReadTypeEnum, assembly_type + AssemblyTypeEnum + MAG QC fields, originating_lab + submitting_lab + data_generator, ena_accession, data_use_terms + DataUseTermsEnum, embargo fields, turnaround timestamps.

### 10. Data governance — access control model

Sharing levels: PRIVATE (owner + Lab Director), LAB (all lab members), DISCOVERABLE (visible, data requires request), PUBLIC (open to all authenticated users). PRIVATE useful for: work in progress, research on organisms ADHS doesn't track.

Org-level policy fields: has_oversight_access, default_sharing_level, access_request_grace_days (default 90), access_requests_enabled, access_policy_note.

Three org profiles:

- ADHS: default_sharing_level=LAB, has_oversight_access=TRUE
- Academic: default_sharing_level=PRIVATE, has_oversight_access=FALSE
- Partner PH: default_sharing_level=LAB, has_oversight_access=FALSE

ADHS oversight scoped to surveillance_relevant=TRUE samples only. Academic private research on non-reportable organisms is excluded from oversight.

Surveillance relevance: organism-driven default from reportable_organisms DB table. Metagenomics uses target_organisms list; untargeted defaults TRUE conservatively; post-pipeline recompute promotes never demotes. Override model: TRUE→FALSE requires governance board; FALSE→TRUE is self-declared. SurveillanceOverrideCategoryEnum captures context.

Access request lifecycle: 90-day passive approval, background job, notification events at request/decision/75-day warning/7-day expiry warning.

can_access_sample(): Platform Admin → lab member → PUBLIC → oversight authority (surveillance_relevant=TRUE only) → approved request. can_see_sample(): less restrictive, for catalog visibility.

### 11. UX information architecture

**Personal Dashboard (login landing page):** Four quadrants — My Activity (feed of recent events), My Active Work (running pipelines, pending requests, PRELIMINARY samples, draft datasets), My Projects (compact list), Quick Actions (Upload, Search, Launch Pipeline, Open Workspace).

**Global Navigation:** Dashboard, Search, Pipeline Zoo, Datasets, Workspace session link, Notifications badge. Lab Directors: My Labs. Platform Admins: Admin.

**Lab Page:** Header (no sequencing lab — it belongs on samples not the lab header). Summary tiles. Projects list. Recent samples. Recent pipeline runs. Members (Lab Director only). Unassigned samples pool.

**Project Page:** Six tabs: Samples (bulk select, inline launch launchpad), Pipelines, Results (cross-sample pivot), Datasets, Collaborators, Activity. Pipeline launchpad is an inline dialog, not a separate page.

**Pipeline Zoo page:** Catalog with soft warnings (yellow, overridable) and hard blocks (red, explains requirement). "Launch for project..." not direct Launch. No graying out — all pipelines clickable.

**Global Search:** Full filter surface. Bulk select with select-all-N-results across pages. Selection persists across filter changes. Action bar splits for mixed-ownership selections. DISCOVERABLE samples show inline Request access button.

**Bulk select:** Same behavior everywhere samples appear. Master checkbox, select-all-N, persistent across filter changes, split action bar.

### 12. Workspace architecture

**JupyterHub on GKE** with Google OAuth shared with JACKPOT. Context injection when user clicks "Open in Workspace" — pod starts with API URL, token, project_id, lab_id pre-set.

Three spawner profiles:

- **Analyst**: Python + R + jackpot-sdk, 2 CPU/8GB, 1hr idle cull.
- **Bioinformatician**: JupyterLab + terminal + Nextflow + samtools + bcftools + jackpot-sdk, 4 CPU/16GB, 2hr idle cull.
- **Developer**: VS Code Server + full stack + jackpot-sdk, 4 CPU/16GB, longer idle timeout.

**One pod per user** regardless of project count. Context switches via environment variable update when "Open in Workspace" is clicked from a different project. Researcher can work across multiple projects in one pod using explicit Session(project_id=N) SDK calls. Named_server feature allows max 2 concurrent pods per user if genuinely needed (e.g. Analyst + Bioinf simultaneously).

**Workspace package management:**

- **Python**: pip install for session, ~/requirements.txt for persistence across sessions. Startup script installs from requirements.txt on pod launch. SDK: session.workspace.add_package("biopython==1.83") adds to requirements.txt and installs immediately.
- **Bioinformatics tools**: conda/mamba available in Bioinformatician profile. Named conda environments on PVC persist across sessions. Custom lab workspace image: Lab Director requests, Platform Admin builds and registers. Appears as additional spawner profile option for that lab.
- **R**: install.packages() / pak. ~/renv.lock on PVC, restored via renv::restore() at pod startup.

**jackpot-sdk** Python package pre-installed in all pods. Session class with samples, pipelines, datasets, sra, references, workspace modules. register_from_notebook() closes the loop back to JACKPOT. R equivalent package. Compute-target agnostic.

Sol HPC integration via batchspawner — Bioinformatician profile can spawn notebook kernel as Slurm job on Sol. Lower priority, ASU-specific.

### 13. Scrubber skip governance

Scrubber runs on all samples by default regardless of source type. A wastewater metagenome, a wildlife sample, and a human clinical sample all go through the scrubber unless a skip is explicitly approved. Skip requires Lab Director approval — sample-level override only, no org/lab-level policy.

scrub_status states: PENDING → IN_PROGRESS → COMPLETE/FAILED/SKIPPED. New state: PENDING_APPROVAL — triggered when ANY user requests to skip the scrubber on ANY sample type. Source type (human, animal, environmental, wastewater, etc.) is irrelevant to the skip approval workflow.

While PENDING_APPROVAL: record visible to lab members, files not downloadable, pipelines cannot launch. 48-hour auto-deny if Lab Director makes no decision — conservative default ensures scrubber is never silently bypassed.

Automatic exceptions (no Lab Director approval needed, SYSTEM logs reason):

- FASTA-only uploads detected by file_detector.py: scrub_status = SKIPPED, skip_reason = no_raw_reads (nothing for scrubber to process)
- SRA-imported samples: scrub_status = SKIPPED, skip_reason = sra_imported (NCBI has already processed these sequences)

### 14. Custom pipeline hierarchy

Three levels — project-pinned → lab-wide → zoo:

- project_pipelines: scoped to one project, only that project's launcher sees it.
- Promotion to lab: Lab Director promotes to lab_pipelines, all lab projects can use it. Promotion logged with source project and promoter.
- Promotion to zoo: Platform Admin review, formal requirements (nextflow_schema.json, public stable repo, documented parameters).

BYOP registration: Bioinformatician or Lab Director provides GitHub/GitLab URL + revision + parameter schema. Auto-detects nextflow_schema.json for nf-core pipelines. Custom badge distinguishes from zoo pipelines.

### 15. External data import — no local download required

Five mechanisms:

1. **Direct URI registration**: gs://, s3://, https:// — server-side copy job.
2. **NCBI/SRA/ENA accession fetch**: background GKE job via fasterq-dump/wget. sra:// URI in fastq_r1_uri resolved by pipeline executor on compute node.
3. **Workspace-to-platform promotion**: session.samples.register_from_workspace() copies PVC file to GCS via sidecar container.
4. **Signed URL direct-to-GCS**: browser/curl uploads directly to GCS for large local files, bypassing API server.
5. **Standard HTTP upload**: small local files via ingest form.

Reference genomes on lab-shared read-only GCS volume mounted in all pods at /ref/{org_slug}/{lab_slug}/. jackpot.references.download() SDK method.

SRA in pipeline context: sra:// URI resolved by fasterq-dump within Nextflow task on compute node. In workspace: session.sra.fetch() to personal PVC.

### 16. Dataset tiers and multi-lab approval

Personal (PRIVATE, My Work) → Project (LAB/DISCOVERABLE, Project page) → Global (global catalog). Promotion requires per-lab Lab Director approval (14-day passive) + Platform Admin final gate + cross-org Platform Admin for cross-org datasets. Dataset governance tab shows approval timeline.

### 17. Data deletion — staged lifecycle

Active → Archived → Soft-deleted → Hard-deleted. Tombstone record permanent.

| Action                              | Who requests    | Who approves              | Reversible    |
| ----------------------------------- | --------------- | ------------------------- | ------------- |
| Archive sample                      | Lab Director    | None                      | Yes           |
| Archive lab                         | Platform Admin  | None (documented)         | Yes           |
| Soft-delete (non-surveillance)      | Lab Director    | Platform Admin            | Yes (90 days) |
| Soft-delete (surveillance_relevant) | Lab Director    | PA + Governance Board     | Yes (90 days) |
| Hard-delete                         | Platform Admin  | Governance Board + 2nd PA | No            |
| Erroneous upload (≤72h)             | Submitting user | Lab Director              | Yes (90 days) |

72-hour fast-path erroneous upload. UI shows countdown. Tombstone: immutable, permanent, cannot be deleted. Pipeline results and audit records preserved after deletion.

### 18. Upload without project association

Lab is sufficient context for upload. Project optional at ingest. Unassigned samples pool on Lab page. Lab Directors can bulk-assign. Pipelines can launch on unassigned samples from Lab page. Datasets cannot be created from unassigned samples without first assigning to a project (soft enforcement).

### 19. DataHarmonizer tiered templates

Tiered templates: Tier 1 (~15 cols), Tier 2 (~20), Tier 3 (~35). Combined templates: "Tier 1, Human Clinical", "Tier 2, Wastewater", etc. Template definition YAML in jackpot-schema. Generator script at build time. Template version embedded in CSV. Old templates handled by harmonizer column mapping. Date precision auto-detected from format. surveillance_relevant read-only. skip_scrub field included. MAG fields excluded (pipeline-output, not user-entered). Offline form: progressive disclosure, date precision auto-detection.

### 20. File-to-sample association — researchers enter samples not files

One CSV row = one sample. File association is automatic, never per-file.

**file_detector.py** handles all pairing and naming conventions:

- Standard R1/R2, numeric 1/2, forward/reverse, multi-lane Illumina (L001_R1_001 etc.), nanopore chunks (barcode01_0.fq.gz etc.)
- Supported FASTQ extensions: .fastq, .fq + .gz/.bz2
- Supported FASTA extensions: .fasta, .fa, .fna + .gz

**GUI**: researcher drops all files at once. file_detector.py groups into samples and presents confirmation view. One metadata form row per detected sample group.

**CSV**: files column is semicolon-separated within a single cell: `AZ-001_R1.fastq.gz;AZ-001_R2.fastq.gz` or URIs. One CSV row per sample.

**CLI**: jackpot upload-dir scans directory, pairs files automatically, matches against --metadata-csv (one row per sample_id) or infers sample_id from filename stem.

**Globus**: deposit-first model — no pre-registration required. Files arrive, file_detector.py groups them into samples, draft records created. Researcher completes metadata via the notification-driven completion form. jackpot-cli upload-globus supports optional pre-registration for researchers who prefer to pre-match.

Sample_files table: canonical per-file registry. fastq_r1_uri/fastq_r2_uri are convenience fields for simple 2-file paired case only.

FASTA-only uploads: scrub_status = SKIPPED automatically (no raw reads).

### 21. jackpot-cli — fifth repository

`jackpot-cli` Python package, fifth repo alongside backend/frontend/schema/iac. Thin wrapper around the REST API (~300–400 lines). Commands:

```bash
jackpot config set --api-url ... --token ...
jackpot auth login          # OAuth browser flow, stores 1-year token
jackpot upload --r1 ... --r2 ... --organism ... --project 42
jackpot upload-dir /data/ --metadata-csv metadata.csv --project 42
jackpot upload-globus --metadata-csv ... --source-endpoint asu-sol \
    --source-path /scratch/ --project 42
jackpot samples list --project 42 --status PENDING
jackpot pipelines list --project 42
jackpot pipelines launch --pipeline viralrecon --project 42
```

upload-dir: auto-pairs files using file_detector.py logic, reports unmatched files, --metadata-csv provides per-sample metadata. Sample_id inferred from filename stem if not in CSV.

### 22. Globus integration — deposit-first (Option 2)

**University Globus subscription architecture.** The host university holds a Globus subscription (Plus or Standard). The Research Computing team installs and manages Globus Connect Server (GCS) v5. JACKPOT's GCS deployment registers under the university subscription. Two collections are created:

- **Staging collection**: mapped collection pointing at gs://jackpot-staging/{org_slug}/{lab_slug}/incoming/. Researchers and external sequencing labs transfer FASTQs here. Write-only for external parties. Read-write for lab members.
- **Results collection**: guest collection pointing at gs://jackpot-results/. Read-only. Allows lab members to pull pipeline outputs back to their HPC (e.g. Sol) via Globus without going through presigned URLs.

**External sequencing lab access.** Any lab (university genomics core, commercial facility, another institution) with a Globus endpoint can transfer directly to the JACKPOT staging collection. Two identity models:

- *Institutional identity*: sequencing lab authenticates via their own university SSO which Globus already knows. Platform Admin grants their Globus identity write-only access to the target lab's staging path.
- *Client credential*: for commercial labs without institutional Globus identity. Platform Admin creates a Globus client credential scoped to write-only on a specific lab's staging path. Shared out-of-band once. Revocable at any time.

Sequencing lab Globus access is managed via `sequencing_labs` table: `globus_identity_id` (their Globus identity or client credential ID), `globus_staging_path` (the path they can write to), `filename_pattern` (JSONB naming convention hints for file_detector.py).

**Globus Groups per lab.** Under the university subscription, Globus Groups mirror JACKPOT lab membership. Adding a user to a JACKPOT lab automatically adds their linked Globus identity to the corresponding Globus Group, granting transfer access without Platform Admin intervention.

**Identity mapping — users.** Each JACKPOT user can link their Globus identity to their account. During onboarding, a "Link Globus identity" button initiates a Globus Auth OAuth flow. JACKPOT stores the Globus identity UUID in `users.globus_identity_id`. Files deposited by an unlinked Globus identity go to a holding pool with Platform Admin notification.

**Deposit-first workflow (Option 2 — no pre-registration required).** Files arrive in staging collection without prior stub records:

```
External sequencing lab or researcher initiates Globus transfer
  → FASTQs land in jackpot-staging/{org}/{lab}/incoming/
  → Globus Flow fires webhook → POST /api/v1/ingest/globus-callback
  → file_detector.py groups files into samples using naming conventions
    (including sequencing_labs.filename_pattern for known facilities)
  → Draft sample records created: scrub_status=PENDING (ALL sample types),
    ingest_method=globus, quality_status=PRELIMINARY
  → Lab member notified: "17 files detected from Sonora Quest —
    8 samples grouped. Please review and complete metadata."
  → Researcher opens metadata completion form:
    sample_id pre-filled from filename stem
    read_type auto-detected from file pattern
    sequencing_lab pre-filled from depositing identity
    researcher adds organism, date_collected, source_type, sector, etc.
  → Researcher confirms → ingest gate pipeline triggers (scrub runs on all)
  → Samples available in JACKPOT
```

Key point: scrub_status = PENDING for ALL sample types in the deposit-first flow. PENDING_APPROVAL only arises if someone explicitly requests to skip the scrubber after the draft record is created.

**Globus Flows** (available under university subscription) replaces the polling fallback. Flow definition registered in jackpot-iac as JSON. Webhook authentication uses a shared secret registered during Flow setup.

**jackpot-cli upload-globus** still works for researchers initiating their own transfers: validates metadata CSV → optionally creates stubs for pre-matching → initiates Globus transfer from source endpoint → polls for completion → confirms ingest triggered. Pre-registration is optional — deposit-first matching is the fallback.

### 23. API token lifetime policy

- **API tokens** (long-lived, for CLI/SDK/scripts): default 1-year lifetime. Researcher can revoke at any time. Platform Admin can revoke any user's tokens. Scoped — separate tokens per use case (laptop, Sol, collaborator). Configurable per org via organizations.max_token_lifetime_days.
- **Signed upload URLs** (GCS direct write): default 4-hour lifetime. Single-use per file. Script requests new URL for remaining files if batch exceeds 4 hours (rare). Long enough to upload large files, short enough that leaked URLs can't be exploited indefinitely.
- **Globus transfer tokens**: managed by Globus, not JACKPOT. JACKPOT Globus endpoint credential doesn't expire.

### 24. Tuberculosis typing

TB typing is distinct from Salmonella/E. coli and needs a dedicated schema.

**Typing systems used simultaneously:**

- **Lineage classification**: Coll et al. and Napier et al. schemes (L1–L9 major lineages, sub-lineages based on SNPs). Primary epidemiological grouping.
- **Spoligotyping**: PCR-based, still widely used. WGS-derived in silico spoligotype stored. SIT number from SITVIT database.
- **MIRU-VNTR**: variable number tandem repeat typing, still in clinical use. In silico derivation from WGS supported.
- **WHO drug susceptibility catalogue**: mutation-based AMR for TB. WHO grades 1–5. Updated regularly. Isoniazid, rifampicin, ethambutol, pyrazinamide, fluoroquinolones, bedaquiline, linezolid, and others.
- **cgMLST + HierCC**: from EnteroBase TB database (DSMZ endpoint).

**New table: tb_typing_results** — lineage, lineage_coll, lineage_confidence, spoligotype_octal, spoligotype_binary, spoligotype_sit, miru_vntr_pattern, miru_vntr_mit_id, who_catalogue_version, drug_susceptibility JSONB (per-drug: prediction R/S/U, confidence, variants, who_grade), tool (tb-profiler/MTBseq), tool_version, analysis_date.

drug_susceptibility JSONB example:

```json
{
  "isoniazid": {"prediction": "R", "confidence": "high",
                "variants": ["katG p.Ser315Thr"], "who_grade": 1},
  "rifampicin": {"prediction": "S", "confidence": "high",
                 "variants": [], "who_grade": 5}
}
```

**tb-profiler** added to pipeline zoo (Month 2/3). Produces lineage, spoligotype, MIRU-VNTR, and WHO catalogue drug resistance from a single FASTQ input. Result registration populates tb_typing_results.

TB drug resistance results also populate amr_results (hAMRonization format) with resistance_mechanism=target_alteration and reference_database=WHO_catalogue so TB samples appear in platform-wide AMR searches.

EnteroBase TB federation uses DSMZ endpoint (enterobase.dsmz.de) — separate API configuration from Warwick endpoint used for Salmonella/E. coli.

### 25. External database search inside JACKPOT

Researchers search NCBI SRA, NCBI GenBank, ENA, and GISAID from within JACKPOT — no separate window or tab required.

**Search page second mode**: toggle between "JACKPOT samples" and "External databases". Database selector: NCBI SRA, GenBank, ENA, GISAID (if lab has credentials). JACKPOT backend acts as proxy — queries databases server-side via E-utilities API (NCBI), ENA REST API, GISAID API. Cross-database search queries selected databases in parallel, deduplicates by accession.

**Two query modes:**

- Simple form: organism (autocomplete from OrganismNameEnum), date range, country, sequencing platform, sequence type, free-text keyword. Covers 80% of use cases.
- Advanced query: native database syntax (SRA Entrez, ENA query language) behind "Advanced" toggle.

**Results table**: same bulk select behavior as internal search (checkboxes, select-all-N, action bar). Actions on external results: Import to JACKPOT, Add to dataset (reference without importing files), Open in source database (new tab). Import flow: full metadata fetch → preview panel with tier assessment → researcher supplements missing fields (e.g. sector) → confirm → background fetch jobs triggered → stub sample records created in JACKPOT.

**Result caching**: 30-minute server-side cache for repeated identical queries to avoid hammering external APIs.

**GISAID special case**: requires registered lab credentials stored (encrypted) in organizations table. Attribution reminder shown before import. GISAID samples imported with data_use_terms=controlled_access and sharing_level=LAB by default — can never be set to PUBLIC (terms of use). gisaid_accession (EPI_ISL_XXXXXXX) stored and always visible for attribution traceability. New field: organizations.gisaid_credentials (encrypted) or separate organization_credentials table for extensibility.

**New backend endpoint**: GET /api/v1/external-search/ — accepts database selection and query parameters, returns paginated results from external APIs.

### 26. BaseSpace integration — three-stage transition path

Many labs already use Illumina BaseSpace (Illumina's cloud platform where sequencing runs land immediately after a run completes on NextSeq, NovaSeq, or MiSeq). BaseSpace has native Globus support — runs can be automatically pushed to a registered Globus endpoint on completion. JACKPOT is built to be that endpoint, with a clear transition path from today's manual workflow to fully automated ingest.

**Stage 0 — Today (labs using BaseSpace manually).** Labs export a SampleSheet or run summary CSV from BaseSpace and import it into JACKPOT via the CSV ingest path. Files are downloaded from BaseSpace and uploaded to JACKPOT via standard HTTP, jackpot-cli, or signed URL. No Globus required. Stub work: BaseSpace SampleSheet format added as a recognized mapping config in harmonizer.py so column names are auto-mapped.

**Stage 1 — Near term (BaseSpace Globus push).** Lab configures their BaseSpace workspace to automatically push completed run FASTQs to the JACKPOT staging collection path for their lab. Files arrive via Globus. Deposit-first webhook triggers, file_detector.py groups using Illumina naming conventions, draft records created, researcher completes metadata. Researcher never downloads to workstation. Stub work: BaseSpace filename pattern stored in `sequencing_labs.filename_pattern` so file_detector.py reliably parses Illumina-specific names.

**Stage 2 — Future (BaseSpace API metadata pull).** When a BaseSpace Globus transfer arrives, JACKPOT optionally pulls run metadata from the BaseSpace API — sample name, index sequences, run parameters, demultiplexing statistics — to pre-populate draft sample records. Eliminates even the metadata completion step for fields BaseSpace already knows. Stub: `baseSpace_run_id` field on draft records, `BaseSpaceAPIClient` class that starts as a stub returning empty metadata, wired to real BaseSpace API when OAuth integration is built.

**Illumina BaseSpace filename convention** (standard FASTQ output):

```
{SampleName}_S{SampleNumber}_L{Lane}_R{Read}_001.fastq.gz
# e.g. AZ-2026-001_S1_L001_R1_001.fastq.gz
```

file_detector.py already handles multi-lane Illumina naming. The `sequencing_labs.filename_pattern` JSONB entry makes the parsing explicit:

```json
{
  "convention": "illumina_basespace",
  "pattern": "{sample_name}_S{sample_number}_L{lane}_R{read}_001.fastq.gz",
  "sample_id_field": "sample_name"
}
```

sample_name extracted from filename becomes sample_id in the draft record. A researcher who named samples `AZ-2026-001` in BaseSpace gets that ID automatically in JACKPOT without typing it.

**New schema fields:**

- `users.globus_identity_id` — Globus identity UUID, set during onboarding
- `users.globus_identity_linked_at` — timestamp of identity linking
- `sequencing_labs.globus_identity_id` — Globus identity or client credential
- `sequencing_labs.globus_staging_path` — staging collection path granted
- `sequencing_labs.filename_pattern` — JSONB naming convention hints
- `samples.basespace_run_id` — stub for future BaseSpace API metadata pull

### 27. GCP production architecture — corrected model

The CLAUDE.md description "PostgreSQL (local dev) / BigQuery (production)" was incorrect and has been corrected. The full mapping:

**Operational database**: PostgreSQL locally → Cloud SQL PostgreSQL in production. Alembic, SQLAlchemy, and all queries work identically against both. Transition is a connection string change. BigQuery is NOT a drop-in replacement for the operational database.

**Why BigQuery cannot replace Cloud SQL**: BigQuery is an analytical warehouse. It does not support row-level locking (required by access request approval), foreign key constraints (required by referential integrity), ACID transactions across multiple tables (required by audit log pattern), or efficient row-level UPDATEs/DELETEs (required by status update patterns).

**BigQuery role**: Separate analytical layer for surveillance dashboards, turnaround reporting, and population-level queries. Populated by a periodic ETL job from Cloud SQL. The FastAPI API never queries BigQuery directly. Month 3+ concern.

**Object storage**: MinIO locally → GCS in production. boto3 via `backend/storage.py` abstraction. STORAGE_BACKEND env var controls routing. This transition genuinely is an env var change.

**Background jobs**: APScheduler in-process locally (SCHEDULER_ENABLED=true) → Cloud Scheduler firing HTTP requests to the job trigger endpoint in GKE (SCHEDULER_ENABLED=false). Prevents multi-pod race conditions where N replicas each run the same job N times simultaneously. Job logic unchanged — only the trigger mechanism changes. Cloud Scheduler defined in jackpot-iac Terraform.

**Pipeline execution**: PIPELINE_EXECUTOR=local (shells to nextflow directly) → PIPELINE_EXECUTOR=gcp_batch (submits via GCP Batch Nextflow config). Nextflow -weblog callback works identically in both environments.

**Workspace**: No local equivalent. WORKSPACE_ENABLED=false in local dev returns 503. WORKSPACE_ENABLED=true in GKE activates JupyterHub launch.

**New env vars added to CLAUDE.md**:

- `SCHEDULER_ENABLED` — true locally, false in GKE
- `PIPELINE_EXECUTOR` — local or gcp_batch
- `WORKSPACE_ENABLED` — false locally, true in GKE

**sequencing_lab_assignments join table**: `sequencing_labs` (physical facilities) and `labs` (JACKPOT organizational units) are linked via a join table `sequencing_lab_assignments` (sequencing_lab_id, lab_id). One facility may serve multiple labs. Used by Globus deposit-first to identify which Lab Directors to notify when files arrive from a given facility. Added as Critical Rule 21 in CLAUDE.md.

### 28. Local development stack — Docker Compose + minikube hybrid

Docker Compose is the primary dev environment for all Month 1 and Month 2 backend/frontend work. Minikube is added in Month 2 specifically for JupyterHub workspace testing. The full stack is never migrated to minikube.

**Docker Compose services** (always running during development):

- `jackpot-backend` FastAPI API at localhost:8000
- `jackpot-frontend` Streamlit UI at localhost:8501
- `postgres` PostgreSQL at localhost:5432
- `minio` Object storage at localhost:9000 (API) / 9001 (console)

**Minikube** (Month 2 only, JupyterHub only):

- `minikube start --driver=docker --cpus=4 --memory=4096`
- Enable `ingress` and `gcp-auth` addons
- JupyterHub deployed via Helm chart
- `minikube tunnel` connects JupyterHub pods to Docker Compose API
- `kind` cluster added to jackpot-iac for CI testing of Kubernetes manifests

**Apple Silicon note**: Many bioinformatics containers are x86-only. When using `PIPELINE_EXECUTOR=local` on Apple Silicon, use `--platform linux/amd64` in the Nextflow process config. Prefer `PIPELINE_EXECUTOR=gcp_batch` for pipeline testing — GCP Batch VMs are x86 by default. Spot instances make this cheap for short test runs.

**Critical Rules added**: Rule 28 (minikube for JupyterHub only), Rule 29 (prefer gcp_batch on Apple Silicon).

### 29. Nextflow GCP Batch execution model

Mac is the Nextflow controller. Tasks run on GCP Batch VMs. Documented in CLAUDE.md with full config template and prerequisites.

**Key design decisions:**

Per-run GCS work directory: `gs://jackpot-work/{run_id}/work/`. Stored in `pipeline_runs.work_dir`. Required for `-resume`. Two runs must never share a workDir prefix.

JACKPOT Nextflow config is generated per-run by the launch endpoint — never a static file. Templated with run_id, API URL, weblog URL, result URL, pipeline token. Written to temp file, passed via `-c jackpot_run.config`.

`resourceLabels` (`jackpot_run_id`, `jackpot_lab`, `jackpot_pipeline`) on every GCP Batch job — required for GCP Billing cost attribution and JACKPOT's billing dashboard.

Weblog callback (`-weblog`) requires a publicly reachable URL when using `gcp_batch` executor. In production: deployed API URL. In local dev testing with gcp_batch: use `cloudflared tunnel` temporarily. Never commit tunnel URLs.

Spot instances (`google.batch.spot = true`) — ~90% cost saving, safe for JACKPOT pipelines because `-resume` recovers from preemptions.

`jackpot-work` GCS bucket has a 90-day lifecycle rule (defined in jackpot-iac) that deletes stale work directories from completed runs.

Result registration: pipeline's final step calls `POST /api/v1/pipelines/{run_id}/results` via curl. Added in JACKPOT pipeline wrapper, not in upstream nf-core pipelines.

Minimal test pipeline (`scripts/test_batch.nf`) verifies GCP Batch connectivity and weblog callback before the full launch endpoint is implemented.

**Critical Rules added**: Rule 25 (isolated workDir per run), Rule 26 (config generated per-run), Rule 27 (resourceLabels required).

### 30. GKE autoscaling architecture

Three workloads with fundamentally different scaling behaviors require three separate GKE node pools. Pipeline compute runs on GCP Batch entirely outside GKE — GKE only runs the lightweight Nextflow controller.

**Three node pools:**

`api-pool` — FastAPI, Streamlit, Nextflow controllers. n2-standard-4 (4CPU/16GB). min=2 (always on for availability), max=6. HPA on CPU utilization adds pods across existing nodes. Never scale-to-zero.

`workspace-pool` — JupyterHub user pods. n2-standard-8 (8CPU/32GB). min=0 (scale-to-zero), max=10. Scaling unit is nodes (cluster autoscaler), not pods. No pod-level HPA — each pod is personal to one researcher sized by profile. No spot — user-interactive, preemption unacceptable.

`scrubber-pool` — SRA Human Scrubber GKE Jobs. n2-highmem-4 (4CPU/32GB). min=0 (scale-to-zero), max=20. Spot/preemptible — scrubber is restartable. One GKE Job per scrubber invocation.

**GCP Batch** handles all Nextflow pipeline task compute. GKE only runs the Nextflow controller process (~2CPU/4GB) in the api-pool. Never submit pipeline tasks as GKE pods.

**Scrubber job queue — bulk upload concurrency control:** When 100 samples arrive via Globus batch, submitting 100 GKE Jobs simultaneously would spike cost. Instead, all pending scrubbers enter a database queue (scrub_status=PENDING). `run_scrubber_queue_job()` in `backend/jobs.py` fires every 60 seconds, checks IN_PROGRESS count, and promotes the next batch up to SCRUBBER_MAX_CONCURRENT (default=10) to IN_PROGRESS and submits their GKE Jobs. Runs via APScheduler locally, Cloud Scheduler in production.

**Workspace cold start mitigation:** Scale-to-zero causes 3–5 minute cold starts for the first workspace launch after inactivity. Two mitigations: (1) placeholder pod CronJob keeps one workspace-pool node warm 8am–8pm AZ time (low-priority pause container, evicted when real pod scheduled), (2) custom pre-cached node image reduces cold start to ~60–90 seconds.

**Cost controls:**

- Workspace idle timeouts (1hr Analyst, 2hr Bioinformatician)
- Pipeline spot instances (google.batch.spot=true, ~90% saving)
- Scrubber spot nodes (preemptible, restartable)
- Max 2 concurrent workspace pods per user (named_server)
- GCP Budget alerts at 50%/80%/100% (visibility, not hard cap)
- resourceLabels on all Batch jobs (per-lab, per-pipeline billing)
- 90-day lifecycle rule on jackpot-work bucket

**New env vars:** `SCRUBBER_MAX_CONCURRENT` (default=10), `SCRUBBER_QUEUE_INTERVAL_SECONDS` (default=60).

**Critical Rules added**: Rule 30 (pipeline compute on GCP Batch not GKE), Rule 31 (bulk scrubber uses queue), Rule 32 (scrubber Jobs on spot nodes).

### 31. Caching architecture — why JACKPOT avoids Celery and Redis

JACKPOT deliberately avoids Celery and Redis as a general-purpose task queue. Each APGAP Celery use case is handled by a GCP-native equivalent:

| APGAP pattern                 | JACKPOT replacement           |
| ----------------------------- | ----------------------------- |
| Celery for pipeline execution | GCP Batch + Nextflow          |
| Celery for scrubbing          | GKE Jobs + scrubber queue     |
| Celery for background jobs    | APScheduler / Cloud Scheduler |
| Celery for email delivery     | Cloud Tasks (when built)      |
| Celery for SRA downloads      | GKE Jobs                      |

**Redis IS used** — but only as a shared external search result cache (Cloud Memorystore for Redis) to solve the multi-pod in-memory cache inconsistency problem. Not used as a task broker, result backend, session store, or general-purpose cache.

**The problem without shared cache**: in multi-pod GKE deployments, each API replica has its own in-memory dict. A NCBI search that ran on pod A is re-executed on pod B, hammering external APIs unnecessarily. Cloud Memorystore Redis (same VPC as GKE, private IP) provides a shared 30-minute cache across all replicas for external search results only.

**Cache abstraction**: `backend/cache.py` with `get_cache()`, `cache_get()`, `cache_set()`, `cache_delete()`. Routes to Redis (production, `SEARCH_CACHE_BACKEND=redis`) or a simple dict (local dev, `SEARCH_CACHE_BACKEND=memory`). All external search caching goes through this module — never a raw dict in a router.

**Cloud Tasks for future email**: when email notifications are implemented, Cloud Tasks (not Celery) delivers tasks to a JACKPOT endpoint which calls SendGrid/SES. GCP-native, no broker to manage.

**New env vars**: `SEARCH_CACHE_BACKEND` (memory/redis), `REDIS_URL` (Cloud Memorystore private IP in GKE), `SEARCH_CACHE_TTL_SECONDS` (default 1800).

**IaC**: Cloud Memorystore Redis in jackpot-iac Terraform — Basic tier, 1GB, same VPC as GKE, no persistence (cache is ephemeral by design).

**Critical Rules added**: Rule 33 (no per-pod in-memory cache for shared data), Rule 34 (no Celery, no Redis as broker or result backend).

### 32. Disaster recovery and backup architecture

Every stateful component has a documented backup strategy. All backup configuration lives in jackpot-iac Terraform — never configured manually in the GCP console.

**Cloud SQL (most critical — three layers):**

Automated daily backups — full backup during 2–4am AZ window, 30-day retention, stored in GCS.

Point-in-time recovery (PITR) — continuous transaction log shipping, 7-day recovery window to any second. Always enabled. Primary defense against bad migrations. Before running any uncertain migration, note the exact timestamp so you know where to restore to.

Weekly SQL export — Cloud Scheduler exports full SQL dump to gs://jackpot-backups/ every Sunday. Independent recovery path. Bucket has Object Lock (WORM, 90 days) — tamper-proof, satisfies public health audit requirements. Bucket in different GCP region from primary.

Cross-region replica — deferred from prototype. Add when real production users on platform.

**GCS buckets — per-bucket policy:**

`jackpot-sequences`: versioning enabled (irreplaceable raw FASTQs). `jackpot-references`: versioning enabled (write-once reference genomes). `jackpot-results`: no versioning (regenerable by re-running pipelines). `jackpot-staging`: no versioning (temporary, moves to sequences after scrub). `jackpot-work`: no versioning — NEVER enable, would fight 90-day lifecycle rule and accumulate unbounded storage costs. `jackpot-backups`: Object Lock WORM, 90-day lifecycle, different region.

**GKE workspace PVCs:** daily snapshot via GCP Compute Engine snapshot schedule, 14-day retention. Defined in jackpot-iac/terraform/snapshots.tf. Allows recovery of accidentally deleted notebooks within 15 minutes.

**GKE cluster state:** not backed up separately — git IS the backup. All cluster state is in jackpot-iac Terraform and Kubernetes manifests. Never configure cluster resources manually in the GCP console.

**After any database restore:** always run `uv run alembic upgrade head` before starting the API. Check with `uv run alembic current`.

**Five documented recovery scenarios** in jackpot-iac/docs/disaster-recovery.md:

1. Accidental row deletion — PITR or versioning. RTO: 30 min.
2. Bad migration — PITR to pre-migration timestamp. RTO: 1–2 hours.
3. Cloud SQL instance failure — restore from daily backup. RTO: 2–4 hours.
4. Regional GCP outage — promote replica, redeploy from IaC. RTO: 4–8 hours.
5. GCS data loss — object versioning or SQL export restore. RTO: varies.

**New IaC files:** cloudsql.tf (backups, PITR, export scheduler), gcs.tf (versioning, Object Lock, lifecycle rules), snapshots.tf (PVC snapshots).

**Critical Rules added:** Rule 35 (never disable PITR), Rule 36 (alembic upgrade head after restore), Rule 37 (never manually configure GCS in console), Rule 38 (never enable versioning on jackpot-work).

### 33. Streamlit migration strategy

**Why Streamlit is right for the prototype:** A solo Python developer can build a functional web UI without JavaScript, HTML, or CSS. The gap between idea and working screen is small, and backend logic and UI can be iterated in the same Python session.

**Where Streamlit starts to hurt at scale:**

State management — Streamlit reruns the entire script on every interaction. Multi-step workflows (ingest flow: drag → detect → review → tier → confirm → track scrub) require fragile `st.session_state` management that becomes hard to reason about as the UI grows.

Real-time updates — pipeline monitoring needs live task progress from the Nextflow weblog event stream. Streamlit can poll with `st.rerun()` but true push-based updates (WebSockets, SSE) aren't natively supported. Polling feels choppy and wastes API calls.

Multi-user session isolation — each browser tab gets its own server-side Python process. Doesn't scale to 50+ concurrent researchers. Makes cross-session features (notification badges that update when someone approves your access request) genuinely difficult without an external layer.

Bulk operations and complex tables — bulk select with master checkbox, select-all-N-results persistent across filter changes, and split action bars require `st.components.v1.html()` injection, which means fighting the framework.

Custom layout — Streamlit's layout model breaks down for complex page designs (project page with six tabs and inline pipeline launchpad dialog, pipeline monitoring four-tab UI, sample detail with timeline view).

**When NOT to migrate:** If primary users are bioinformaticians and public health analysts who prioritize function over aesthetics, Streamlit is completely acceptable. Many production bioinformatics platforms run on Streamlit. The data matters more than pixel-perfect UI.

**Signal to reconsider:** When writing more `st.components.v1.html()` than `st.dataframe()` — that's when the framework is fighting you more than helping you.

**Natural migration path:**

- Month 1–2: prototype on Streamlit. Prove out all backend logic.
- Month 3+: if user feedback indicates UI is a genuine blocker, start building React frontend in `jackpot-frontend` repo talking to the same FastAPI API. Run Streamlit and React in parallel — Streamlit for admin/power users, React for the polished researcher-facing UI.
- Retire Streamlit when React covers all the same ground.

**Technical candidate:** React + shadcn/ui (component library) + TanStack Query (server state management). Covers table virtualization, real-time polling, complex multi-step forms, and notification system that Streamlit struggles with. Stays approachable for a Python developer learning frontend.

**Why migration is clean:** FastAPI backend knows nothing about the frontend. Swapping Streamlit for React is purely a frontend concern — backend, database, auth, and all business logic stay identical.

**What to do now:** Keep Streamlit code in `jackpot-frontend` organized by page module (one file per major page, `components/` directory for shared widgets). This 1:1 mapping of Streamlit page to React route makes a future migration less painful. No migration plan needed until Month 3+ user feedback provides a clear signal.

### 34. LLM support assistant architecture

A context-aware LLM support assistant for JACKPOT covering site orientation, how-to guidance, and data-specific support questions.

**Core pattern: RAG, not fine-tuning.** The LLM is never fine-tuned on JACKPOT data — documentation is the retrieval source. Answers stay current as docs change without retraining. Grounded in authoritative sources rather than model hallucination.

**Real-world precedent:** The PRIDE database at EBI built a directly comparable chatbot for their proteomics data repository — same use case (documentation Q&A + dataset search), same RAG architecture. Published in Proteomics (2024). https://www.ebi.ac.uk/pride/chatbot/

**Three use cases and what each requires:**

Site orientation ("how do I get started") — easiest case. Static docs knowledge base. Chunked markdown files embedded in a vector DB.

How-tos ("how do I upload a batch of samples") — requires context injection. The chat widget passes current_page, user_role, and lab_id in every request so the assistant gives role-appropriate answers. A Lab Director gets a different answer to "how do I approve a scrub skip?" than a Lab Collaborator.

Data-specific support ("why is my sample stuck") — requires tool-augmented RAG. The LLM calls read-only JACKPOT API endpoints to retrieve live data. The assistant inherits the logged-in user's permissions — never a privileged service account.

**Two implementation levels:**

Level 1 (Year 2, early) — Documentation RAG. Vector DB of chunked JACKPOT docs. No live data access. Covers orientation and how-to questions. Vector store: pgvector extension in existing Cloud SQL (no new infra).

Level 2 (Year 2, later) — Tool-augmented RAG. LLM given access to curated read-only API endpoints as tools. Same access control as the API. Covers data-specific questions. Never give the assistant write access.

**Chat API endpoint:** `POST /api/v1/assistant/chat` — accepts message + context (current_page, user_role, lab_id). Context injected by frontend automatically. Response includes answer + source citations.

**Model choice:** Default: Anthropic API (claude-haiku-4-5) — cheapest, fastest, sufficient for documentation Q&A. Same vendor as the rest of the platform. Alternative: Local model via Ollama (Llama 3.1 8B or Mistral 7B on GKE GPU node) if data sensitivity requires on-prem processing.

**Hallucination controls (mandatory in every system prompt):**

- Grounded responses only — never use general LLM knowledge, only retrieved context. If no context found, say so and direct to support.
- Source citations — every answer cites which document section it came from.
- Explicit capability boundary — JACKPOT features and workflows only. Never clinical interpretation, pathogen advice, or surveillance commentary.
- Role-scoped tool access (Level 2) — tool calls authenticated with the user's session token, not a privileged service account.

**UI placement:** Slide-out help panel from every page via "Help" button in nav bar. Opens without leaving current page. Never full-page navigation.

**Knowledge base:** JACKPOT user guide (to be written), pipeline docs, metadata tier explanations, DataHarmonizer templates, governance policy summaries, role descriptions, FAQ. CLAUDE.md is a developer guide — not included in user-facing knowledge base.

**Implementation order:**

1. Write good user documentation (Month 1–3) — assistant quality depends entirely on documentation quality.
2. Level 1 documentation RAG (Year 2, early) — vector DB, chat endpoint, UI widget. Covers orientation and how-to.
3. Level 2 tool-augmented RAG (Year 2, later) — data-specific support.

**New env vars:** ASSISTANT_ENABLED (false until Year 2), ASSISTANT_BACKEND (anthropic/ollama), ASSISTANT_MODEL, OLLAMA_ENDPOINT, ASSISTANT_VECTOR_DB (pgvector/chroma), ASSISTANT_MAX_CHUNKS (5), ASSISTANT_CACHE_TTL (3600).

------

## To-Do List — ordered for execution

### Immediate (before next Claude Code session)

1. **Apply schema v4.2** — run update_schema_v4_2.py in jackpot-schema, commit, push to main.
2. **Update submodule pointer in jackpot-backend** — git submodule update --remote schema, commit.
3. **Regenerate models** — gen-pydantic and gen-json-schema from updated schema.
4. **Write Alembic migration for v4.2 columns + new tables** — ALTER TABLE for all new BaseSample columns. New tables: reportable_organisms, sample_access_requests, sample_scrub_override_requests, deletion_requests, deleted_samples (tombstone), tb_typing_results, sequencing_lab_assignments (sequencing_lab_id FK, lab_id FK — join table linking physical sequencing facilities to JACKPOT labs for Globus deposit-first notification routing). New columns on organizations: has_oversight_access, default_sharing_level, access_request_grace_days, access_requests_enabled, access_policy_note, max_token_lifetime_days, gisaid_credentials (encrypted). New columns on samples: is_deleted, deleted_at, deletion_stage, basespace_run_id. New columns on users: globus_identity_id, globus_identity_linked_at. New columns on sequencing_labs: globus_identity_id, globus_staging_path, filename_pattern JSONB.
5. **Seed reportable_organisms table** — ADHS mandatory reportable communicable diseases list.
6. **Rewrite validator.py** — tier-aware ValidationResult, compute_surveillance_relevant(), validate_surveillance_relevant(), date_collected_precision handling, FASTA-only auto-skip detection.
7. **Update tests/test_validator.py** — tier computation, year-only dates, case_id on non-human samples, surveillance_relevant defaults, metagenomics target_organisms logic.
8. **Update docs/CLAUDE.md** — tier-aware validation, new BaseSample fields, surveillance_relevant logic, scrub skip workflow, file-to-sample association principle.
9. **Write DataHarmonizer template generator** — template definition YAML in jackpot-schema, Python script producing one JSON Schema per template combination at build time. Add to schema build step.
10. **Update offline metadata form** — progressive disclosure (Tier 1 default, expandable), date precision auto-detection, skip_scrub field, files column as semicolon-separated list.
11. **Write JACKPOT Nextflow config template and test pipeline** — create `backend/pipeline_config.py` with a `generate_nextflow_config(run_id, pipeline_name, pipeline_executor, lab_slug, jackpot_api_url, pipeline_token)` function that returns the templated config string. Create `scripts/test_batch.nf` minimal pipeline that verifies GCP Batch connectivity and weblog callback. Verify end-to-end: config generated → nextflow run scripts/test_batch.nf -c jackpot_run.config -weblog http://localhost:8000/api/v1/pipelines/events → event received by API. This must be done before the pipeline launch endpoint is implemented.
12. **Create jackpot-work GCS bucket with lifecycle rule** — in jackpot-iac Terraform: create gs://jackpot-work-dev (development) and gs://jackpot-work (production) buckets in us-central1. Apply lifecycle rule: delete objects older than 90 days. Never delete work directories manually — breaks -resume for in-flight runs.

### Month 1 — Core data layer (Claude Code sessions)

1. **Implement POST /api/v1/ingest/upload** — first Claude Code task. Multipart form, tier-aware validate, FASTA-only scrub-skip, compute surveillance_relevant, file_detector.py pairing, stage to MinIO, epiweek, write samples + sample_files, log audit.
2. **Implement signed URL direct-to-GCS upload** — POST /api/v1/ingest/signed-url issues GCS signed URL, POST /api/v1/ingest/signed-url/{id}/complete confirms.
3. **Implement URI registration** — POST /api/v1/ingest/uri validates accessibility, records URI, optional server-side copy job.
4. **Implement SRA/accession import** — POST /api/v1/ingest/accession, NCBI E-utilities metadata fetch, background GKE fasterq-dump job, sra:// URI scheme.
5. **Implement workspace-to-platform promotion** — jackpot-sdk register_from_workspace() copies PVC to GCS via sidecar container.
6. **Implement POST /api/v1/ingest/csv** — harmonize, bulk tier-aware validate, semicolon-delimited files column.
7. **Implement scrub override request workflow** — PENDING_APPROVAL status, Lab Director notification, 48-hour auto-deny job, FASTA-only SYSTEM auto-approve.
8. **Implement GET /api/v1/samples/** — search with can_see_sample(), all filters, bulk-select-compatible (select-all-N-results).
9. **Implement GET/PATCH /api/v1/samples/{sample_id}** — with can_access_sample().
10. **Implement can_access_sample() and can_see_sample()** in guards.py.
11. **Implement org, lab, project, user management endpoints** — all existing stubs with org policy fields.
12. **Implement sample_access_requests endpoints + background job** — four notification events, 75-day and 7-day warnings.
13. **Implement reference_genomes table and API** — seed with common genomes, lab-shared GCS bucket.
14. **Build frontend/pages/upload.py** — drag-and-drop, metadata form, tier badge, year-only date, file group confirmation view ("Detected 200 samples — 3 warnings. Confirm?"), all upload mechanisms, scrub-skip request flow, 72-hour erroneous upload countdown.
15. **Build frontend/pages/search.py** — filter sidebar (sector, tier, surveillance_relevant, AMR, typing, external databases), bulk select with select-all-N, persistent selection, split action bar, external database search mode (NCBI/SRA/ENA/GISAID), DISCOVERABLE inline Request access button.
16. **Build personal dashboard** — My Activity, My Active Work, My Projects, Quick Actions.
17. **Build Lab page** — summary tiles (no sequencing lab in header), projects list, recent samples and runs, unassigned samples pool, bulk assign to project.
18. **Build Project page** — six tabs, bulk select on Samples tab, inline pipeline launchpad dialog, cross-sample pivot on Results tab.
19. **Implement GET /api/v1/external-search/** — proxy to NCBI E-utilities, ENA REST API, GISAID API. Results cached via backend/cache.py (30-minute TTL). Cross-database deduplication by accession.

29a. **Write backend/cache.py** — cache abstraction with cache_get(), cache_set(), cache_delete(). SEARCH_CACHE_BACKEND=memory routes to in-memory dict (local dev). SEARCH_CACHE_BACKEND=redis routes to Cloud Memorystore (GKE). Must be written before external search endpoint.

1. **Implement Globus integration (Option 2 — deposit-first)** — Register GCS staging bucket as Globus endpoint under university subscription. Create staging collection (write-only for external parties) and results collection (read-only for lab members). Implement POST /api/v1/ingest/globus-callback webhook with Globus shared-secret authentication. file_detector.py runs on arriving files using sequencing_labs.filename_pattern conventions. Draft sample records created with scrub_status=PENDING (ALL sample types), ingest_method=globus. Notification sent to lab members: metadata completion required. Implement user Globus identity linking flow (GET /api/v1/auth/globus/link). Implement sequencing lab Globus provisioning endpoint: POST /api/v1/admin/sequencing-labs/{id}/provision-globus — creates Globus path grant and stores credential reference. Add Globus Flows definition to jackpot-iac. Add BaseSpace SampleSheet mapping config to harmonizer.py (Stage 0 stub). Add BaseSpaceAPIClient stub class (Stage 2 stub). Add basespace_run_id field to draft record creation path.

### Month 2 — Pipelines, workspace, access control UI

1. **Add pipeline schema tables** — pipeline_catalog, pipeline_runs, pipeline_tasks, pipeline_events, pipeline_restarts, pipeline_results, pipeline_files, project_pipelines, lab_pipelines. Alembic migration.
2. **Implement pipeline launch** — POST /api/v1/pipelines/launch, Nextflow -weblog, GCP Batch, compatibility check (soft warning vs. hard block).
3. **Implement pipeline event ingestion** — POST /api/v1/pipelines/events.
4. **Implement pipeline monitoring endpoints** — run detail, tasks, events, result registration, presigned file URLs.
5. **Implement pipeline -resume** — POST /api/v1/pipelines/{run_id}/resume.
6. **Implement BYOP registration** — POST /api/v1/pipelines/custom. project_pipelines and lab_pipelines tables.
7. **Implement pipeline promotion** — POST /api/v1/pipelines/{id}/promote, project→lab (Lab Director), lab→zoo (Platform Admin). Logged.
8. **Seed pipeline zoo** — GHRU assembly, nf-core/viralrecon, nf-core/mag, nf-core/taxprofiler, nf-core/funcscan, tb-profiler.
9. **Build pipelines frontend** — Zoo catalog page, four-tab run monitoring, Resume button, BYOP registration form, promote button.
10. **Deploy JupyterHub on GKE** — Helm chart, Google OAuth, PVC provisioner, idle culler, three spawner profiles, context injection, custom lab image support, named_server (max 2 concurrent pods), ~/requirements.txt startup script, ~/renv.lock R restore.
11. **Set up local minikube workspace environment** — minikube with Docker driver (--cpus=4 --memory=4096). Enable ingress and gcp-auth addons. Deploy JupyterHub Helm chart to minikube. Configure minikube tunnel so JupyterHub pods can reach FastAPI running in Docker Compose. Add minikube setup guide and manifests to jackpot-iac. Add kind cluster config for CI testing of Kubernetes manifests. Note: Docker Compose remains the primary dev environment — minikube is for JupyterHub only. Apple Silicon: use --platform linux/amd64 for x86-only bioinformatics containers or use GCP Batch for pipeline test runs even during local dev.
12. **Write GKE node pool Terraform in jackpot-iac** — three node pools: api-pool (n2-standard-4, min=2 max=6, HPA for FastAPI/Streamlit), workspace-pool (n2-standard-8, min=0 max=10, scale-to-zero, no spot), scrubber-pool (n2-highmem-4, min=0 max=20, scale-to-zero, spot). Cluster autoscaler on all three. Workspace placeholder pod CronJob (8am–8pm AZ). Scrubber GKE Job template manifest. GCP Budget alerts at 50%/80%/100%. All resourceLabels on Batch jobs. jackpot-work bucket lifecycle rule (90 days).
13. **Implement scrubber job queue in backend/jobs.py** — run_scrubber_queue_job() checks IN_PROGRESS count against SCRUBBER_MAX_CONCURRENT env var (default=10), promotes next PENDING samples to IN_PROGRESS, submits GKE Jobs for each. Fires every SCRUBBER_QUEUE_INTERVAL_SECONDS (default=60) via APScheduler locally and Cloud Scheduler in production. Handles spot node preemption: if a scrubber Job fails due to preemption, sample stays IN_PROGRESS and is resubmitted on the next queue cycle.
14. **Build jackpot-sdk** — Python package in new jackpot-sdk repo (or jackpot-cli repo): Session, samples, pipelines, datasets, sra, references, workspace modules. register_from_notebook(), register_from_workspace(), session.workspace.add_package(), jackpot.references.download(). R equivalent. Pre-installed in all pods.
15. **Build jackpot-cli** — new jackpot-cli repo. Commands: config set, auth login, upload, upload-dir, upload-globus, samples list, pipelines list, pipelines launch. 1-year API token stored in ~/.jackpot/config. upload-dir uses file_detector.py pairing, --metadata-csv, filename stem inference. upload-globus: validates → creates stubs → initiates transfer → polls completion.
16. **Implement workspace launch endpoint** — POST /api/v1/workspaces/launch, mints short-lived workspace token, returns spawn URL with context params. Open in Workspace button on project, dataset, pipeline result pages.
17. **Implement API token management** — GET/POST/DELETE /api/v1/tokens/, 1-year default, organizations.max_token_lifetime_days per-org policy.
18. **Build frontend/pages/access_requests.py** — incoming queue (Lab Directors), outgoing status, scrub skip queue, erroneous upload fast-path.
19. **Build frontend/pages/lab_director.py** — member management, project management, custom pipeline management, promote-to-lab button.
20. **Build frontend/pages/platform_admin.py** — unified dashboard: org management (with policy fields and Globus/GISAID credentials), user management, domain whitelist, sequencing lab registry, audit log, governance override queue, reportable organism management, pipeline zoo management, deletion request queue, lab departure workflow, reference genome management, workspace/custom image management.

### Month 3 — AMR, typing, datasets, submissions, deletion

1. **Add AMR results schema (hAMRonization)** — amr_results table with full genomic context fields.
2. **Add typing results schema** — typing_results + tb_typing_results. Alembic migration.
3. **Wire AMR, typing, and TB result ingestion** from pipeline result registration. tb-profiler results populate both tb_typing_results and amr_results (WHO_catalogue reference_database).
4. **Implement deletion workflow** — staged lifecycle, tombstone, 72-hour fast-path, background GCS lifecycle job, lab departure DEPARTING status.
5. **Implement dataset tiers and promotion workflow** — personal/project/ global, per-lab approval chain, Platform Admin final gate, cross-org PA approval, Dataset governance tab.
6. **Implement dataset endpoints** — create, manage, share, publish, promote.
7. **Implement Microreact export** — GET /api/v1/datasets/{id}/export/microreact.
8. **Build NCBI submission frontend** — Tier 3 only.
9. **Build GISAID export frontend** — gisaid_export.py. Backend implemented.
10. **Implement notifications** — all key events: skip_scrub requested/decided, surveillance override, deletion request, dataset promotion, erroneous upload fast-path expiring, TB drug resistance flag, turnaround benchmark missed, Globus transfer complete.

### Ongoing / cross-cutting

1. **Reportable organisms admin UI** — no code deployment needed to update.
2. **Surveillance override governance workflow UI** — governance board notification and approve/deny.
3. **Turnaround dashboard** — Rockefeller KPIs per lab and platform-wide.
4. **Pipeline resource analytics** — CPU/memory/wall time by process, pipeline, lab, date.
5. **Dataset governance tab** — visual approval timeline on dataset detail.
6. **TB EnteroBase federation** — DSMZ endpoint (enterobase.dsmz.de), separate API configuration from Warwick endpoint.
7. **Write disaster recovery IaC and runbook** — jackpot-iac/terraform/: cloudsql.tf backup config (daily backups, PITR, weekly export scheduler, jackpot-backups bucket with Object Lock and 90-day lifecycle), gcs.tf versioning config (versioning on jackpot-sequences and jackpot-references, never on jackpot-work), snapshots.tf (PVC daily snapshot schedule, 14-day retention). Write jackpot-iac/docs/disaster-recovery.md with all 5 recovery scenarios and expected RTOs. Must be complete before platform goes into production.
8. **Signed URL direct-to-GCS** — for large local file uploads.
9. **External database search caching** — 30-minute server-side cache, rate limiting to avoid external API abuse.

### Future / Year 2

1. Visual pipeline builder (nf-core module graph → Nextflow DSL)
2. Seqera Platform API integration
3. AI-assisted natural language search and query
4. Metagenomic orchestration layer — chain mag + taxprofiler + funcscan with JACKPOT-native MAG-to-sample linkage, cross-pipeline result aggregation, and surveillance_relevant recomputation (nf-core/mag standalone is already in Month 2 zoo — this is the orchestration layer)
5. Phylocanvas tree viewer integration
6. EnteroBase cgMLST/HierCC federation for Salmonella/E. coli (Warwick)
7. Hub-and-spoke multi-instance federation
8. Snakemake/WDL/CWL pipeline engine support
9. Sol HPC batchspawner integration
10. GISAID EpiFlu and EpiPox support (currently EpiCoV only)
11. **LLM support assistant — Level 1 (documentation RAG)** — pgvector extension on Cloud SQL, documentation chunking and embedding pipeline (Cloud Scheduler job triggered on doc updates), POST /api/v1/assistant/chat endpoint with context injection (current_page, user_role, lab_id), slide-out help panel UI widget. Anthropic API (claude-haiku-4-5) as default backend, Ollama as alternative. System prompt with mandatory hallucination controls: grounded responses only, source citations, explicit capability boundary. ASSISTANT_ENABLED env var (false until deployed). Knowledge base: user guide, pipeline docs, metadata tier docs, governance summaries, role descriptions, FAQ.
12. **LLM support assistant — Level 2 (tool-augmented RAG)** — extend Level 1 with read-only JACKPOT API tool use. LLM can call GET /api/v1/samples/{id}, GET /api/v1/pipelines/{id}/status, and other read-only endpoints on behalf of the logged-in user. Tool calls authenticated with user session token — never a privileged service account. Covers data-specific questions ("why is my sample stuck?").
13. **React frontend migration** — replace Streamlit with React + shadcn/ui + TanStack Query when user feedback indicates Streamlit is a genuine blocker, OR when writing more `st.components.v1.html()` than `st.dataframe()`. Migration path: build React in `jackpot-frontend` repo, run Streamlit and React in parallel, retire Streamlit when React covers all the same ground. FastAPI backend requires zero changes. Preparatory work now: keep Streamlit organized by page module (one file per major page, `components/` directory for shared widgets) so each Streamlit page maps 1:1 to a future React route.

------

------

# JACKPOT Feature Backlog

Last updated: April 2026 (session 2 — final pre-coding revision) Status: Living document. Prioritization in the To-Do List above.

------

## How to read this table

**Feature** — the user-facing capability **Area** — system area **Schema changes** — new tables, columns, or LinkML additions **Backend** — FastAPI endpoints, business logic, background jobs **Frontend** — Streamlit pages or components **Notes** — constraints, dependencies, decisions

------

## Schema (apply before Month 1 coding)

| Feature                               | Area   | Schema changes                                               | Backend                                                      | Frontend                                              | Notes                                                        |
| ------------------------------------- | ------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ----------------------------------------------------- | ------------------------------------------------------------ |
| Apply schema v4.2                     | Schema | Run update_schema_v4_2.py — 22 changes including case_id to BaseSample, sector, surveillance_relevant, quality_status, date_collected_precision, read_type, assembly_type, MAG QC, provenance, turnaround timestamps | Alembic migration: all new columns on samples                | none                                                  | Prerequisite for all Month 1 work. Script validated.         |
| Reportable organisms table            | Schema | New table: reportable_organisms (organism_name PK, reporting_jurisdiction, effective_date, notes) | Seed ADHS list. GET/POST/DELETE /api/v1/admin/reportable-organisms/ | platform_admin.py                                     | DB-managed. Drives surveillance_relevant default.            |
| Sample access requests table          | Schema | New table: sample_access_requests (full lifecycle cols, auto_approve_after, access_expires_at) | Background job: 90-day auto-approve, 75-day warning, expire grants, mark moot | access_requests.py                                    | 90-day passive approval.                                     |
| Sample scrub override requests table  | Schema | New table: sample_scrub_override_requests (sample_id, requested_by_id, request_reason, status, auto_deny_after) | Background job: 48-hour auto-deny                            | upload.py — skip scrub request flow                   | Lab Director approval required. FASTA-only = SYSTEM auto-approve. |
| Deletion workflow tables              | Schema | samples: is_deleted, deleted_at, deletion_stage. New: deletion_requests, deleted_samples (tombstone — immutable) | Staged lifecycle backend, GCS lifecycle job                  | platform_admin.py — deletion queue                    | Tombstone permanent. Audit records preserved.                |
| Organization policy fields            | Schema | organizations: has_oversight_access, default_sharing_level, access_request_grace_days, access_requests_enabled, access_policy_note, max_token_lifetime_days, gisaid_credentials (encrypted) | PATCH /api/v1/organizations/{id}                             | platform_admin.py                                     | Three profiles: ADHS, academic, partner PH.                  |
| Reference genomes table               | Schema | New table: reference_genomes (organism_name, accession, fasta_uri, genome_version, added_by_id) | GET/POST/DELETE /api/v1/admin/reference-genomes/. Lab-shared GCS bucket /ref/{org}/{lab}/ | platform_admin.py                                     | Fed into pipeline parameter dropdowns.                       |
| Project and lab pipeline tables       | Schema | New tables: project_pipelines, lab_pipelines (both: source_pipeline_id, name, parameter_overrides JSONB, version, created_by_id) | GET/POST/PATCH/DELETE for both. POST /api/v1/pipelines/{id}/promote | pipelines.py, lab_director.py                         | Three-level hierarchy: project → lab → zoo.                  |
| TB typing table                       | Schema | New table: tb_typing_results (lineage, lineage_coll, spoligotype_octal, spoligotype_binary, spoligotype_sit, miru_vntr_pattern, miru_vntr_mit_id, who_catalogue_version, drug_susceptibility JSONB, tool, tool_version, analysis_date) | Alembic migration                                            | none                                                  | TB-specific. TB AMR also populates generic amr_results for platform-wide search. |
| Globus identity fields                | Schema | users: globus_identity_id, globus_identity_linked_at. sequencing_labs: globus_identity_id, globus_staging_path, filename_pattern JSONB. samples: basespace_run_id (stub). | Alembic migration                                            | none                                                  | Enables deposit-first Globus ingest and future BaseSpace API pull. |
| sequencing_lab_assignments join table | Schema | New table: sequencing_lab_assignments (sequencing_lab_id FK, lab_id FK, created_at, created_by_id) | Alembic migration. GET /api/v1/admin/sequencing-labs/{id}/labs — list lab assignments. POST/DELETE to manage assignments. | platform_admin.py — sequencing lab assignments editor | Links physical sequencing facilities to JACKPOT labs. One facility may serve multiple labs. Used by Globus deposit-first workflow to identify Lab Directors to notify when files arrive. |

------

## Core Data Platform

| Feature                                  | Area    | Schema changes                                               | Backend                                                      | Frontend                                                     | Notes                                                        |
| ---------------------------------------- | ------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Sample ingest — standard upload          | Ingest  | none                                                         | POST /api/v1/ingest/upload — tier-aware validate, FASTA-only scrub-skip, file_detector.py pairing, compute surveillance_relevant, stage to MinIO, epiweek, write samples + sample_files, log audit | upload.py — drag-and-drop, metadata form, tier badge, file group confirmation ("Detected 200 samples — 3 warnings"), 72h erroneous countdown | First Claude Code task. One row per sample, files auto-paired. |
| Sample ingest — signed URL direct-to-GCS | Ingest  | none                                                         | POST /api/v1/ingest/signed-url issues URL (4-hour TTL). POST /api/v1/ingest/signed-url/{id}/complete confirms. | upload.py — large file tab                                   | Browser/curl uploads directly to GCS. API polls for completion. |
| Sample ingest — URI registration         | Ingest  | none                                                         | POST /api/v1/ingest/uri — HEAD validates, records URI, optional server-side copy job | upload.py — "From cloud URI" tab                             | gs://, s3://, https://. No local transit.                    |
| Sample ingest — SRA/accession import     | Ingest  | ingest_method: sra_import, ena_import                        | POST /api/v1/ingest/accession — E-utilities metadata fetch, preview, background GKE fasterq-dump. sra:// URI in fastq_r1_uri | upload.py — accession lookup with metadata preview + tier assessment | No local download. scrub_status=SKIPPED default (sra_imported). |
| Sample ingest — workspace promotion      | Ingest  | ingest_method: workspace_promotion                           | jackpot-sdk register_from_workspace() — PVC to GCS via sidecar | none (SDK only)                                              | Server-side. No local transit.                               |
| Sample ingest — CSV batch                | Ingest  | none                                                         | POST /api/v1/ingest/csv — harmonize, bulk tier-aware validate, semicolon-delimited files column | upload.py — CSV tab, per-row tier display                    | One row per sample. files column: `R1.fastq.gz;R2.fastq.gz` or URIs. |
| Sample ingest — Globus (deposit-first)   | Ingest  | ingest_method: globus. users.globus_identity_id. sequencing_labs.globus_identity_id/staging_path/filename_pattern. samples.basespace_run_id | POST /api/v1/ingest/globus-callback — webhook with shared-secret auth. file_detector.py groups arriving files using filename_pattern convention hints. Draft sample records created: scrub_status=PENDING (ALL sample types), ingest_method=globus. Notification to lab members. Metadata completion endpoint. | upload.py — Globus tab showing pending metadata completions, completion form with pre-filled fields | No pre-registration required. External sequencing labs (including BaseSpace) transfer directly to staging collection. Illumina BaseSpace filename convention recognized via sequencing_labs.filename_pattern. Stage 0 BaseSpace: harmonizer.py SampleSheet mapping config. Stage 2 BaseSpace: BaseSpaceAPIClient stub for future API metadata pull. |
| Tier-aware validator                     | Ingest  | none                                                         | Rewrite validator.py — ValidationResult gains tier, tier2_missing, tier3_missing, compute_surveillance_relevant(), date precision handling, FASTA-only auto-skip | none                                                         | Year-only and month-only dates accepted at Tier 1/2.         |
| Scrubber skip governance                 | Ingest  | sample_scrub_override_requests table                         | PENDING_APPROVAL status, Lab Director notification, 48-hour auto-deny, FASTA-only SYSTEM auto-approve | upload.py — skip request with justification field            | No org/lab default policy. Sample-level only.                |
| Sample search and filtering              | Samples | none                                                         | GET /api/v1/samples/ — can_see_sample(), all filters including sector, surveillance_relevant, quality_status, AMR, typing cluster | search.py — full filter sidebar, tier badges, bulk select with select-all-N, persistent selection, split action bar |                                                              |
| Sample detail view                       | Samples | none                                                         | GET /api/v1/samples/{sample_id} — can_access_sample(), full record + all results + turnaround metrics | search.py + detail panel                                     |                                                              |
| Sample edit                              | Samples | none                                                         | PATCH /api/v1/samples/{sample_id} — re-compute tier and surveillance_relevant, log audit | data_entry.py                                                | Lab Director and above.                                      |
| My samples dashboard                     | Samples | none                                                         | GET /api/v1/samples/?owner=me                                | my_samples.py — tier badges                                  |                                                              |
| Bulk select / deselect                   | UX      | none                                                         | All sample table endpoints support select-all-N              | search.py + all sample tables — master checkbox, select-all-N, persistent across filters, split action bar | Same behavior everywhere.                                    |
| Metadata harmonizer                      | Ingest  | none                                                         | harmonizer.py wired to CSV ingest                            | upload.py — mapping config selector                          |                                                              |

------

## External Database Search

| Feature                             | Area     | Schema changes                               | Backend                                                      | Frontend                                                     | Notes                                                        |
| ----------------------------------- | -------- | -------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| External database search            | Search   | organizations.gisaid_credentials             | GET /api/v1/external-search/ — proxy to NCBI E-utilities, ENA REST, GISAID API. Results cached via backend/cache.py (30-minute TTL, SEARCH_CACHE_BACKEND env var). Cross-database deduplication. | search.py — toggle "JACKPOT samples" / "External databases". Simple form + Advanced query toggle. Database selector. | Inside JACKPOT, no separate window needed. Cache shared across all API pod replicas via Cloud Memorystore Redis in GKE. |
| Import from external search         | Ingest   | none                                         | Full metadata fetch on selection → preview panel with tier assessment → confirm → background fetch jobs → stub sample records | search.py — Import button on external results, metadata supplement panel | Same bulk select as internal samples.                        |
| GISAID search                       | Search   | organizations.gisaid_credentials (encrypted) | GISAID API client using org credentials                      | search.py — GISAID option in database selector               | Attribution reminder before import. Imported samples: data_use_terms=controlled_access, sharing_level=LAB, cannot be PUBLIC. |
| Add to dataset (external reference) | Datasets | none                                         | POST /api/v1/datasets/ with external accession reference — no file import | search.py — "Add to dataset" action on external results      | Links to external accession without importing files.         |

------

## Access Control and Data Governance

| Feature                                 | Area       | Schema changes                                               | Backend                                                      | Frontend                                                     | Notes                                                        |
| --------------------------------------- | ---------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| can_access_sample() / can_see_sample()  | Auth       | none                                                         | backend/auth/guards.py — single source of truth              | none                                                         | Platform Admin → lab member → PUBLIC → oversight (surveillance_relevant=TRUE) → approved request. |
| Oversight authority access              | Auth       | organizations.has_oversight_access                           | is_oversight_authority resolved from org + role in get_current_user() | none                                                         | ADHS Lab Directors and Bioinformatics Users. Scoped to surveillance_relevant=TRUE only. |
| Surveillance relevance logic            | Governance | reportable_organisms table                                   | compute_surveillance_relevant(), validate_surveillance_relevant(), post-pipeline recompute for metagenomics, governance board workflow | platform_admin.py — governance override queue                | Organism-driven default.                                     |
| Sample access request workflow          | Access     | sample_access_requests table                                 | POST/GET/PATCH/DELETE /api/v1/sample-access/. Background job. Four notification events. | access_requests.py — incoming queue, outgoing status, 90-day countdown | Configurable per org.                                        |
| Deletion lifecycle                      | Governance | deletion_requests, deleted_samples, samples.is_deleted/deleted_at/deletion_stage | Staged archive→soft-delete→hard-delete. Three-party hard-delete. Lab departure DEPARTING status. Background GCS lifecycle job. 72h fast-path. | platform_admin.py — deletion queue, approval chain UI        | Tombstone immutable. Audit records preserved.                |
| Dataset governance — multi-lab approval | Datasets   | none                                                         | Per-lab Lab Director + PA final gate + cross-org PA. 14-day passive approval. | datasets.py — governance tab with visual approval timeline   |                                                              |
| API token management                    | Auth       | none                                                         | GET/POST/DELETE /api/v1/tokens/. 1-year default. organizations.max_token_lifetime_days. | platform_admin.py or user settings                           | For CLI, SDK, bash scripts. Revocable.                       |
| Audit log                               | Governance | none                                                         | log_audit() on all state transitions                         | platform_admin.py — filterable audit log                     | Immutable.                                                   |

------

## UX — Pages and Navigation

| Feature            | Area | Schema changes                  | Backend                                             | Frontend                                                     | Notes                                    |
| ------------------ | ---- | ------------------------------- | --------------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------- |
| Personal dashboard | UX   | none                            | GET /api/v1/dashboard/                              | dashboard.py — My Activity, My Active Work, My Projects, Quick Actions | Login landing page.                      |
| Lab page           | UX   | labs.status enum adds DEPARTING | GET /api/v1/labs/{id}/summary                       | lab_page.py — summary tiles (no sequencing lab in header), projects, recent samples/runs, unassigned samples pool, bulk assign to project |                                          |
| Project page       | UX   | none                            | GET /api/v1/projects/{id}/summary                   | project_page.py — six tabs: Samples, Pipelines, Results, Datasets, Collaborators, Activity | Pipeline launchpad inline dialog.        |
| Pipeline Zoo page  | UX   | none                            | GET /api/v1/pipelines/catalog                       | pipelines.py — soft warnings (yellow, overridable, logged), hard blocks (red, explains requirement), "Launch for project...", BYOP registration | No graying out. All pipelines clickable. |
| Global Search page | UX   | none                            | GET /api/v1/samples/ + GET /api/v1/external-search/ | search.py — internal + external database search modes, full filters, bulk select |                                          |
| Global Navigation  | UX   | none                            | none                                                | Persistent: Dashboard, Search, Pipeline Zoo, Datasets, Workspace session link, Notifications. Lab Directors: My Labs. Platform Admins: Admin. |                                          |

------

## Organizations, Labs, Projects, Users

| Feature                                       | Area       | Schema changes                                               | Backend                                                      | Frontend                                                     | Notes                                                        |
| --------------------------------------------- | ---------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Organization management                       | Admin      | org policy + credentials fields                              | GET/POST/PATCH /api/v1/organizations/ — includes policy editing, GISAID credentials | platform_admin.py                                            | Three org profiles.                                          |
| Lab management                                | Admin      | none                                                         | GET/POST/PATCH /api/v1/labs/                                 | platform_admin.py                                            |                                                              |
| Lab membership management                     | Labs       | none                                                         | GET/POST/DELETE /api/v1/labs/{id}/members/                   | lab_director.py                                              | is_lab_director flag.                                        |
| Project management                            | Projects   | none                                                         | GET/POST/PATCH /api/v1/projects/                             | lab_director.py + project_page.py                            | Upload without project is valid.                             |
| User management                               | Admin      | none                                                         | GET/POST/PATCH /api/v1/users/                                | platform_admin.py                                            | No self-registration.                                        |
| Domain whitelist                              | Admin      | none                                                         | GET/POST/DELETE /api/v1/domain-whitelist/                    | platform_admin.py                                            |                                                              |
| Sequencing lab registry + Globus provisioning | Labs       | sequencing_labs: globus_identity_id, globus_staging_path, filename_pattern JSONB | GET/POST/PATCH /api/v1/sequencing-labs/. POST /api/v1/admin/sequencing-labs/{id}/provision-globus — creates Globus path grant, stores credential, adds lab to Globus Group. Credential rotation job. | platform_admin.py — sequencing lab list with Globus status badge, provision button, filename pattern editor | External sequencing labs (BaseSpace, university cores, commercial) get write-only access to specific lab staging paths. Two identity models: institutional Globus identity or client credential. |
| Reportable organism management                | Admin      | reportable_organisms table                                   | GET/POST/DELETE /api/v1/admin/reportable-organisms/          | platform_admin.py                                            | No code deployment needed.                                   |
| Governance override queue                     | Governance | surveillance override fields                                 | GET/POST /api/v1/admin/surveillance-overrides/               | platform_admin.py                                            | TRUE→FALSE override approval.                                |
| Lab departure workflow                        | Admin      | labs.status: DEPARTING                                       | PATCH /api/v1/labs/{id}/status — freezes uploads, notifies members, 90-day wind-down → auto-archive | platform_admin.py                                            | Archived data stays indefinitely unless deletion explicitly requested. |

------

## Authentication

| Feature                 | Area   | Schema changes                                            | Backend                                                      | Frontend                           | Notes                                                        |
| ----------------------- | ------ | --------------------------------------------------------- | ------------------------------------------------------------ | ---------------------------------- | ------------------------------------------------------------ |
| Google OAuth login      | Auth   | none                                                      | POST /api/v1/auth/google/login — implemented                 | Login page                         | Production only.                                             |
| JWT token refresh       | Auth   | none                                                      | POST /api/v1/auth/refresh                                    | Transparent                        |                                                              |
| API token management    | Auth   | none                                                      | GET/POST/DELETE /api/v1/tokens/ — 1-year default, per-org max_token_lifetime_days | platform_admin.py or user settings | Long-lived for CLI/SDK/bash scripts.                         |
| Dataset access grants   | Access | none                                                      | GET/POST/DELETE /api/v1/dataset-access/                      | datasets.py                        | Presigned URLs for external collaborators. No raw FASTQ.     |
| Globus identity linking | Auth   | users.globus_identity_id, users.globus_identity_linked_at | GET /api/v1/auth/globus/link — initiates Globus Auth OAuth flow, stores returned Globus identity UUID. GET /api/v1/auth/globus/unlink — removes stored identity. | User settings / onboarding prompt  | Encouraged but not mandatory on first login. Unlinked identities that deposit files go to holding pool with Platform Admin notification. |

------

## Workspace

| Feature                              | Area      | Schema changes | Backend                                                      | Frontend                                                     | Notes                                                        |
| ------------------------------------ | --------- | -------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| JupyterHub on GKE                    | Workspace | none           | Helm chart, Google OAuth, PVC provisioner, idle culler, three spawner profiles, ~/requirements.txt startup script, ~/renv.lock R restore, named_server (max 2 concurrent pods) | none (infra)                                                 | Analyst (2CPU/8GB/1hr), Bioinformatician (4CPU/16GB/2hr), Developer (VS Code/4CPU/16GB). |
| Custom lab workspace image           | Workspace | none           | Platform Admin builds and registers lab-specific Docker image extending base Bioinformatician image | platform_admin.py — workspace image management               | Appears as additional spawner profile for that lab.          |
| Context injection                    | Workspace | none           | POST /api/v1/workspaces/launch — validates access, mints short-lived workspace token, returns spawn URL with context params (API URL, token, project_id, lab_id) | "Open in Workspace" button on project, dataset, pipeline result pages | Single pod per user. Context updates on project switch.      |
| jackpot-sdk                          | Workspace | none           | New jackpot-sdk repo (or jackpot-cli repo). Session class with samples, pipelines, datasets, sra, references, workspace modules. register_from_notebook(), register_from_workspace(), add_package(), references.download(). R equivalent. | Pre-installed in all pods                                    | Compute-target agnostic.                                     |
| jackpot-cli                          | Workspace | none           | New jackpot-cli repo. Commands: config set, auth login (1-year token), upload, upload-dir (file_detector pairing, --metadata-csv, filename stem inference), upload-globus, samples list, pipelines list/launch | pip install jackpot-cli                                      | Thin REST API wrapper. Enables bash script bulk uploads.     |
| Workspace session management         | Workspace | none           | GET /api/v1/workspaces/, DELETE /api/v1/workspaces/{id}      | Global nav — active session link, session manager dropdown   |                                                              |
| Sol HPC integration                  | Workspace | none           | batchspawner config for Slurm job spawning                   | Spawner profile option                                       | ASU-specific. Lower priority.                                |
| Globus endpoint infrastructure       | Workspace | none           | jackpot-iac: GCS v5 deployment under university subscription, mapped staging collection (/incoming/ per lab), guest results collection (read-only). Globus Groups per lab mirroring JACKPOT lab membership. Globus Flows definition registered. Credential rotation job for external sequencing lab client credentials. | none (infra)                                                 | Coordinate with university Research Computing team early — they control GCS v5 install and subscription. |
| Local minikube workspace environment | Workspace | none           | jackpot-iac: minikube setup guide and manifests for local JupyterHub testing. minikube start --driver=docker --cpus=4 --memory=4096. Enable ingress and gcp-auth addons. JupyterHub Helm chart deployed to minikube. minikube tunnel connects JupyterHub to FastAPI running in Docker Compose. | none (infra)                                                 | Added in Month 2 when workspace work begins. Docker Compose remains primary dev environment for all Month 1 work. minikube is for JupyterHub only — do not migrate the full stack. Apple Silicon note: nf-core and bioinformatics tool containers are often x86-only — use --platform linux/amd64 in local Nextflow config or use GCP Batch for pipeline test runs even in dev. kind cluster added to jackpot-iac for CI testing of Kubernetes manifests. |

------

## Local Dev Infrastructure

| Feature                                         | Area    | Schema changes | Backend                                                      | Frontend | Notes                                                        |
| ----------------------------------------------- | ------- | -------------- | ------------------------------------------------------------ | -------- | ------------------------------------------------------------ |
| Docker Compose primary dev stack                | Infra   | none           | none                                                         | none     | Services: jackpot-backend (8000), jackpot-frontend (8501), postgres (5432), minio (9000/9001). Primary environment for all Month 1 and Month 2 backend/frontend work. Never migrate full stack to minikube. |
| Minikube JupyterHub local environment           | Infra   | none           | jackpot-iac: minikube manifests and setup guide. minikube start --driver=docker --cpus=4 --memory=4096. Enable ingress and gcp-auth addons. JupyterHub Helm chart with values.yaml. minikube tunnel for Docker Compose API connectivity. kind cluster for CI Kubernetes manifest testing. | none     | Month 2 only. Mirrors production topology: JupyterHub and API as separate services. Apple Silicon: prefer gcp_batch for pipelines — GCP Batch VMs are x86 by default. |
| Nextflow local + GCP Batch dev setup            | Infra   | none           | brew install openjdk@17. curl -s https://get.nextflow.io \| bash. gcloud auth application-default login. Enable batch.googleapis.com and compute.googleapis.com. One-time setup documented in jackpot-iac. PIPELINE_EXECUTOR env var controls local vs gcp_batch. cloudflared tunnel for weblog callbacks during local gcp_batch testing. | none     | Prerequisites for pipeline launch endpoint work.             |
| GKE node pool definitions                       | Infra   | none           | jackpot-iac Terraform: api-pool (n2-standard-4, min=2 max=6, no spot), workspace-pool (n2-standard-8, min=0 max=10, no spot, scale-to-zero), scrubber-pool (n2-highmem-4, min=0 max=20, spot/preemptible, scale-to-zero). Cluster autoscaler on all pools. | none     | Three pools required — one per workload type. Never mix workloads across pools. |
| HPA for API and frontend                        | Infra   | none           | jackpot-iac: HPA manifest targeting CPU utilization for FastAPI and Streamlit deployments in api-pool. Min replicas=2 for availability. | none     | Standard Kubernetes HPA. api-pool never scales to zero.      |
| Workspace placeholder pod CronJob               | Infra   | none           | jackpot-iac: Kubernetes CronJob that creates a low-priority pause container in workspace-pool 8am–8pm AZ time. Evicted when real workspace pod scheduled. Prevents 3–5 minute cold starts during business hours. | none     | Simplest cold start mitigation. Pre-cached node image (60–90s) is the second mitigation. |
| Scrubber GKE Job template                       | Infra   | none           | jackpot-iac: GKE Job manifest template for SRA Human Scrubber. nodeSelector for scrubber-pool. Toleration for spot nodes. Restartable — preemption leaves sample IN_PROGRESS, queue job resubmits. | none     | One Job per scrubber invocation. Never run scrubber as a Deployment. |
| Scrubber job queue                              | Backend | none           | backend/jobs.py — run_scrubber_queue_job() fires every SCRUBBER_QUEUE_INTERVAL_SECONDS (default=60). Checks IN_PROGRESS count against SCRUBBER_MAX_CONCURRENT (default=10). Promotes next PENDING samples to IN_PROGRESS and submits GKE Jobs. APScheduler locally, Cloud Scheduler in production. | none     | Critical for bulk Globus uploads. Without queue, 100 simultaneous samples would submit 100 GKE Jobs spiking cost unpredictably. |
| GCP Budget alerts                               | Infra   | none           | jackpot-iac Terraform: GCP Budget resource with alerts at 50%/80%/100% of monthly budget. Email notification to Platform Admin. Not a hard cap — visibility only. | none     |                                                              |
| Cloud Memorystore Redis (external search cache) | Infra   | none           | jackpot-iac Terraform: Cloud Memorystore Redis instance — Basic tier, 1GB, same VPC as GKE cluster, private IP only, no persistence. Used exclusively for external search result caching across API pod replicas. REDIS_URL env var in GKE. | none     | Not a general-purpose cache. Not a task broker. External search results only. |
| backend/cache.py — cache abstraction            | Backend | none           | backend/cache.py with cache_get(), cache_set(), cache_delete(), get_cache(). Routes to Redis (SEARCH_CACHE_BACKEND=redis) or in-memory dict (SEARCH_CACHE_BACKEND=memory). All external search caching goes through this module — never a raw dict in a router. | none     | Must be written before external search endpoint. Critical Rules 33–34. |
| Cloud SQL backup configuration                  | Infra   | none           | jackpot-iac/terraform/cloudsql.tf: automated daily backups (2–4am AZ, 30-day retention), PITR enabled, weekly SQL export to jackpot-backups via Cloud Scheduler. | none     | PITR is always-on requirement. Critical Rule 35.             |
| GCS bucket versioning and Object Lock           | Infra   | none           | jackpot-iac/terraform/gcs.tf: versioning on jackpot-sequences and jackpot-references. Object Lock (WORM, 90 days) on jackpot-backups. Lifecycle rules on jackpot-work (90 days) and jackpot-backups (90 days). Never versioning on jackpot-work. | none     | Critical Rules 37–38.                                        |
| GKE PVC daily snapshot schedule                 | Infra   | none           | jackpot-iac/terraform/snapshots.tf: GCP Compute Engine snapshot schedule for JupyterHub workspace PVCs. Daily snapshots, 14-day retention. Enables 15-minute recovery of accidentally deleted notebooks. | none     | Applies to active PVCs only. Idle PVCs snapshotted on demand before deletion. |
| Disaster recovery runbook                       | Infra   | none           | jackpot-iac/docs/disaster-recovery.md: documented recovery procedures for all 5 scenarios — accidental deletion, bad migration, instance failure, regional outage, GCS data loss. Expected RTOs documented for each. | none     | Must be written before platform goes into production.        |

------

## Pipeline Zoo

| Feature                             | Area      | Schema changes                                               | Backend                                                      | Frontend                                                     | Notes                                                        |
| ----------------------------------- | --------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Nextflow config template generator  | Pipelines | none                                                         | backend/pipeline_config.py — generate_nextflow_config() returns templated config string per run. Fields: run_id, pipeline_name, pipeline_version, pipeline_executor, lab_slug, gcp_project_id, gcp_region, jackpot_api_url, pipeline_token. Includes resourceLabels, spot=true, per-run workDir, weblog URL, results URL. Written to temp file, passed via -c flag. | none                                                         | Must be written before launch endpoint. Never a static config file. Critical Rules 25–27. |
| Minimal GCP Batch test pipeline     | Pipelines | none                                                         | scripts/test_batch.nf — verifies GCP Batch connectivity, weblog callback, and result registration before full launch endpoint implementation. Run manually during pipeline dev setup. | none                                                         | Prerequisite for pipeline launch endpoint work.              |
| jackpot-work GCS bucket + lifecycle | Infra     | none                                                         | jackpot-iac Terraform: gs://jackpot-work-dev and gs://jackpot-work buckets in us-central1. 90-day lifecycle rule on both. resourceLabels on all Batch jobs for billing attribution. | none                                                         | One-time IaC task. Do not manually delete work dirs — breaks -resume. |
| Pipeline catalog schema             | Pipelines | pipeline_catalog, project_pipelines, lab_pipelines           | Seed data migration                                          | none                                                         | Three-level hierarchy.                                       |
| Pipeline launch                     | Pipelines | pipeline_runs, pipeline_tasks, pipeline_events, pipeline_restarts | POST /api/v1/pipelines/launch — Nextflow -weblog, GCP Batch, work_dir stored, compatibility check | pipelines.py — inline launchpad dialog in Project Pipelines tab |                                                              |
| Pipeline compatibility check        | Pipelines | none                                                         | compute_pipeline_compatibility() — soft_warnings and hard_blocks | Launchpad — yellow overridable badges (override logged), red badges with specific missing requirement | No graying out.                                              |
| Real-time event ingestion           | Pipelines | pipeline_events                                              | POST /api/v1/pipelines/events                                | none                                                         | No auth — run_id in path.                                    |
| Pipeline monitoring                 | Pipelines | none                                                         | GET /api/v1/pipelines/{run_id} + /tasks + /events            | pipelines.py — four tabs: Overview, Tasks, Events, Files     |                                                              |
| Pipeline resume                     | Pipelines | pipeline_restarts                                            | POST /api/v1/pipelines/{run_id}/resume                       | pipelines.py — Resume button                                 |                                                              |
| Pipeline result registration        | Pipelines | pipeline_results, pipeline_files                             | POST /api/v1/pipelines/{run_id}/results — triggers surveillance_relevant recompute for metagenomics | none                                                         |                                                              |
| Pipeline result viewing             | Pipelines | none                                                         | GET /api/v1/pipelines/{run_id}/results + /files              | pipelines.py — metrics, MultiQC iframe, downloads            |                                                              |
| Pipeline resource analytics         | Pipelines | none                                                         | GET /api/v1/pipelines/analytics                              | pipelines.py — charts                                        | Cost optimization.                                           |
| BYOP registration                   | Pipelines | project_pipelines                                            | POST /api/v1/pipelines/custom — GitHub/GitLab URL + revision + parameter schema | pipelines.py — BYOP form                                     | Auto-detects nextflow_schema.json. Custom badge.             |
| Pipeline promotion                  | Pipelines | lab_pipelines                                                | POST /api/v1/pipelines/{id}/promote — project→lab (Lab Director), lab→zoo (Platform Admin). Logged. | lab_director.py, platform_admin.py                           |                                                              |
| Initial zoo seed data               | Pipelines | pipeline_catalog rows                                        | GHRU assembly, nf-core/viralrecon, nf-core/mag, nf-core/taxprofiler, nf-core/funcscan, tb-profiler | none                                                         | Six pipelines.                                               |
| Turnaround dashboard                | Analytics | none                                                         | Queries turnaround timestamps vs. Rockefeller benchmarks     | platform_admin.py or dedicated dashboard                     |                                                              |

------

## AMR Analysis

| Feature                            | Area | Schema changes                                               | Backend                              | Frontend                                       | Notes                                                        |
| ---------------------------------- | ---- | ------------------------------------------------------------ | ------------------------------------ | ---------------------------------------------- | ------------------------------------------------------------ |
| AMR results schema (hAMRonization) | AMR  | New table: amr_results — full hAMRonization fields + genomic context (replicon_type, mobile_element, contig_id, positions) | Alembic migration                    | none                                           | TB AMR populates this table with reference_database=WHO_catalogue. |
| AMR result ingestion               | AMR  | amr_results                                                  | POST /api/v1/samples/{sample_id}/amr | none                                           | From pipeline result registration.                           |
| AMR result viewing                 | AMR  | none                                                         | GET /api/v1/samples/{sample_id}/amr  | Sample detail — S/I/R badges, replicon context |                                                              |
| AMR filtering in search            | AMR  | none                                                         | Extend GET /api/v1/samples/          | search.py — AMR filter panel                   |                                                              |

------

## Genomic Typing

| Feature                  | Area   | Schema changes                                               | Backend                                          | Frontend                                                     | Notes                                                        |
| ------------------------ | ------ | ------------------------------------------------------------ | ------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Typing results schema    | Typing | New table: typing_results (scheme, st, allele_profile JSONB, hiercc_levels JSONB, tool, tool_version) | Alembic migration                                | none                                                         | Covers MLST, cgMLST, wgMLST for all organisms.               |
| TB typing results schema | Typing | tb_typing_results table (see Schema section)                 | Alembic migration                                | none                                                         | lineage, spoligotype, MIRU-VNTR, WHO drug susceptibility JSONB. |
| Typing result ingestion  | Typing | typing_results                                               | POST /api/v1/samples/{sample_id}/typing          | none                                                         | tb-profiler results also populate tb_typing_results.         |
| Typing result viewing    | Typing | none                                                         | GET /api/v1/samples/{sample_id}/typing           | Sample detail — ST badge, HierCC codes, TB lineage and drug resistance |                                                              |
| Cluster-based search     | Typing | none                                                         | GET /api/v1/samples/?hiercc_level=HC5&cluster=42 | search.py — cluster filter                                   | Outbreak investigation.                                      |

------

## Datasets and Sharing

| Feature                      | Area     | Schema changes                           | Backend                                                      | Frontend                                                   | Notes                                                        |
| ---------------------------- | -------- | ---------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------- | ------------------------------------------------------------ |
| Dataset tiers                | Datasets | datasets.scope (personal/project/global) | POST /api/v1/datasets/                                       | datasets.py — tier badges, promotion button                | Personal=PRIVATE in My Work. Project=LAB in Project page. Global=global catalog. |
| Dataset promotion workflow   | Datasets | none                                     | POST /api/v1/datasets/{id}/promote — per-lab Director approval + PA final gate + cross-org PA. 14-day passive. | datasets.py — governance tab with visual approval timeline |                                                              |
| Dataset management           | Datasets | none                                     | GET/PATCH/DELETE /api/v1/datasets/                           | datasets.py                                                |                                                              |
| External collaborator access | Datasets | none                                     | POST /api/v1/dataset-access/ — presigned package             | datasets.py — share dialog                                 | No raw FASTQ.                                                |
| Public dataset publishing    | Datasets | none                                     | PATCH /api/v1/datasets/{id}                                  | datasets.py                                                | Raw files protected regardless.                              |
| Microreact export            | Datasets | none                                     | GET /api/v1/datasets/{id}/export/microreact                  | datasets.py — "View in Microreact" button                  |                                                              |

------

## Metadata Tooling

| Feature                         | Area   | Schema changes                             | Backend                                                      | Frontend                                                     | Notes                                                        |
| ------------------------------- | ------ | ------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| DataHarmonizer tiered templates | Schema | Template definition YAML in jackpot-schema | Template generator script at build time — one JSON Schema per combined template. Template version in CSV. | DataHarmonizer configured with combined templates            | T1 (~15 cols), T2 (~20), T3 (~35). Date precision auto-detected. surveillance_relevant read-only. files column semicolon-delimited. MAG fields excluded. |
| Offline metadata form update    | Ingest | none                                       | none                                                         | Offline HTML form — progressive disclosure, date precision auto-detection, files column |                                                              |
| Old template compatibility      | Ingest | none                                       | harmonizer.py column mapping for pre-v4.2 CSV                | none                                                         | Missing fields get defaults + validation warning.            |

------

## Submissions

| Feature                         | Area        | Schema changes | Backend                                     | Frontend            | Notes                         |
| ------------------------------- | ----------- | -------------- | ------------------------------------------- | ------------------- | ----------------------------- |
| NCBI BioSample / SRA submission | Submissions | none           | POST /api/v1/ncbi-submissions/ via TOSTADAS | ncbi_submission.py  | Tier 3 (SUBMITTABLE) only.    |
| GISAID EpiCoV export            | Submissions | none           | Already implemented                         | gisaid_export.py    | Frontend stub needs building. |
| Archive request management      | Archive     | none           | GET/POST/PATCH /api/v1/archive-requests/    | archive_requests.py |                               |

------

## Notifications

| Feature              | Area          | Schema changes | Backend                                                      | Frontend                                 | Notes              |
| -------------------- | ------------- | -------------- | ------------------------------------------------------------ | ---------------------------------------- | ------------------ |
| In-app notifications | Notifications | none           | GET /api/v1/notifications/. All events including: scrub skip requested/decided, surveillance override, deletion lifecycle, dataset promotion, erroneous upload expiring, TB drug resistance flagged, Globus transfer complete, external import complete, turnaround benchmark missed | notifications.py + notification_badge.py |                    |
| Email notifications  | Notifications | none           | Worker via SendGrid or SES                                   | none                                     | User-configurable. |

------

## Platform Administration

| Feature                  | Area    | Schema changes | Backend                                 | Frontend                                                     | Notes                                                        |
| ------------------------ | ------- | -------------- | --------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Platform admin dashboard | Admin   | none           | All admin endpoints                     | platform_admin.py — unified: orgs (with GISAID credentials), users, domain whitelist, sequencing labs, audit log, governance queue, reportable organisms, pipeline zoo, deletion queue, lab departure, reference genomes, workspace images, external search credentials |                                                              |
| Billing and usage        | Billing | none           | GET /api/v1/billing/                    | billing.py                                                   | GCP Batch + GCS + workspace compute + Globus transfer costs. |
| Audit log viewer         | Admin   | none           | GET /api/v1/audit-log/                  | platform_admin.py                                            | Immutable.                                                   |
| Saved searches           | Search  | none           | GET/POST/DELETE /api/v1/saved-searches/ | search.py                                                    | Per-user. Applies to both JACKPOT and external database searches. |

------

## Future / Year 2

| Feature                                      | Area        | Schema changes                                               | Backend                                                      | Frontend                                                     | Notes                                                        |
| -------------------------------------------- | ----------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Visual pipeline builder                      | Pipelines   | pipeline_templates, steps, params tables                     | Nextflow DSL generator from nf-core module graph             | Visual DAG editor                                            | 4–6 months solo. Data-flo adaptor model is reference.        |
| Snakemake / WDL / CWL support                | Pipelines   | pipeline_catalog.workflow_engine                             | Execution adapter per engine                                 | none                                                         | Add when specific request justifies it.                      |
| Seqera Platform API integration              | Pipelines   | none                                                         | Seqera API adapter                                           | Optional toggle                                              | Schema supports via workspace_id/compute_env_id.             |
| AI-assisted search                           | Search      | none                                                         | NLP query parser, vector embeddings, LLM result interpretation | Natural language search bar                                  | Third major differentiator.                                  |
| Metagenomic orchestration layer              | Pipelines   | none beyond existing                                         | Chain mag + taxprofiler + funcscan with MAG-to-sample linkage, cross-pipeline result aggregation, surveillance_relevant recompute (nf-core/mag standalone is already in Month 2 zoo — this is the orchestration layer on top) | Metagenomics project mode                                    | No existing platform models this.                            |
| Phylocanvas tree viewer                      | Analysis    | phylogenetic_trees table                                     | POST /api/v1/datasets/{id}/trees                             | Embedded Phylocanvas viewer                                  | MIT license.                                                 |
| EnteroBase federation — Salmonella/E. coli   | Typing      | none                                                         | EnteroBase API client (Warwick endpoint)                     | "Look up in EnteroBase" link                                 | 1.7M public strains for context.                             |
| EnteroBase federation — TB                   | Typing      | none                                                         | EnteroBase TB API client (DSMZ endpoint, enterobase.dsmz.de) | "Look up in EnteroBase" link on TB samples                   | Separate API config from Warwick.                            |
| Hub-and-spoke federation                     | Platform    | none                                                         | Multi-instance de-identified data sharing                    | none                                                         | IPSN-aligned. Rockefeller hub model.                         |
| Sol HPC batchspawner                         | Workspace   | none                                                         | batchspawner config                                          | Spawner profile option                                       | ASU-specific.                                                |
| GISAID EpiFlu and EpiPox                     | Submissions | none                                                         | Extend GISAID router and export for influenza and mpox schemas | gisaid_export.py — pathogen selector                         | Currently EpiCoV only.                                       |
| LLM assistant — Level 1 (documentation RAG)  | AI/UX       | assistant_queries log table, pgvector extension on Cloud SQL | POST /api/v1/assistant/chat — embed query, retrieve top-k chunks, call LLM API with system context + retrieved chunks, return response + citations. Doc embedding pipeline (chunker + embedder + upsert). ASSISTANT_ENABLED, ASSISTANT_BACKEND, ASSISTANT_MODEL, ASSISTANT_VECTOR_DB, ASSISTANT_MAX_CHUNKS, ASSISTANT_CACHE_TTL env vars. | Slide-out help panel in nav, chat widget with message history and source citation display. | Covers orientation and how-to questions. No live data access. PRIDE/EBI chatbot is direct precedent. Write user docs first — assistant quality depends on doc quality. |
| LLM assistant — Level 2 (tool-augmented RAG) | AI/UX       | none beyond Level 1                                          | Extend chat endpoint with tool definitions for read-only API endpoints. LLM decides when to call tools vs. retrieve docs. Tool calls use user session token — never service account. Covers data-specific questions. | none beyond Level 1                                          | Never give assistant write access. Level 2 only after Level 1 is stable and user-tested. |
| React frontend migration                     | Frontend    | none                                                         | No backend changes required — FastAPI API is frontend-agnostic. | jackpot-frontend: React + shadcn/ui + TanStack Query. One React route per current Streamlit page. Run Streamlit and React in parallel during transition. Retire Streamlit when React covers all the same ground. | Trigger: user feedback indicating Streamlit is a blocker, OR writing more st.components.v1.html() than st.dataframe(). Preparatory work now: keep Streamlit organized by page module with components/ directory. |

------

# Session 2 — 2026-04-10

## Context

This session was a continuity recovery after the previous chat crashed during a strategic discussion about JACKPOT's relationship to APGAP. Glen uploaded nine documentation files to restore context. The session focused entirely on architectural clarification and open design questions — no code was written.

------

## Topics Discussed

### 35. Full audit and state-of-the-union

Reviewed all uploaded documentation to establish a clean consolidated picture of the project state. Key confirmed facts:

- Schema is at v4.4 (jackpot_schema_v4_4.yaml provided)
- Last documented test baseline: 95 tests, 63.96% coverage
- Docker Compose stack has not been touched since the previous session crash
- Routers confirmed full: auth, gisaid, organizations, labs, projects, users, domain_whitelist, sequencing_labs, tokens, dataharmonizer
- Routers confirmed stub: samples, ingest, datasets, sample_access, dataset_access, archive_requests, ncbi_submissions, notifications, saved_searches, billing, pipelines
- Next implementation targets: samples.py + ingest.py (Month 1 blockers)
- Everything else (pipelines, governance, datasets) depends on ingest working

### 36. GCP production architecture — confirmed corrections (from Section 27)

Confirmed the CLAUDE.md correction from the previous session: production database is Cloud SQL PostgreSQL, not BigQuery. Full environment mapping:

- Operational DB: PostgreSQL (Docker local) → Cloud SQL PostgreSQL (GCP)
- Object storage: MinIO → GCS (env var change only)
- Background jobs: APScheduler in-process → Cloud Scheduler → HTTP endpoint
- Pipeline executor: PIPELINE_EXECUTOR=local → PIPELINE_EXECUTOR=gcp_batch
- Workspace: WORKSPACE_ENABLED=false (local) → true (GKE)
- Shared cache: in-memory dict (local) → Cloud Memorystore Redis (GKE)

BigQuery role clarified: analytical warehouse only, populated by periodic ETL from Cloud SQL. FastAPI never queries BigQuery directly. Month 3+ concern.

Critical Rules 21–38 confirmed as added to CLAUDE.md during the previous session (see Section 27–34 of Session 1 summary for details).

### 37. Seven open architectural questions resolved

**Q1 — Tiered access to sample metadata**

Two orthogonal tier concepts clarified:

Quality tiers (quality_status): PRELIMINARY (Tier 1, ~15 fields, pipelines can launch) → ANALYZABLE (Tier 2, ~20 fields, can join datasets) → SUBMITTABLE (Tier 3, ~35 fields, NCBI/GISAID submission). Computed by validator.py, rises only, never falls. Replaces APGAP's binary DRAFT/PRIMARY gate that caused the backlog.

Sharing levels (sharing_level): PRIVATE (owner + Lab Director) → LAB (all lab members) → DISCOVERABLE (catalog visible, files require access request) → PUBLIC (all authenticated users). Enforced via can_see_sample() and can_access_sample() — two distinct permission checks.

Open design item: field-level metadata redaction for DISCOVERABLE samples (which fields are visible before access is granted) — to be decided at can_see_sample() implementation time. Suggested safe subset: organism, date_collected, collection country/state, source_type, quality_tier.

**Q2 — Documentation while coding**

Four-layer strategy:

1. CLAUDE.md — continuous, updated every coding session, same commit as code.
2. Architecture doc — updated per major design decision, not per session.
3. OpenAPI autodocs — free from FastAPI docstrings, zero extra effort.
4. User guide (docs/user_guide/) — written alongside features, not deferred. Critical: user guide is the source material for the Year 2 LLM assistant. Assistant quality depends entirely on documentation quality.

CHANGELOG.md at repo root: one line per completed feature, one line per breaking change.

**Q3 — FAIR standards status and roadmap**

Schema is FAIR at the design level (ontology anchoring, DUO codes, data_use_terms, provenance fields all in v4.4). Implementation gaps:

Month 1–2: Schema fields populate FAIR metadata automatically at ingest. Month 3: JSON-LD endpoint (GET /api/v1/samples/{id}.jsonld) — one endpoint, ~1 day of work. Enables external crawler indexing. Year 2: GA4GH DRS endpoints for file access — interoperability with Terra, AnVIL, and other GA4GH-compliant platforms.

**Q4 — Sequencing Lab controlled vocabulary**

sequencing_lab is DB-managed via sequencing_labs table — NOT a static enum (Critical Rule in CLAUDE.md). Three registration paths:

1. Platform Admin registers facility directly via admin interface.
2. Lab Director requests addition → Platform Admin approves.
3. Unknown Globus depositor → Platform Admin notification → one-click create.

Table fields: name, display_name, lab_type, contact_email, website, globus_identity_id, globus_staging_path, filename_pattern JSONB, is_active.

Linked to labs via sequencing_lab_assignments join table (Critical Rule 21).

**Q5 — Federation architecture**

Three progressive levels, each independently useful:

Level 1 — Query federation (Month 2–3): federated_instances table registers trusted JACKPOT deployments. Search toggle queries partner instances via their GET /api/v1/samples/ endpoint using federation API key. Results are DISCOVERABLE-equivalent (no clinical metadata, no file URLs). Actions on results: import stub, open in source, request data sharing. Cached 30 min.

Level 2 — De-identified hub push (Year 2, early): surveillance_relevant=TRUE samples at sharing_level ≥ LAB are pushed nightly to a hub instance. Payload: FASTA (presigned URL, 24h), typing results, AMR profiles, lineage, organism, date, country/state, source_type, sector, quality_tier. Never pushed: raw FASTQ, host_age, host_sex, adhs_medsis_id, case_id, collection_facility. Each org controls minimum sharing level for federation participation via organizations.min_sharing_level_for_federation.

Level 3 — Bidirectional sharing (Year 2, late): cross-instance access requests. Researcher at Org B requests specific samples from Org A. Org A Lab Director approves via same UI as internal access requests. On approval: presigned URLs issued, JACKPOT at Org B pulls files into jackpot-sequences. Imported sample retains external_source attribution. Scrubber runs on import.

New schema: federated_instances table, new org fields (min_sharing_level_ for_federation, federation_enabled, hub_instance_url, federation_role). New env vars: FEDERATION_ENABLED (false until Year 2), FEDERATION_ROLE (hub/spoke/peer), HUB_INSTANCE_URL, FEDERATION_PUSH_SCHEDULE. Federation API keys stored in GCP Secret Manager, not in DB directly.

**Q6 — Dataset file copies**

Decision: reference-based internally — never copy FASTQs into a dataset bucket. Three-tier model:

Tier 1 (internal dataset): named collection of sample_id references in datasets + dataset_samples join table. Pipelines read directly from jackpot-sequences/{org_slug}/{lab_slug}/{sample_id}/ via API service account. No copy, no duplication, no cost.

Tier 2 (published dataset snapshot): frozen metadata export + GCS URI manifest written to gs://jackpot-results/datasets/{dataset_id}/ at publication time. Files are not copied — URIs are recorded. Snapshot is what researchers cite in papers.

Tier 3 (external collaborator access): presigned URL package (JSON manifest with time-limited per-file URLs, 30-day default). No file copy at rest. GISAID-sourced samples: metadata-only entries (redistribution prohibited).

Open governance question for later: whether to copy FASTA (not FASTQ) into the snapshot for published global datasets as a permanent scientific record. FASTA files are 1–5 MB each — negligible storage cost. Preserves reproducibility if source sample is later deleted. Decision not needed before Month 1.

**Q7 — Lab, Project, and Personal storage organization**

GCS bucket structure (path-based isolation, not per-lab/per-project buckets):

jackpot-sequences/{org_slug}/{lab_slug}/{sample_id}/   ← all sequence data jackpot-staging/{org_slug}/{lab_slug}/incoming/         ← Globus staging jackpot-results/{run_id}/                               ← pipeline outputs jackpot-work/{run_id}/work/                             ← Nextflow work dirs jackpot-backups/                                        ← Cloud SQL exports

Lab storage: implicit — created when first sample ingested. No Terraform per lab required.

Project storage: does not exist as a GCS path. Projects are a DB concept (named sample collection), not a storage container.

Personal workspace: JupyterHub PVC (per-user Kubernetes persistent disk, 10GB default). Not for long-term sequence storage — working scratch only. Files promoted back to JACKPOT via session.samples.register_from_workspace().

Future consideration: if ADHS requires per-lab IAM isolation (files provably inaccessible across lab boundaries at the GCS level), per-lab buckets would be needed. Current path-based model supports clean migration to that structure if a compliance requirement arises.

### 38. Session summary versioning workflow established

Document renamed: jackpot_session_summary_and_backlog.md (stable filename). Version header added at top: Document version, Last updated, Sessions covered. Each session appended as a dated top-level section at bottom of document.

Workflow:

- End of each session: Glen asks "Save and version the session summary"
- Claude reads existing document from uploads/, appends current session summary from context window, increments version, saves to outputs/
- Glen downloads → saves to ~/ASU/jackpot/docs/ on Mac
- Start of next session: Glen uploads saved document as attachment

Companion script: scripts/new_session_stub.py — generates a blank session section stub for manual notes between Claude sessions.

------

## Backlog Updates from This Session

No new backlog items — all seven questions resolved architectural ambiguity in existing backlog items. Affected items:

- To-do item 20 (can_access_sample / can_see_sample): field-level redaction for DISCOVERABLE samples is an open sub-item to be defined at implementation.
- To-do item 4 (Alembic migration): add federated_instances table and new org-level federation fields to migration scope (Year 2, not Month 1).
- To-do item 30 (Globus integration): sequencing_lab_assignments join table already in scope — confirmed.
- Dataset schema: datasets + dataset_samples tables confirmed as reference- based. No dataset-specific GCS bucket. Published snapshot to jackpot-results/datasets/{id}/ confirmed.
- User guide: added as explicit deliverable alongside Month 1 feature implementation. Not deferred.

------

## Next Steps

When ready to code:

1. docker compose up -d — verify stack health
2. uv run alembic current — verify schema state
3. First Claude Code session: POST /api/v1/ingest/upload + samples.py

------

# Session 3 — 2026-04-10

## What we covered

Diagram library audit and standardisation, CLAUDE.md full rewrite, codebase review (backend, schema, frontend, CLI), Docker/uvicorn stack debugging, pre-commit hook workflow fix, and full alignment of code to CLAUDE.md's designed interfaces. All 95 tests passing at 67.78% coverage at session end.

------

## Topics discussed

### 39. Diagram library audit and filename standardisation

Uploaded all 31 diagram HTML files. Full accuracy audit performed across all files. Issues found and fixed:

**High — architecture incorrect (patched):**

- `jackpot_tech_stack.html` — 5 fixes: BigQuery → Cloud SQL PostgreSQL
- `jackpot_schema_pipeline.html` — 4 fixes: production target corrected
- `jackpot_api_and_fastapi.html` — 1 fix: production data store label
- `jackpot_environment_variables_and_configuration.html` — 5 fixes: DATABASE_URL production value → Cloud SQL pg8000 format, `is_lab_admin` → `is_lab_director`
- `jackpot_sql_basics.html` — 3 fixes: `is_lab_admin` → `is_lab_director`
- `jackpot_ui_layer.html` — 5 fixes: `lab_admin.py` → `lab_director.py`, `org_admin.py` → `platform_admin.py`
- `jackpot_data_standards_explorer.html` — 1 fix: v4.0 → v4.4

**New diagrams added to library:**

- `jackpot_backend_directory_contents.html` — corrected version with all 18 backend modules (7 were missing from original), Session 2 additions shown in amber, legend added.

**Filename standardisation — rename_diagrams.py:**

- All files renamed to lowercase `jackpot_` prefix convention
- `jackpot_apgap_*` → `jackpot_vs_apgap_*`
- `jackpot_mental_model_N_*` → `jackpot_*` (figure number dropped)
- `JACKPOT___*` → `jackpot_*`
- `JACKPOT — Figure N_ *` files identified as duplicates, skipped not renamed
- `.htm` → `.html` normalised
- macOS case-insensitive filesystem two-step rename bug fixed
- Final: 27 renames, 0 conflicts

**Two new diagrams identified as missing from library:**

- `jackpot_dictionaries.html`
- `jackpot_functions_type_hints.html` Both added to Section 29 of architecture doc.

### 40. Architecture doc — Section 29 Diagram Reference added

Replaced all four appendices (A–D) with a clean Section 29 table. Four groups: Architecture & Governance (5), APGAP Comparison (4), Platform Architecture Mental Models (7), Developer Reference (12). All 28 standardised lowercase filenames. No iframes, no broken links, no cautionary notes — clean reference table only.

Final architecture doc: `jackpot_architecture_v5.md`, 1,860 lines.

### 41. CLAUDE.md full rewrite

Complete rewrite of CLAUDE.md. Changes from previous version:

**Bugs fixed:**

- `is_lab_admin` → `is_lab_director` everywhere (0 occurrences remain)
- `LinkML v4.1` → `v4.4`
- Health check `"version":"4.0.0"` → `"5.0.0"`
- `claude-haiku-4-5` → `claude-haiku-4-5-20251001` (full model string)

**Structure changes:**

- All 40 Critical Rules consolidated into one section (was split across five "continued" sections throughout the document)
- Rules 39 and 40 added: dynamic PATCH pattern and RETURNING clause
- APGAP compatibility note given its own section header
- Directory listing expanded to show all 18 backend modules with one-line descriptions each
- Pre-requisite callout added: `responses.py` and `notifications.py` must exist before first router session
- CLI/SDK section added at end

### 42. Preparing for Claude Code

Reviewed what Claude Code needs to know before first session:

- Keep sessions small and focused (one router per session)
- Always start with clean git working tree
- Give it a specific task with the existing pattern file to follow
- Let it run `uv run pytest` and iterate on failures itself
- Watch for: coverage threshold lowering, `# type: ignore` shortcuts, BigQuery connection strings, `is_lab_admin` column name

### 43. Docker/uvicorn stack debugging — full resolution

Series of import and container issues discovered and resolved:

**Problem 1 — bare intra-package imports** All `from config import`, `from database import`, etc. needed `backend.` prefix. Fixed with a Python script using `re.subn()` across all backend files. Files fixed: `main.py`, `audit.py`, `auth/guards.py`, `auth/oauth.py`, `auth/dependencies.py`, `database.py`, `storage.py`, `routers/auth.py`, `routers/gisaid.py`.

**Problem 2 — Dockerfile used flat layout** `COPY backend/ .` dumped files flat into `/app/`. Fixed to `COPY backend/ ./backend/` and `CMD uvicorn backend.main:app`.

**Problem 3 — docker-compose.yml volume mount overrode Dockerfile** `volumes: - ./backend:/app` mounted backend flat, defeating the Dockerfile fix. Fixed to `volumes: - .:/app` (mount whole repo root).

**Problem 4 — docker-compose.yml command override** `command: uvicorn main:app` overrode Dockerfile CMD. Fixed to `command: uvicorn backend.main:app`.

Final result: `curl http://localhost:8000/health` returns `{"status":"ok","version":"4.0.0","project":"JACKPOT"}`. Note: version in `FastAPI(version=...)` still says 4.0.0 — update to 5.0.0.

### 44. Pre-commit hook workflow fix

Problem: ruff auto-fixes staged files but stash conflict with unstaged files causes rollback, requiring two commits.

Fix: run ruff manually before staging:

```bash
uv run ruff check --fix . && uv run ruff format . && git add -A && git commit -m "message"
```

Shell alias added to `~/.zshrc`:

```bash
alias gac='uv run ruff check --fix . && uv run ruff format . && git add -A && git commit -m'
```

Usage: `gac "commit message"`

### 45. Codebase review — backend flat file

Full review of `jackpot_backend_flat.txt`. Issues found:

**Blockers (fixed this session):**

- `execute_write()` returned `None` — cannot use RETURNING. Fixed to return `list[dict]` matching `execute_query()`.
- `responses.py` missing entirely — created from scratch.
- `pagination.py` had `PaginatedResponse` model but no `paginate()` function — function added.
- `backend/notifications.py` missing — created from scratch.

**Interface mismatches (fixed this session):**

- `audit.py` — wrong signature and module-level string constants instead of `AuditActions` class. Full rewrite to match CLAUDE.md.
- `storage.py` — wrong function names (`upload_fileobj` → `stage_file`, `object_exists` → `file_exists`, etc.). Full rewrite.
- `epiweek.py` — missing `precision` parameter. Added with correct None return for month/year precision.

**Schema mismatches resolved via Alembic migrations:**

- `audit_log` table: renamed `user_id` → `actor_id`, `resource` → `resource_type`, `detail` → dropped, added `before_state`, `after_state`, `metadata`. Migration: `redesign_audit_log`.
- `notifications` table: renamed `user_id` → `recipient_id`, `type` → `event_type`, `link` → `action_url`, added `resource_type`, `resource_id`. Migration: `redesign_notifications`.

**Minor issues noted (not yet fixed):**

- `main.py` has `version="4.0.0"` in `FastAPI()` but health endpoint returns `"5.0.0"` — inconsistent.
- `validator.py` docstring still says "jackpot_schema v4.1".
- `validator.py` missing `compute_quality_status()` and `compute_surveillance_relevant()` — documented in CLAUDE.md Rules 16/17 as living in validator.py, not yet written.

### 46. Schema, frontend, CLI review

**Frontend (jackpot_frontend_flat.txt):** All pages are stubs. Filenames already correct (`lab_director.py`, `platform_admin.py`). Nothing blocking backend work.

**Schema (jackpot_schema_flat.txt):** Schema is at v4.4. Key finding: `sector` is `required: true` in the schema but was missing from `BASE_REQUIRED` in `validator.py`. Fixed by adding `"sector"` to `BASE_REQUIRED` and `"sector": "clinical"` to the `valid_human_sample` fixture in `tests/conftest.py`. 15 test failures resolved.

`date_collected_precision` drives `compute_epiweeks()` precision parameter but validator doesn't validate or extract it yet — noted for ingest implementation.

**CLI (jackpot_cli_flat.txt):** Well-structured SDK/CLI (`jackpot-cli` repo). Key finding: `JACKPOTClient` already expects the exact response envelope that `backend/responses.py` produces — confirms the two repos were designed together and are consistent. Priority endpoints for CLI usability: `ingest/upload` → `samples/` list and get → `pipelines/` list and launch.

CLI section added to CLAUDE.md.

### 47. Correct router implementation order established

Ingest/samples cannot be first — users must exist first. Correct order:

1. `organizations` — no dependencies
2. `labs` — depends on organizations
3. `users` — depends on organizations
4. `lab_membership` (part of labs router) — depends on labs + users
5. `domain_whitelist` — standalone, needed for OAuth
6. `tokens` — API token management, needed for CLI auth
7. `ingest` — now all dependencies exist

------

## State at end of Session 3

**Tests:** 95 passed, 0 failed, 67.78% coverage **Stack:** Docker Compose running, health check responding **Git:** All changes committed to development branch

**Files changed this session:**

- `Dockerfile.api` — corrected COPY and CMD
- `docker-compose.yml` — corrected volume mount and command
- `backend/main.py` — `backend.` prefix on all imports, router imports
- `backend/audit.py` — full rewrite: AuditActions class, correct signature
- `backend/auth/guards.py` — `backend.` prefix
- `backend/auth/oauth.py` — `backend.` prefix
- `backend/auth/dependencies.py` — `backend.` prefix
- `backend/database.py` — `backend.` prefix; `execute_write()` now returns rows
- `backend/storage.py` — full rewrite: correct function names per CLAUDE.md
- `backend/epiweek.py` — added `precision` parameter
- `backend/routers/auth.py` — `backend.` prefix
- `backend/routers/gisaid.py` — `backend.` prefix
- `backend/validator.py` — `sector` added to `BASE_REQUIRED`
- `backend/pagination.py` — `paginate()` function added
- `backend/responses.py` — created from scratch
- `backend/notifications.py` — created from scratch
- `tests/conftest.py` — `sector: clinical` added to `valid_human_sample`
- `pyproject.toml` — new modules added to coverage omit list
- `CLAUDE.md` — full rewrite (see item 41)
- `db/migrations/versions/*_redesign_audit_log.py` — new migration
- `db/migrations/versions/*_redesign_notifications.py` — new migration

**Pending (not yet done):**

- Update `version="4.0.0"` in `FastAPI()` in `main.py` to `"5.0.0"`
- Add `compute_quality_status()` and `compute_surveillance_relevant()` to `validator.py` before ingest implementation
- Implement `responses.py` error helper as `JSONResponse` (currently returns dict — needs to return actual HTTP error status codes)
- Begin Claude Code sessions in order: organizations → labs → users → domain_whitelist → tokens → ingest

------

### 48. rsync/rclone ingest path — decisions locked

**Transfer protocol for CSV batch ingest:** Option C selected.

- `jackpot-cli` wraps rclone (preferred) or rsync (fallback) transparently
- Local dev: rsync/rclone → MinIO staging
- Production: rclone → GCS jackpot-staging/{org_slug}/{lab_slug}/incoming/
- Last resort fallback: HTTP multipart signed URL upload

**Backend detection logic in `jackpot upload`:**

```python
if shutil.which("rclone"):   # preferred
    backend = "rclone"
elif shutil.which("rsync"):  # local dev fallback
    backend = "rsync"
else:
    backend = "http"          # multipart fallback, no wildcards
```

rclone is a soft dependency — recommended, not required. Lab researchers never need to know which backend is running.

**Project identification:** CLI accepts project name, not ID. Name resolved to ID via GET /api/v1/projects/?name=... before transfer. Lab scoping required since project names are unique within a lab, not globally:

```bash
# Explicit
jackpot upload --dir ./sequences/ --csv metadata.csv \
    --lab "Otero Lab" --project "Arizona Flu Surveillance 2026"

# Using stored defaults from `jackpot config set`
jackpot upload --dir ./sequences/ --csv metadata.csv
```

**Implementation notes for router work:**

- GET /api/v1/projects/ must support ?name= filter
- tokens router should store default lab_id and project_id in user context
- CLI config stores default lab and project — set via `jackpot config set`

------

### 49. Final structural fixes before Claude Code

Six structural weaknesses identified and resolved:

**Fix 1 — `execute_write()` transaction isolation** Added optional `conn` parameter so audit and notification writes can participate in the caller's transaction. Without this, audit writes were in separate transactions from the operations they audited — silent audit gaps possible on write failure.

**Fix 2 — module-level `get_settings()` calls** Removed module-level `settings = get_settings()` from `auth/guards.py`, `auth/oauth.py`, and `storage.py`. Moved inside each function. Module-level calls cache settings before test fixtures can override `DATABASE_URL`, breaking the lazy engine pattern (Critical Rule 14).

**Fix 3 — SQL injection in `paginate()`** Added `ALLOWED_SORT_COLUMNS` whitelist. `sort_by` parameter was interpolated directly into ORDER BY clause — any query parameter could inject arbitrary SQL. Falls back to `created_at` if column not in whitelist.

**Fix 4 — `VALID_SECTORS` missing from validator** `sector` was in `BASE_REQUIRED` but no enum check existed. Added `VALID_SECTORS` constant and validation block inside `validate_sample()`.

**Fix 5 — `bigquery_dataset` removed from config** Stale field removed from `Settings` class. Would confuse Claude Code into thinking BigQuery is a valid database target.

**Fix 6 — `responses.py` all helpers return `JSONResponse`** `success()`, `success_list()`, `success_message()` all now return `JSONResponse` with configurable `status_code` parameter. Previously returned plain dicts — impossible to return `201 Created` for POST endpoints.

**Fix 7 — `get_db_dep()` FastAPI dependency injector added** Added to `backend/database.py`. Yields a Session for use with `Depends()` in router function signatures. Without this Claude Code would either use context managers inline (verbose) or `Depends(get_db)` directly (broken).

**Fix 8 — Critical Rule 41 added to CLAUDE.md** Documents the `get_db_dep()` + `Depends()` pattern with a complete code example showing the correct router pattern: one transaction covering the write + audit + notification.

**Fix 9 — `Otero Lab` → `Otero Outpost` in test fixture** Updated `valid_human_sample` fixture in `tests/conftest.py`.

**Fix 10 — `backend/version.py` created** Single source of truth for version string. Imported in `main.py` for both `FastAPI(version=...)` and the health endpoint.

**Fix 11 — `seed_sequencing_labs.py` created** Seed script for sequencing_labs table — survives `docker compose down -v`. Three labs: Sonora Quest Laboratories, Laboratory Corporation of America, Otero Outpost.

### 50. Final state at end of Session 3

**Tests:** 95 passed, 0 failed, 67.78% coverage **Stack:** Docker Compose running, health check responding **Alembic:** At head (5 migrations applied) **Seed data:** 75 reportable organisms, 3 sequencing labs **CLAUDE.md:** 41 Critical Rules, all interfaces correct

**Router implementation order for Claude Code sessions:**

1. organizations
2. labs (including lab_membership endpoints)
3. users
4. domain_whitelist
5. sequencing_labs
6. tokens
7. ingest
8. samples

**rsync/rclone ingest decisions locked:**

- CLI wraps rclone (preferred) / rsync (fallback) / HTTP (last resort)
- Project identified by name not ID
- GET /api/v1/projects/ must support ?name= filter
- tokens router stores default lab_id and project_id

------

# Session 4 — 2026-04-12

## What we covered

Comprehensive code audit review and remediation, pre-Claude Code preparation, implementation guide v2.0, and final platform readiness check.

------

## Topics discussed

### 51. Code audit review — jackpot_code_audit.md

A comprehensive audit was performed by a Senior Technical Software Engineering Lead across all six repos. Key findings:

**Overall assessment:** Strong architectural foundation, solid test culture, good security posture. "Scaffolding complete, core logic partially implemented." No red-flag anti-patterns. B+ grade for jackpot-backend.

**P0 fixes completed:**

1. Renamed `backend/response.py` → `backend/responses.py` — highest-impact doc/code mismatch. CLAUDE.md referenced plural form throughout.
2. Fixed `sharing_level` validation bug in `validator.py` — empty string was failing validation, rejecting samples without explicit sharing_level. Fixed with `is not None` check instead of truthiness.
3. Removed duplicate `source_type` validation check in `validator.py`
4. Fixed GISAID `collection_location_country` bracket access → `.get()`
5. Fixed GISAID docstring placement — moved above guard clause
6. Registered all 21 routers in `main.py` (was only 2)

**P1 fixes completed:** 7. Added DB connectivity check to `/health` endpoint — now returns `{"database": "connected"}` with SELECT 1 probe 8. Added default secret key rejection in `validate_for_production()` — rejects literal `"dev-secret-key-change-in-prod"` in production 9. Fixed `file_exists()` to catch `ClientError` specifically, not bare Exception 10. Added `StorageError` wrapper class to `storage.py` — all functions now catch `ClientError` and raise meaningful errors 11. Migrated from deprecated `on_event` to `lifespan` context manager in `main.py`

**P2/P3 deferred:** Rate limiting, init.sql regeneration, CORS restrictions, Google ID token verification, API versioning — all pre-Month 3 or Year 2.

### 52. Implementation guide v2.0 produced

`jackpot_implementation_v2.md` — complete rewrite of the v1.0 guide. Key changes: jackpot-cli added as 5th repo, schema version v4.1→v4.4, Dockerfile and docker-compose corrections documented, seed data step added as Step 12, gac alias documented, all router implementation sessions A-H, corrected pyproject.toml pythonpath, updated appendices with all new modules.

### 53. Claude Code operating prompt designed

Two documents reviewed: generic vibe-coding framework and JACKPOT-specific prompt. Combined best elements into a lean session prompt:

```
## Operating Rules
- Enter plan mode for any non-trivial task. Explain plan before writing code.
  Wait for "Go" before architectural changes.
- After any correction, update tasks/lessons.md with the pattern.
- Never mark a task complete without passing tests.
- Make every change as simple as possible. Find root causes. No temporary fixes.

## Role
You are the lead engineer on JACKPOT. I am the product owner.
Read docs/CLAUDE.md before doing anything else.

## Session Task
[paste specific task here]
```

"Mentorship over Execution" section dropped — too slow for production output. Ingest-specific reminders scoped to ingest sessions only.

### 54. Python alias added

Added to `~/.zshrc`:

```bash
alias python='uv run python'
alias python3='uv run python3'
alias pip='uv pip'
```

### 55. Final pre-Claude Code issues identified and remediated

Six additional issues found in final critical review:

**🔴 Critical — test DB missing Alembic migrations** `tests/conftest.py` only runs `db/init.sql`, never applies Alembic migrations. The 31 columns added via migration (`sector`, `quality_status`, `surveillance_relevant`, etc.) don't exist in the test database. First ingest test will fail with "column does not exist". Fix: add `alembic upgrade head` to `initialize_test_db` fixture.

**🔴 Critical — `routers/auth.py` has module-level `settings = get_settings()`** Was fixed in guards.py, oauth.py, storage.py but missed auth router. Causes test isolation failure.

**🔴 Critical — `valid_human_sample` fixture has two "Otero Lab" occurrences** Line 4491 (second conftest or test file) still has old name. Fix: `grep -n "Otero" tests/conftest.py tests/test_samples_api.py`

**🟡 Important — no JWT refresh endpoint** `issue_refresh_token()` exists and cookie is set on login but no `POST /api/v1/auth/refresh` endpoint exists. 15-minute access tokens expire with no renewal path. Add to `routers/auth.py` before Month 1.

**🟡 Important — `active` vs `is_active` inconsistency** `organizations` and `labs` tables use `active` column. Every other table uses `is_active`. Claude Code needs to know: use `active` for orgs and labs, `is_active` for everything else. Or fix with migration before implementing those routers.

**🟡 Important — `test_samples_api.py` actually tests `file_detector.py`** Misleadingly named file. No actual samples API tests exist yet.

**🟡 Minor — `contextlib.suppress(Exception)` in test DB setup** Silently swallows ALL SQL errors when loading init.sql. A broken schema wouldn't cause test failures — tests would run against incomplete DB.

### 56. Location data validation gap identified

No validation prevents logically false location data (e.g. "Phoenix, British Columbia, United States"). Current behavior:

- `collection_location_country` presence is required
- `collection_location_state` is free text with no cross-validation
- GISAID/NCBI will reject invalid INSDC country names at submission time (practical check happens at submission, not ingest)

Planned fix for Month 2: US-states controlled vocabulary for `collection_location_state` when country is "United States". International sub-national locations remain free text.

------

## State at end of Session 4

**Tests:** 95 passed (pending Alembic migration fix in conftest) **Stack:** Docker Compose running, health check returning database status **All 21 routers:** Registered and reachable **P0/P1 audit fixes:** Complete **Pending before first Claude Code session:**

1. Fix `conftest.py` to apply Alembic migrations in test DB setup
2. Fix `routers/auth.py` module-level `settings = get_settings()`
3. Fix remaining "Otero Lab" in test fixtures
4. Add CLAUDE.md note about `active` vs `is_active` for orgs/labs
5. Add JWT refresh endpoint to `routers/auth.py`

**Router implementation order (unchanged):** A: organizations → B: labs → C: users → D: domain_whitelist → E: sequencing_labs → F: tokens → G: ingest → H: samples

------

# Session 5 — 2026-04-15

## What we covered

Iterative refinement of the JACKPOT Data Model Architecture HTML diagram (Mental Model 3). Work focused entirely on visual quality: font sizing, arrow routing, color consistency, and text collision fixes across all four diagrams.

------

## Topics discussed

### 57. Data Model Architecture diagram — initial delivery (MM3 HTML)

Produced `JACKPOT_Data_Model_Architecture.html` — a standalone, single-file HTML document rendering all 27 PostgreSQL tables across four SVG diagrams:

- **Diagram 1:** Platform Identity & Access Control (9 tables)
- **Diagram 2:** Core Sample Data Model (5 tables + source_type taxonomy)
- **Diagram 3:** Governance & Data Lifecycle (7 tables)
- **Diagram 4:** Platform Operations & Services (8 tables)

Color scheme: green = org hierarchy, blue = identity/access, brown = sample data, purple = governance, red/pink = platform services, grey = bridge tables.

### 58. Diagram v2 — font size, arrow routing, and text collision fixes

Three rounds of fixes applied to produce `JACKPOT_Data_Model_Architecture_v2.html`:

**Font sizes increased across all four diagrams:**

- Table names: 12.5 → 14px
- Body mono fields: 10 → 11.5px
- Badge labels and italic notes: 9 → 10px
- `samples` giant label: 15 → 17px

**Arrow routing fixed (lines crossing through tables):**

- Diagram 3: `samples → archive_requests` rerouted above the table row
- Diagram 3: `samples → ncbi_submissions` rerouted above the table row with label repositioned to clear space
- Diagram 4: `users → notification_preferences` rerouted above the second row of boxes to avoid passing through `notifications`

**Box height fix:**

- `sequencing_labs` box height increased to prevent italic note clipping

### 59. Diagram v3 — Diagram 2 color and text collision fixes

`JACKPOT_Data_Model_Architecture_v3.html` produced with:

**Text collision fix:**

- `reportable_organisms` validator arrow rerouted to exit from box bottom instead of squeezing through the 28px side gap between boxes
- "validator reads / → surveillance_relevant" labels moved to clear space below the reference box

**Color shading fix:**

- Three washed-out lightest greens in source_type taxonomy darkened: Water/Air/Soil `#72b898` → `#5aaa85` Surface/Food/Produce `#88c8ae` → `#6db89a` Isolate (generic) `#9ed5c0` → `#7ec5ae`

**Taxonomy panel fix:**

- Source-type panel widened by 15px (185 → 200px) to prevent text clipping at right edge after font size increase
- `drives` arrow updated to match new panel right edge

**Samples box fix:**

- Height increased by 20px (430 → 450px) to give POST-PIPELINE RESULTS section breathing room at the bottom

------

## State at end of Session 5

**Diagram artifact:** `JACKPOT_Data_Model_Architecture_v3.html` — current canonical version of MM3.

**Known remaining issues (if any):** None identified — v3 addresses all reported visual issues across all four diagrams.

**Next session focus:** Resume Claude Code implementation sessions starting with router A (organizations), incorporating all pre-session fixes identified at end of Session 4.

------

# Session 6 — 2026-04-16

## What we covered

Comprehensive senior engineering review of the entire JACKPOT codebase, followed by a re-evaluation against the updated flattened repos showing significant progress. Also completed final iteration of the Data Model Architecture diagram (v3).

------

## Topics discussed

### 60. Senior engineering review — initial report

A full-stack critical review performed from the perspective of a Senior Technical Software Engineering Lead. Covered security, error handling, logic gaps, naming consistency, testing gaps, and operational readiness across all project files.

**Two critical bugs identified:**

1. `log_audit()` accepts `db_conn` parameter but never forwards it to `execute_write()` as `conn=db_conn`. Audit writes run in separate auto-committed transactions, breaking the documented transactional cohesion. CLIA compliance gap.
2. `create_notification()` has the identical bug — accepts `db_conn`, ignores it.

**Security gaps identified:**

- JWT `type` claim not validated in `get_current_user()` — refresh tokens (7-day TTL) accepted as access tokens (15-min TTL)
- Google ID token decoded without signature verification
- No JWT refresh endpoint (users logged out every 15 minutes)
- CORS config hardcoded to localhost
- Pipeline events endpoint uses `run_id` as bearer with no token validation
- No request body size limit

**Logic gaps identified:**

- `validate_sample()` BASE_REQUIRED includes Tier 2/3 fields, blocking Tier 1 PRELIMINARY ingest — contradicts the three-tier model
- `compute_quality_status()` was a skeleton with only 6 fields checked for SUBMITTABLE vs ~35 documented
- `Isolate` source type missing from `VALID_SOURCE_TYPES`
- APScheduler job intervals (both `hours=1`) don't match architecture doc (scrubber: 60s, access requests: nightly)
- Health endpoint returns 200 when DB is unavailable

**15 "Need to Have" and 15 "Nice to Have" items documented in table format.**

Output: `jackpot_engineering_review.md`

### 61. Senior engineering review — updated report (v2)

Re-evaluated all findings against the current flattened repos (flattened_backend, flattened_frontend, flattened_iac, flattened_schema).

**Significant progress confirmed:**

- Tests: 95 → 275 (nearly tripled)
- Coverage: 63.96% → 75.62%
- Three new modules: `dlp_scanner.py` (PII/PHI scanning), `pipeline_results_loader.py` (iridanext output parsing), `template_generator.py` (DataHarmonizer CSV generation)
- Pipelines weblog receiver fully implemented with task-level event tracking
- Templates router implemented
- `spec.md` created (330 lines) — complete Claude Code operating spec
- `todo.md` created (420+ lines) — structured task list with P0 fixes
- `CLAUDE_addition.md` — autonomous operating mode instructions
- `active` vs `is_active` documented in spec.md
- `compute_quality_status()` improved — host_age/host_sex conditional on HumanSample

**Items correctly documented in todo.md but not yet fixed in code:**

- P0-1: conftest.py missing Alembic migrations
- P0-2: routers/auth.py module-level settings
- P0-3: "Otero Lab" stale reference in fixtures
- P0-4: JWT refresh endpoint
- P0-5: contextlib.suppress(Exception) in conftest

**New bug discovered:** `_handle_workflow_complete()` in `backend/routers/pipelines.py` calls `execute_query(..., conn=conn)` but `execute_query()` doesn't accept a `conn=` parameter. Will crash with `TypeError` at runtime when Nextflow posts a `workflow.complete` event.

**10 items identified as missing from todo.md Phase 0:**

- P0-7: `log_audit()` forward `conn=db_conn`
- P0-8: `create_notification()` forward `conn=db_conn`
- P0-9: `execute_query()` add `conn=` parameter
- P0-10: JWT `type` claim validation
- P0-11: Health endpoint return 503 when DB unavailable
- P0-12: APScheduler intervals and job IDs
- P0-13: Validator BASE_REQUIRED tier split
- P0-14: Add `Isolate` source type to validator
- P0-15: Validator docstring v4.1 → v4.4
- P0-16: CORS origins configurable via Settings

Output: `jackpot_engineering_review_v2.md`

### 62. Data Model Architecture diagram — Session 5 completion

Diagram v3 fixes applied in this session (carried over from Session 5):

- Diagram 2: `reportable_organisms` arrow rerouted to exit from bottom
- Diagram 2: source_type taxonomy colors darkened (3 washed-out greens)
- Diagram 2: taxonomy panel widened 15px, samples box height +20px

------

## State at end of Session 6

**Tests:** 275 passed, 0 failed, 75.62% coverage **New modules since Session 4:** dlp_scanner.py, pipeline_results_loader.py, template_generator.py, pipelines router (weblog receiver), templates router **Planning artifacts:** spec.md, todo.md, CLAUDE_addition.md all created **Review artifacts:** jackpot_engineering_review.md (v1), jackpot_engineering_review_v2.md (updated)

**Pending before first Claude Code router session (expanded P0 list):**

1. Fix conftest.py — add Alembic migrations (todo.md P0-1)
2. Fix routers/auth.py — module-level settings (todo.md P0-2)
3. Fix "Otero Lab" stale reference (todo.md P0-3)
4. Add JWT refresh endpoint (todo.md P0-4)
5. Fix contextlib.suppress in conftest (todo.md P0-5)
6. Fix log_audit() — add conn=db_conn (NEW — not in todo.md)
7. Fix create_notification() — add conn=db_conn (NEW — not in todo.md)
8. Fix execute_query() — add conn= parameter (NEW — not in todo.md)
9. Fix JWT type claim validation in guards.py (NEW — not in todo.md)
10. Fix health endpoint — 503 when DB unavailable (NEW — not in todo.md)
11. Fix APScheduler intervals and job IDs (NEW — not in todo.md)
12. Fix validator BASE_REQUIRED — tier split (NEW — not in todo.md)
13. Add Isolate source type to validator (NEW — not in todo.md)
14. Fix validator docstring v4.1 → v4.4 (NEW — not in todo.md)
15. Make CORS origins configurable (NEW — not in todo.md)

**Router implementation order (unchanged):** A: organizations → B: labs → C: users → D: domain_whitelist → E: sequencing_labs → F: tokens → G: ingest → H: samples

------

# Session 7 — 2026-04-16

## What we covered

Claude Code autonomous setup, pre-commit config repair, schema additions (mosquito pool biospecimen type), validator rewrite (tier split + sector auto-derivation), data model architecture diagrams, and multiple design reviews including the sector field, tier system, and metadata edit workflow.

------

## Topics discussed

### 58. Claude Code autonomous operating mode configured

Added Autonomous Operating Mode section to `docs/CLAUDE.md` with work loop, decision rules, and commit conventions. Created `spec.md` (full project specification with router-by-router endpoint definitions) and `todo.md` (phased task list, 50+ items). Added `dangerouslySkipPermissions: true` and `effortLevel: "high"` to `.claude/settings.json`. Disabled detect-secrets pre-commit hook until GCP deployment. Added `CLAUDE_CODE_DISABLE_AUTO_MEMORY` and `CLAUDE_CODE_SUBAGENT_MODEL: sonnet` to settings env.

### 59. Pre-commit config repaired

`.pre-commit-config.yaml` was mangled by earlier string-replacement scripts — detect-secrets had been incorrectly nested under the ruff repo entry. Fully rewrote the config file. Cleared pre-commit cache to resolve stale v1.4.0 ruff hook reference. detect-secrets disabled for local dev; ruff hooks restored correctly.

### 60. Alembic --autogenerate limitation documented

Discovered that `uv run alembic revision --autogenerate` fails with "no MetaData object" because JACKPOT uses raw SQL, not SQLAlchemy ORM models. Critical Rule 2 in CLAUDE.md updated: always use `uv run alembic revision -m "description"` (no --autogenerate), then hand-write upgrade() and downgrade().

### 61. Schema additions — mosquito pool biospecimen type

Added `pooled_homogenate` to `VectorBiospecimenTypeEnum` with description distinguishing it from single-specimen `homogenized`. Added `pool_size_min` and `pool_size_max` integer fields to `VectorSample` — range fields rather than a single integer because field collectors record "up to 50" mosquitoes, not always an exact count. `pool_size_min/max` are required for Minimum Infection Rate (MIR) calculations. Alembic migration written by hand.

### 62. Data model architecture diagrams produced

Created `JACKPOT_Data_Model_Architecture.html` — four SVG diagrams covering all 27 database tables organized by domain, using the same IBM Plex font stack and CSS variable system as existing mental model files. Diagrams: (1) Platform Identity & Access Control, (2) Core Sample Data Model, (3) Governance & Data Lifecycle, (4) Platform Operations & Services.

### 63. Sector field design decision

Researcher challenge: `sector` was in BASE_REQUIRED but researchers don't know this field — it's derivable from `source_type` in all cases except `research`. Decision: remove `sector` from BASE_REQUIRED and auto-derive it from `source_type` via `SECTOR_FROM_SOURCE_TYPE` mapping at ingest. Researchers only need to explicitly supply `sector = "research"` for non-surveillance samples. VALID_SECTORS aligned with schema SectorEnum: replaced `livestock`, `companion_animal`, `food` with `veterinary`, `agricultural`. Added `vector` sector.

### 64. Validator rewrite — tier split, sector auto-derivation, ValidationResult expansion

Full rewrite of `backend/validator.py`:

- `BASE_REQUIRED` reduced to 7 true Tier 1 fields (was 13 — blocked ingest on fields that should only be Tier 2/3 warnings)
- `TIER2_REQUIRED` added: sequencing_lab, collection_facility, library_preparation_method, nucleic_acid_extraction_method, date_sequenced, collection_location_state
- `TIER3_REQUIRED` added: sequencing_protocol, purpose_for_collection, originating_lab, submitting_lab, collection_location_county
- `TIER3_REQUIRED_HUMAN` added: host_age, host_sex
- `SECTOR_FROM_SOURCE_TYPE` mapping added for auto-derivation
- `ValidationResult` expanded: added `tier` (int), `sector` (str), `tier2_missing` (list), `tier3_missing` (list)
- `compute_quality_status()` signature simplified: takes only `ValidationResult` (no longer needs `data` dict — tier computed inside `validate_sample()`)
- `_is_absent()` helper extracted for consistent empty-value detection
- Docstring updated: v4.1 → v4.4
- Tests updated to match new API — `_run(data)` helper calls `validate_sample()` then `compute_quality_status()`
- Test helpers `_full_human_data()` and `_full_wastewater_data()` expanded to include all Tier 1 + Tier 2 + Tier 3 fields

**New baseline: 316 tests passing, 76.63% coverage**

### 65. Metadata edit post-submission warning requirement documented

When a sample has been submitted to NCBI or GISAID, edits to submission-critical fields create a discrepancy between JACKPOT and the external database. The PATCH endpoint should detect this and include a warning in the response. The Streamlit data_entry.py page must surface the warning before saving. Fields to check: organism_name, collection_location_country, collection_location_state, date_collected, host_species, isolation_source, bioproject_accession, biosample_accession. Documented in session backlog topic 57.

### 66. pre-shipping checklist review

Reviewed a generic pre-shipping checklist against JACKPOT. 15 of 25 items fully covered. Action items added to todo.md: SEC-1 (tighten CORS methods/headers), SEC-2 (rate limiting), DEPLOY-1 (staging gate), DEPLOY-2 (backup restore drill). All appropriately deferred to Month 2 / pre-GCP.

------

## State at end of Session 7

**Tests:** 316 passed, 0 failed, 76.63% coverage **Validator:** Tier split complete, sector auto-derived, ValidationResult expanded **Schema:** v4.4 + mosquito pool fields (pool_size_min/max, pooled_homogenate) **Diagrams:** JACKPOT_Data_Model_Architecture.html — all 27 tables **todo.md:** P0-13 (validator tier split) and P0-15 (docstring) complete **Pending P0 items before first Claude Code session:** P0-1 through P0-12, P0-14 (Isolate source type), P0-16 (CORS origins configurable)

## Topics discussed

### 57. `cors_origins` Pydantic Settings JSON-parse failure

First failure of the deploy — the Alembic migration Job in the Helm
pre-upgrade hook crashed before it ever touched the database. Root cause:
`cors_origins: list[str]` in `backend/config.py`. Pydantic-settings v2
unconditionally runs the env var value through `json.loads()` for any
`list[*]` field, and the ConfigMap supplied `CORS_ORIGINS:
"https://staging.jackpot.example.org"` — a plain string, not JSON.
`JSONDecodeError` at import time killed Alembic before it could call
`upgrade head`.

Tactical fix: changed the ConfigMap value (via `values-staging.yaml`) to a
JSON-array string: `'["https://staging.jackpot.example.org","http://localhost:8501"]'`.
Outer single quotes + inner double quotes in YAML renders as a literal
string that pydantic-settings can parse.

Permanent fix (deferred to next session, tracked as backlog item): add
`Annotated[list[str], NoDecode]` + `@field_validator("cors_origins",
mode="before")` to `Settings` so the class tolerates JSON arrays,
comma-separated strings, empty strings, and real lists. Prevents the next
`values-*.yaml` edit from recreating this class of bug.

### 58. `DATABASE_URL` pointed at the wrong database name

With `cors_origins` fixed, Alembic got past import, loaded Settings, and
tried to connect to Cloud SQL. Crashed with:

```
psycopg2.OperationalError: connection to server at "10.188.230.3",
  port 5432 failed: FATAL:  database "jackpot" does not exist
```

Cloud SQL had a database named `jackpot_db` (matching the Terraform
module's default and every reference in the codebase). The Secret Manager
entry `jackpot-staging-database-url` had been hand-populated with
`/jackpot` — missing the `_db` suffix. Presumably someone followed
`docs/staging_access.md` too quickly and dropped the suffix.

Fix: `gcloud secrets versions add jackpot-staging-database-url
--data-file=-` with the corrected URL. The workflow re-syncs the
Kubernetes Secret from Secret Manager on every run, so no additional
kubectl work needed. Backlog: let Terraform own this Secret (the
`terraform/modules/secrets/variables.tf` already lists `database-url` as a
key — we just never wired the value construction).

### 59. Alembic migration assumed `db/init.sql` had already run

Third failure — Alembic connected to Cloud SQL successfully, ran the first
migration (`a7fd1fcccb77`, rename_is_lab_admin_to_is_lab_director)
cleanly, then died on the second (`1de94c16e612`,
schema_v4_2_case_sector_surveillance_quality) with:

```
psycopg2.errors.UndefinedTable: relation "samples" does not exist
```

This is exactly the WEAK-3 / STATE-1 warning flagged in the code audit.
Locally, `db/init.sql` runs via the postgres Docker container's
`/docker-entrypoint-initdb.d/` on first start, creating all 27 tables
before Alembic applies the four patch migrations on top. Cloud SQL has no
such entrypoint — a fresh Cloud SQL database is empty and Alembic's
migration chain assumed `samples` already existed.

Fix: one-off bootstrap Job that loaded `init.sql` into `jackpot_db` and
then stamped Alembic at `a7fd1fcccb77`. Design:

- Three containers, sequenced via initContainers + emptyDir volume.
- `copy-init-sql` (jackpot image): copies `/app/db/init.sql` →
  `/shared/init.sql`. `psql` not installed in the jackpot image, so the
  SQL file had to be copied out to a neutral volume.
- `load-init-sql` (`postgres:16-alpine`): `psql "$DATABASE_URL"
  -v ON_ERROR_STOP=1 -f /shared/init.sql`. Ran clean — 28 CREATE TABLE,
  multiple CREATE INDEX, several INSERT seeds.
- `alembic-stamp` (jackpot image): `/opt/venv/bin/alembic stamp
  a7fd1fcccb77`. Recorded the baseline revision in `alembic_version`.

After the bootstrap, the next deploy's migration Job chained cleanly
through revisions 2–5. Job completed in 13 seconds, then self-deleted via
`ttlSecondsAfterFinished: 3600`.

Backlog: make `init.sql`'s DDL the first Alembic migration so
`alembic upgrade head` works from an empty database without a separate
bootstrap. This is Option 1 from the in-session triage — the durable fix.
Add to CLAUDE.md Critical Rules: "Never depend on `init.sql` running
before Alembic in any deployment target. The full schema must be
reachable via `alembic upgrade head` from an empty database."

### 60. `jackpot-nf` submodule URL pointed at a local filesystem path

Fourth failure — with migrations finally chaining, Helm rolled the
Deployment forward and API pods crash-looped with:

```
ModuleNotFoundError: No module named 'shared'
```

`backend/routers/pipelines.py` does a `sys.path.insert(0, "../nf")` hack
at import time so `from shared.schemas import RESULT_SCHEMAS` resolves to
`nf/shared/schemas/__init__.py` in the sibling `jackpot-nf` submodule.
This works on Glen's Mac. It fails on any machine that doesn't have
`jackpot-nf` sitting next to `jackpot-backend`.

Two compounding problems:

1. `.gitmodules` in `jackpot-backend` declared the `nf` submodule with
   `url = /Users/glen/ASU/jackpot/jackpot-nf` — a local filesystem path.
   CI runners can't clone that. `jackpot-nf` hadn't been pushed to GitHub
   at all.
2. `Dockerfile.api` did not `COPY nf/` into the image. Even if the
   submodule had cloned on the CI runner, the Docker build stage would
   have left `nf/` out of `/app/`.

Fix was four commits:

- Pushed `jackpot-nf` to `gotero/jackpot-nf` on GitHub (`gh repo create
  gotero/jackpot-nf --private --source=. --remote=origin` then
  `git push -u origin main`). Three commits, `a45fb13` at head.
- Updated `.gitmodules` in `jackpot-backend` via `git submodule set-url
  nf git@github.com:gotero/jackpot-nf.git` + `git config -f .gitmodules
  submodule.nf.branch main`. Matches the `schema` submodule pattern.
- Added `COPY nf/ ./nf/` to `Dockerfile.api` immediately after the
  existing `COPY backend/ ./backend/` line.
- Added `submodules: recursive` to the `actions/checkout@v4` step for
  `jackpot-backend` in `.github/workflows/deploy-staging.yml`.

Permanent fix (backlog): move `RESULT_SCHEMAS` into the backend package
(e.g. `backend/pipeline_schemas.py`) so `pipelines.py` doesn't need
`sys.path` manipulation and Dockerfile doesn't need a second COPY
stanza. The `sys.path` gymnastics work but make the app fragile — any
tool that evaluates `backend/routers/pipelines.py` without the `nf/`
sibling (linting in CI, tests in sandboxes, backend-only docker builds)
explodes. Target: Claude Code session when pipelines router is
implemented in Month 2.

### 61. Duplicate YAML key broke the workflow before it could run

After landing the `submodules: recursive` patch, two consecutive workflow
runs failed at 0s elapsed. Every step showed `-` status except `Set up
job` which showed a red X.

Root cause: the Python heredoc that performed the YAML edit had been run
twice (once inadvertently during a re-run of the diagnostic steps, once
intentionally). The result:

```yaml
          persist-credentials: false
          submodules: recursive
          submodules: recursive
```

PyYAML's `safe_load` silently last-wins on duplicate keys, so
`python3 -c "import yaml; yaml.safe_load(open('...'))"` reported clean.
GitHub Actions' workflow-schema validator is stricter and refuses to
start any job on a file with duplicate mapping keys — hence the 0s
failure.

Fix: removed the duplicate line. Lesson: `yaml.safe_load` lies about
duplicate-key validity. GitHub Actions runs a separate validator and is
stricter than PyYAML.

### 62. `persist-credentials: false` vs submodule auth — the forked path

With the YAML repaired, the workflow started running steps but failed at
`Checkout jackpot-backend`. Submodule fetches of both
`gotero/jackpot-nf` and `gotero/jackpot-schema` got
`403 Forbidden → 128`. The primary repo clone of `gotero/jackpot-backend`
succeeded.

The existing workflow had `persist-credentials: false`. This is a
hardening option that tells `actions/checkout@v4` not to write the token
to `.git/config` after the primary fetch. Fine for top-level clones, but
submodule fetches run as separate `git fetch` invocations that inherit
nothing and fall back to anonymous HTTPS.

Attempted fix 1: flipped `persist-credentials` to `true`. Didn't resolve
it — checkout still only persists credentials for the primary repo's URL
(`github.com/gotero/jackpot-backend`), not for the URLs in `.gitmodules`.
Submodule fetches still got `128`: `could not read Username for
'https://github.com': terminal prompts disabled`.

Working fix: split the checkout into two explicit steps. First step
fetches the primary repo with `persist-credentials: false` (no auth
residue). Second step uses git's `url.<tokenized>.insteadOf <plain>`
config trick to rewrite github.com URLs on the fly to include the PAT in
Basic Auth, runs `git submodule update --init --recursive`, then scrubs
the config key. The block in the workflow:

```yaml
- name: Initialise jackpot-backend submodules
  working-directory: jackpot-backend
  env:
    GH_PAT: ${{ secrets.CROSS_REPO_PAT }}
  run: |
    set -euo pipefail
    git config --global url."https://x-access-token:${GH_PAT}@github.com/".insteadOf "https://github.com/"
    git config --global url."https://x-access-token:${GH_PAT}@github.com/".insteadOf "git@github.com:"
    git submodule update --init --recursive
    git config --global --unset-all url."https://x-access-token:${GH_PAT}@github.com/".insteadOf || true
```

### 63. `CROSS_REPO_PAT` was a Google OAuth client secret, not a GitHub PAT

Nastiest surprise of the night. Even after the workflow was restructured
to use the PAT correctly for submodule clones, it failed with the same
"terminal prompts disabled" error — this time on the **primary**
`jackpot-backend` clone, which had been working in earlier runs.

Diagnostic step revealed:

```
PAT length: 35
PAT prefix: GOCSPX-j...
api.github.com/repos/gotero/jackpot-backend: 401
```

`GOCSPX-` is the prefix for a Google OAuth client secret. Real GitHub
PATs start with `ghp_` (classic) or `github_pat_` (fine-grained). At
04:52:22 UTC someone had accidentally overwritten `CROSS_REPO_PAT` with
the value of one of the Google OAuth secrets — likely a cross-paste
during the earlier Secret Manager work on `jackpot-staging-database-url`.
The real PAT had been fine until then.

Why it appeared to work for the primary repo earlier: it didn't. The
earlier runs were all failing before this step executed, so the bad PAT
was silently riding in `CROSS_REPO_PAT` for hours without being
exercised.

Fix: `gh secret set CROSS_REPO_PAT --repo gotero/jackpot-iac`, pasted the
correct token. The real PAT had been validated directly with `curl` in
the prior step — all three repos returned `200` on both
`/repos/gotero/*` and `/repos/gotero/*/contents/README.md`.

Also revealed that the PAT type is fine-grained (classic PATs with `repo`
scope would have worked on any new private repo under `gotero/`).
Fine-grained PATs need their repo access list edited explicitly when new
repos like `jackpot-nf` are added — another footgun to remember.

### 64. Helm release stuck at `pending-upgrade`

After fixing the PAT, the workflow made it all the way to the Helm
upgrade step and immediately failed without attempting anything. The
cause: the previous revision (revision 8, which hit the 10-minute
`--wait` timeout on the `context deadline exceeded` path) had left
revision 9 in `pending-upgrade` state. Helm refuses to upgrade a release
that's mid-transaction, so every subsequent attempt was a no-op.

Fix: `helm -n jackpot rollback jackpot-api 8`. This created revision 10
with STATUS: `deployed`, allowing the next upgrade to proceed.

Backlog (operational): consider whether the workflow should run
`helm rollback` or `helm upgrade --atomic` to handle this automatically.
`--atomic` rolls back on failure, which keeps the release clean but
means timeouts lose the evidence for debugging. Glen's call, probably a
brief item when the next deploy pain point surfaces.

### 65. Smoke test placeholder URL — in-cluster port-forward workaround

Last failure was the `Smoke test` step, which hit
`https://api.staging.jackpot.example.org`. That domain was a placeholder
in `values-staging.yaml`, never intended to resolve. No Ingress,
LoadBalancer, or public DNS had been configured yet. curl returned
`000000` — connect-failed — on all three checks.

Verified the API was actually healthy by spinning up a curl pod inside
the cluster:

```
$ kubectl -n jackpot run curl-test --rm -it --restart=Never \
    --image=curlimages/curl:latest --command -- \
    curl -s -v http://jackpot-api.jackpot.svc.cluster.local/health
HTTP/1.1 200 OK
server: uvicorn
x-request-id: 22b21d1c-eed2-47df-8c23-e8d3e07ac731
{"status":"ok","version":"5.0.0","project":"JACKPOT","database":"connected"}
```

That confirmed uvicorn, the RequestID middleware, Cloud SQL connectivity,
and `/health` database probe were all working.

Tactical fix: rewrote the `Smoke test` step to use `kubectl port-forward
svc/jackpot-api 8080:80` (runs in the background after the earlier `Get
GKE credentials` step has authenticated kubectl), polls `localhost:8080`
for readiness, then runs the unchanged smoke test script pointed at
`http://localhost:8080`. One more commit, one more workflow run — green.

Backlog: set up the real external URL. Ingress, DNS, managed cert, update
`JACKPOT_API_URL` + `CORS_ORIGINS` + `GOOGLE_OAUTH_REDIRECT_URL` across
values files. Then the smoke test can go back to hitting the public URL.
Probably a Terraform session — likely goes with production prep in
Month 3.

### 66. `jackpot-frontend` is a vestigial stub — real UI lives in `jackpot-backend/frontend/`

With staging green, shifted focus to validating the Streamlit UI locally
end-to-end. Quickly discovered that the `jackpot-frontend` repo's `main.py`
is literally `print("Hello from jackpot-frontend!")` — no `app.py`, no
pages, no components. The Session 5 code audit correctly flagged this,
but the implication wasn't what the audit said it was.

The actual Streamlit code lives inside `jackpot-backend/frontend/`:

```
jackpot-backend/frontend/
├── __init__.py
├── app.py                # entry point — landing + navigation
├── components/           # shared widgets (tier badges, etc.)
├── lib/
│   ├── api.py           # ApiClient + ApiError (single HTTP surface)
│   └── session.py       # current_user(), my_user_id(), is_platform_admin()
└── pages/               # 9 researcher pages, auto-loaded by Streamlit
    ├── dashboard.py
    ├── search.py
    ├── upload.py
    ├── data_entry.py
    ├── my_samples.py
    ├── datasets.py
    ├── access_requests.py
    ├── notifications.py
    └── pipelines.py
```

The admin pages (`lab_director.py`, `platform_admin.py`,
`archive_requests.py`, `billing.py`) are intentionally absent — they're
deferred to Month 3.

**Consequence:** the `jackpot-frontend` repo is vestigial. It serves no
purpose today. Retirement of that repo goes on the Month 3 stretch goals
list so the future React migration can repurpose the repo name. All
current Streamlit work should happen inside `jackpot-backend/frontend/`.

### 67. Streamlit UI Docker plumbing — six chained bugs

The `ui` service in Docker Compose had been running for 23 hours reporting
"You can now view your Streamlit app" — but clicking into any page
threw `ModuleNotFoundError: No module named 'frontend'`. The fix was a
six-step chain where each fix revealed the next issue.

**Bug 1 — Dockerfile.ui flattened the layout.** `COPY frontend/ .`
copied the *contents* of `frontend/` into `/app/`, so inside the
container `app.py` sat at `/app/app.py` with `lib/` and `pages/` as
direct children of `/app/`. The absolute import
`from frontend.lib.session import current_user` couldn't resolve
because there was no `frontend/` package. Fix:

```dockerfile
COPY frontend/ ./frontend/      # preserve package name
CMD ["/opt/venv/bin/streamlit", "run", "frontend/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
```

**Bug 2 — Compose mount overrode the image layout.** Even with the
Dockerfile fix, the container still had the flattened layout. Root
cause: `docker-compose.yml` had
`volumes: - ./frontend:/app` which maps the host's `frontend/` dir
directly onto `/app/`, erasing whatever the image put there. Fix:

```yaml
volumes:
  - ./frontend:/app/frontend   # mount as subdirectory, preserve package
  - ./schema:/app/schema
```

**Bug 3 — Compose `command:` override.** The image CMD was now correct,
but the compose service had its own explicit
`command: /opt/venv/bin/streamlit run app.py ...` line that overrode
the image's CMD and still pointed at the old flattened path. Fix:
removed the compose-level `command:` line entirely so the image CMD
takes over.

**Bug 4 — Streamlit's `sys.path[0]` is the script directory, not the
repo root.** With the correct container layout,
`/app/frontend/app.py` executes, but Streamlit sets `sys.path[0]` to
`/app/frontend/` — so `from frontend.lib.session import current_user`
still fails because `/app/` isn't on the path. Fix: added
`PYTHONPATH: /app` to the `ui` service environment block.

**Bug 5 — `ApiClient` read the wrong env var name.** With all the
path issues resolved and Streamlit finally rendering the landing
page, the page showed "API unreachable — start the backend" even
though the API container was green and reachable. Root cause:
`frontend/lib/api.py`'s `ApiClient.__init__` read `JACKPOT_API_URL`
from env, falling back to `http://localhost:8000`, but compose was
setting `API_BASE_URL=http://api:8000`. Inside the UI container,
`localhost` is the UI container itself — so `/api/v1/users/me`
returned connection refused → `ApiError` → `current_user()` returned
`None` → misleading banner. Fix:

```python
self.base_url = (
    base_url
    or os.getenv("JACKPOT_API_URL")
    or os.getenv("API_BASE_URL")      # NEW fallback
    or "http://localhost:8000"
).rstrip("/")
```

**Bug 6 — `MOCK_USER_EMAIL` needed on both services.** Fixing Bug 5
alone surfaced that the API container wasn't identifying the user
either. The UI client ships `X-Mock-User-Email` as a parity header,
but the actual identity lookup happens server-side via
`os.getenv("MOCK_USER_EMAIL")` on the API process. Confirmed the env
var was already set on both services (compose line 78 for `api`, line
102 for `ui`). A patch-attempt accidentally created a duplicate
`MOCK_USER_EMAIL` on the `api` service; reverted it.

**Validation of the full stack:**

```bash
docker compose exec ui /opt/venv/bin/python -c \
    "from frontend.lib.api import get_client; \
     me = get_client().get('/api/v1/users/me'); \
     print('me:', me)"
```

Returned:

```
me: {'id': 1, 'email': 'gotero@linuxprophet.com', 'name': 'Glen Otero',
     'organization_id': 1, 'is_platform_admin': True, ...
     'lab_memberships': [{'lab_id': 1, 'is_lab_director': True,
                          'permission_group_id': 2, 'lab_name': 'Otero Lab',
                          'permission_group_name': 'Lab Director'}]}
```

Full UI-to-API-to-DB-to-UI loop verified. Mock auth identifies the
seeded admin user. `docker compose ps ui` reports `Up`, Streamlit
landing page renders at http://localhost:8501, all 9 researcher pages
appear in the sidebar.

**One remaining cosmetic issue:** the landing page still displays
"API unreachable" even when auth works — because `current_user()`
returns `None` for both network failures AND auth failures, and
`app.py` conflates the two paths. Tracked as backlog item Q-18.

### 68. CLAUDE.md Critical Rule 50 added

Consolidated the six bugs from topic 67 into a single Critical Rule so
the next developer who runs the stack locally doesn't repeat the full
debug sequence:

> **Rule 50 — Streamlit `frontend` package must be importable from `/app`.**
> Dockerfile must `COPY frontend/ ./frontend/`. Compose mount must be
> `./frontend:/app/frontend` (not `./frontend:/app`). No `command:`
> override in compose. `PYTHONPATH: /app` on the `ui` service. Both
> `ui` and `api` services must set `MOCK_USER_EMAIL`. `ApiClient` reads
> both `JACKPOT_API_URL` and `API_BASE_URL` as fallbacks.

Also added rules 44-49 from the earlier Session 5 addendum (Alembic
baseline, `list[str]` validators, `nf/` imports, secret prefixes,
`yaml.safe_load`, Helm `--wait` timeouts). CLAUDE.md now at 50
Critical Rules.

### 69. Documentation trio produced

Three project documents updated end-of-session to reflect current state:

**`todo.md`** — merged the user-provided task-level completion history
(477 tests / 86.99% coverage, Phase 0 through Phase 18 all checked)
with the Session 5 backlog. Added Phase 20 (Q-9 through Q-18 — Session
5 debt including UI fix for Q-18), Phase 21 (UI-A through UI-G — the
per-page triage burndown), Phase 23 (P3.1 test_batch.nf), Phase 24
(E2E staging pipeline test closing Q-5). Phase 21 UI-A marked complete
as of end of tonight.

**`spec.md`** — aggregated the user-provided spec v1.0 (dated 2026-04-15,
still claiming 275 tests and only 2 routers implemented) with Session 5
learnings. Updated Section 2 baseline to 477 tests / 86.99% coverage,
14 routers implemented. Preserved router specifications Sessions A-H
and Month 2 Sessions I-Q verbatim. Added new Section 9 (GCP staging
as-built topology — project, VPC, WIF, node pools, managed services,
secrets, access path, known quirks, cost profile), Section 10
(Streamlit UI local environment — layout, Docker/Compose contract,
ApiClient contract, the six bugs fixed), and Section 11 (current
priorities).

**`CLAUDE.md`** — aggregated the user-provided CLAUDE.md (had Rule 41
misplaced after Rules 42 and 43) with the Session 5 rules addendum.
Fixed the Rule 41 ordering, added Rules 44-50 for Session 5 lessons,
updated Docker Compose service names, corrected the Frontend
Architecture section to point at `jackpot-backend/frontend/`.

All three files rewrite their predecessors cleanly — no residual
inaccuracies around the Streamlit UI layout, the staging topology, or
the test baseline.

---

## Backlog Updates from This Session

Ten backlog items surfaced — all tactical fixes were applied during the
session, but permanent fixes need follow-up PRs. Seven from the staging
deploy work, three from the Streamlit UI debugging:

1. **`cors_origins` validator in `backend/config.py`.** Add
   `Annotated[list[str], NoDecode]` + `@field_validator` to accept JSON
   arrays, comma-separated strings, empty strings, and real lists.
   Prevents the next `values-*.yaml` edit from reproducing the opening
   failure mode. Quick PR, high leverage. Assign to Claude Code session.
   (Tracked as **Q-10** in `todo.md`.)

2. **Alembic baseline migration.** New migration that contains the full
   `db/init.sql` DDL as its `upgrade()` body, chained before
   `a7fd1fcccb77`. Makes `alembic upgrade head` work from an empty
   database in any deployment target without a bootstrap Job. Add
   Critical Rule 42 to CLAUDE.md: "The full schema must be reachable via
   `alembic upgrade head` from an empty database — never depend on
   `init.sql` running via Docker's entrypoint in production."
   (Tracked as **Q-9** in `todo.md`.)

3. **Terraform-owned `DATABASE_URL` Secret.** Wire the
   `terraform/modules/secrets/` module to construct the URL from the
   Cloud SQL module's outputs (host, port, db name) + the password
   Secret Manager entry. Eliminates the hand-populated Secret that gave
   us the `/jackpot` vs `/jackpot_db` drift. (Tracked as **Q-12**.)

4. **Rotate staging DB password.** Current value was visible in chat
   during debugging. Low blast radius (staging only), hygienic to rotate.
   `gcloud sql users set-password jackpot ...` + `gcloud secrets versions
   add` + redeploy. ~5 minutes of work. (Tracked as **Q-13**.)

5. **Move `RESULT_SCHEMAS` out of `nf/shared/`.** `backend/routers/
   pipelines.py`'s `sys.path.insert` hack works but is fragile. Vendor or
   relocate the Pydantic result schemas into `backend/pipeline_schemas.py`
   so backend Docker builds don't need a second `COPY nf/` stanza and
   import-time evaluation doesn't depend on a sibling repo's presence.
   Pairs naturally with the pipelines router implementation in Month 2.
   (Tracked as **Q-11**.)

6. **Public URL for staging.** Ingress + managed cert (cert-manager on
   GKE or GCP-managed certs with Ingress controller) + Cloud DNS record.
   Update `JACKPOT_API_URL` in `values-staging.yaml`, `CORS_ORIGINS`,
   `GOOGLE_OAUTH_REDIRECT_URL`, and the smoke test target. Terraform
   session. (Tracked as **Q-14**.)

7. **Bump GitHub Actions to Node 24.** Every workflow run currently
   warns that Node 20 is deprecated as of 2026-09-16. Either set
   `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` at the workflow level or
   wait for `actions/checkout@v5`, `azure/setup-helm@v5`,
   `google-github-actions/*@v3` releases. Trivial, not urgent.
   (Tracked as **Q-16**.)

8. **Helm `--wait` timeout recovery.** The first staging deploy had a
   Helm release stuck at `pending-upgrade` for ~30 minutes because
   revision 8 timed out and revision 9 never finished transitioning.
   Required manual `helm rollback`. Either add `--atomic` to the deploy
   workflow's `helm upgrade` command (auto-rolls-back on failure; clean
   but loses debug evidence) or add a pre-upgrade step that detects
   `pending-*` status and rolls back automatically before the next
   attempt. (Tracked as **Q-15**.)

9. **Fix misleading "API unreachable" banner on Streamlit landing
   page.** `current_user()` in `frontend/lib/session.py` returns `None`
   for both auth failures AND network failures; `frontend/app.py`
   conflates the two into a single warning that's misleading when auth
   is the real issue. Either change `ApiClient` to raise distinct
   exceptions for network vs. auth, or probe `/health` first in
   `app.py` and distinguish banners. 15 minutes with fresh eyes.
   (Tracked as **Q-18**.)

10. **Retire `jackpot-frontend` repo.** Vestigial stub — actual UI code
    lives in `jackpot-backend/frontend/`. Not a Q-series item; goes on
    the Month 3 stretch list so the repo name can be reused for the
    React migration when that arrives.

---

## State at end of Session 7

**Deployed:** Staging API live on GKE cluster `jackpot-staging-gke` in
`us-central1`, namespace `jackpot`. Deployment `jackpot-api`, 2/2 pods
Ready, ReplicaSet `jackpot-api-6f8b854cf5`, image
`us-central1-docker.pkg.dev/gotero3-acdp-488517/jackpot/jackpot-api:535dcdb`.
Helm release at revision 12, STATUS: `deployed`.

**Database:** Cloud SQL PostgreSQL 16 instance `jackpot-staging-db`,
database `jackpot_db`, private IP `10.188.230.3`, `alembic_version` at
`c536de6329e0` (head). All five migrations applied: initial baseline +
four patches.

**Health probe:** `GET /health` returns `200 OK` with body
`{"status":"ok","version":"5.0.0","project":"JACKPOT","database":"connected"}`
via in-cluster Service DNS (`jackpot-api.jackpot.svc.cluster.local`).
RequestID middleware firing.

**CI/CD:** `deploy-staging.yml` workflow green end-to-end from push-to-
`staging` through image build, push, migration, rollout, smoke test.
`CROSS_REPO_PAT` secret contains a real GitHub PAT with Contents: Read
on `gotero/jackpot-backend`, `gotero/jackpot-nf`, `gotero/jackpot-schema`.
Submodule auth handled via explicit `insteadOf` injection step.

**Streamlit UI (local Docker Compose):** Running cleanly at
`http://localhost:8501`. All 9 researcher pages in sidebar
(dashboard, search, upload, data_entry, my_samples, datasets,
access_requests, notifications, pipelines). Mock auth works end-to-end
— landing page's `current_user()` call returns Glen Otero with Otero
Lab Director membership. UI-to-API loop verified via
`docker compose exec ui`. The misleading "API unreachable" banner on
the landing page is cosmetic (tracked as Q-18).

**Repository state:**

- `jackpot-backend` on `staging` branch at HEAD commit `535dcdb`. Changes
  committed: `.gitmodules` (nf URL), `nf` pointer bump, `Dockerfile.api`
  (COPY nf/), `Dockerfile.ui` (COPY frontend/ ./frontend/ + CMD path),
  `docker-compose.yml` (volume mounts fixed, PYTHONPATH added,
  redundant command line removed), `frontend/lib/api.py` (API_BASE_URL
  fallback).
- `jackpot-iac` on `staging` branch. Changes committed: workflow
  restructure (split checkout, PAT injection, port-forwarded smoke test),
  `values-staging.yaml` (CORS_ORIGINS JSON-array form).
- `jackpot-nf` new repo at `gotero/jackpot-nf`, `main` branch, HEAD
  `a45fb13`.

**Documentation trio produced end-of-session:**

- `todo.md` — merged with existing Phase 0-18 completion history; added
  Phase 20 (Session 5 debt, Q-9 through Q-18), Phase 21 (UI page
  triage UI-A through UI-G, with UI-A complete), Phase 23 (test_batch.nf),
  Phase 24 (staging E2E closing Q-5).
- `spec.md` v2.0 — aggregated prior v1.0 content with Session 5
  as-built GCP topology (Section 9), Streamlit local environment
  (Section 10), current priorities (Section 11). 1,388 lines.
- `CLAUDE.md` — aggregated with Session 5 Critical Rules addendum.
  Fixed misplaced Rule 41. Added Rules 44-50. 2,272 lines, 50 Critical
  Rules total.
- `local_test_checklist.md` — Part 1 (API, always run) + Part 2 (UI,
  skip until P2.1 landed — which as of end of Session 5 is now
  landed and runnable).
- `jackpot_gcp_staging_deployment.html` — two-diagram reference
  (infrastructure topology + mental model with 6 callouts on Session 5
  quirks) saved to `~/ASU/jackpot/docs/`.

**Not yet done:**

- Public Ingress / DNS / cert for staging (Q-14)
- The ten backlog items above (Q-9 through Q-18 + repo retirement)
- Phase 21 UI-B through UI-G — per-page triage burndown
- Phase 23 — `scripts/test_batch.nf` minimal pipeline harness
- Phase 24 — end-to-end staging pipeline test (closes Q-5, gates
  `month-2-complete` tag)

**Next session candidates (in rough priority order):**

1. **Phase 21 UI page triage** (UI-B Upload → UI-C Search → UI-D Sample
   detail). After those three land, the Month 1 human-testable demo
   works: upload → search → view, all in the browser. One focused
   Claude Code session per page.
2. **Q-18 landing page banner fix.** 15-minute cleanup — distinguish
   network failure from auth failure in `frontend/app.py`.
3. **Q-10 cors_origins validator.** Permanent, prevents regressions.
4. **Q-9 Alembic baseline migration.** Permanent, eliminates bootstrap
   Job requirement for future environments including production.
5. **Q-14 public Ingress + DNS for staging.** Unblocks real Google OAuth
   flow testing and the staging E2E pipeline test.
