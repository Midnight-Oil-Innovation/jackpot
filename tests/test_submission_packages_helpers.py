"""I-2 submission-package helper / edge-case tests.

Targets the shared helpers in :mod:`backend.submission_packages` that the
per-repo generator tests don't naturally exercise: cloud-bucket
``output_root`` rejection, ``sra://`` and broken/file-already-present
URIs in the linker, malformed JSON entries in the joined ``files``
column, and the empty-samples branch of the dispatcher.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend.config import get_settings
from backend.database import execute_query, execute_write, get_db
from backend.submission_packages import (
    _link_or_copy,
    _resolve_output_root,
    _sample_file_uris,
    generate_package,
)
from backend.submissions import create_submission

SEED_USER_ID = 1
SEED_LAB_ID = 1


def _cleanup_submissions(prefix: str = "I2-HLP-") -> None:
    rows = execute_query("SELECT id FROM submissions WHERE title LIKE :p", {"p": f"{prefix}%"})
    for r in rows:
        execute_write("DELETE FROM submission_samples WHERE submission_id = :id", {"id": r["id"]})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'submission' AND resource_id = :rid",
            {"rid": str(r["id"])},
        )
        execute_write("DELETE FROM submissions WHERE id = :id", {"id": r["id"]})


def _cleanup_samples(prefix: str = "I2-HLP-S-") -> None:
    rows = execute_query("SELECT id FROM samples WHERE sample_id LIKE :p", {"p": f"{prefix}%"})
    for r in rows:
        execute_write("DELETE FROM sample_files WHERE sample_id_fk = :id", {"id": r["id"]})
        execute_write("DELETE FROM submission_samples WHERE sample_id_fk = :id", {"id": r["id"]})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'sample' AND resource_id = :rid",
            {"rid": str(r["id"])},
        )
        execute_write("DELETE FROM samples WHERE id = :id", {"id": r["id"]})


def _insert_sample(sample_id: str, **overrides) -> int:
    payload = {
        "sample_id": sample_id,
        "lab_id": SEED_LAB_ID,
        "project_id": 1,
        "owner_id": SEED_USER_ID,
        "source_type": "Human",
        "organism_name": "Severe acute respiratory syndrome coronavirus 2",
        "type_of_experiment": "WGS",
        "library_preparation_method": "ARTIC",
        "sequencing_protocol": "https://www.protocols.io/view/artic-v4-1",
        "sequencing_platform": "Illumina",
        "sequencing_lab": "Example Sequencing Lab",
        "date_collected": "2026-01-15",
        "date_sequenced": "2026-01-17",
        "collection_facility": "Example Hospital",
        "collection_location_country": "United States",
        "collection_location_state": "California",
        "host_species": "Homo sapiens",
        "isolation_source": "nasopharyngeal swab",
        "sharing_level": "PRIVATE",
        "fastq_r1_uri": "gs://test/R1.fq.gz",
        "surveillance_relevant": False,
    }
    payload.update(overrides)
    cols = sorted(payload.keys())
    placeholders = [f":{c}" for c in cols]
    rows = execute_write(
        f"INSERT INTO samples ({', '.join(cols)}) VALUES ({', '.join(placeholders)}) RETURNING id",
        payload,
    )
    return rows[0]["id"]


def test_resolve_output_root_rejects_cloud_bucket(monkeypatch):
    """gs:// or s3:// for SUBMISSIONS_OUTPUT_ROOT is a known v1 limitation."""
    monkeypatch.setenv("SUBMISSIONS_OUTPUT_ROOT", "gs://example-bucket/subs")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        _resolve_output_root()
    assert exc.value.status_code == 501
    get_settings.cache_clear()


def test_link_or_copy_passes_through_sra_uri(tmp_path):
    """sra:// URIs reference accessions on NCBI and are kept verbatim."""
    dest = tmp_path / "files"
    out = _link_or_copy("sra://SRR123456", dest)
    assert out == "sra://SRR123456"
    # files/ is not created — nothing to link.
    assert not dest.exists()


def test_link_or_copy_returns_broken_marker_when_source_missing(tmp_path):
    """Broken file:// URI surfaces a `# BROKEN:` marker rather than crashing."""
    dest = tmp_path / "files"
    bogus = tmp_path / "does-not-exist.fastq"
    out = _link_or_copy(f"file://{bogus}", dest)
    assert out.startswith("# BROKEN:")
    assert str(bogus) in out


def test_link_or_copy_overwrites_existing_dest_symlink(tmp_path):
    """A pre-existing symlink at dest is unlinked before re-linking."""
    src = tmp_path / "src.fastq"
    src.write_bytes(b"@A\nN\n+\n!\n")
    dest_dir = tmp_path / "files"
    dest_dir.mkdir()
    pre_existing = dest_dir / "src.fastq"
    # Create a bogus pre-existing symlink that the linker must replace.
    pre_existing.symlink_to(tmp_path / "phantom-target")
    assert pre_existing.is_symlink()
    out = _link_or_copy(f"file://{src}", dest_dir)
    assert out == f"files/{src.name}"
    assert pre_existing.is_symlink()
    # New symlink resolves to the real source.
    assert pre_existing.resolve() == src.resolve()


def test_sample_file_uris_skips_invalid_json_entries():
    """Malformed JSON in the joined ``files`` array is skipped silently."""
    row = {
        "files": [
            "{not valid json",
            '{"uri": "gs://valid/path.fq"}',
            "{also broken",
        ]
    }
    assert _sample_file_uris(row) == ["gs://valid/path.fq"]


def test_sample_file_uris_handles_non_string_entries():
    """When the array carries dicts (not JSON-encoded strings), they are used directly."""
    row = {"files": [{"uri": "gs://direct/path.fq"}, {"no_uri_key": True}]}
    assert _sample_file_uris(row) == ["gs://direct/path.fq"]


def test_generate_package_rejects_submission_with_no_samples(tmp_path, monkeypatch):
    """Submissions with zero samples are rejected with a 422 before generation."""
    root = tmp_path / "submissions_root"
    root.mkdir()
    monkeypatch.setenv("SUBMISSIONS_OUTPUT_ROOT", str(root))
    get_settings.cache_clear()

    _cleanup_submissions()
    _cleanup_samples()
    sid = _insert_sample("I2-HLP-S-EMPTY")
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-HLP-EMPTY",
            sample_ids=[sid],
            conn=db,
        )
        # Patch the sample-fetch helper so the dispatcher sees zero rows.
        with (
            patch(
                "backend.submission_packages._fetch_samples_for_submission",
                return_value=[],
            ),
            pytest.raises(HTTPException) as exc,
        ):
            generate_package(submission_id=sub["id"], actor_id=SEED_USER_ID, conn=db)
    assert exc.value.status_code == 422
    assert "no samples" in str(exc.value.detail).lower()
    get_settings.cache_clear()
    _cleanup_submissions()
    _cleanup_samples()
