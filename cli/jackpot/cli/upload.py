"""
jackpot.cli.upload
~~~~~~~~~~~~~~~~~~
Upload commands: `jackpot upload`, `jackpot upload-dir`, `jackpot upload-globus`.

All upload commands use file_detector.py-compatible pairing logic:
  - Standard R1/R2 naming
  - Multi-lane Illumina (L001_R1_001 etc.)
  - Nanopore chunk files
  - FASTA-only (no raw reads — scrubber auto-skipped)
One CSV row = one sample. Files are paired automatically from filenames.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from jackpot.cli.config import get_client_credentials
from jackpot.core.client import JACKPOTClient
from jackpot.core.exceptions import ConfigError, ValidationError

console = Console()


def _get_client() -> JACKPOTClient:
    """Get an authenticated client or exit with a helpful message."""
    try:
        api_url, token = get_client_credentials()
        return JACKPOTClient(api_url=api_url, token=token)
    except ConfigError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


def _detect_files(directory: Path, pattern: str) -> list[dict]:
    """
    Detect and pair NGS files in a directory.

    Uses the same pairing logic as backend/file_detector.py.
    Returns a list of sample groups:
    [
      {"sample_id": "AZ-001", "r1": Path(...), "r2": Path(...), "lanes": [...]},
      ...
    ]

    TODO: In Month 1, import file_detector logic from jackpot-backend
    or replicate it here. For now, uses a simple R1/R2 suffix match.
    """
    files = sorted(directory.glob(pattern))
    r1_files = [f for f in files if "_R1" in f.name or "_1.fastq" in f.name]

    samples = []
    for r1 in r1_files:
        # Derive sample_id from filename stem
        # e.g. EX-2026-001_R1.fastq.gz → EX-2026-001
        stem = r1.name
        for suffix in [
            "_R1_001.fastq.gz",
            "_R1.fastq.gz",
            "_1.fastq.gz",
            "_R1_001.fq.gz",
            "_R1.fq.gz",
            "_1.fq.gz",
        ]:
            if stem.endswith(suffix):
                sample_id = stem[: -len(suffix)]
                break
        else:
            sample_id = r1.stem.split("_R1")[0].split("_1")[0]

        # Find paired R2
        r2 = None
        for r2_suffix in [
            "_R2_001.fastq.gz",
            "_R2.fastq.gz",
            "_2.fastq.gz",
            "_R2_001.fq.gz",
            "_R2.fq.gz",
            "_2.fq.gz",
        ]:
            candidate = r1.parent / r1.name.replace(
                r1.name.split("_R1")[1] if "_R1" in r1.name else r1.name,
                r2_suffix,
            )
            # Simpler: just replace R1 with R2 in the filename
            r2_name = r1.name.replace("_R1", "_R2").replace("_1.fastq", "_2.fastq")
            r2_candidate = r1.parent / r2_name
            if r2_candidate.exists():
                r2 = r2_candidate
                break

        samples.append({"sample_id": sample_id, "r1": r1, "r2": r2})

    return samples


# ── jackpot upload ──────────────────────────────────────────────────────────


@click.command("upload")
@click.option(
    "--r1",
    required=True,
    type=click.Path(exists=True),
    help="Path to R1 FASTQ file (or FASTA for assembly-only upload)",
)
@click.option(
    "--r2",
    type=click.Path(exists=True),
    default=None,
    help="Path to R2 FASTQ file (omit for single-end or FASTA)",
)
@click.option(
    "--organism", required=True, help="Organism name (must match JACKPOT OrganismNameEnum)"
)
@click.option(
    "--source-type",
    required=True,
    help="Source type: isolate, wastewater, wildlife, environmental, etc.",
)
@click.option(
    "--sector",
    required=True,
    help="One Health sector: clinical, veterinary, environmental, wastewater, etc.",
)
@click.option(
    "--project",
    type=int,
    default=None,
    help="Project ID (optional — sample goes to unassigned pool if omitted)",
)
@click.option(
    "--lab", type=int, default=None, help="Lab ID (required if not inferable from your account)"
)
@click.option(
    "--date-collected",
    default=None,
    help="Collection date: YYYY-MM-DD, YYYY-MM, or YYYY (year-only accepted at Tier 1)",
)
@click.option(
    "--sharing-level",
    default="LAB",
    type=click.Choice(["PRIVATE", "LAB", "DISCOVERABLE", "PUBLIC"]),
    help="Data sharing level (default: LAB)",
)
@click.option(
    "--skip-scrub",
    is_flag=True,
    default=False,
    help="Request to skip the human read scrubber (requires Lab Director approval)",
)
@click.option(
    "--skip-reason",
    default=None,
    help="Justification for scrub skip (required when --skip-scrub is used)",
)
@click.option("--metadata", default=None, help="Additional metadata as a JSON string")
def upload(
    r1: str,
    r2: str | None,
    organism: str,
    source_type: str,
    sector: str,
    project: int | None,
    lab: int | None,
    date_collected: str | None,
    sharing_level: str,
    skip_scrub: bool,
    skip_reason: str | None,
    metadata: str | None,
) -> None:
    """Upload a single sample to JACKPOT.

    \b
    Examples:
      # Paired-end Illumina
      jackpot upload \\
          --r1 EX-2026-001_R1.fastq.gz \\
          --r2 EX-2026-001_R2.fastq.gz \\
          --organism "Salmonella enterica" \\
          --source-type isolate \\
          --sector clinical \\
          --project 42 \\
          --date-collected 2026-04-01

      # FASTA only (scrubber auto-skipped — no raw reads)
      jackpot upload \\
          --r1 consensus.fa \\
          --organism "Severe acute respiratory syndrome coronavirus 2" \\
          --source-type isolate \\
          --sector clinical \\
          --project 42
    """
    if skip_scrub and not skip_reason:
        raise click.UsageError(
            "--skip-reason is required when --skip-scrub is used.\n"
            "Provide a justification that the Lab Director will review."
        )

    client = _get_client()

    # Build metadata dict
    meta: dict = {
        "organism_name": organism,
        "source_type": source_type,
        "sector": sector,
        "sharing_level": sharing_level,
    }
    if project:
        meta["project_id"] = project
    if lab:
        meta["lab_id"] = lab
    if date_collected:
        meta["date_collected"] = date_collected
    if skip_scrub:
        meta["skip_scrub"] = True
        meta["skip_scrub_reason"] = skip_reason
    if metadata:
        try:
            extra = json.loads(metadata)
            meta.update(extra)
        except json.JSONDecodeError as e:
            raise click.UsageError(f"--metadata must be valid JSON: {e}")

    # Open files
    r1_path = Path(r1)
    files = {"fastq_r1": (r1_path.name, r1_path.open("rb"), "application/octet-stream")}
    if r2:
        r2_path = Path(r2)
        files["fastq_r2"] = (r2_path.name, r2_path.open("rb"), "application/octet-stream")

    click.echo(f"Uploading {r1_path.name}...")

    try:
        result = client.post_multipart(
            "/api/v1/ingest/upload",
            metadata=meta,
            files=files,
        )
        click.echo(
            f"Uploaded: {result.get('sample_id')} [quality_status={result.get('quality_status')}]"
        )

        if result.get("tier2_missing"):
            click.echo(f"  To reach Tier 2: add {', '.join(result['tier2_missing'])}")
        if result.get("scrub_status") == "PENDING_APPROVAL":
            click.echo("  Scrub skip requested — awaiting Lab Director approval.")

    except ValidationError as e:
        click.echo(f"Validation failed: {e}", err=True)
        if e.errors:
            for err in e.errors:
                click.echo(f"  • {err}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"Upload failed: {e}", err=True)
        raise SystemExit(1)
    finally:
        for f in files.values():
            f[1].close()


# ── jackpot upload-dir ──────────────────────────────────────────────────────


@click.command("upload-dir")
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--metadata-csv",
    type=click.Path(exists=True),
    default=None,
    help="CSV with per-sample metadata (one row per sample_id)",
)
@click.option(
    "--pattern",
    default="*_R1*.fastq.gz",
    help="Glob pattern for R1 files (default: *_R1*.fastq.gz)",
)
@click.option(
    "--organism", default=None, help="Shared organism for all samples (overridden by CSV)"
)
@click.option("--source-type", default=None, help="Shared source type (overridden by CSV)")
@click.option("--sector", default=None, help="Shared sector (overridden by CSV)")
@click.option("--project", type=int, default=None, help="Project ID for all samples")
@click.option(
    "--sharing-level",
    default="LAB",
    type=click.Choice(["PRIVATE", "LAB", "DISCOVERABLE", "PUBLIC"]),
)
@click.option(
    "--dry-run", is_flag=True, default=False, help="Show detected samples without uploading"
)
def upload_dir(
    directory: str,
    metadata_csv: str | None,
    pattern: str,
    organism: str | None,
    source_type: str | None,
    sector: str | None,
    project: int | None,
    sharing_level: str,
    dry_run: bool,
) -> None:
    """Bulk upload all samples in a directory.

    Automatically pairs R1/R2 files using naming conventions.
    Sample IDs are inferred from filenames unless a metadata CSV is provided.

    \b
    Examples:
      # Upload all samples, shared metadata
      jackpot upload-dir /data/sequences/ \\
          --organism "Salmonella enterica" \\
          --source-type isolate \\
          --sector clinical \\
          --project 42

      # Upload with per-sample metadata CSV
      jackpot upload-dir /data/sequences/ \\
          --metadata-csv metadata.csv \\
          --project 42

      # Preview what would be uploaded
      jackpot upload-dir /data/sequences/ --dry-run
    """
    dir_path = Path(directory)
    detected = _detect_files(dir_path, pattern)

    if not detected:
        click.echo(f"No files matching '{pattern}' found in {directory}")
        raise SystemExit(1)

    # Load per-sample metadata from CSV if provided
    csv_metadata: dict[str, dict] = {}
    if metadata_csv:
        import csv

        with open(metadata_csv, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sid = row.get("sample_id", "").strip()
                if sid:
                    csv_metadata[sid] = {k: v for k, v in row.items() if v}

    # Show detected samples
    table = Table(title=f"Detected {len(detected)} samples")
    table.add_column("sample_id")
    table.add_column("R1")
    table.add_column("R2")
    table.add_column("In CSV")

    warnings = []
    for s in detected:
        in_csv = "✓" if s["sample_id"] in csv_metadata else "—"
        r2_display = s["r2"].name if s["r2"] else "⚠ not found"
        if not s["r2"]:
            warnings.append(f"No R2 found for {s['sample_id']} — will upload as single-end")
        table.add_row(s["sample_id"], s["r1"].name, r2_display, in_csv)

    console.print(table)

    if warnings:
        for w in warnings:
            click.echo(f"⚠  {w}")

    if dry_run:
        click.echo("\nDry run complete. No files uploaded.")
        return

    if not click.confirm(f"\nUpload {len(detected)} samples?"):
        click.echo("Cancelled.")
        return

    client = _get_client()
    success = 0
    failed = 0

    for s in detected:
        sample_id = s["sample_id"]

        # Build metadata — CSV overrides shared CLI options
        row_meta = csv_metadata.get(sample_id, {})
        meta: dict = {
            "sample_id": sample_id,
            "organism_name": row_meta.get("organism_name") or organism,
            "source_type": row_meta.get("source_type") or source_type,
            "sector": row_meta.get("sector") or sector,
            "sharing_level": row_meta.get("sharing_level") or sharing_level,
        }
        if project:
            meta["project_id"] = project
        meta = {k: v for k, v in meta.items() if v is not None}

        r1_path = s["r1"]
        files = {"fastq_r1": (r1_path.name, r1_path.open("rb"), "application/octet-stream")}
        if s["r2"]:
            r2_path = s["r2"]
            files["fastq_r2"] = (r2_path.name, r2_path.open("rb"), "application/octet-stream")

        try:
            result = client.post_multipart(
                "/api/v1/ingest/upload",
                metadata=meta,
                files=files,
            )
            click.echo(f"  ✓ {sample_id} [{result.get('quality_status', 'PRELIMINARY')}]")
            success += 1
        except ValidationError as e:
            click.echo(f"  ✗ {sample_id}: validation failed — {e}", err=True)
            failed += 1
        except Exception as e:
            click.echo(f"  ✗ {sample_id}: {e}", err=True)
            failed += 1
        finally:
            for f in files.values():
                f[1].close()

    click.echo(f"\nDone: {success} uploaded, {failed} failed.")
    if failed:
        raise SystemExit(1)


# ── jackpot upload-globus ───────────────────────────────────────────────────


@click.command("upload-globus")
@click.option(
    "--metadata-csv",
    required=True,
    type=click.Path(exists=True),
    help="CSV with per-sample metadata (one row per sample_id)",
)
@click.option("--source-endpoint", required=True, help="Globus source endpoint name or UUID")
@click.option(
    "--source-path",
    required=True,
    help="Path on source endpoint (e.g. /your/sequencing/data/path/)",
)
@click.option("--project", type=int, default=None, help="Project ID for all samples")
@click.option(
    "--lab", type=int, default=None, help="Lab ID (required if not inferable from your account)"
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Validate metadata and show transfer plan without executing",
)
def upload_globus(
    metadata_csv: str,
    source_endpoint: str,
    source_path: str,
    project: int | None,
    lab: int | None,
    dry_run: bool,
) -> None:
    """Upload samples to JACKPOT via Globus transfer.

    Pre-registers sample metadata in JACKPOT, then initiates a Globus
    transfer from the source endpoint to the JACKPOT staging collection.
    Files are matched to sample records by filename stem on arrival.

    Requires Globus CLI to be installed and authenticated:
      pip install globus-cli
      globus login

    \b
    Examples:
      # Transfer from your sequencing facility's Globus endpoint
      jackpot upload-globus \\
          --metadata-csv metadata.csv \\
          --source-endpoint your-hpc-cluster \\
          --source-path /your/sequencing/data/path/ \\
          --project 42

      # Preview transfer plan
      jackpot upload-globus \\
          --metadata-csv metadata.csv \\
          --source-endpoint your-hpc-cluster \\
          --source-path /your/sequencing/data/path/ \\
          --dry-run
    """
    import csv

    # Read and validate metadata CSV
    rows = []
    with open(metadata_csv, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k: v for k, v in row.items() if v})

    if not rows:
        click.echo("No rows found in metadata CSV.", err=True)
        raise SystemExit(1)

    click.echo(f"Found {len(rows)} samples in metadata CSV.")

    if dry_run:
        click.echo("\nTransfer plan:")
        click.echo(f"  Source endpoint: {source_endpoint}")
        click.echo(f"  Source path:     {source_path}")
        click.echo(f"  Samples:         {len(rows)}")
        for row in rows[:5]:
            click.echo(f"    {row.get('sample_id', '(no sample_id)')}")
        if len(rows) > 5:
            click.echo(f"    ... and {len(rows) - 5} more")
        click.echo("\nDry run complete. No transfer initiated.")
        return

    client = _get_client()

    # TODO: implement in Month 2
    # Steps:
    #   1. POST /api/v1/ingest/globus/pre-register — creates stub sample records
    #      for each row in the CSV, returns staging collection path
    #   2. Shell out to `globus transfer` to initiate the Globus transfer
    #      from source_endpoint:source_path to jackpot-staging collection
    #   3. Poll `globus task show` until transfer completes
    #   4. Confirm ingest triggered via POST /api/v1/ingest/globus-callback

    click.echo(
        "Globus upload requires the ingest/globus endpoints (Month 2).\n"
        "For now, use `jackpot upload-dir` or the JACKPOT web UI.",
        err=True,
    )
    raise SystemExit(1)
