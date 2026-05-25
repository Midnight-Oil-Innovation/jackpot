# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Per-repository package generators for I-2.

Each function in this module turns a submission + its samples into a
Seqsender-compatible directory on disk. The directory layout is:

    <output_root>/<package_name>/
        biosample.tsv   (NCBI)
        sra.tsv         (NCBI)
        gisaid.tsv      (GISAID variants)
        webin.tsv       (ENA)
        ddbj.tsv        (DDBJ)
        files/          symlinks (or copies, --copy-files) for file:// URIs
        seqsender_config.yaml
        README.md       human-readable summary + run instructions

Per Critical Rule 57 the default is "link, don't copy" — the package
references files in their existing locations rather than duplicating
multi-gigabyte FASTQs. ``gs://`` and ``s3://`` URIs are referenced
directly in the TSVs and seqsender_config; Seqsender / cloud-aware
tools read them in place.

v1 ships a working NCBI generator. GISAID, ENA, and DDBJ generators
write minimal-but-valid scaffolds with the correct file layout and a
README pointing at follow-up work for full vendor-format coverage.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException

from backend.config import get_settings
from backend.database import execute_query

logger = logging.getLogger(__name__)


# ── package directory naming ──────────────────────────────────────


def _package_dirname(submission: dict) -> str:
    """Build a stable, human-readable package directory name."""
    when = submission.get("created_at") or datetime.now(UTC)
    ts = when.strftime("%Y-%m-%d") if hasattr(when, "strftime") else str(when)[:10]
    return f"sub_{ts}_{submission['target_repository']}_{submission['id']}"


def _resolve_output_root() -> Path:
    settings = get_settings()
    root = (settings.submissions_output_root or "").strip()
    if not root:
        raise HTTPException(
            status_code=500,
            detail=(
                "submissions_output_root is not configured. Set "
                "SUBMISSIONS_OUTPUT_ROOT in the deployment environment."
            ),
        )
    if root.startswith(("gs://", "s3://")):
        # v1 supports a local-filesystem path; cloud-bucket targets
        # land in a follow-up alongside the credential infrastructure.
        raise HTTPException(
            status_code=501,
            detail=(
                "Cloud-bucket submissions_output_root is planned; "
                "use a local filesystem path for v1."
            ),
        )
    p = Path(root)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── file linking ──────────────────────────────────────────────────


def _link_or_copy(uri: str, dest_dir: Path, *, copy: bool = False) -> str:
    """Place a file:// URI inside the package's files/ subdirectory.

    Returns the relative path string for embedding in the TSV. For
    ``gs://`` and ``s3://`` URIs the function returns the URI
    unchanged — Seqsender reads them directly.
    """
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    if scheme in ("gs", "s3", "http", "https"):
        return uri
    if scheme == "sra":
        # SRA URIs reference samples already on NCBI; surface a warning
        # and leave the URI in place.
        logger.warning("Skipping sra:// URI in package: %s", uri)
        return uri

    src_path = Path(parsed.path if scheme == "file" else uri)
    if not src_path.exists():
        # Surface the broken file in the package so the operator can
        # see it; don't crash the whole package generation.
        return f"# BROKEN: {uri}"

    dest_dir.mkdir(parents=True, exist_ok=True)
    src_resolved = src_path.resolve()
    dest = dest_dir / src_path.name
    # Two different source files can share a basename (e.g. R1.fastq.gz from
    # two samples). If the slot already holds a *different* file that still
    # exists, disambiguate with a short hash of the source path so the second
    # placement can't clobber the first (which would make that sample's TSV
    # row reference the wrong file's contents). Stale leftovers and
    # re-placements of the same source are simply overwritten.
    if dest.exists() or dest.is_symlink():
        existing = Path(os.readlink(dest)) if dest.is_symlink() else dest
        if existing.exists() and existing.resolve() != src_resolved:
            digest = hashlib.sha256(str(src_resolved).encode()).hexdigest()[:8]
            dest = dest_dir / f"{digest}_{src_path.name}"

    if dest.exists() or dest.is_symlink():
        dest.unlink()

    if copy:
        shutil.copy2(src_path, dest)
    else:
        os.symlink(src_resolved, dest)

    return str(dest.relative_to(dest_dir.parent))


# ── shared helpers ────────────────────────────────────────────────


def _fetch_samples_for_submission(submission_id: int, conn) -> list[dict]:
    """Pull the joined sample + sample_files data the generators need."""
    return execute_query(
        """
        SELECT s.*,
               ARRAY(
                   SELECT row_to_json(sf)::text
                     FROM sample_files sf
                    WHERE sf.sample_id_fk = s.id
                      AND sf.is_deleted = FALSE
                    ORDER BY sf.id ASC
               ) AS files
          FROM samples s
          JOIN submission_samples ss ON ss.sample_id_fk = s.id
         WHERE ss.submission_id = :id
           AND s.is_deleted = FALSE
         ORDER BY s.sample_id ASC
        """,
        {"id": submission_id},
        conn=conn,
    )


def _sample_file_uris(sample_row: dict) -> list[str]:
    """Extract the URI list for a sample from the joined ``files`` column."""
    import json  # noqa: PLC0415

    out: list[str] = []
    for entry in sample_row.get("files") or []:
        if isinstance(entry, str):
            try:
                f = json.loads(entry)
            except Exception:  # noqa: BLE001
                continue
        else:
            f = entry
        uri = f.get("uri") if isinstance(f, dict) else None
        if uri:
            out.append(uri)
    return out


def _write_readme(
    package_dir: Path,
    submission: dict,
    samples: list[dict],
    repo_specific_notes: str = "",
) -> None:
    repo = submission["target_repository"]
    body = f"""# {submission["title"]}

**Submission ID:** {submission["id"]}
**Target repository:** {repo}
**Created at:** {submission["created_at"]}
**Sample count:** {len(samples)}

## How to run

1. Configure your repository credentials. JACKPOT does not store or
   transmit them.
   - **NCBI:** see https://submit.ncbi.nlm.nih.gov/biosample/template/
   - **GISAID:** `seqsender configure-gisaid`
   - **ENA:** `~/.webin.txt`

2. From this directory, run:

       seqsender submit --config seqsender_config.yaml

3. Once Seqsender returns accessions (typically 24–72 hours for NCBI),
   register them with JACKPOT:

       jackpot submissions register --pkg-id {submission["id"]} --accessions accessions.tsv

   or use the web UI on the submission's detail page.

{repo_specific_notes}
"""
    (package_dir / "README.md").write_text(body)


def _write_seqsender_config(
    package_dir: Path,
    submission: dict,
) -> None:
    """Stub seqsender_config.yaml. Operators will tune per their setup."""
    body = f"""# Generated by JACKPOT (I-2). Edit before running Seqsender.
submission_id: {submission["id"]}
target_repository: {submission["target_repository"]}
title: {submission["title"]!r}
bioproject_accession: {submission.get("bioproject_accession") or ""!r}
release_date: {submission.get("release_date") or ""!r}
"""
    (package_dir / "seqsender_config.yaml").write_text(body)


# ── repository generators ─────────────────────────────────────────


def generate_ncbi_package(
    submission: dict,
    samples: list[dict],
    package_dir: Path,
    *,
    copy_files: bool = False,
) -> None:
    """Write biosample.tsv + sra.tsv + files/ + seqsender_config + README."""
    files_dir = package_dir / "files"

    biosample_cols = [
        "sample_name",
        "organism",
        "collection_date",
        "geo_loc_name",
        "host",
        "isolation_source",
        "collected_by",
        "isolate",
        "lat_lon",
    ]
    sra_cols = [
        "sample_name",
        "library_id",
        "title",
        "library_strategy",
        "library_source",
        "library_selection",
        "library_layout",
        "platform",
        "instrument_model",
        "filename",
        "filename2",
    ]

    with open(package_dir / "biosample.tsv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=biosample_cols, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for s in samples:
            country = s.get("collection_location_country") or ""
            state = s.get("collection_location_state") or ""
            geo = country + (f": {state}" if state else "")
            writer.writerow(
                {
                    "sample_name": s.get("sample_id", ""),
                    "organism": s.get("organism_name", ""),
                    "collection_date": str(s.get("date_collected") or ""),
                    "geo_loc_name": geo,
                    "host": s.get("host_species") or s.get("source_type") or "",
                    "isolation_source": s.get("isolation_source") or "",
                    "collected_by": s.get("collection_facility") or "",
                    "isolate": s.get("isolate") or s.get("strain") or "",
                    "lat_lon": (
                        f"{s['geo_lat']} {s['geo_lon']}"
                        if s.get("geo_lat") and s.get("geo_lon")
                        else ""
                    ),
                }
            )

    with open(package_dir / "sra.tsv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=sra_cols, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for s in samples:
            uris = _sample_file_uris(s)
            placed = [_link_or_copy(u, files_dir, copy=copy_files) for u in uris]
            writer.writerow(
                {
                    "sample_name": s.get("sample_id", ""),
                    "library_id": s.get("sample_id", ""),
                    "title": s.get("organism_name", ""),
                    "library_strategy": s.get("type_of_experiment") or "WGS",
                    "library_source": "GENOMIC",
                    "library_selection": "RANDOM",
                    "library_layout": "PAIRED" if len(uris) >= 2 else "SINGLE",
                    "platform": (s.get("sequencing_platform") or "").upper(),
                    "instrument_model": s.get("sequencing_instrument") or "",
                    "filename": placed[0] if placed else "",
                    "filename2": placed[1] if len(placed) >= 2 else "",
                }
            )

    _write_seqsender_config(package_dir, submission)
    _write_readme(
        package_dir,
        submission,
        samples,
        repo_specific_notes=(
            "## NCBI-specific notes\n\n"
            "- biosample.tsv targets the standard PHA4GE BioSample format.\n"
            "- sra.tsv targets the SRA submission format.\n"
            "- File references in `files/` are symlinks unless `--copy-files` was used."
        ),
    )


def _write_minimal_tsv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict],
) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _gisaid_rows(samples: list[dict], variant: str) -> list[dict]:
    rows: list[dict] = []
    for s in samples:
        rows.append(
            {
                "Virus name": (
                    f"{variant}/{(s.get('collection_location_country') or '').replace(' ', '_')}/"
                    f"{s.get('sample_id', '')}/{str(s.get('date_collected') or '')[:4]}"
                ),
                "Type": variant,
                "Collection date": str(s.get("date_collected") or ""),
                "Location": (
                    f"{s.get('collection_location_country') or ''} / "
                    f"{s.get('collection_location_state') or ''}"
                ),
                "Host": s.get("host_species") or s.get("source_type") or "",
                "Sequencing technology": s.get("sequencing_platform") or "",
                "Originating lab": s.get("collection_facility") or "",
                "Submitting lab": s.get("collection_facility") or "",
                "Sample ID given by the originating laboratory": s.get("sample_id", ""),
                "Sample ID given by the submitting laboratory": s.get("sample_id", ""),
            }
        )
    return rows


_GISAID_BASE_COLS = [
    "Virus name",
    "Type",
    "Collection date",
    "Location",
    "Host",
    "Sequencing technology",
    "Originating lab",
    "Submitting lab",
    "Sample ID given by the originating laboratory",
    "Sample ID given by the submitting laboratory",
]


def _generate_gisaid_package(
    submission: dict,
    samples: list[dict],
    package_dir: Path,
    *,
    variant: str,
    tsv_filename: str,
    repo_specific_notes: str,
    copy_files: bool = False,
) -> None:
    files_dir = package_dir / "files"
    _write_minimal_tsv(
        package_dir / tsv_filename,
        _GISAID_BASE_COLS,
        _gisaid_rows(samples, variant=variant),
    )
    for s in samples:
        for u in _sample_file_uris(s):
            _link_or_copy(u, files_dir, copy=copy_files)
    _write_seqsender_config(package_dir, submission)
    _write_readme(
        package_dir,
        submission,
        samples,
        repo_specific_notes=repo_specific_notes,
    )


def generate_gisaid_epicov_package(
    submission: dict,
    samples: list[dict],
    package_dir: Path,
    *,
    copy_files: bool = False,
) -> None:
    _generate_gisaid_package(
        submission,
        samples,
        package_dir,
        variant="hCoV-19",
        tsv_filename="gisaid_epicov.tsv",
        repo_specific_notes=(
            "## GISAID EpiCoV notes\n\n"
            "v1 emits a minimal TSV scaffold with the standard EpiCoV "
            "header. Full PHA4GE-compatible field coverage is tracked as "
            "I-2-followup-A."
        ),
        copy_files=copy_files,
    )


def generate_gisaid_epiflu_package(
    submission: dict,
    samples: list[dict],
    package_dir: Path,
    *,
    copy_files: bool = False,
) -> None:
    _generate_gisaid_package(
        submission,
        samples,
        package_dir,
        variant="A",
        tsv_filename="gisaid_epiflu.tsv",
        repo_specific_notes=(
            "## GISAID EpiFlu notes\n\nMinimal scaffold; full coverage in I-2-followup-A."
        ),
        copy_files=copy_files,
    )


def generate_gisaid_epipox_package(
    submission: dict,
    samples: list[dict],
    package_dir: Path,
    *,
    copy_files: bool = False,
) -> None:
    _generate_gisaid_package(
        submission,
        samples,
        package_dir,
        variant="MPXV",
        tsv_filename="gisaid_epipox.tsv",
        repo_specific_notes=(
            "## GISAID EpiPox notes\n\nMinimal scaffold; full coverage in I-2-followup-A."
        ),
        copy_files=copy_files,
    )


def generate_ena_package(
    submission: dict,
    samples: list[dict],
    package_dir: Path,
    *,
    copy_files: bool = False,
) -> None:
    files_dir = package_dir / "files"
    cols = [
        "sample_alias",
        "tax_id",
        "scientific_name",
        "common_name",
        "collection_date",
        "geographic_location_country",
        "host",
        "isolation_source",
    ]
    rows = [
        {
            "sample_alias": s.get("sample_id", ""),
            "tax_id": "",
            "scientific_name": s.get("organism_name", ""),
            "common_name": "",
            "collection_date": str(s.get("date_collected") or ""),
            "geographic_location_country": s.get("collection_location_country") or "",
            "host": s.get("host_species") or s.get("source_type") or "",
            "isolation_source": s.get("isolation_source") or "",
        }
        for s in samples
    ]
    _write_minimal_tsv(package_dir / "webin.tsv", cols, rows)
    for s in samples:
        for u in _sample_file_uris(s):
            _link_or_copy(u, files_dir, copy=copy_files)
    _write_seqsender_config(package_dir, submission)
    _write_readme(
        package_dir,
        submission,
        samples,
        repo_specific_notes=(
            "## ENA Webin notes\n\nMinimal scaffold; full coverage in I-2-followup-B."
        ),
    )


def generate_ddbj_package(
    submission: dict,
    samples: list[dict],
    package_dir: Path,
    *,
    copy_files: bool = False,
) -> None:
    files_dir = package_dir / "files"
    cols = ["sample_id", "organism", "collection_date", "country", "host"]
    rows = [
        {
            "sample_id": s.get("sample_id", ""),
            "organism": s.get("organism_name", ""),
            "collection_date": str(s.get("date_collected") or ""),
            "country": s.get("collection_location_country") or "",
            "host": s.get("host_species") or s.get("source_type") or "",
        }
        for s in samples
    ]
    _write_minimal_tsv(package_dir / "ddbj.tsv", cols, rows)
    for s in samples:
        for u in _sample_file_uris(s):
            _link_or_copy(u, files_dir, copy=copy_files)
    _write_seqsender_config(package_dir, submission)
    _write_readme(
        package_dir,
        submission,
        samples,
        repo_specific_notes="## DDBJ notes\n\nMinimal scaffold; full coverage in I-2-followup-C.",
    )


_GENERATORS = {
    "NCBI": generate_ncbi_package,
    "GISAID_EPICOV": generate_gisaid_epicov_package,
    "GISAID_EPIFLU": generate_gisaid_epiflu_package,
    "GISAID_EPIPOX": generate_gisaid_epipox_package,
    "ENA": generate_ena_package,
    "DDBJ": generate_ddbj_package,
}


# ── public entrypoint ─────────────────────────────────────────────


def generate_package(
    *,
    submission_id: int,
    actor_id: int | None,
    conn,
    copy_files: bool = False,
) -> str:
    """Generate the on-disk submission package and transition the row.

    Returns the absolute path of the package directory. Calls the
    state-machine helper :func:`backend.submissions.mark_package_generated`
    on success, which transitions DRAFT/READY_TO_SUBMIT → READY_TO_SUBMIT,
    writes the audit log entry, and notifies the creator.
    """
    from backend.submissions import (  # noqa: PLC0415
        _require_submission,
        mark_package_generated,
        validate_submission_readiness,
    )

    submission = _require_submission(submission_id, conn)
    repo = submission["target_repository"]
    if repo not in _GENERATORS:
        raise HTTPException(status_code=422, detail=f"Unsupported target_repository {repo!r}.")

    settings = get_settings()
    samples = _fetch_samples_for_submission(submission_id, conn)
    if not samples:
        raise HTTPException(
            status_code=422, detail="Submission has no samples — add samples first."
        )

    cap = settings.submission_max_samples_per_package or 1000
    if len(samples) > cap:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Submission has {len(samples)} samples; the per-package "
                f"limit is {cap}. Split into multiple submissions or raise "
                "submission_max_samples_per_package."
            ),
        )

    # Pre-flight validation. Re-uses the readiness check that the
    # standalone /validate endpoint exposes; the user has already had
    # an opportunity to fix or exclude failing samples in the wizard.
    validation = validate_submission_readiness(submission_id, conn)
    if not validation.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VALIDATION_FAILED",
                "message": (
                    "Submission failed readiness validation. Fix or exclude "
                    "the listed samples before generating a package."
                ),
                "per_sample": [
                    {"sample_id": v.sample_id, "issues": v.issues} for v in validation.per_sample
                ],
            },
        )

    output_root = _resolve_output_root()
    package_dir = output_root / _package_dirname(submission)
    package_dir.mkdir(parents=True, exist_ok=True)

    generator = _GENERATORS[repo]
    generator(submission, samples, package_dir, copy_files=copy_files)

    mark_package_generated(
        submission_id=submission_id,
        package_path=str(package_dir),
        actor_id=actor_id,
        conn=conn,
    )
    return str(package_dir)


__all__ = [
    "generate_ddbj_package",
    "generate_ena_package",
    "generate_gisaid_epicov_package",
    "generate_gisaid_epiflu_package",
    "generate_gisaid_epipox_package",
    "generate_ncbi_package",
    "generate_package",
]
