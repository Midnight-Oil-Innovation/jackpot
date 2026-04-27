-- =====================================================================
-- JACKPOT SCHEMA REFERENCE
-- DO NOT EDIT. This file is a human-readable snapshot of the schema.
-- Source of truth: Alembic migrations in db/migrations/versions/.
-- Regenerate with: pg_dump --schema-only -h localhost -U jackpot \
--   jackpot_db > db/SCHEMA.sql
-- =====================================================================

-- =============================================================================
-- JACKPOT Database Schema v4.1
-- Local: PostgreSQL 16 | Production: BigQuery
-- APGAP migration compatible
-- =============================================================================

CREATE TABLE IF NOT EXISTS permission_groups (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

INSERT INTO permission_groups (name) VALUES
    ('Platform Admin'), ('Lab Director'), ('Lab Collaborator'),
    ('Lab Reader'), ('Bioinformatics User'), ('Data Analyst')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Domain Whitelist
-- =============================================================================
CREATE TABLE IF NOT EXISTS domain_whitelist (
    id          SERIAL PRIMARY KEY,
    domain      TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- Sequencing Labs (database-managed controlled vocabulary)
-- NOT a static enum — managed at runtime by Platform Admins.
-- Auto-populated when new JACKPOT Labs are registered (APGAP backlog #42).
-- Lab Directors request new entries via sequencing_lab_requests (backlog #7).
-- =============================================================================
CREATE TABLE IF NOT EXISTS sequencing_labs (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    organization TEXT,
    lab_id       INTEGER,        -- FK to labs(id) added after labs table created
    is_external  BOOLEAN NOT NULL DEFAULT TRUE,
    -- FALSE = registered JACKPOT Lab (auto-added on lab creation)
    -- TRUE  = external commercial lab (Platform Admin approves)
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO sequencing_labs (name, organization, is_external) VALUES
    ('Sonora Quest Laboratories',         'Sonora Quest', TRUE),
    ('Laboratory Corporation of America', 'LabCorp',      TRUE)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Sequencing Lab Requests (Lab Director → Platform Admin approval)
-- =============================================================================
CREATE TABLE IF NOT EXISTS sequencing_lab_requests (
    id              SERIAL PRIMARY KEY,
    requested_name  TEXT NOT NULL,
    organization    TEXT,
    requested_by_id INTEGER NOT NULL,
    lab_id          INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'PENDING',   -- PENDING/APPROVED/DENIED
    reviewed_by_id  INTEGER,
    reviewed_at     TIMESTAMPTZ,
    denial_reason   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- Organizations
-- =============================================================================
CREATE TABLE IF NOT EXISTS organizations (
    id                                          SERIAL PRIMARY KEY,
    display_name                                TEXT NOT NULL UNIQUE,
    default_approve_analytical_dataset_requests BOOLEAN NOT NULL DEFAULT FALSE,
    active                                      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                                  TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- Users
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id                SERIAL PRIMARY KEY,
    email             TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL DEFAULT '',
    organization_id   INTEGER REFERENCES organizations(id),
    is_platform_admin BOOLEAN NOT NULL DEFAULT FALSE,
    is_data_analyst   BOOLEAN NOT NULL DEFAULT FALSE,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id     INTEGER REFERENCES users(id),
    deleted_by_id     INTEGER REFERENCES users(id),
    reactivated_by_id INTEGER REFERENCES users(id),
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- =============================================================================
-- Personal API Tokens (APGAP backlog #8)
-- token_hash is SHA-256 of the raw token; raw token shown once, never stored.
-- =============================================================================
CREATE TABLE IF NOT EXISTS personal_tokens (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    scopes     TEXT[] NOT NULL DEFAULT ARRAY['read'],
    last_used  TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- Audit Log (CLIA-aware — append-only; never UPDATE or DELETE rows here)
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id     INTEGER REFERENCES users(id),
    action      TEXT NOT NULL,
    resource    TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    detail      JSONB,
    ip_address  TEXT,
    request_id  TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_user     ON audit_log(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource, resource_id);

-- =============================================================================
-- Labs
-- =============================================================================
CREATE TABLE IF NOT EXISTS labs (
    id              SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    display_name    TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    gcs_bucket      TEXT,
    project_prefix  TEXT UNIQUE,
    build_status    TEXT,
    created_by_id   INTEGER REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Add FK from sequencing_labs to labs now that labs table exists
ALTER TABLE sequencing_labs
    ADD CONSTRAINT fk_sequencing_labs_lab
    FOREIGN KEY (lab_id) REFERENCES labs(id);

-- =============================================================================
-- Lab Membership
-- =============================================================================
CREATE TABLE IF NOT EXISTS lab_membership (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lab_id              INTEGER NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
    permission_group_id INTEGER NOT NULL REFERENCES permission_groups(id),
    is_lab_director        BOOLEAN NOT NULL DEFAULT FALSE,
    granted_by_id       INTEGER REFERENCES users(id),
    granted_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, lab_id)
);

-- =============================================================================
-- Projects (Seqera fields preserved for APGAP migration)
-- =============================================================================
CREATE TABLE IF NOT EXISTS projects (
    id                    SERIAL PRIMARY KEY,
    lab_id                INTEGER NOT NULL REFERENCES labs(id),
    display_name          TEXT NOT NULL,
    description           TEXT NOT NULL DEFAULT '',
    status                TEXT NOT NULL DEFAULT 'ACTIVE',
    gcs_bucket            TEXT,
    project_prefix        TEXT UNIQUE,
    pathogen_scope        TEXT[],
    active                BOOLEAN NOT NULL DEFAULT TRUE,
    build_status          TEXT,
    opt_out_of_seqera     BOOLEAN NOT NULL DEFAULT FALSE,
    seqera_workspace_id   TEXT NOT NULL DEFAULT '',
    seqera_compute_env_id TEXT NOT NULL DEFAULT '',
    seqera_credentials_id TEXT NOT NULL DEFAULT '',
    created_by_id         INTEGER REFERENCES users(id),
    deleted_by_id         INTEGER REFERENCES users(id),
    archived_by_id        INTEGER REFERENCES users(id),
    archived_at           TIMESTAMPTZ,
    deleted_at            TIMESTAMPTZ,
    deletion_justification TEXT NOT NULL DEFAULT '',
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- Project Membership
-- =============================================================================
CREATE TABLE IF NOT EXISTS project_membership (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id          INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    permission_group_id INTEGER NOT NULL REFERENCES permission_groups(id),
    granted_by_id       INTEGER REFERENCES users(id),
    granted_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, project_id)
);

-- =============================================================================
-- Samples — all 13 source types in one table
-- BigQuery prod: PARTITION BY DATE(ingest_timestamp)
--                CLUSTER BY organism_name, lab_id, sharing_level
-- =============================================================================
CREATE TABLE IF NOT EXISTS samples (
    id      SERIAL PRIMARY KEY,

    -- Identity
    sample_id           TEXT NOT NULL UNIQUE,
    jackpot_uri         TEXT UNIQUE,
    lab_id              INTEGER NOT NULL REFERENCES labs(id),
    project_id          INTEGER NOT NULL REFERENCES projects(id),
    owner_id            INTEGER NOT NULL REFERENCES users(id),
    source_type         TEXT NOT NULL,

    -- Pathogen
    organism_name       TEXT NOT NULL,
    strain              TEXT,
    isolate             TEXT,
    serotype            TEXT,

    -- Accessions (post-submission)
    biosample_accession TEXT,
    sra_accession       TEXT,
    genbank_accession   TEXT,
    gisaid_accession    TEXT,
    bioproject_accession TEXT,

    -- Experiment
    type_of_experiment              TEXT NOT NULL,
    nucleic_acid_extraction_method  TEXT[],
    library_preparation_method      TEXT NOT NULL,
    sequencing_protocol             TEXT NOT NULL,
    sequencing_platform             TEXT NOT NULL,
    sequencing_instrument           TEXT,
    sequencing_lab                  TEXT NOT NULL,

    -- Collection
    date_collected                  DATE NOT NULL,
    date_sequenced                  DATE NOT NULL,
    collection_facility             TEXT NOT NULL,
    purpose_for_collection          TEXT[],
    collection_location_country     TEXT NOT NULL,
    collection_location_state       TEXT,
    collection_location_county      TEXT,
    collection_location_zipcode     TEXT,
    geo_lat                         FLOAT,
    geo_lon                         FLOAT,
    mmwr_year                       INTEGER,
    mmwr_week                       INTEGER,
    iso_year                        INTEGER,
    iso_week                        INTEGER,

    -- Optional clinical / lab
    ct_value                        FLOAT,
    other_testing_performed         TEXT[],
    lab_of_other_testing            TEXT[],
    intermediary_clinical_lab       TEXT,

    -- Post-pipeline results
    assembly_method                 TEXT,
    coverage_depth                  FLOAT,
    genome_completeness             FLOAT,

    -- Viral lineage (auto-populated by Pangolin + Nextclade)
    pango_lineage                   TEXT,
    pango_lineage_version           TEXT,
    nextstrain_clade                TEXT,
    nextclade_qc_score              FLOAT,
    nextclade_version               TEXT,

    -- VADR (gates NCBI submission)
    vadr_status                     TEXT,
    vadr_alerts                     TEXT[],

    -- AMR (auto-populated by AMRFinder + MLST)
    mlst_scheme                     TEXT,
    mlst_sequence_type              TEXT,
    amrfinder_genes                 TEXT[],
    card_aro_terms                  TEXT[],

    -- ELR / clinical coding
    loinc_code                      TEXT,
    loinc_system                    TEXT,
    snomed_clinical_finding         TEXT,

    -- Submission status
    ncbi_submission_status          TEXT NOT NULL DEFAULT 'NOT_SUBMITTED',
    ncbi_submitted_at               TIMESTAMPTZ,
    gisaid_submission_status        TEXT NOT NULL DEFAULT 'NOT_SUBMITTED',
    gisaid_submitted_at             TIMESTAMPTZ,

    -- File locations (gs:// and drs:// both supported)
    fastq_r1_uri                    TEXT NOT NULL,
    fastq_r2_uri                    TEXT,
    raw_fastq_uri                   TEXT,
    consensus_fasta_uri             TEXT,
    assembly_uri                    TEXT,

    -- Ingest / lifecycle
    scrub_status                    TEXT NOT NULL DEFAULT 'PENDING',
    pii_scan_status                 TEXT NOT NULL DEFAULT 'PENDING',
    ingest_method                   TEXT NOT NULL DEFAULT 'gui',
    ingest_timestamp                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sharing_level                   TEXT NOT NULL DEFAULT 'PRIVATE',

    -- Administrative
    pi_name                         TEXT,
    grant_number                    TEXT,
    contact_other                   TEXT,
    comments                        TEXT,

    -- Human host
    external_case_id                  TEXT,
    case_id                         TEXT,
    biospecimen_type                TEXT,
    reason_for_collection           TEXT[],
    host_sex                        TEXT,
    host_age                        INTEGER,
    host_age_unit                   TEXT,
    host_species                    TEXT,
    host_disease                    TEXT[],
    isolation_source                TEXT,
    vaccination_status              TEXT,
    clinical_outcome                TEXT,
    underlying_conditions           TEXT[],

    -- Animal host fields
    wildlife_subject_id             TEXT,
    companion_subject_id            TEXT,
    livestock_subject_id            TEXT,
    location_type                   TEXT,
    vaccine_status_against_pathogen TEXT,
    symptomatic                     TEXT,
    livestock_products              TEXT[],
    distribution_scale              TEXT[],
    antibiotic_use                  TEXT,

    -- Vector fields
    vector_species                  TEXT,
    vector_host_species             TEXT,

    -- Wastewater (NWSS-aligned)
    wwtp_name                       TEXT,
    sample_location_zipcode         TEXT,
    county_names                    TEXT[],
    population_served               INTEGER,
    sample_type_ww                  TEXT,
    sample_matrix                   TEXT,
    pretreatment                    TEXT[],
    concentration_method            TEXT,
    flow_rate_mgd                   FLOAT,
    sample_collect_time             TEXT,
    pcr_target                      TEXT,
    pcr_gene_target                 TEXT,
    pcr_gene_target_ref             TEXT,
    pcr_type                        TEXT,
    quant_stan_type                 TEXT,
    stan_ref                        TEXT,
    lod_ref                         TEXT,
    inhibition_method               TEXT,
    num_no_target_control           INTEGER,
    pasteurized                     BOOLEAN,

    -- Water
    water_source                    TEXT,
    water_temperature_c             FLOAT,
    turbidity_ntu                   FLOAT,
    ph                              FLOAT,
    salinity_ppm                    FLOAT,

    -- Air
    air_source                      TEXT,
    airflow_rate_m3_s               FLOAT,
    pm25_ug_m3                      FLOAT,
    pm10_ug_m3                      FLOAT,

    -- Soil
    soil_site_type                  TEXT,
    sample_depth_cm                 TEXT,
    nitrogen_mg_kg                  FLOAT,
    soil_temperature_c              FLOAT,
    moisture_g_g                    FLOAT,
    organic_carbon_g_kg             FLOAT,
    soil_ph                         FLOAT,
    soil_salinity_ppm               FLOAT,

    -- Surface
    indoor_space                    TEXT,
    indoor_surface                  TEXT,
    indoor_surface_subpart          TEXT,
    surface_orientation             TEXT[],
    surface_material                TEXT[],
    surface_temperature_c           FLOAT,
    surface_air_contaminants        TEXT[],
    surface_moisture_qualitative    TEXT,
    surface_moisture_cm3_cm3        FLOAT,
    surface_moisture_ph             FLOAT,
    surface_humidity_pct            FLOAT,
    wall_surface_treatment          TEXT[],
    wall_texture                    TEXT[],
    wall_mold_signs                 TEXT,

    -- Food / Produce
    food_location_type              TEXT,
    storage_temperature_setting     TEXT,
    product_temperature_c           FLOAT,
    food_product_type               TEXT,
    plant_species                   TEXT,
    produce_water_source            TEXT[],
    fertilizer_type                 TEXT[],
    near_animal_agriculture         BOOLEAN,
    washed_before_packing           BOOLEAN,

    -- MIxS environmental context
    env_broad_scale                 TEXT,
    env_local_scale                 TEXT,
    env_medium                      TEXT,

    -- Soft delete
    is_deleted                      BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at                      TIMESTAMPTZ,
    deleted_by_id                   INTEGER REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_samples_lab      ON samples(lab_id);
CREATE INDEX IF NOT EXISTS idx_samples_project  ON samples(project_id);
CREATE INDEX IF NOT EXISTS idx_samples_organism ON samples(organism_name);
CREATE INDEX IF NOT EXISTS idx_samples_sharing  ON samples(sharing_level);
CREATE INDEX IF NOT EXISTS idx_samples_date     ON samples(date_collected);
CREATE INDEX IF NOT EXISTS idx_samples_scrub    ON samples(scrub_status);
CREATE INDEX IF NOT EXISTS idx_samples_pango    ON samples(pango_lineage);
CREATE INDEX IF NOT EXISTS idx_samples_ncbi     ON samples(ncbi_submission_status);
CREATE INDEX IF NOT EXISTS idx_samples_mmwr     ON samples(mmwr_year, mmwr_week);
CREATE INDEX IF NOT EXISTS idx_samples_source   ON samples(source_type);

-- =============================================================================
-- Sample Associations (cross-sample linkage)
-- From 'IDs of any associated samples' in ALL APGAP spreadsheets.
-- Stored as directed pairs; application maintains bidirectionality.
-- =============================================================================
CREATE TABLE IF NOT EXISTS sample_associations (
    id               SERIAL PRIMARY KEY,
    source_sample_id INTEGER NOT NULL REFERENCES samples(id),
    target_sample_id INTEGER NOT NULL REFERENCES samples(id),
    association_type TEXT NOT NULL,
    notes            TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_sample_id, target_sample_id)
);

-- =============================================================================
-- Sample Files — canonical per-file registry
-- Replaces flat fastq_r1_uri / fastq_r2_uri as source of truth for all files.
-- Those columns are kept on samples as convenience denormalized fields,
-- populated automatically by file_detector.py for simple 2-file paired runs.
--
-- Handles: simple paired-end, multi-lane Illumina, nanopore multi-chunk,
-- single-end, and any mix of .fastq/.fq/.fasta/.fa/.fna + .gz/.bz2.
--
-- After adding this table, run:
--   uv run alembic revision --autogenerate -m "add_sample_files_table"
--   uv run alembic upgrade head
-- =============================================================================
CREATE TABLE IF NOT EXISTS sample_files (
    id               SERIAL PRIMARY KEY,
    sample_id_fk     INTEGER NOT NULL REFERENCES samples(id) ON DELETE CASCADE,

    -- File identity
    uri              TEXT NOT NULL UNIQUE,
    -- gs:// or drs:// URI of the scrubbed file. UNIQUE — same physical
    -- file cannot be registered twice.
    raw_uri          TEXT,
    -- Pre-scrub URI; NULL after 30-day lifecycle deletion.
    -- Accessible to Lab Directors only.
    filename         TEXT NOT NULL,
    -- Original filename as uploaded.
    -- e.g. covid-19_sample_18_R1.fastq.gz, barcode01_0.fq.gz
    file_size_bytes  BIGINT,
    md5              TEXT,       -- populated post-upload for integrity checks

    -- Read structure (populated by file_detector.py)
    file_type        TEXT NOT NULL DEFAULT 'FASTQ',
    -- FASTQ / FASTA / OTHER — derived from file extension
    library_layout   TEXT NOT NULL DEFAULT 'UNPAIRED',
    -- PAIRED / SINGLE / UNPAIRED
    -- PAIRED   = one of a paired-end pair; partner in paired_file_id
    -- SINGLE   = paired-end read with missing partner
    -- UNPAIRED = genuinely single-end or nanopore chunk
    read_direction   TEXT,
    -- R1 / R2 / NULL (for unpaired or FASTA assembly files)
    lane             TEXT,
    -- Illumina lane: L001, L002, etc. NULL for non-multi-lane runs.
    chunk_index      INTEGER,
    -- Nanopore/multi-file chunk index (0-based). NULL for non-chunked.

    -- Pairing linkage
    paired_file_id   INTEGER REFERENCES sample_files(id),
    -- Points to the partner R2 file when this is R1, and vice versa.
    -- NULL for unpaired / single-end files.

    -- Lifecycle
    scrub_status     TEXT NOT NULL DEFAULT 'PENDING',
    pii_scan_status  TEXT NOT NULL DEFAULT 'PENDING',
    ingest_method    TEXT NOT NULL DEFAULT 'gui',
    ingest_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted       BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_sample_files_sample ON sample_files(sample_id_fk);
CREATE INDEX IF NOT EXISTS idx_sample_files_uri    ON sample_files(uri);
CREATE INDEX IF NOT EXISTS idx_sample_files_scrub  ON sample_files(scrub_status);

-- =============================================================================
-- Dynamic Metadata Tags (for lab-specific fields not in core schema)
-- =============================================================================
CREATE TABLE IF NOT EXISTS metadata_tags (
    id          SERIAL PRIMARY KEY,
    sample_id   INTEGER NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    key         TEXT NOT NULL,
    value       TEXT,
    values      TEXT[],
    data_type   TEXT NOT NULL DEFAULT 'TEXT',
    unit        TEXT,
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    source      TEXT
);

-- =============================================================================
-- Analytical Datasets
-- =============================================================================
CREATE TABLE IF NOT EXISTS analytical_datasets (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    gcs_bucket      TEXT NOT NULL DEFAULT '',
    approval_status TEXT NOT NULL DEFAULT 'PENDING',
    duo_codes       TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    seqera_data_link_id TEXT NOT NULL DEFAULT '',
    created_by_id   INTEGER REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dataset_files (
    id                    SERIAL PRIMARY KEY,
    analytical_dataset_id INTEGER NOT NULL REFERENCES analytical_datasets(id) ON DELETE CASCADE,
    original_sample_id    INTEGER NOT NULL REFERENCES samples(id),
    gcs_file_path         TEXT NOT NULL,
    file_size             BIGINT,
    status                TEXT NOT NULL DEFAULT 'PENDING',
    denied_by_id          INTEGER REFERENCES users(id),
    denial_reason         TEXT,
    copied_at             TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- Access Requests
-- =============================================================================
CREATE TABLE IF NOT EXISTS dataset_access_requests (
    id                  SERIAL PRIMARY KEY,
    dataset_id          INTEGER NOT NULL REFERENCES analytical_datasets(id),
    requester_id        INTEGER NOT NULL REFERENCES users(id),
    status              TEXT NOT NULL DEFAULT 'PENDING',
    purpose             TEXT,
    dua_accepted        BOOLEAN NOT NULL DEFAULT FALSE,
    requested_duo_codes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    reviewed_by_id      INTEGER REFERENCES users(id),
    reviewed_at         TIMESTAMPTZ,
    denial_reason       TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sample_access_requests (
    id             SERIAL PRIMARY KEY,
    sample_id      INTEGER NOT NULL REFERENCES samples(id),
    requester_id   INTEGER NOT NULL REFERENCES users(id),
    owner_id       INTEGER NOT NULL REFERENCES users(id),
    status         TEXT NOT NULL DEFAULT 'PENDING',
    dua_accepted   BOOLEAN NOT NULL DEFAULT FALSE,
    purpose        TEXT,
    reviewed_by_id INTEGER REFERENCES users(id),
    reviewed_at    TIMESTAMPTZ,
    denial_reason  TEXT,
    requested_at   TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- Archive Requests
-- =============================================================================
CREATE TABLE IF NOT EXISTS archive_requests (
    id                        SERIAL PRIMARY KEY,
    sample_id                 INTEGER NOT NULL REFERENCES samples(id),
    requested_by_id           INTEGER NOT NULL REFERENCES users(id),
    justification             TEXT NOT NULL,
    external_storage_location TEXT NOT NULL DEFAULT '',
    external_storage_type     TEXT NOT NULL DEFAULT 'OTHER',
    retention_requirement_met BOOLEAN NOT NULL DEFAULT FALSE,
    status                    TEXT NOT NULL DEFAULT 'PENDING',
    reviewed_by_id            INTEGER REFERENCES users(id),
    reviewed_at               TIMESTAMPTZ,
    denial_reason             TEXT NOT NULL DEFAULT '',
    created_at                TIMESTAMPTZ DEFAULT NOW(),
    updated_at                TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- NCBI Submissions (TOSTADAS)
-- =============================================================================
CREATE TABLE IF NOT EXISTS ncbi_submissions (
    id                     SERIAL PRIMARY KEY,
    submission_name        TEXT NOT NULL,
    lab_id                 INTEGER NOT NULL REFERENCES labs(id),
    project_id             INTEGER NOT NULL REFERENCES projects(id),
    submitted_by_id        INTEGER NOT NULL REFERENCES users(id),
    sample_ids             INTEGER[],
    submission_type        TEXT NOT NULL DEFAULT 'SRA',
    tostadas_run_id        TEXT,
    status                 TEXT NOT NULL DEFAULT 'PENDING',
    submission_package_uri TEXT,
    bioproject_accession   TEXT,
    submitted_at           TIMESTAMPTZ,
    completed_at           TIMESTAMPTZ,
    error_detail           TEXT,
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- GISAID Submissions
-- =============================================================================
CREATE TABLE IF NOT EXISTS gisaid_submissions (
    id              SERIAL PRIMARY KEY,
    lab_id          INTEGER NOT NULL REFERENCES labs(id),
    submitted_by_id INTEGER NOT NULL REFERENCES users(id),
    sample_ids      INTEGER[],
    pathogen        TEXT NOT NULL DEFAULT 'SARS-CoV-2',
    export_csv_uri  TEXT,
    status          TEXT NOT NULL DEFAULT 'DRAFT',
    submitted_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- Notifications
-- =============================================================================
CREATE TABLE IF NOT EXISTS notification_preferences (
    id                         SERIAL PRIMARY KEY,
    user_id                    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    email_on_upload            BOOLEAN NOT NULL DEFAULT TRUE,
    email_on_access_request    BOOLEAN NOT NULL DEFAULT TRUE,
    email_on_pipeline_complete BOOLEAN NOT NULL DEFAULT TRUE,
    email_on_budget_alert      BOOLEAN NOT NULL DEFAULT TRUE,
    email_on_ncbi_submission   BOOLEAN NOT NULL DEFAULT TRUE,
    in_app_enabled             BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS notifications (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type       TEXT NOT NULL,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    read       BOOLEAN NOT NULL DEFAULT FALSE,
    link       TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- Pipeline Runs
-- =============================================================================
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                  SERIAL PRIMARY KEY,
    lab_id              INTEGER NOT NULL REFERENCES labs(id),
    project_id          INTEGER NOT NULL REFERENCES projects(id),
    launched_by_id      INTEGER NOT NULL REFERENCES users(id),
    pipeline_name       TEXT NOT NULL,
    pipeline_version    TEXT,
    sample_ids          INTEGER[],
    status              TEXT NOT NULL DEFAULT 'PENDING',
    launcher_type       TEXT NOT NULL DEFAULT 'native',
    gcp_batch_job_id    TEXT,
    seqera_run_id       TEXT,
    result_uri          TEXT,
    multiqc_report_uri  TEXT,
    nextstrain_json_uri TEXT,
    launched_at         TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

-- =============================================================================
-- Saved Searches (APGAP backlog #21)
-- =============================================================================
CREATE TABLE IF NOT EXISTS saved_searches (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lab_id       INTEGER REFERENCES labs(id),
    name         TEXT NOT NULL,
    query_params JSONB NOT NULL,
    scope        TEXT NOT NULL DEFAULT 'personal',
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- Seed data for local development
-- =============================================================================
INSERT INTO domain_whitelist (domain, description)
VALUES ('linuxprophet.org', 'Linux Prophet'),
       ('gmail.com', 'Local dev — REMOVE IN PRODUCTION')
ON CONFLICT DO NOTHING;

INSERT INTO organizations (display_name)
VALUES ('Linux Prophet'), ('ADHS')
ON CONFLICT DO NOTHING;

INSERT INTO users (email, name, organization_id, is_platform_admin)
VALUES ('gotero@linuxprophet.com', 'Glen Otero', 1, TRUE)
ON CONFLICT DO NOTHING;

INSERT INTO labs (organization_id, display_name, description, created_by_id)
VALUES (1, 'Otero Outpost', 'Local dev seed lab', 1)
ON CONFLICT DO NOTHING;

INSERT INTO lab_membership (user_id, lab_id, permission_group_id, is_lab_director, granted_by_id)
SELECT 1, 1, pg.id, TRUE, 1
FROM permission_groups pg WHERE pg.name = 'Lab Director'
ON CONFLICT DO NOTHING;

INSERT INTO projects (lab_id, display_name, description, created_by_id, pathogen_scope)
VALUES (1, 'Dev Project', 'Local dev seed project', 1,
        ARRAY['Severe acute respiratory syndrome coronavirus 2'])
ON CONFLICT DO NOTHING;

-- Auto-add Otero Outpost as a sequencing lab (demonstrates the backlog #42 auto-add hook)
INSERT INTO sequencing_labs (name, organization, lab_id, is_external)
VALUES ('Otero Outpost', 'Linux Prophet', 1, FALSE)
ON CONFLICT DO NOTHING;
