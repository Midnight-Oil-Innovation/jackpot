"""I-2 NCBI package-generator tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.config import get_settings
from backend.database import execute_query, execute_write, get_db
from backend.submission_packages import generate_package
from backend.submissions import create_submission

SEED_USER_ID = 1
SEED_LAB_ID = 1


def _cleanup_submissions(prefix: str = "I2-NCBI-") -> None:
    rows = execute_query("SELECT id FROM submissions WHERE title LIKE :p", {"p": f"{prefix}%"})
    for r in rows:
        execute_write("DELETE FROM submission_samples WHERE submission_id = :id", {"id": r["id"]})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'submission' AND resource_id = :rid",
            {"rid": str(r["id"])},
        )
        execute_write("DELETE FROM submissions WHERE id = :id", {"id": r["id"]})


def _cleanup_samples(prefix: str = "I2-NCBI-S-") -> None:
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


def _attach_local_files(sample_id_fk: int, dir_: Path) -> tuple[Path, Path]:
    r1 = dir_ / "r1.fastq"
    r2 = dir_ / "r2.fastq"
    r1.write_bytes(b"@A\nN\n+\n!\n")
    r2.write_bytes(b"@B\nN\n+\n!\n")
    for path, role in ((r1, "R1"), (r2, "R2")):
        execute_write(
            """
            INSERT INTO sample_files (
                sample_id_fk, uri, filename, file_size_bytes,
                file_type, library_layout, read_direction,
                storage_state, scrub_status, ingest_method
            ) VALUES (
                :sid, :uri, :fn, :sz,
                'FASTQ', 'PAIRED', :rd,
                CAST('EXTERNAL' AS file_storage_state), 'PENDING', 'register'
            )
            """,
            {
                "sid": sample_id_fk,
                "uri": f"file://{path}",
                "fn": path.name,
                "sz": path.stat().st_size,
                "rd": role,
            },
        )
    return r1, r2


@pytest.fixture
def output_root(tmp_path, monkeypatch):
    root = tmp_path / "submissions_root"
    root.mkdir()
    monkeypatch.setenv("SUBMISSIONS_OUTPUT_ROOT", str(root))
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


def test_generate_ncbi_package_writes_expected_files(output_root, tmp_path):
    _cleanup_submissions()
    _cleanup_samples()
    sid = _insert_sample("I2-NCBI-S-A")
    file_dir = tmp_path / "src"
    file_dir.mkdir()
    _attach_local_files(sid, file_dir)
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-NCBI-OK",
            sample_ids=[sid],
            conn=db,
        )
        path = generate_package(submission_id=sub["id"], actor_id=SEED_USER_ID, conn=db)
    pkg = Path(path)
    assert pkg.is_dir()
    assert (pkg / "biosample.tsv").exists()
    assert (pkg / "sra.tsv").exists()
    assert (pkg / "seqsender_config.yaml").exists()
    assert (pkg / "README.md").exists()
    files_dir = pkg / "files"
    assert files_dir.is_dir()
    placed = sorted(p.name for p in files_dir.iterdir())
    assert "r1.fastq" in placed
    # Default is symlink (link, not copy).
    assert (files_dir / "r1.fastq").is_symlink()
    _cleanup_submissions()
    _cleanup_samples()


def test_generate_ncbi_package_copy_files_creates_real_copies(output_root, tmp_path):
    _cleanup_submissions()
    _cleanup_samples()
    sid = _insert_sample("I2-NCBI-S-COPY")
    file_dir = tmp_path / "src"
    file_dir.mkdir()
    _attach_local_files(sid, file_dir)
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-NCBI-COPY",
            sample_ids=[sid],
            conn=db,
        )
        path = generate_package(
            submission_id=sub["id"],
            actor_id=SEED_USER_ID,
            copy_files=True,
            conn=db,
        )
    files_dir = Path(path) / "files"
    assert (files_dir / "r1.fastq").exists()
    # copy_files=True must produce a real file, not a symlink.
    assert not (files_dir / "r1.fastq").is_symlink()
    _cleanup_submissions()
    _cleanup_samples()


def test_generate_ncbi_biosample_tsv_has_expected_columns(output_root, tmp_path):
    _cleanup_submissions()
    _cleanup_samples()
    sid = _insert_sample("I2-NCBI-S-COLS")
    file_dir = tmp_path / "src"
    file_dir.mkdir()
    _attach_local_files(sid, file_dir)
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-NCBI-COLS",
            sample_ids=[sid],
            conn=db,
        )
        path = generate_package(submission_id=sub["id"], actor_id=SEED_USER_ID, conn=db)
    biosample = (Path(path) / "biosample.tsv").read_text()
    assert "sample_name" in biosample.splitlines()[0]
    assert "organism" in biosample.splitlines()[0]
    assert "I2-NCBI-S-COLS" in biosample
    assert "Severe acute respiratory syndrome coronavirus 2" in biosample
    _cleanup_submissions()
    _cleanup_samples()


def test_generate_package_unconfigured_root_returns_500(monkeypatch):
    monkeypatch.setenv("SUBMISSIONS_OUTPUT_ROOT", "")
    get_settings.cache_clear()
    from fastapi import HTTPException

    _cleanup_submissions()
    _cleanup_samples()
    sid = _insert_sample("I2-NCBI-S-NOROOT")
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-NCBI-NOROOT",
            sample_ids=[sid],
            conn=db,
        )
        with pytest.raises(HTTPException) as exc:
            generate_package(submission_id=sub["id"], actor_id=SEED_USER_ID, conn=db)
    assert exc.value.status_code == 500
    get_settings.cache_clear()
    _cleanup_submissions()
    _cleanup_samples()


def test_generate_package_transitions_to_ready_to_submit(output_root, tmp_path):
    _cleanup_submissions()
    _cleanup_samples()
    sid = _insert_sample("I2-NCBI-S-RTS")
    file_dir = tmp_path / "src"
    file_dir.mkdir()
    _attach_local_files(sid, file_dir)
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-NCBI-RTS",
            sample_ids=[sid],
            conn=db,
        )
        generate_package(submission_id=sub["id"], actor_id=SEED_USER_ID, conn=db)
    rows = execute_query(
        "SELECT status, package_path, package_generated_at FROM submissions WHERE id = :id",
        {"id": sub["id"]},
    )
    assert rows[0]["status"] == "READY_TO_SUBMIT"
    assert rows[0]["package_path"]
    assert rows[0]["package_generated_at"]
    _cleanup_submissions()
    _cleanup_samples()


def test_generate_package_rejects_too_many_samples(output_root, tmp_path, monkeypatch):
    monkeypatch.setenv("SUBMISSION_MAX_SAMPLES_PER_PACKAGE", "1")
    get_settings.cache_clear()
    from fastapi import HTTPException

    _cleanup_submissions()
    _cleanup_samples()
    a = _insert_sample("I2-NCBI-S-CAP-A")
    b = _insert_sample("I2-NCBI-S-CAP-B")
    file_dir = tmp_path / "src"
    file_dir.mkdir()
    file_dir_b = file_dir / "b"
    file_dir_b.mkdir()
    _attach_local_files(a, file_dir)
    _attach_local_files(b, file_dir_b)
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-NCBI-CAP",
            sample_ids=[a, b],
            conn=db,
        )
        with pytest.raises(HTTPException) as exc:
            generate_package(submission_id=sub["id"], actor_id=SEED_USER_ID, conn=db)
    assert exc.value.status_code == 422
    get_settings.cache_clear()
    _cleanup_submissions()
    _cleanup_samples()
