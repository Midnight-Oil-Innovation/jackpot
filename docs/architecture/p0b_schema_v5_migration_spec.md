# P0b (Schema v5.0) Migration Spec — Phase 24.5 Close-out

**Branch point:** new single migration off head `85d92864ed38` (FED-D, `down_revision = 591318fd3049`, Create Date 2026-05-12).
**Style:** raw SQL via `op.execute("...")` with `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. Not `op.create_table`.
**Two-track rule:** `target_metadata=None`. Every change below states the DDL side and the LinkML side (or "DDL-only") plus whether `regen_schema.py` must run.
**Scope discipline:** this closes the sovereignty-deletion, BYOP-table, eukaryotic-metadata, and two cryptWWDB-readiness schema items only. Behavior (P0c) and deferred observatory items are noted, not specced.

> **Read the "Drift and gaps" section first if you are the implementing agent.** Three assumptions carried in the P0b planning brief do not match the applied schema (`audit_log.event_type`, the `pipeline_results` FK, and the eukaryotic organism count). The spec below is written against the real applied state, not the brief.

---

## 1. Source-doc mapping

The P0b migration draws from four sources. `sovereignty-compliant-deletion.md` §12 supplies the deletion-lifecycle columns on `samples`, one boolean on `pipeline_results`, one index, and one check constraint; its §13 is P0c behavior and is out of scope. `byop_and_eukaryotic_design.md` §7 supplies the `byop_pipelines` table and four net-new pipeline enums, plus two `pipeline_results` columns; its §12.1 supplies OrganismNameEnum additions, §12.2 supplies five eukaryotic `samples` columns and two supporting enums, and §12.3 supplies eight typed result tables that this spec **defers** (rationale in §4). `cryptwwdb_integration.md` supplies exactly two schema-readiness items (`B-CWB-SCHEMA-1`, `B-CWB-SCHEMA-2`), both named only in its Open Questions and Rec-2, and both thinly specified; their shape is derived from the applied `wastewater_lineage_abundance` pattern and the applied `sample_associations` pattern respectively and marked `[THIN-SOURCE]`. Where a source is too thin to spec confidently: cryptWWDB gives no column list for `wastewater_target_concentration` (derived below); the sovereignty doc assumes a `pipeline_results` FK and an `audit_log.event_type` column that do not exist in the applied schema (both resolved in §4); and the BYOP design writes a LinkML block for `pipeline_results` that has no corresponding yaml class (resolved as DDL-only).

---

## 2. Change catalog

Grouped by target. "Verified against" cites the line/table in `applied_ddl_chain.txt` that was read before asserting net-new vs modifies-applied.

### 2.1 `samples` — sovereignty deletion columns

**Source:** sovereignty §12 (schema table + Constraints).
**Net-new:** all six columns. Verified against `CREATE TABLE ... samples` (applied_ddl_chain.txt line 2821) and the v4.2 additions migration `1de94c16e612` (line 2484): none of `deletion_status`, `deletion_requested_at`, `deletion_requested_by_user_id`, `deletion_reason`, `tombstoned_at`, `vacuumed_at` are present. Grep for `deletion_status|tombston|vacuum` across the full chain returns zero hits.

DDL:

```sql
ALTER TABLE samples
    ADD COLUMN IF NOT EXISTS deletion_status               TEXT NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS deletion_requested_at         TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS deletion_requested_by_user_id INTEGER REFERENCES users(id),
    ADD COLUMN IF NOT EXISTS deletion_reason               TEXT,
    ADD COLUMN IF NOT EXISTS tombstoned_at                 TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS vacuumed_at                   TIMESTAMPTZ;
```

**deletion_status representation — deliberate divergence from §12.** §12 specs `CREATE TYPE deletion_status_enum AS ENUM (...)`. This migration implements `deletion_status` as **TEXT + CHECK**, not a native Postgres enum. Rationale: the lifecycle can gain states (a `LEGAL_HOLD` state is already foreseeable) and Postgres cannot drop an enum value once added, so TEXT+CHECK is the forward-flexible choice. It also matches the applied house precedent: `audit_log.action`, `data_source_lab` status columns, and the v4.2 `quality_status`/`sector` columns are all TEXT, not native enums. The divergence is intentional and documented here so it is not silent drift.

yaml edit: add `DeletionStatusEnum` to the `enums:` block and add `deletion_status` (range `DeletionStatusEnum`), `deletion_requested_at`, `deletion_requested_by_user_id`, `deletion_reason`, `tombstoned_at`, `vacuumed_at` to the base `Sample` class (`jackpot_schema.yaml` line 85). The LinkML enum stays even though the DDL is TEXT: it drives the Pydantic and JSON layer per §12. **regen required** (gen-pydantic + Rule 20 boolean/newline patch, then gen-json-schema).

```yaml
DeletionStatusEnum:
  permissible_values:
    ACTIVE:
    DELETION_REQUESTED:
    TOMBSTONED:
    VACUUMED:
```

Rollback: `ALTER TABLE samples DROP COLUMN IF EXISTS deletion_status, ... vacuumed_at;` and drop the check/index below first (constraint depends on the column).

### 2.2 `samples` — deletion check constraint + index

**Source:** sovereignty §12 Constraints.
**Net-new.** No existing named constraint or index on these columns (they did not exist until 2.1).

DDL:

```sql
ALTER TABLE samples
    ADD CONSTRAINT samples_deletion_status_values_chk
    CHECK (deletion_status IN ('ACTIVE','DELETION_REQUESTED','TOMBSTONED','VACUUMED'));

ALTER TABLE samples
    ADD CONSTRAINT samples_deletion_active_requested_chk
    CHECK ((deletion_status = 'ACTIVE') = (deletion_requested_at IS NULL));

CREATE INDEX IF NOT EXISTS samples_deletion_status_tombstoned_at_idx
    ON samples (deletion_status, tombstoned_at);
```

Existing rows are safe: all default to `deletion_status='ACTIVE'` with `deletion_requested_at IS NULL`, satisfying both checks. The value-set check is the TEXT+CHECK stand-in for the rejected native enum.

yaml edit: none beyond the enum in 2.1 (LinkML does not model check constraints). **DDL-only for the constraint and index.**

Rollback: `DROP INDEX IF EXISTS samples_deletion_status_tombstoned_at_idx;` and `ALTER TABLE samples DROP CONSTRAINT IF EXISTS ...` for both constraints.

### 2.3 `pipeline_results` — tombstoned boolean

**Source:** sovereignty §12 schema table.
**Net-new.** Verified against `CREATE TABLE ... pipeline_results` (line 1963): columns are `id, run_id, sample_id, pipeline_name, pipeline_version, metrics, results_json, created_at, updated_at`, `UNIQUE (run_id, sample_id)`. No `tombstoned`.

DDL:

```sql
ALTER TABLE pipeline_results
    ADD COLUMN IF NOT EXISTS tombstoned BOOLEAN NOT NULL DEFAULT FALSE;
```

**No FK change.** §12 Constraints instruct that "the FK from `pipeline_results.sample_id` to `samples.sample_id` MUST NOT cascade-delete." There is no such FK to modify: `pipeline_results.sample_id` is `TEXT NOT NULL` with no `REFERENCES` clause (line 1965), linked to `samples.sample_id` (`TEXT NOT NULL UNIQUE`, line 2824) by value only. The non-cascade requirement is therefore vacuously satisfied. **Do not add an FK in P0b** — adding one now risks failing on any orphan `pipeline_results` rows and is behavior-scope creep. The P0c tombstone step (`B-CARE-3b`) updates `pipeline_results.tombstoned = TRUE WHERE sample_id = <the sample's business sample_id string>`; it joins on the TEXT value, not a referential key.

yaml edit: **DDL-only.** There is no `pipeline_results` class in `jackpot_schema.yaml` (the class list runs Sample → ... → SampleFile → ExecutionProfile → PipelineDefaultProfile; result tables are DDL-only). No regen.

Rollback: `ALTER TABLE pipeline_results DROP COLUMN IF EXISTS tombstoned;`

### 2.4 `pipeline_results` — BYOP linkage columns

**Source:** byop §7 ("`pipeline_results` table gains").
**Net-new.** Same verification as 2.3; no `byop_pipeline_id` / `byop_pipeline_version`.

DDL (create `byop_pipelines` first — see 2.6 — so the FK target exists):

```sql
ALTER TABLE pipeline_results
    ADD COLUMN IF NOT EXISTS byop_pipeline_id      INTEGER REFERENCES byop_pipelines(id),
    ADD COLUMN IF NOT EXISTS byop_pipeline_version TEXT;
```

`byop_pipeline_id` is nullable: null for curated-zoo runs, set for BYOP runs. This FK does not need a non-cascade note; `byop_pipelines` rows are not deletion-lifecycle subjects.

yaml edit: **DDL-only.** The BYOP design writes a `pipeline_results: attributes:` yaml block, but no `pipeline_results` class exists in the applied yaml, so there is nothing to extend. Do not create a `pipeline_results` LinkML class in P0b (that is a larger modeling decision, and every other result table is DDL-only). No regen. This is a design-vs-applied mismatch, flagged in §4.

Rollback: `ALTER TABLE pipeline_results DROP COLUMN IF EXISTS byop_pipeline_id, DROP COLUMN IF EXISTS byop_pipeline_version;` (drop before dropping `byop_pipelines`).

### 2.5 Enums — four net-new BYOP pipeline enums

**Source:** byop §7.
**Net-new.** Grep of `jackpot_schema.yaml` confirms `PipelineEngineEnum`, `PipelineSourceTypeEnum`, `PipelineStatusEnum`, `DataTypeEnum` are all absent. Note: `SourceTypeEnum` (line 2131) and `ContainerEngineEnum` (line 2845) already exist and are **not** these; do not confuse `applicable_source_types: range: SourceTypeEnum` (reuses the existing sample-source enum) with `source_type: range: PipelineSourceTypeEnum` (net-new code-delivery enum). The design uses both intentionally.

yaml edit: add the four enums to the `enums:` block, values exactly as §7 lists them (PipelineEngineEnum: nextflow/snakemake/wdl/manifest; PipelineSourceTypeEnum: git/git_private/tarball/docker; PipelineStatusEnum: SUBMITTED/VALIDATING/SANDBOX_PENDING/SANDBOX_RUNNING/ACTIVE/DEACTIVATED/ARCHIVED/VALIDATION_FAILED/SANDBOX_FAILED/SANDBOX_TIMEOUT; DataTypeEnum: paired_end_short_read/single_end_short_read/long_read/assembly/raw_signal/metagenomic). **regen required.**

These enums are added to yaml even though `byop_pipelines` itself is DDL-only (2.6): gen-pydantic emits standalone enum classes regardless of whether a LinkML class consumes them, giving the P0c BYOP API a typed vocabulary to import. The DDL encodes the same value sets as CHECK constraints (2.6). This is the deliberate split: enums in yaml for the Pydantic layer, table in DDL for the house operational-table pattern.

DDL: none for the enums themselves (values live in the 2.6 CHECK constraints).

Rollback: remove the four enums from yaml and regen; no DDL rollback.

### 2.6 New table — `byop_pipelines`

**Source:** byop §7.
**Net-new.** No `byop_pipelines` anywhere in the chain.
**Reconciliation with the applied `project_pipelines` skeleton (line 1785):** supersede, do not extend. Rationale in §4.

DDL (TEXT+CHECK for the enum-typed columns, matching house convention and the deletion_status decision):

```sql
CREATE TABLE IF NOT EXISTS byop_pipelines (
    id                     SERIAL PRIMARY KEY,
    name                   TEXT NOT NULL,
    display_name           TEXT NOT NULL,
    version                TEXT NOT NULL,
    description            TEXT,
    engine_type            TEXT NOT NULL
        CHECK (engine_type IN ('nextflow','snakemake','wdl','manifest')),
    engine_version         TEXT NOT NULL,
    source_type            TEXT NOT NULL
        CHECK (source_type IN ('git','git_private','tarball','docker')),
    source_url             TEXT,
    source_ref             TEXT,
    source_uploaded_uri    TEXT,
    source_sha256          TEXT,
    docker_image           TEXT,
    docker_digest          TEXT,
    manifest_yaml          TEXT NOT NULL,
    applicable_organisms   TEXT[],
    applicable_source_types TEXT[],
    applicable_data_types  TEXT[],
    owner_lab_id           INTEGER REFERENCES labs(id),
    sharing_scope          TEXT NOT NULL DEFAULT 'lab'
        CHECK (sharing_scope IN ('private','lab','federation')),
    origin_instance_id     UUID REFERENCES federated_instances(id),
    pipeline_status        TEXT NOT NULL DEFAULT 'SUBMITTED'
        CHECK (pipeline_status IN (
            'SUBMITTED','VALIDATING','SANDBOX_PENDING','SANDBOX_RUNNING',
            'ACTIVE','DEACTIVATED','ARCHIVED','VALIDATION_FAILED',
            'SANDBOX_FAILED','SANDBOX_TIMEOUT')),
    validation_log         TEXT,
    sandbox_log            TEXT,
    registered_by_user_id  INTEGER NOT NULL REFERENCES users(id),
    registered_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at           TIMESTAMPTZ,
    deactivated_at         TIMESTAMPTZ,
    last_validated_at      TIMESTAMPTZ,
    license_spdx           TEXT NOT NULL,
    citation               TEXT,
    cost_estimate_usd      DOUBLE PRECISION,
    UNIQUE (name, version)
);
```

Notes: `applicable_organisms` / `applicable_source_types` / `applicable_data_types` are stored as `TEXT[]` (matching the applied `samples.purpose_for_collection TEXT[]` etc. pattern) rather than as per-value FK join tables; the enumerations are validated at the application layer against the yaml enums, consistent with how the applied `samples` array columns already work. `UNIQUE (name, version)` follows the manifest identity model (§7 name = lowercase-hyphen from manifest, version = semver).

**Tenancy resolved (design gap closed in P0b).** §7 gave `byop_pipelines` no tenancy scope at all. That gap is closed here rather than deferred, because retrofitting scope columns in P0c is exactly the double-migrate churn Phase 24.5 exists to prevent. Three columns are added at creation:

- `owner_lab_id INTEGER REFERENCES labs(id)` — ownership pointer. A pipeline is owned by exactly one lab. Nullable to allow operator-global pipelines with no single owning lab.
- `sharing_scope TEXT NOT NULL DEFAULT 'lab'` (CHECK `private`/`lab`/`federation`) — visibility, orthogonal to ownership. `federation` is the value that publishes a pipeline to federation peers. Ownership and visibility are deliberately separate columns; collapsing them breaks the moment a pipeline is shared.
- `origin_instance_id UUID REFERENCES federated_instances(id)` — federation provenance. NULL for locally-owned pipelines; populated on a federation-imported pipeline to record the originating instance. Typed UUID to match `federated_instances.id` (UUID PK), not INTEGER.

**Federation semantics: copy-on-import.** A pipeline shared at `sharing_scope='federation'` is materialized as an independent row on the importing instance, with `origin_instance_id` set to the source and its own local `id`. It is a copy, not a live cross-instance reference. This is the only model compatible with air-gappable, network-denied deployment (Scenario R): a lab must be able to run an imported pipeline with the network down, which a live reference to the originating instance cannot guarantee. `origin_instance_id` is therefore provenance, not a live pointer; drift between the copy and the source when the source updates is accepted and is a P0c sync-policy concern, not a P0b schema concern.

yaml edit: **DDL-only for the table.** Keep `byop_pipelines` out of the yaml `classes:` block, matching the applied precedent that `project_pipelines`, `lab_pipelines`, `pipeline_catalog`, and all result tables are DDL-only. The backend hand-writes the SQLAlchemy model and a Pydantic schema that imports the 2.5 enums. (The design wrote a LinkML `byop_pipelines` class; this spec declines it for consistency — see §4.) No regen attributable to the table itself; regen in 2.5 covers the enums.

Rollback: `DROP TABLE IF EXISTS byop_pipelines;` (drop the 2.4 `pipeline_results.byop_pipeline_id` FK column first).

### 2.7 Enums + `samples` — eukaryotic metadata

**Source:** byop §12.1 (OrganismNameEnum), §12.2 (samples columns + two enums).
**Net-new columns.** Verified against samples (line 2821) and `1de94c16e612`: no `parasite_developmental_stage`, `sample_preservation_method`, `parasitemia_percent`, `multiplicity_of_infection`, `coinfection_organisms`.

DDL:

```sql
ALTER TABLE samples
    ADD COLUMN IF NOT EXISTS parasite_developmental_stage TEXT,
    ADD COLUMN IF NOT EXISTS sample_preservation_method    TEXT,
    ADD COLUMN IF NOT EXISTS parasitemia_percent           DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS multiplicity_of_infection     INTEGER,
    ADD COLUMN IF NOT EXISTS coinfection_organisms         TEXT[];
```

`parasite_developmental_stage` and `sample_preservation_method` are enum-typed in yaml but stored as plain TEXT in DDL (no CHECK) to match how the existing enum-backed sample columns are stored (`biospecimen_type`, `host_sex`, etc. are TEXT with application-layer validation). `coinfection_organisms TEXT[]` matches the `target_organisms TEXT[]` precedent from v4.2.

**OrganismNameEnum additions — corrected count.** §12.1's header says "~25 additions" and states the enum currently has 62 values; the enumerated list actually contains **39** species-level values, and one of them (`Toxoplasma gondii`) is **already present** in the applied enum (verified: grep of OrganismNameEnum returns an existing `Toxoplasma gondii:` and `Naegleria fowleri:`). Add the **38 net-new** values only; omit the duplicate `Toxoplasma gondii` to avoid a duplicate `permissible_values` key. See §4.

yaml edit: add `ParasiteDevelopmentalStageEnum` and `SamplePreservationMethodEnum` to `enums:` (values exactly as §12.2 lists); add the 38 net-new OrganismNameEnum values (line 1854); add `parasite_developmental_stage` (range `ParasiteDevelopmentalStageEnum`), `sample_preservation_method` (range `SamplePreservationMethodEnum`), `parasitemia_percent`, `multiplicity_of_infection`, and `coinfection_organisms` (multivalued, range `OrganismNameEnum`) to the base `Sample` class. **regen required.**

Rollback: `ALTER TABLE samples DROP COLUMN IF EXISTS parasite_developmental_stage, ... coinfection_organisms;` remove the two enums and 38 values from yaml and regen.

### 2.8 `sample_associations` — `wastewater_upstream_of` association type (`B-CWB-SCHEMA-2`) `[THIN-SOURCE]`

**Source:** cryptwwdb Open Questions ("Schema versioning strategy" bullet names B-CWB-SCHEMA-2); shape derived from the applied `sample_associations` pattern.
**Modifies-applied at the yaml layer only; no DDL.** Verified against `CREATE TABLE ... sample_associations` (line 3027): `association_type` is `TEXT NOT NULL` with no CHECK constraint. A new association type is therefore a new string value, not a schema change.

DDL: **none.** `association_type` is free TEXT; `wastewater_upstream_of` is a valid value already.

yaml edit: add `wastewater_upstream_of:` to `SampleAssociationTypeEnum` (line 2618, which currently holds same_household, same_outbreak, host_vector, human_pet, food_source_clinical, environmental_clinical, longitudinal, other). This is a directional association (source sample is upstream of target in the sewershed), which fits the existing directional `source_sample_id → target_sample_id` model. **regen required** (the enum drives the Pydantic layer; the DDL does not enforce it).

Rollback: remove the value from yaml and regen; no DDL rollback.

### 2.9 New table — `wastewater_target_concentration` (`B-CWB-SCHEMA-1`) `[THIN-SOURCE]`

**Source:** cryptwwdb Rec-2 and Open Questions name the result type; no column list given. Shape derived from the applied `wastewater_lineage_abundance` result-table pattern (line 2167) and the cryptWWDB framework's stated per-sample data (flow rate, target concentration, units, timestamp, LOD/non-detect handling).
**Net-new.** No `wastewater_target_concentration` in the chain.

DDL (follows the applied result-table pattern: `run_id TEXT`, `sample_id TEXT`, no FK, `UNIQUE` including the discriminating dimension):

```sql
CREATE TABLE IF NOT EXISTS wastewater_target_concentration (
    id                     SERIAL PRIMARY KEY,
    run_id                 TEXT NOT NULL,
    sample_id              TEXT NOT NULL,
    target                 TEXT NOT NULL,
    target_type            TEXT,
    concentration          DOUBLE PRECISION,
    concentration_unit     TEXT NOT NULL,
    flow_rate_mgd          DOUBLE PRECISION,
    below_lod              BOOLEAN NOT NULL DEFAULT FALSE,
    lod_value              DOUBLE PRECISION,
    collection_timestamp   TIMESTAMPTZ,
    tool_name              TEXT,
    tool_version           TEXT,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (run_id, sample_id, target)
);
```

Derivation notes, flagged `[THIN-SOURCE]` because the doc specifies no columns: `target`/`target_type` generalize the framework's "target chemical or pathogen RNA copies"; `concentration` + `concentration_unit` + `flow_rate_mgd` are the `(C, Q)` operands the mass-balance query consumes; `below_lod` + `lod_value` encode the framework's LOD/2 non-detect substitution referenced in the mass-balance module; `collection_timestamp` supports the framework's temporal-equality query. The `flow_rate_mgd` naming matches the applied `samples.flow_rate_mgd` column. Confirm target semantics against the cryptWWDB reference implementation before P0c wiring; this is a readiness stub, not a validated schema.

**Sample linkage divergence.** The BYOP/eukaryotic design models result tables with `sample_id: range: samples` (an integer FK). This table instead uses `sample_id TEXT` with no FK, matching every applied result table (`pangolin_results`, `wastewater_lineage_abundance`, etc.). The LinkML `range: samples` convention is not honored in DDL for result tables; flagged in §4.

yaml edit: **DDL-only.** No result-table class exists in the yaml; do not add one (consistency with 2.3/2.4). No regen.

Rollback: `DROP TABLE IF EXISTS wastewater_target_concentration;`

### 2.10 `audit_log` — four new event constants

**Source:** sovereignty §12 (labeled "enum extension") and §13 `B-CARE-3f`.
**No DDL, no yaml.** Verified against the applied `audit_log`: the init.sql baseline (line 2735) creates it with `action TEXT NOT NULL`, and the redesign migration `655903cf2603` (line 2432) renames `user_id→actor_id`, `resource→resource_type`, drops `detail/ip_address/request_id`, and adds `before_state/after_state/metadata`. The final applied columns are `id, timestamp, actor_id, action, resource_type, resource_id, before_state, after_state, metadata`. **There is no `event_type` column on `audit_log`** (the only `event_type` in the chain is on the `notifications` table, added by `3f18545e3844` at line 2388). §12's "enum extension to `audit_log.event_type`" is doubly inaccurate: there is no enum and no `event_type` column.

The four event names (`sample_deletion_requested`, `sample_tombstoned`, `sample_vacuumed`, `outbreak_investigation_override`) are **application-level string constants** written into `audit_log.action` (the applied event-descriptor column) via `log_audit()`, added as `AuditActions` constants in `backend/audit.py` during P0c (`B-CARE-3f`). **P0b emits no DDL for this and touches no yaml.** Do not `CREATE TYPE`, `ALTER TYPE`, or `ADD COLUMN`. Listed here only so the item is closed explicitly rather than dropped.

Rollback: n/a (no schema object).

---

## 3. Ordered operation list (single migration off `85d92864ed38`)

Dependency-ordered: value-set constraints and FK-target tables precede the columns and constraints that depend on them.

1. **`byop_pipelines` table** (2.6) — create first; `pipeline_results.byop_pipeline_id` FK targets it. Its own FK targets (`labs`, `federated_instances`) are already applied, so no ordering constraint against them; `origin_instance_id` is `UUID` to match `federated_instances.id`.
2. **`samples` deletion columns** (2.1) — six `ADD COLUMN IF NOT EXISTS`, including `deletion_status TEXT NOT NULL DEFAULT 'ACTIVE'`.
3. **`samples` deletion constraints + index** (2.2) — value-set CHECK, ACTIVE/requested-at CHECK, then the composite index. After 2, because they reference the new columns.
4. **`samples` eukaryotic columns** (2.7 DDL) — five `ADD COLUMN IF NOT EXISTS`.
5. **`pipeline_results.tombstoned`** (2.3).
6. **`pipeline_results` BYOP columns** (2.4) — after step 1 (FK target exists).
7. **`wastewater_target_concentration` table** (2.9).
8. **No-op close-outs** — `audit_log` event constants (2.10) and `wastewater_upstream_of` (2.8 DDL side) require no DDL; do not emit statements for them.

**yaml + regen, done alongside the migration (not inside it):**

9. Edit `jackpot_schema.yaml`: add `DeletionStatusEnum`, the four BYOP enums, `ParasiteDevelopmentalStageEnum`, `SamplePreservationMethodEnum`; add the 38 net-new OrganismNameEnum values (exclude `Toxoplasma gondii`); add `wastewater_upstream_of` to `SampleAssociationTypeEnum`; add the deletion columns and the five eukaryotic columns to the base `Sample` class.
10. Run `scripts/regen_schema.py` (gen-pydantic → `models_generated.py`, Rule 20 boolean/newline patch, gen-json-schema). Commit `pyproject.toml` and `uv.lock` together if the run touches deps (it should not).

`byop_pipelines` (table), `pipeline_results.*` columns, and `wastewater_target_concentration` are DDL-only and produce no yaml/regen work.

---

## 4. Drift and gaps

**Assumption failures in the planning brief (verify against applied_ddl_chain.txt, then act on the corrected version):**

- **`audit_log.event_type` does not exist.** Applied `audit_log` uses `action TEXT` as its event descriptor (baseline line 2735, redesign `655903cf2603` line 2432). The four sovereignty event names are application constants in `action`, added in P0c `B-CARE-3f`. No DDL, no enum, no column. The brief and §12 both mis-describe this as an enum extension.
- **`pipeline_results.sample_id` has no FK.** It is `TEXT NOT NULL` (line 1965), value-matched to `samples.sample_id TEXT UNIQUE` (line 2824). The §12 "MUST NOT cascade-delete" requirement is vacuously satisfied; do not add an FK in P0b.
- **OrganismNameEnum count.** §12.1 header says ~25; the list contains 39; `Toxoplasma gondii` is already in the applied enum. Add **38** net-new values.

**yaml/DDL mismatches:**

- **`is_deleted` / `deleted_at` / `deleted_by_id` — dual deletion representation `[UNSOURCED]`.** These exist in the applied `samples` table (baseline) but not in the yaml `Sample` class, and the sovereignty design never mentions them. P0b adds the four-state `deletion_status` lifecycle on top without reconciling the legacy soft-delete. This is safe and additive for P0b (no existing column is modified; the new CHECK governs only `deletion_status` vs `deletion_requested_at`, not `is_deleted`). It is **not** safe to leave undefined past P0b. P0c (`B-P0C-DELETION-RECONCILE`, see §5) must define the mapping before either representation is written by new code:
  - Is `is_deleted = true` equivalent to `deletion_status != 'ACTIVE'`, or only to specific states (`TOMBSTONED`, `VACUUMED`)?
  - Does existing soft-delete state get backfilled into the new lifecycle, and to which state?
  - Is the old soft-delete path retired, or kept as a coarse boolean with the lifecycle as authoritative?

  Until P0c resolves this, application code **must not write both representations in the same path**, or they will silently disagree (one path checks `is_deleted`, another checks `deletion_status`, and they diverge). Recorded here so the ambiguity is tracked, not discovered in production.
- **No `pipeline_results` class in yaml.** The BYOP design writes `pipeline_results:` yaml blocks for `tombstoned`, `byop_pipeline_id`, `byop_pipeline_version`, but the applied yaml has no such class (result tables are DDL-only). Resolved DDL-only; no `pipeline_results` LinkML class created in P0b. Direction: DDL leads, yaml stays silent, matching every other result table.
- **Result-table sample linkage convention.** Design models result tables with `sample_id: range: samples` (integer FK); every applied result table uses `sample_id TEXT` with no FK plus `run_id`. `wastewater_target_concentration` (2.9) follows the applied pattern, not the LinkML convention. The deferred §12.3 tables must do the same when they land.
- **yaml `Sample` subclass hierarchy vs flat `samples` table.** yaml models `Sample` with subclasses (`HumanSample`, `WastewaterSample`, etc.); DDL is a single flat `samples` table. New columns go on the base `Sample` class in yaml and into the flat table in DDL. Pre-existing structural drift; P0b does not resolve it.

**`[THIN-SOURCE]` items:**

- **`B-CWB-SCHEMA-1` (`wastewater_target_concentration`)** — cryptWWDB gives no column list. The 2.9 columns are derived from the `wastewater_lineage_abundance` pattern and the framework's stated `(Q, C, unit, timestamp, LOD)` data. Confirm target/target_type semantics against the reference implementation before P0c wiring.
- **`B-CWB-SCHEMA-2` (`wastewater_upstream_of`)** — named only in Open Questions. Derived as a directional value on the existing free-TEXT `association_type`; yaml-only, no DDL.

**Resolved design gaps (were `[UNSOURCED]`, now decided):**

- **`byop_pipelines` tenancy — RESOLVED, columns added in P0b (§2.6).** §7 gave no tenancy scope. Decision: federation-global visibility with a lab-ownership pointer, using three columns added at table creation: `owner_lab_id` (ownership), `sharing_scope` private/lab/federation (visibility), `origin_instance_id` UUID (federation provenance). Federation sharing uses **copy-on-import**: an imported pipeline is an independent local row with `origin_instance_id` set to the source, not a live cross-instance reference, so it survives network-denied (Scenario R) operation. Closed in P0b rather than deferred to avoid a P0c retrofit migration. Source-to-copy sync policy on update is a P0c concern, not a schema concern.

**Deliberate `deletion_status` TEXT+CHECK divergence from §12:** §12 specs a native `deletion_status_enum`. P0b uses TEXT + CHECK because the lifecycle can gain states (`LEGAL_HOLD`) and Postgres cannot drop enum values, and because it matches the applied TEXT precedent (`audit_log.action`, v4.2 `quality_status`/`sector`, `data_source_lab` status). The LinkML `DeletionStatusEnum` is retained to drive Pydantic/JSON. Documented, not silent.

**§12.3 eight-table scope decision — DEFER all eight.** The eukaryotic result tables (`plasmodium_drug_resistance_results`, `leishmania_typing_results`, `trypanosoma_typing_results`, `schistosoma_typing_results`, `helminth_drug_resistance_results`, `filarial_typing_results`, `cryptogiardia_typing_results`, `toxo_entamoeba_typing_results`) and their result-only enums (`TcDTUEnum`, `WolbachiaStatusEnum`, `GiardiaAssemblageEnum`, `ToxoClonalLineageEnum`, `EhVsEdEnum`, `ResistanceCallEnum`) are **not** created in P0b. Rationale: §12.3 itself frames these as examples of a one-per-pipeline pattern, not a locked set; none of the eight pipelines exists yet (they are backlog group P); no P0b object references these tables or enums, so deferring costs nothing structurally. **Premature-table-creation risk:** each table's exact columns are a guess at the pipeline's real output and will churn as each pipeline lands, leaving empty tables and migration debt. Follow the applied precedent exactly: result tables were created when their pipelines existed (`pangolin_results`, `wastewater_lineage_abundance`). Create each eukaryotic result table (and its enums) in the migration that lands its pipeline, using the applied `run_id TEXT`/`sample_id TEXT`/no-FK pattern, not the LinkML `range: samples` FK convention. The shared `ResistanceCallEnum` is deferred with them; the first pipeline PR that needs it introduces it. Contrast: §12.1 OrganismNameEnum values and §12.2 `samples` columns **are** in P0b, because operators populate that metadata at ingest independent of whether any eukaryotic pipeline exists.

**`byop_pipelines` vs `project_pipelines` reconciliation — SUPERSEDE, coexist for now.** The applied `project_pipelines` (line 1785, migration `cea9c08543ee`) is the "BYOP skeleton (UNVERIFIED)": `id, project_id (FK CASCADE), pipeline_name, github_url, revision, parameter_schema JSONB, status DEFAULT 'UNVERIFIED', created_by_id, timestamps, UNIQUE(project_id, pipeline_name)`. It is project-scoped and carries no validation lifecycle. The §7 `byop_pipelines` is user-registered (no project scope), carries the full engine/source/manifest/validation/sandbox/license model, and a ten-state lifecycle the skeleton lacks. Decision: create `byop_pipelines` as the canonical registry; do **not** extend `project_pipelines` in place (that would force a `project_id` onto `byop_pipelines` the design deliberately omits). **Do not drop `project_pipelines`** — `lab_pipelines.source_project_pipeline_id` references it (line 1808); dropping it breaks that FK. Leave `project_pipelines` as a deprecated skeleton; retirement is scheduled as `B-P0C-DEPRECATE-PROJPIPE` (§5), which migrates any rows into `byop_pipelines`, repoints the `lab_pipelines.source_project_pipeline_id` FK, and drops the table once BYOP behavior ships. Note the skeleton's docstring "BYOP skeleton (UNVERIFIED)" in the new migration's docstring so the supersession is traceable. The coexistence is accepted migration debt, now tracked rather than silent.

**Deferred, not specced (noted per scope):** cryptWWDB `R-1..R-6` and `Rec-1..3` are P0c and immune-track behavior (`B-IMMUNE-MPC-1`, `B-CWB-QSV-1`, `B-CWB-PCERT-1`, `B-CWB-AUDIT-1`, `B-CWB-PLAN-1`, etc.), not P0b schema; `B-CWB-FED-1` is already applied in FED-D (`FederationRole.DATA_SOURCE_LAB`). `OBS-1` (dairy bulk milk), `OBS-2` (air filter), `OBS-3` (external_data_sources), `OBS-4` (ICTV taxonomy versioning) are out of P0b. `OBS-4` specifically needs reference-table design: JACKPOT has no organism-taxonomy table (`reportable_organisms` is a reportability lookup, organism identity is an unversioned enum), so versioning ICTV lineage requires a new reference table, not an enum edit.

---

## 5. P0c handoff backlog items

Generated by this spec; these are P0c work, not P0b migration content. Recorded here so they land in `todo.md` rather than living only in a spec.

- **`B-P0C-DEPRECATE-PROJPIPE`** (P0c) — Retire `project_pipelines` in favor of `byop_pipelines`. Backfill existing `project_pipelines` rows into `byop_pipelines` with `sharing_scope='lab'` and `owner_lab_id` derived from the project's lab, repoint the `lab_pipelines.source_project_pipeline_id` FK at `byop_pipelines`, then drop `project_pipelines`. Owner: Glen. Blocked by: P0b `byop_pipelines` landing. The FK repoint is the load-bearing step; the table drop is trivial once nothing references it.
- **`B-P0C-DELETION-RECONCILE`** (P0c) — Define and implement the `is_deleted` / `deleted_at` / `deleted_by_id` ↔ `deletion_status` mapping per the §4 dual-deletion drift note. Decide equivalence, backfill target state, and whether the legacy soft-delete path retires. Enforce that no code path writes both representations until the mapping is defined. Owner: Glen. Blocked by: P0b deletion-lifecycle columns landing. Related: sovereignty `B-CARE-3*` implementation.
