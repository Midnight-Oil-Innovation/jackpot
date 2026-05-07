"""I-2 submission-package dispatcher tests.

The dispatcher (``generate_package`` in :mod:`backend.submission_packages`)
maps each ``target_repository`` value to a per-repo generator. These
tests verify that routing — that the right generator is invoked for each
supported repository, and that an unknown repository is rejected with
a 422 before any state mutation.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from backend.config import get_settings
from backend.database import execute_query, execute_write, get_db
from backend.submission_packages import generate_package
from backend.submissions import create_submission

SEED_USER_ID = 1
SEED_LAB_ID = 1


def _cleanup_submissions(prefix: str = "I2-DISP-") -> None:
    rows = execute_query("SELECT id FROM submissions WHERE title LIKE :p", {"p": f"{prefix}%"})
    for r in rows:
        execute_write("DELETE FROM submission_samples WHERE submission_id = :id", {"id": r["id"]})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'submission' AND resource_id = :rid",
            {"rid": str(r["id"])},
        )
        execute_write("DELETE FROM submissions WHERE id = :id", {"id": r["id"]})


def _cleanup_samples(prefix: str = "I2-DISP-S-") -> None:
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


def _attach_local_files(sample_id_fk: int, dir_: Path) -> None:
    r1 = dir_ / "r1.fastq"
    r1.write_bytes(b"@A\nN\n+\n!\n")
    execute_write(
        """
        INSERT INTO sample_files (
            sample_id_fk, uri, filename, file_size_bytes,
            file_type, library_layout, read_direction,
            storage_state, scrub_status, ingest_method
        ) VALUES (
            :sid, :uri, :fn, :sz,
            'FASTQ', 'SINGLE', 'R1',
            CAST('EXTERNAL' AS file_storage_state), 'PENDING', 'register'
        )
        """,
        {
            "sid": sample_id_fk,
            "uri": f"file://{r1}",
            "fn": r1.name,
            "sz": r1.stat().st_size,
        },
    )


@pytest.fixture
def output_root(tmp_path, monkeypatch):
    root = tmp_path / "submissions_root"
    root.mkdir()
    monkeypatch.setenv("SUBMISSIONS_OUTPUT_ROOT", str(root))
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


def test_dispatcher_routes_ncbi_to_ncbi_generator(output_root, tmp_path):
    """A submission whose target_repository == 'NCBI' invokes the NCBI generator."""
    _cleanup_submissions()
    _cleanup_samples()
    calls: list[tuple] = []

    def spy(submission, samples, package_dir, *, copy_files=False):
        calls.append((submission["target_repository"], len(samples), package_dir))

    sid = _insert_sample("I2-DISP-S-NCBI")
    file_dir = tmp_path / "src"
    file_dir.mkdir()
    _attach_local_files(sid, file_dir)
    with (
        get_db() as db,
        patch.dict("backend.submission_packages._GENERATORS", {"NCBI": spy}),
    ):
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-DISP-NCBI",
            sample_ids=[sid],
            conn=db,
        )
        generate_package(submission_id=sub["id"], actor_id=SEED_USER_ID, conn=db)
    assert len(calls) == 1
    assert calls[0][0] == "NCBI"
    _cleanup_submissions()
    _cleanup_samples()


@pytest.mark.parametrize(
    "repo,expected_variant",
    [
        ("GISAID_EPICOV", "hCoV-19"),
        ("GISAID_EPIFLU", "A"),
        ("GISAID_EPIPOX", "MPXV"),
    ],
)
def test_dispatcher_routes_gisaid_variants_to_gisaid_generator(
    output_root, tmp_path, repo, expected_variant
):
    """Each GISAID repo code routes to its dedicated wrapper which writes the
    correct variant string into the TSV. This catches dispatcher mis-routing."""
    _cleanup_submissions()
    _cleanup_samples()
    suffix = repo.replace("GISAID_EPI", "G-")
    sid = _insert_sample(f"I2-DISP-S-{suffix}")
    file_dir = tmp_path / "src"
    file_dir.mkdir()
    _attach_local_files(sid, file_dir)
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository=repo,
            title=f"I2-DISP-{suffix}",
            sample_ids=[sid],
            conn=db,
        )
        path = generate_package(submission_id=sub["id"], actor_id=SEED_USER_ID, conn=db)
    pkg = Path(path)
    expected_tsv = {
        "GISAID_EPICOV": "gisaid_epicov.tsv",
        "GISAID_EPIFLU": "gisaid_epiflu.tsv",
        "GISAID_EPIPOX": "gisaid_epipox.tsv",
    }[repo]
    tsv_text = (pkg / expected_tsv).read_text()
    assert expected_variant in tsv_text
    _cleanup_submissions()
    _cleanup_samples()


def test_dispatcher_routes_ena_to_ena_generator(output_root, tmp_path):
    _cleanup_submissions()
    _cleanup_samples()
    sid = _insert_sample("I2-DISP-S-ENA")
    file_dir = tmp_path / "src"
    file_dir.mkdir()
    _attach_local_files(sid, file_dir)
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="ENA",
            title="I2-DISP-ENA",
            sample_ids=[sid],
            conn=db,
        )
        path = generate_package(submission_id=sub["id"], actor_id=SEED_USER_ID, conn=db)
    pkg = Path(path)
    # webin.tsv is the ENA-specific artifact and only the ENA generator writes it.
    assert (pkg / "webin.tsv").exists()
    assert not (pkg / "biosample.tsv").exists()
    assert not (pkg / "ddbj.tsv").exists()
    _cleanup_submissions()
    _cleanup_samples()


def test_dispatcher_routes_ddbj_to_ddbj_generator(output_root, tmp_path):
    _cleanup_submissions()
    _cleanup_samples()
    sid = _insert_sample("I2-DISP-S-DDBJ")
    file_dir = tmp_path / "src"
    file_dir.mkdir()
    _attach_local_files(sid, file_dir)
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="DDBJ",
            title="I2-DISP-DDBJ",
            sample_ids=[sid],
            conn=db,
        )
        path = generate_package(submission_id=sub["id"], actor_id=SEED_USER_ID, conn=db)
    pkg = Path(path)
    # ddbj.tsv is the DDBJ-specific artifact.
    assert (pkg / "ddbj.tsv").exists()
    assert not (pkg / "webin.tsv").exists()
    assert not (pkg / "biosample.tsv").exists()
    _cleanup_submissions()
    _cleanup_samples()


def test_dispatcher_rejects_unknown_target_repository(output_root, tmp_path):
    """The dispatcher rejects with a 422 when the target_repository is not in
    ``_GENERATORS``. Simulated by emptying the registry under patch.dict,
    so any submission's repo becomes "unknown" from the dispatcher's view."""
    from fastapi import HTTPException

    _cleanup_submissions()
    _cleanup_samples()
    sid = _insert_sample("I2-DISP-S-UNK")
    file_dir = tmp_path / "src"
    file_dir.mkdir()
    _attach_local_files(sid, file_dir)
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-DISP-UNK",
            sample_ids=[sid],
            conn=db,
        )
        with (
            patch.dict("backend.submission_packages._GENERATORS", {}, clear=True),
            pytest.raises(HTTPException) as exc,
        ):
            generate_package(submission_id=sub["id"], actor_id=SEED_USER_ID, conn=db)
    assert exc.value.status_code == 422
    assert "Unsupported target_repository" in str(exc.value.detail)
    _cleanup_submissions()
    _cleanup_samples()
