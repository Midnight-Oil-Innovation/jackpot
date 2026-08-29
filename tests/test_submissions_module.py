"""I-2 unit tests for backend.submissions state machine + helpers."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.database import execute_query, execute_write, get_db
from backend.submissions import (
    AccessionEntry,
    add_samples_to_submission,
    create_submission,
    get_submission,
    list_submissions,
    mark_package_generated,
    mark_rejected,
    mark_submitted,
    parse_accessions_tsv,
    register_accessions,
    remove_samples_from_submission,
    soft_delete_submission,
    update_submission,
    validate_submission_readiness,
    withdraw_submission,
)

SEED_USER_ID = 1
SEED_LAB_ID = 1


def _cleanup_submissions(prefix: str = "I2-") -> None:
    rows = execute_query(
        "SELECT id FROM submissions WHERE title LIKE :p",
        {"p": f"{prefix}%"},
    )
    for r in rows:
        sid = r["id"]
        execute_write("DELETE FROM submission_samples WHERE submission_id = :id", {"id": sid})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'submission' AND resource_id = :rid",
            {"rid": str(sid)},
        )
        execute_write("DELETE FROM submissions WHERE id = :id", {"id": sid})


def _cleanup_samples(prefix: str = "I2-SAMPLE-") -> None:
    rows = execute_query(
        "SELECT id FROM samples WHERE sample_id LIKE :p",
        {"p": f"{prefix}%"},
    )
    for r in rows:
        sid = r["id"]
        execute_write("DELETE FROM submission_samples WHERE sample_id_fk = :id", {"id": sid})
        execute_write("DELETE FROM sample_files WHERE sample_id_fk = :id", {"id": sid})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'sample' AND resource_id = :rid",
            {"rid": str(sid)},
        )
        execute_write("DELETE FROM samples WHERE id = :id", {"id": sid})


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


# ── create / list / get / update ─────────────────────────────────


def test_create_submission_persists_and_attaches_samples():
    _cleanup_submissions()
    _cleanup_samples()
    sample_id_a = _insert_sample("I2-SAMPLE-A")
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-CREATE",
            sample_ids=[sample_id_a],
            conn=db,
        )
    assert sub["status"] == "DRAFT"
    assert sub["target_repository"] == "NCBI"
    assert sub["title"] == "I2-CREATE"
    assert sub["bioproject_accession"] is None

    with get_db() as db:
        full = get_submission(sub["id"], db)
    assert len(full["samples"]) == 1
    assert full["samples"][0]["sample_id"] == "I2-SAMPLE-A"
    _cleanup_submissions()
    _cleanup_samples()


def test_create_submission_rejects_invalid_repository():
    from fastapi import HTTPException

    sample_id = _insert_sample("I2-SAMPLE-INV")
    with get_db() as db, pytest.raises(HTTPException) as exc:
        create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="GARBAGE",
            title="I2-INV",
            sample_ids=[sample_id],
            conn=db,
        )
    assert exc.value.status_code == 422
    _cleanup_samples()


def test_create_submission_rejects_empty_sample_list():
    from fastapi import HTTPException

    with get_db() as db, pytest.raises(HTTPException) as exc:
        create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-EMPTY",
            sample_ids=[],
            conn=db,
        )
    assert exc.value.status_code == 422


def test_list_submissions_filters_by_status():
    _cleanup_submissions()
    sid = _insert_sample("I2-SAMPLE-LIST")
    with get_db() as db:
        a = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-LIST-A",
            sample_ids=[sid],
            conn=db,
        )
        create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-LIST-B",
            sample_ids=[sid],
            conn=db,
        )
        execute_write(
            "UPDATE submissions SET status = 'SUBMITTED' WHERE id = :id",
            {"id": a["id"]},
            conn=db,
        )
        rows, total = list_submissions(lab_id=SEED_LAB_ID, status="SUBMITTED", conn=db)
    titles = {r["title"] for r in rows}
    assert "I2-LIST-A" in titles
    assert "I2-LIST-B" not in titles
    _cleanup_submissions()
    _cleanup_samples()


def test_update_submission_locks_target_repo_post_draft():
    from fastapi import HTTPException

    _cleanup_submissions()
    sid = _insert_sample("I2-SAMPLE-LOCK")
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-LOCK",
            sample_ids=[sid],
            conn=db,
        )
        # Move past DRAFT.
        execute_write(
            "UPDATE submissions SET status = 'READY_TO_SUBMIT' WHERE id = :id",
            {"id": sub["id"]},
            conn=db,
        )
        with pytest.raises(HTTPException) as exc:
            update_submission(
                submission_id=sub["id"],
                actor_id=SEED_USER_ID,
                fields={"target_repository": "ENA"},
                conn=db,
            )
    assert exc.value.status_code == 422
    _cleanup_submissions()
    _cleanup_samples()


# ── add / remove samples (DRAFT only) ─────────────────────────────


def test_add_remove_samples_only_in_draft():
    from fastapi import HTTPException

    _cleanup_submissions()
    a = _insert_sample("I2-SAMPLE-AR-A")
    b = _insert_sample("I2-SAMPLE-AR-B")
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-AR",
            sample_ids=[a],
            conn=db,
        )
        # Add b
        added = add_samples_to_submission(
            submission_id=sub["id"],
            sample_ids=[b],
            actor_id=SEED_USER_ID,
            conn=db,
        )
        assert len(added) == 1
        # Remove a
        removed = remove_samples_from_submission(
            submission_id=sub["id"],
            sample_ids=[a],
            actor_id=SEED_USER_ID,
            conn=db,
        )
        assert removed == 1
        # Move past DRAFT and confirm subsequent add fails.
        execute_write(
            "UPDATE submissions SET status = 'READY_TO_SUBMIT' WHERE id = :id",
            {"id": sub["id"]},
            conn=db,
        )
        with pytest.raises(HTTPException) as exc:
            add_samples_to_submission(
                submission_id=sub["id"],
                sample_ids=[a],
                actor_id=SEED_USER_ID,
                conn=db,
            )
    assert exc.value.status_code == 422
    _cleanup_submissions()
    _cleanup_samples()


# ── validate_submission_readiness ─────────────────────────────────


def test_validate_returns_per_sample_issues():
    _cleanup_submissions()
    good = _insert_sample("I2-VAL-GOOD")
    bad = _insert_sample(
        "I2-VAL-BAD",
        organism_name="",
        collection_location_country="",
    )
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-VAL",
            sample_ids=[good, bad],
            conn=db,
        )
        result = validate_submission_readiness(sub["id"], db)
    assert result.valid is False
    assert any(s.sample_id == "I2-VAL-BAD" for s in result.per_sample)
    _cleanup_submissions()
    _cleanup_samples(prefix="I2-VAL-")


# ── state transitions: mark_submitted, register_accessions, etc. ─


def test_mark_submitted_only_from_ready_to_submit():
    from fastapi import HTTPException

    _cleanup_submissions()
    sid = _insert_sample("I2-MS-A")
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-MS",
            sample_ids=[sid],
            conn=db,
        )
        with pytest.raises(HTTPException) as exc:
            mark_submitted(submission_id=sub["id"], actor_id=SEED_USER_ID, conn=db)
    assert exc.value.status_code == 422

    with get_db() as db:
        execute_write(
            "UPDATE submissions SET status = 'READY_TO_SUBMIT' WHERE id = :id",
            {"id": sub["id"]},
            conn=db,
        )
        out = mark_submitted(submission_id=sub["id"], actor_id=SEED_USER_ID, conn=db)
    assert out["status"] == "SUBMITTED"
    assert out["submitted_at"] is not None
    _cleanup_submissions()
    _cleanup_samples()


def test_mark_package_generated_writes_path_and_status():
    _cleanup_submissions()
    sid = _insert_sample("I2-MPG")
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-MPG",
            sample_ids=[sid],
            conn=db,
        )
        out = mark_package_generated(
            submission_id=sub["id"],
            package_path="/tmp/i2_mpg",
            actor_id=SEED_USER_ID,
            conn=db,
        )
    assert out["status"] == "READY_TO_SUBMIT"
    assert out["package_path"] == "/tmp/i2_mpg"
    assert out["package_generated_at"] is not None
    _cleanup_submissions()
    _cleanup_samples()


def test_register_accessions_full_acceptance_with_no_release_date_releases_immediately():
    _cleanup_submissions()
    sid = _insert_sample("I2-REG-A")
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-REG",
            sample_ids=[sid],
            conn=db,
        )
        execute_write(
            "UPDATE submissions SET status = 'SUBMITTED' WHERE id = :id",
            {"id": sub["id"]},
            conn=db,
        )
        out = register_accessions(
            submission_id=sub["id"],
            accessions=[AccessionEntry(sample_id="I2-REG-A", biosample="SAMN001", sra="SRR001")],
            actor_id=SEED_USER_ID,
            conn=db,
        )
    assert out["status"] == "RELEASED"
    assert out["accepted_at"] is not None
    _cleanup_submissions()
    _cleanup_samples()


def test_register_accessions_with_future_release_date_goes_embargoed():
    _cleanup_submissions()
    sid = _insert_sample("I2-EMB-A")
    future = (date.today() + timedelta(days=30)).isoformat()
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-EMB",
            sample_ids=[sid],
            release_date=date.fromisoformat(future),
            conn=db,
        )
        execute_write(
            "UPDATE submissions SET status = 'SUBMITTED' WHERE id = :id",
            {"id": sub["id"]},
            conn=db,
        )
        out = register_accessions(
            submission_id=sub["id"],
            accessions=[AccessionEntry(sample_id="I2-EMB-A", biosample="SAMN002")],
            actor_id=SEED_USER_ID,
            conn=db,
        )
    assert out["status"] == "EMBARGOED"
    _cleanup_submissions()
    _cleanup_samples()


def test_register_accessions_partial_success():
    _cleanup_submissions()
    a = _insert_sample("I2-PS-A")
    b = _insert_sample("I2-PS-B")
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-PS",
            sample_ids=[a, b],
            conn=db,
        )
        execute_write(
            "UPDATE submissions SET status = 'SUBMITTED' WHERE id = :id",
            {"id": sub["id"]},
            conn=db,
        )
        out = register_accessions(
            submission_id=sub["id"],
            accessions=[
                AccessionEntry(sample_id="I2-PS-A", biosample="SAMN100"),
                AccessionEntry(
                    sample_id="I2-PS-B",
                    rejection_reason="missing host metadata",
                ),
            ],
            actor_id=SEED_USER_ID,
            conn=db,
        )
    assert out["status"] == "PARTIAL_SUCCESS"
    _cleanup_submissions()
    _cleanup_samples()


def test_mark_rejected_requires_reason_and_submitted_status():
    from fastapi import HTTPException

    _cleanup_submissions()
    sid = _insert_sample("I2-REJ")
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-REJ",
            sample_ids=[sid],
            conn=db,
        )
        with pytest.raises(HTTPException) as exc:
            mark_rejected(
                submission_id=sub["id"],
                reason="x",
                actor_id=SEED_USER_ID,
                conn=db,
            )
    assert exc.value.status_code == 422  # status not SUBMITTED yet

    with get_db() as db:
        execute_write(
            "UPDATE submissions SET status = 'SUBMITTED' WHERE id = :id",
            {"id": sub["id"]},
            conn=db,
        )
        with pytest.raises(HTTPException) as exc:
            mark_rejected(
                submission_id=sub["id"],
                reason="",
                actor_id=SEED_USER_ID,
                conn=db,
            )
    assert exc.value.status_code == 422  # empty reason

    with get_db() as db:
        out = mark_rejected(
            submission_id=sub["id"],
            reason="BioSample fields incomplete",
            actor_id=SEED_USER_ID,
            conn=db,
        )
    assert out["status"] == "REJECTED"
    _cleanup_submissions()
    _cleanup_samples()


def test_withdraw_submission_works_from_any_post_submitted_state():
    _cleanup_submissions()
    sid = _insert_sample("I2-WDR")
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-WDR",
            sample_ids=[sid],
            conn=db,
        )
        execute_write(
            "UPDATE submissions SET status = 'ACCEPTED' WHERE id = :id",
            {"id": sub["id"]},
            conn=db,
        )
        out = withdraw_submission(
            submission_id=sub["id"],
            reason="post-acceptance contamination identified",
            actor_id=SEED_USER_ID,
            conn=db,
        )
    assert out["status"] == "WITHDRAWN"
    assert "contamination" in out["withdrawal_reason"]
    _cleanup_submissions()
    _cleanup_samples()


# ── soft delete (DRAFT only) ──────────────────────────────────────


def test_soft_delete_only_drafts():
    from fastapi import HTTPException

    _cleanup_submissions()
    sid = _insert_sample("I2-SD")
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-SD",
            sample_ids=[sid],
            conn=db,
        )
        out = soft_delete_submission(submission_id=sub["id"], actor_id=SEED_USER_ID, conn=db)
        assert out["is_archived"] is True

        # Create another, advance status, ensure delete is rejected.
        sub2 = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-SD2",
            sample_ids=[sid],
            conn=db,
        )
        execute_write(
            "UPDATE submissions SET status = 'READY_TO_SUBMIT' WHERE id = :id",
            {"id": sub2["id"]},
            conn=db,
        )
        with pytest.raises(HTTPException) as exc:
            soft_delete_submission(submission_id=sub2["id"], actor_id=SEED_USER_ID, conn=db)
    assert exc.value.status_code == 422
    _cleanup_submissions()
    _cleanup_samples()


# ── parse_accessions_tsv ──────────────────────────────────────────


def test_parse_accessions_tsv_happy_path():
    text = (
        "sample_id\tbiosample\tsra\tgenbank\tgisaid\tena\tddbj\trejection_reason\n"
        "EX-001\tSAMN1\tSRR1\t-\t-\t-\t-\t-\n"
        "EX-002\t-\t-\t-\t-\t-\t-\trejected: missing host\n"
    )
    out = parse_accessions_tsv(text)
    assert len(out) == 2
    assert out[0].biosample == "SAMN1"
    assert out[0].rejection_reason is None
    assert out[1].biosample is None
    assert out[1].rejection_reason == "rejected: missing host"


def test_parse_accessions_tsv_missing_sample_id_column_raises_422():
    from fastapi import HTTPException

    text = "biosample\tsra\nSAMN1\tSRR1\n"
    with pytest.raises(HTTPException) as exc:
        parse_accessions_tsv(text)
    assert exc.value.status_code == 422


def test_parse_accessions_tsv_empty_returns_422():
    from fastapi import HTTPException

    text = "sample_id\tbiosample\n"
    with pytest.raises(HTTPException) as exc:
        parse_accessions_tsv(text)
    assert exc.value.status_code == 422


# ── audit + notification side effects (light coverage) ───────────


def test_create_submission_writes_audit_log():
    _cleanup_submissions()
    sid = _insert_sample("I2-AUD")
    with get_db() as db:
        sub = create_submission(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            target_repository="NCBI",
            title="I2-AUD",
            sample_ids=[sid],
            conn=db,
        )
    rows = execute_query(
        "SELECT action FROM audit_log WHERE resource_type = 'submission' AND resource_id = :rid",
        {"rid": str(sub["id"])},
    )
    actions = [r["action"] for r in rows]
    assert "SUBMISSION_CREATED" in actions
    _cleanup_submissions()
    _cleanup_samples()
