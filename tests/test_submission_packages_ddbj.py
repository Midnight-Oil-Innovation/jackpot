"""I-2 DDBJ package-generator tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.config import get_settings
from backend.database import execute_query, execute_write, get_db
from backend.submission_packages import generate_package
from backend.submissions import create_submission

SEED_USER_ID = 1
SEED_LAB_ID = 1


def _cleanup_submissions(prefix: str = "I2-DDBJ-") -> None:
    rows = execute_query("SELECT id FROM submissions WHERE title LIKE :p", {"p": f"{prefix}%"})
    for r in rows:
        execute_write("DELETE FROM submission_samples WHERE submission_id = :id", {"id": r["id"]})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'submission' AND resource_id = :rid",
            {"rid": str(r["id"])},
        )
        execute_write("DELETE FROM submissions WHERE id = :id", {"id": r["id"]})


def _cleanup_samples(prefix: str = "I2-DDBJ-S-") -> None:
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
        "collection_location_country": "Japan",
        "collection_location_state": "Tokyo",
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


def _make_package(*, sample_suffix: str, tmp_path: Path) -> Path:
    sid = _insert_sample(f"I2-DDBJ-S-{sample_suffix}")
    file_dir = tmp_path / "src"
    file_dir.mkdir()
    _attach_local_files(sid, file_dir)
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="DDBJ",
            title=f"I2-DDBJ-{sample_suffix}",
            sample_ids=[sid],
            conn=db,
        )
        path = generate_package(submission_id=sub["id"], actor_id=SEED_USER_ID, conn=db)
    return Path(path)


def test_generate_ddbj_writes_submission_files(output_root, tmp_path):
    _cleanup_submissions()
    _cleanup_samples()
    pkg = _make_package(sample_suffix="FILES", tmp_path=tmp_path)
    assert (pkg / "ddbj.tsv").exists()
    assert (pkg / "seqsender_config.yaml").exists()
    assert (pkg / "README.md").exists()
    _cleanup_submissions()
    _cleanup_samples()


def test_generate_ddbj_includes_required_fields(output_root, tmp_path):
    _cleanup_submissions()
    _cleanup_samples()
    pkg = _make_package(sample_suffix="COLS", tmp_path=tmp_path)
    tsv = (pkg / "ddbj.tsv").read_text()
    header = tsv.splitlines()[0]
    for required in ("sample_id", "organism", "collection_date", "country", "host"):
        assert required in header, f"DDBJ tsv missing required column {required!r}"
    # Body row carries the sample data.
    assert "I2-DDBJ-S-COLS" in tsv
    assert "Japan" in tsv
    _cleanup_submissions()
    _cleanup_samples()


def test_generate_ddbj_writes_readme(output_root, tmp_path):
    _cleanup_submissions()
    _cleanup_samples()
    pkg = _make_package(sample_suffix="RM", tmp_path=tmp_path)
    readme = (pkg / "README.md").read_text()
    assert "DDBJ notes" in readme
    _cleanup_submissions()
    _cleanup_samples()


def test_generate_ddbj_links_files(output_root, tmp_path):
    """Default behaviour is symlink (link, don't copy)."""
    _cleanup_submissions()
    _cleanup_samples()
    pkg = _make_package(sample_suffix="LINK", tmp_path=tmp_path)
    files_dir = pkg / "files"
    assert files_dir.is_dir()
    placed = sorted(p.name for p in files_dir.iterdir())
    assert "r1.fastq" in placed
    assert (files_dir / "r1.fastq").is_symlink()
    _cleanup_submissions()
    _cleanup_samples()
