"""
JACKPOT pipeline results loader.

Reads the iridanext.output.json.gz manifest produced by nf-iridanext
and writes results back to the database when a pipeline run completes.

Triggered by: POST /api/v1/pipelines/events when event == 'workflow.complete'

Writes to:
  - pipeline_results  — immutable per-run snapshot (JSONB), append-only
  - pipeline_files    — output file registry (GCS URIs)
  - samples           — canonical fields updated to latest run values
  - audit_log         — one entry per sample updated

Never updates an existing pipeline_results row. Every run gets a new row.
"""

import gzip
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Schema column map ──────────────────────────────────────────────────────────
# Maps iridanext metadata keys → samples table columns.
# Only keys listed here are written to the samples table.
# Everything else is preserved in pipeline_results.results_json only.
#
# Format: "iridanext_key": ("column_name", type_coercion)
# type_coercion: str | float | int | list | bool | None (None = keep as-is)

SCHEMA_COLUMN_MAP: dict[str, tuple[str, Any]] = {
    # Lineage / clade
    "pango_lineage": ("pango_lineage", str),
    "pango_lineage_confidence": ("lineage_confidence", float),
    "nextclade_clade": ("nextclade_clade", str),
    "nextclade_qc_overall": ("nextclade_qc_status", str),
    # Assembly QC
    "coverage_depth": ("coverage_depth", float),
    "genome_completeness": ("genome_completeness", float),
    "consensus_n_count": ("consensus_n_count", int),
    "assembly_method": ("assembly_method", str),
    "assembly_length": ("assembly_length", int),
    # MLST / typing
    "mlst_st": ("mlst_st", str),
    "mlst_scheme": ("mlst_scheme", str),
    # AMR
    "amr_genes": ("amr_genes", list),
    # VADR
    "vadr_status": ("vadr_status", str),
    "vadr_alerts": ("vadr_alerts", list),
    # MAG-specific (metagenomics)
    "mag_completeness_pct": ("mag_completeness_pct", float),
    "mag_contamination_pct": ("mag_contamination_pct", float),
    "mag_strain_heterogeneity": ("mag_strain_heterogeneity", float),
    # TB-specific
    "tb_lineage": ("tb_lineage", str),
    "tb_lineage_confidence": ("tb_lineage_confidence", float),
}

# ── File type map ──────────────────────────────────────────────────────────────
# Maps glob-recognizable filename patterns → file_type labels stored in
# pipeline_files. Used for display and downstream tooling.
# Pattern matching is suffix-based (case-insensitive).

FILE_TYPE_PATTERNS: list[tuple[str, str]] = [
    (".consensus.fa.gz", "consensus_fasta"),
    (".consensus.fasta.gz", "consensus_fasta"),
    (".assembly.fa.gz", "assembly_fasta"),
    (".assembly.fasta.gz", "assembly_fasta"),
    (".vcf.gz", "variant_calls"),
    (".bam", "alignment"),
    (".bam.bai", "alignment_index"),
    ("multiqc_report.html", "multiqc_report"),
    ("multiqc_data.json", "multiqc_data"),
    (".kraken2.report.txt", "taxonomy_report"),
    (".bracken.txt", "abundance_report"),
    ("iridanext.output.json.gz", "pipeline_manifest"),
]


def _infer_file_type(path: str) -> str:
    """Infer file_type label from filename suffix."""
    lower = path.lower()
    for suffix, ftype in FILE_TYPE_PATTERNS:
        if lower.endswith(suffix):
            return ftype
    return "pipeline_output"


def _coerce_value(value: Any, coercion: Any) -> Any:
    """Apply type coercion to a metadata value. Returns None on failure."""
    if value is None or value == "":
        return None
    try:
        if coercion is list:
            if isinstance(value, list):
                return value
            # Semicolon or comma-separated string → list
            if isinstance(value, str):
                sep = ";" if ";" in value else ","
                return [v.strip() for v in value.split(sep) if v.strip()]
            return [value]
        if coercion is bool:
            if isinstance(value, bool):
                return value
            return str(value).lower() in ("true", "1", "yes", "pass")
        if coercion is not None:
            return coercion(value)
        return value
    except (ValueError, TypeError):
        return None


@dataclass
class LoaderResult:
    """Summary of what the loader wrote."""

    run_id: str
    samples_updated: list[str] = field(default_factory=list)
    files_registered: int = 0
    global_files_registered: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


def _read_manifest(result_uri: str) -> dict:
    """
    Download and parse iridanext.output.json.gz from GCS.

    result_uri is the run's --outdir GCS path, e.g.:
        gs://jackpot-results/run-abc-123/

    The manifest is always at:
        {result_uri}iridanext.output.json.gz
    """
    from backend.storage import _get_client

    # Normalise trailing slash
    base = result_uri.rstrip("/")
    manifest_uri = f"{base}/iridanext.output.json.gz"

    # Parse gs://bucket/key
    without_scheme = manifest_uri[len("gs://") :]
    bucket_name, _, key = without_scheme.partition("/")

    client = _get_client()
    response = client.get_object(Bucket=bucket_name, Key=key)
    compressed = response["Body"].read()
    raw = gzip.decompress(compressed)
    return json.loads(raw)


def _build_sample_updates(
    sample_metadata: dict[str, Any],
) -> dict[str, Any]:
    """
    Map iridanext metadata keys to samples table columns.
    Returns only the columns that have non-None values.
    """
    updates: dict[str, Any] = {}
    for meta_key, value in sample_metadata.items():
        if meta_key not in SCHEMA_COLUMN_MAP:
            continue
        col_name, coercion = SCHEMA_COLUMN_MAP[meta_key]
        coerced = _coerce_value(value, coercion)
        if coerced is not None:
            updates[col_name] = coerced
    return updates


def load_pipeline_results(
    run_id: str,
    result_uri: str,
    pipeline_name: str,
    pipeline_version: str | None,
    launched_by_id: int,
    conn: Any,
) -> LoaderResult:
    """
    Main entry point. Called by the weblog endpoint on workflow.complete.

    Args:
        run_id:           JACKPOT run UUID (pipeline_runs.run_id)
        result_uri:       GCS outdir, e.g. gs://jackpot-results/run-abc-123/
        pipeline_name:    e.g. "nf-core/viralrecon"
        pipeline_version: e.g. "2.6.0"
        launched_by_id:   user_id of whoever launched the run
        conn:             SQLAlchemy connection (shared transaction)
    """
    from backend.database import execute_write

    result = LoaderResult(run_id=run_id)

    # ── 1. Download and parse manifest ────────────────────────────────────────
    try:
        manifest = _read_manifest(result_uri)
    except Exception as e:
        msg = f"Failed to read manifest from {result_uri}: {e}"
        logger.error(msg)
        result.errors.append(msg)
        return result

    files_section = manifest.get("files", {})
    metadata_section = manifest.get("metadata", {})
    global_files = files_section.get("global", [])
    sample_files = files_section.get("samples", {})
    sample_metadata = metadata_section.get("samples", {})

    base_uri = result_uri.rstrip("/")

    # ── 2. Register global files ───────────────────────────────────────────────
    for file_entry in global_files:
        path = file_entry.get("path", "")
        if not path:
            continue
        full_uri = f"{base_uri}/{path}"
        file_type = _infer_file_type(path)
        try:
            execute_write(
                """
                INSERT INTO pipeline_files
                    (run_id, sample_id, file_uri, file_type, scope, created_at)
                VALUES
                    (:run_id, NULL, :uri, :file_type, 'global', NOW())
                ON CONFLICT (run_id, file_uri) DO NOTHING
                """,
                {
                    "run_id": run_id,
                    "uri": full_uri,
                    "file_type": file_type,
                },
                conn=conn,
            )
            result.global_files_registered += 1
        except Exception as e:
            result.errors.append(f"Global file {path}: {e}")

    # ── 3. Process each sample ─────────────────────────────────────────────────
    # Collect all sample IDs that appear in either files or metadata
    all_sample_ids = set(sample_files.keys()) | set(sample_metadata.keys())

    for sample_id in all_sample_ids:
        try:
            _process_sample(
                sample_id=sample_id,
                run_id=run_id,
                base_uri=base_uri,
                pipeline_name=pipeline_name,
                pipeline_version=pipeline_version,
                launched_by_id=launched_by_id,
                sample_file_list=sample_files.get(sample_id, []),
                raw_metadata=sample_metadata.get(sample_id, {}),
                full_manifest_metadata=sample_metadata,
                conn=conn,
                result=result,
            )
        except Exception as e:
            msg = f"Sample {sample_id}: {e}"
            logger.error(msg)
            result.errors.append(msg)

    logger.info(
        "Pipeline results loaded: run=%s samples=%d files=%d global=%d errors=%d",
        run_id,
        len(result.samples_updated),
        result.files_registered,
        result.global_files_registered,
        len(result.errors),
    )
    return result


def _process_sample(
    sample_id: str,
    run_id: str,
    base_uri: str,
    pipeline_name: str,
    pipeline_version: str | None,
    launched_by_id: int,
    sample_file_list: list[dict],
    raw_metadata: dict[str, Any],
    full_manifest_metadata: dict,
    conn: Any,
    result: LoaderResult,
) -> None:
    """Process one sample from the manifest — files, results row, sample update."""
    from backend.audit import AuditActions, log_audit
    from backend.database import execute_query, execute_write

    # Verify the sample exists in JACKPOT
    rows = execute_query(
        "SELECT id FROM samples WHERE sample_id = :sid",
        {"sid": sample_id},
        conn=conn,
    )
    if not rows:
        logger.warning("Sample %s not found in JACKPOT — skipping", sample_id)
        result.errors.append(f"Sample {sample_id} not found in database")
        return

    # ── 3a. Register per-sample output files ──────────────────────────────────
    for file_entry in sample_file_list:
        path = file_entry.get("path", "")
        if not path:
            continue
        full_uri = f"{base_uri}/{path}"
        file_type = _infer_file_type(path)
        execute_write(
            """
            INSERT INTO pipeline_files
                (run_id, sample_id, file_uri, file_type, scope, created_at)
            VALUES
                (:run_id, :sample_id, :uri, :file_type, 'sample', NOW())
            ON CONFLICT (run_id, file_uri) DO NOTHING
            """,
            {
                "run_id": run_id,
                "sample_id": sample_id,
                "uri": full_uri,
                "file_type": file_type,
            },
            conn=conn,
        )
        result.files_registered += 1

    # ── 3b. Insert immutable pipeline_results row ──────────────────────────────
    execute_write(
        """
        INSERT INTO pipeline_results
            (run_id, sample_id, pipeline_name, pipeline_version,
             results_json, created_at)
        VALUES
            (:run_id, :sample_id, :pipeline_name, :pipeline_version,
             :results_json, NOW())
        """,
        {
            "run_id": run_id,
            "sample_id": sample_id,
            "pipeline_name": pipeline_name,
            "pipeline_version": pipeline_version,
            "results_json": json.dumps(raw_metadata),
        },
        conn=conn,
    )

    # ── 3c. Update canonical sample fields ────────────────────────────────────
    updates = _build_sample_updates(raw_metadata)
    if updates:
        # Fetch before state for audit
        before_row = execute_query(
            f"SELECT {', '.join(updates.keys())} FROM samples WHERE sample_id = :sid",
            {"sid": sample_id},
            conn=conn,
        )
        before = dict(before_row[0]) if before_row else {}

        set_clause = ", ".join(f"{col} = :{col}" for col in updates)
        updates["sid"] = sample_id
        execute_write(
            f"UPDATE samples SET {set_clause} WHERE sample_id = :sid",
            updates,
            conn=conn,
        )

        log_audit(
            action=AuditActions.UPDATE_SAMPLE,
            actor_id=launched_by_id,
            resource_type="sample",
            resource_id=sample_id,
            before=before,
            after={k: v for k, v in updates.items() if k != "sid"},
            metadata={
                "source": "pipeline_results_loader",
                "run_id": run_id,
                "pipeline": pipeline_name,
                "version": pipeline_version,
            },
            db_conn=conn,
        )

    result.samples_updated.append(sample_id)
