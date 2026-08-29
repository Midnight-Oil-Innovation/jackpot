"""baseline schema from init.sql

Revision ID: 5adf11b77c19
Revises:
Create Date: 2026-04-24 20:22:50.366819

Q-9: Alembic baseline. Reproduces the v4.1 schema previously bootstrapped
by db/init.sql via the postgres entrypoint. After this migration lands,
`alembic upgrade head` works against an empty database in every
deployment target. db/SCHEMA.sql is the read-only reference snapshot.

The DDL below is a verbatim copy of db/init.sql at the time of this
revision. Idempotent (CREATE TABLE IF NOT EXISTS, ON CONFLICT DO
NOTHING) so re-running on a populated DB is safe — useful for the
one-time `alembic stamp 5adf11b77c19` flow on environments deployed
before Q-9 (see deploy/docs/staging_access.md, "Baseline stamp for environments deployed before Q-9").

P0e A.3 (Critical Rule 55): the seed-data INSERTs at the bottom of the
DDL block originally hardcoded operator-specific names (Sonora Quest /
LabCorp / ASU / ADHS / Otero Lab / gotero@linuxprophet.com). They have
been edited in-place to use operator-agnostic dev-fixture values
(Example Sequencing Lab / Example Reference Lab / Example Org /
Example Lab / admin@example.org / Example Admin). The three follow-on
rename migrations (e5315db18d40, c1bd67369a7c, 00b4bd99ddee) become
no-ops on fresh installs (their UPDATE WHERE clauses match no rows)
but stay functional for any DB deployed before this edit landed.
Operator-customized seed data goes through `jackpot init` (P0e),
not migrations.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "5adf11b77c19"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA_DDL = r"""
CREATE TABLE IF NOT EXISTS permission_groups (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

INSERT INTO permission_groups (name) VALUES
    ('Platform Admin'), ('Lab Director'), ('Lab Collaborator'),
    ('Lab Reader'), ('Bioinformatics User'), ('Data Analyst')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS domain_whitelist (
    id          SERIAL PRIMARY KEY,
    domain      TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sequencing_labs (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    organization TEXT,
    lab_id       INTEGER,
    is_external  BOOLEAN NOT NULL DEFAULT TRUE,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO sequencing_labs (name, organization, is_external) VALUES
    ('Example Sequencing Lab',  'Example Sequencing Lab', TRUE),
    ('Example Reference Lab',   'Example Reference Lab',  TRUE)
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS sequencing_lab_requests (
    id              SERIAL PRIMARY KEY,
    requested_name  TEXT NOT NULL,
    organization    TEXT,
    requested_by_id INTEGER NOT NULL,
    lab_id          INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'PENDING',
    reviewed_by_id  INTEGER,
    reviewed_at     TIMESTAMPTZ,
    denial_reason   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS organizations (
    id                                          SERIAL PRIMARY KEY,
    display_name                                TEXT NOT NULL UNIQUE,
    default_approve_analytical_dataset_requests BOOLEAN NOT NULL DEFAULT FALSE,
    active                                      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                                  TIMESTAMPTZ DEFAULT NOW()
);

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

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_sequencing_labs_lab'
    ) THEN
        ALTER TABLE sequencing_labs
            ADD CONSTRAINT fk_sequencing_labs_lab
            FOREIGN KEY (lab_id) REFERENCES labs(id);
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS lab_membership (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lab_id              INTEGER NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
    permission_group_id INTEGER NOT NULL REFERENCES permission_groups(id),
    is_lab_director     BOOLEAN NOT NULL DEFAULT FALSE,
    granted_by_id       INTEGER REFERENCES users(id),
    granted_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, lab_id)
);

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

CREATE TABLE IF NOT EXISTS project_membership (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id          INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    permission_group_id INTEGER NOT NULL REFERENCES permission_groups(id),
    granted_by_id       INTEGER REFERENCES users(id),
    granted_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, project_id)
);

CREATE TABLE IF NOT EXISTS samples (
    id      SERIAL PRIMARY KEY,

    sample_id           TEXT NOT NULL UNIQUE,
    jackpot_uri         TEXT UNIQUE,
    lab_id              INTEGER NOT NULL REFERENCES labs(id),
    project_id          INTEGER NOT NULL REFERENCES projects(id),
    owner_id            INTEGER NOT NULL REFERENCES users(id),
    source_type         TEXT NOT NULL,

    organism_name       TEXT NOT NULL,
    strain              TEXT,
    isolate             TEXT,
    serotype            TEXT,

    biosample_accession TEXT,
    sra_accession       TEXT,
    genbank_accession   TEXT,
    gisaid_accession    TEXT,
    bioproject_accession TEXT,

    type_of_experiment              TEXT NOT NULL,
    nucleic_acid_extraction_method  TEXT[],
    library_preparation_method      TEXT NOT NULL,
    sequencing_protocol             TEXT NOT NULL,
    sequencing_platform             TEXT NOT NULL,
    sequencing_instrument           TEXT,
    sequencing_lab                  TEXT NOT NULL,

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

    ct_value                        FLOAT,
    other_testing_performed         TEXT[],
    lab_of_other_testing            TEXT[],
    intermediary_clinical_lab       TEXT,

    assembly_method                 TEXT,
    coverage_depth                  FLOAT,
    genome_completeness             FLOAT,

    pango_lineage                   TEXT,
    pango_lineage_version           TEXT,
    nextstrain_clade                TEXT,
    nextclade_qc_score              FLOAT,
    nextclade_version               TEXT,

    vadr_status                     TEXT,
    vadr_alerts                     TEXT[],

    mlst_scheme                     TEXT,
    mlst_sequence_type              TEXT,
    amrfinder_genes                 TEXT[],
    card_aro_terms                  TEXT[],

    loinc_code                      TEXT,
    loinc_system                    TEXT,
    snomed_clinical_finding         TEXT,

    ncbi_submission_status          TEXT NOT NULL DEFAULT 'NOT_SUBMITTED',
    ncbi_submitted_at               TIMESTAMPTZ,
    gisaid_submission_status        TEXT NOT NULL DEFAULT 'NOT_SUBMITTED',
    gisaid_submitted_at             TIMESTAMPTZ,

    fastq_r1_uri                    TEXT NOT NULL,
    fastq_r2_uri                    TEXT,
    raw_fastq_uri                   TEXT,
    consensus_fasta_uri             TEXT,
    assembly_uri                    TEXT,

    scrub_status                    TEXT NOT NULL DEFAULT 'PENDING',
    pii_scan_status                 TEXT NOT NULL DEFAULT 'PENDING',
    ingest_method                   TEXT NOT NULL DEFAULT 'gui',
    ingest_timestamp                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sharing_level                   TEXT NOT NULL DEFAULT 'PRIVATE',

    pi_name                         TEXT,
    grant_number                    TEXT,
    contact_other                   TEXT,
    comments                        TEXT,

    adhs_medsis_id                  TEXT,
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

    wildlife_subject_id             TEXT,
    companion_subject_id            TEXT,
    livestock_subject_id            TEXT,
    location_type                   TEXT,
    vaccine_status_against_pathogen TEXT,
    symptomatic                     TEXT,
    livestock_products              TEXT[],
    distribution_scale              TEXT[],
    antibiotic_use                  TEXT,

    vector_species                  TEXT,
    vector_host_species             TEXT,

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

    water_source                    TEXT,
    water_temperature_c             FLOAT,
    turbidity_ntu                   FLOAT,
    ph                              FLOAT,
    salinity_ppm                    FLOAT,

    air_source                      TEXT,
    airflow_rate_m3_s               FLOAT,
    pm25_ug_m3                      FLOAT,
    pm10_ug_m3                      FLOAT,

    soil_site_type                  TEXT,
    sample_depth_cm                 TEXT,
    nitrogen_mg_kg                  FLOAT,
    soil_temperature_c              FLOAT,
    moisture_g_g                    FLOAT,
    organic_carbon_g_kg             FLOAT,
    soil_ph                         FLOAT,
    soil_salinity_ppm               FLOAT,

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

    food_location_type              TEXT,
    storage_temperature_setting     TEXT,
    product_temperature_c           FLOAT,
    food_product_type               TEXT,
    plant_species                   TEXT,
    produce_water_source            TEXT[],
    fertilizer_type                 TEXT[],
    near_animal_agriculture         BOOLEAN,
    washed_before_packing           BOOLEAN,

    env_broad_scale                 TEXT,
    env_local_scale                 TEXT,
    env_medium                      TEXT,

    is_archived                      BOOLEAN NOT NULL DEFAULT FALSE,
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

CREATE TABLE IF NOT EXISTS sample_associations (
    id               SERIAL PRIMARY KEY,
    source_sample_id INTEGER NOT NULL REFERENCES samples(id),
    target_sample_id INTEGER NOT NULL REFERENCES samples(id),
    association_type TEXT NOT NULL,
    notes            TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_sample_id, target_sample_id)
);

CREATE TABLE IF NOT EXISTS sample_files (
    id               SERIAL PRIMARY KEY,
    sample_id_fk     INTEGER NOT NULL REFERENCES samples(id) ON DELETE CASCADE,

    uri              TEXT NOT NULL UNIQUE,
    raw_uri          TEXT,
    filename         TEXT NOT NULL,
    file_size_bytes  BIGINT,
    md5              TEXT,

    file_type        TEXT NOT NULL DEFAULT 'FASTQ',
    library_layout   TEXT NOT NULL DEFAULT 'UNPAIRED',
    read_direction   TEXT,
    lane             TEXT,
    chunk_index      INTEGER,

    paired_file_id   INTEGER REFERENCES sample_files(id),

    scrub_status     TEXT NOT NULL DEFAULT 'PENDING',
    pii_scan_status  TEXT NOT NULL DEFAULT 'PENDING',
    ingest_method    TEXT NOT NULL DEFAULT 'gui',
    ingest_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_archived       BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_sample_files_sample ON sample_files(sample_id_fk);
CREATE INDEX IF NOT EXISTS idx_sample_files_uri    ON sample_files(uri);
CREATE INDEX IF NOT EXISTS idx_sample_files_scrub  ON sample_files(scrub_status);

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

CREATE TABLE IF NOT EXISTS saved_searches (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lab_id       INTEGER REFERENCES labs(id),
    name         TEXT NOT NULL,
    query_params JSONB NOT NULL,
    scope        TEXT NOT NULL DEFAULT 'personal',
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO domain_whitelist (domain, description)
VALUES ('example.org', 'Example Org'),
       ('gmail.com',   'Local dev — REMOVE IN PRODUCTION')
ON CONFLICT DO NOTHING;

INSERT INTO organizations (display_name)
VALUES ('Example Org')
ON CONFLICT DO NOTHING;

INSERT INTO users (email, name, organization_id, is_platform_admin)
VALUES ('admin@example.org', 'Example Admin', 1, TRUE)
ON CONFLICT DO NOTHING;

INSERT INTO labs (organization_id, display_name, description, created_by_id)
VALUES (1, 'Example Lab', 'Local dev seed lab', 1)
ON CONFLICT DO NOTHING;

INSERT INTO lab_membership (user_id, lab_id, permission_group_id, is_lab_director, granted_by_id)
SELECT 1, 1, pg.id, TRUE, 1
FROM permission_groups pg WHERE pg.name = 'Lab Director'
ON CONFLICT DO NOTHING;

INSERT INTO projects (lab_id, display_name, description, created_by_id, pathogen_scope)
VALUES (1, 'Dev Project', 'Local dev seed project', 1,
        ARRAY['Severe acute respiratory syndrome coronavirus 2'])
ON CONFLICT DO NOTHING;

INSERT INTO sequencing_labs (name, organization, lab_id, is_external)
VALUES ('Example Lab', 'Example Org', 1, FALSE)
ON CONFLICT DO NOTHING;
"""


# Reverse FK-dependency order. Children before parents. The
# fk_sequencing_labs_lab constraint must be dropped before labs.
DROP_TABLES_REVERSE_ORDER = [
    "saved_searches",
    "pipeline_runs",
    "notifications",
    "notification_preferences",
    "gisaid_submissions",
    "ncbi_submissions",
    "archive_requests",
    "sample_access_requests",
    "dataset_access_requests",
    "dataset_files",
    "analytical_datasets",
    "metadata_tags",
    "sample_files",
    "sample_associations",
    "samples",
    "project_membership",
    "projects",
    "lab_membership",
    "labs",
    "audit_log",
    "personal_tokens",
    "users",
    "organizations",
    "sequencing_lab_requests",
    "sequencing_labs",
    "domain_whitelist",
    "permission_groups",
]


def upgrade() -> None:
    op.execute(SCHEMA_DDL)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE IF EXISTS sequencing_labs DROP CONSTRAINT IF EXISTS fk_sequencing_labs_lab;"
    )
    for table in DROP_TABLES_REVERSE_ORDER:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
