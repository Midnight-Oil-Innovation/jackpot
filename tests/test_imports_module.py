"""I-1 tests for backend.imports business-logic functions.

Pure-logic + DB-only tests; the router thin-shell is exercised by
``tests/test_imports_router.py``.
"""

from __future__ import annotations

import io

import openpyxl
import pytest

from backend.database import execute_query, execute_write, get_db
from backend.imports import (
    MAX_ROWS_PER_IMPORT,
    STEP_COLUMN_MAPPING,
    STEP_FILE_REFERENCE,
    STEP_IMPORT,
    STEP_PREVIEW,
    abandon_session,
    compute_diff,
    compute_preview,
    convert_to_csv,
    create_import_session,
    get_session_for_user,
    list_user_sessions,
    parse_spreadsheet,
    update_import_session,
)

SEED_USER_ID = 1
SEED_LAB_ID = 1


def _make_xlsx(rows: list[list[str]]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _cleanup_sessions(user_id: int = SEED_USER_ID) -> None:
    execute_write(
        "DELETE FROM import_sessions WHERE created_by_user_id = :uid",
        {"uid": user_id},
    )


def _cleanup_samples(prefix: str) -> None:
    rows = execute_query(
        "SELECT id FROM samples WHERE sample_id LIKE :p",
        {"p": f"{prefix}%"},
    )
    for r in rows:
        sid = r["id"]
        execute_write("DELETE FROM sample_files WHERE sample_id_fk = :id", {"id": sid})
        execute_write(
            "UPDATE audit_log SET actor_id = NULL "
            "WHERE resource_type = 'sample' AND resource_id = :rid",
            {"rid": str(sid)},
        )
        execute_write("DELETE FROM samples WHERE id = :id", {"id": sid})


# ── parse_spreadsheet ──────────────────────────────────────────────


def test_parse_spreadsheet_xlsx_returns_sheets_and_columns():
    blob = _make_xlsx(
        [
            ["Sample ID", "Country", "Source"],
            ["EX-001", "United States", "clinical"],
            ["EX-002", "Canada", "wastewater"],
        ]
    )
    meta = parse_spreadsheet(blob, "xlsx")
    assert meta.sheets == ["Sheet"]
    assert meta.columns_by_sheet["Sheet"] == ["Sample ID", "Country", "Source"]
    assert meta.row_counts_by_sheet["Sheet"] == 2
    samples = meta.sample_values_by_sheet["Sheet"]
    assert "EX-001" in samples["Sample ID"]
    assert "United States" in samples["Country"]


def test_parse_spreadsheet_csv_returns_single_sheet():
    csv_bytes = b"Sample ID,Country\nEX-001,United States\nEX-002,Canada\n"
    meta = parse_spreadsheet(csv_bytes, "csv")
    assert meta.sheets == ["__single__"]
    assert meta.columns_by_sheet["__single__"] == ["Sample ID", "Country"]
    assert meta.row_counts_by_sheet["__single__"] == 2


def test_parse_spreadsheet_tsv_returns_single_sheet():
    tsv_bytes = b"Sample ID\tCountry\nEX-001\tUSA\n"
    meta = parse_spreadsheet(tsv_bytes, "tsv")
    assert meta.columns_by_sheet["__single__"] == ["Sample ID", "Country"]


def test_parse_spreadsheet_empty_file_raises_400():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        parse_spreadsheet(b"", "csv")
    assert exc.value.status_code == 400


# ── create_import_session ──────────────────────────────────────────


def test_create_import_session_persists_bytes_and_metadata():
    _cleanup_sessions()
    blob = _make_xlsx([["Sample ID"], ["EX-001"]])
    with get_db() as db:
        session = create_import_session(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            file_bytes=blob,
            file_name="t.xlsx",
            file_format="xlsx",
            conn=db,
        )
    assert session["file_name"] == "t.xlsx"
    assert session["file_format"] == "xlsx"
    assert session["file_size_bytes"] == len(blob)
    assert session["status"] == "in_progress"
    assert session["current_step"] == 1
    _cleanup_sessions()


def test_create_import_session_oversized_raises_400():
    from fastapi import HTTPException

    huge = b"x" * (11 * 1024 * 1024)
    with get_db() as db, pytest.raises(HTTPException) as exc:
        create_import_session(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            file_bytes=huge,
            file_name="big.xlsx",
            file_format="xlsx",
            conn=db,
        )
    assert exc.value.status_code == 400


def test_create_import_session_at_limit_raises_409():
    from fastapi import HTTPException

    _cleanup_sessions()
    with get_db() as db:
        for i in range(5):
            create_import_session(
                user_id=SEED_USER_ID,
                lab_id=SEED_LAB_ID,
                file_bytes=b"a,b\n1,2\n",
                file_name=f"t{i}.csv",
                file_format="csv",
                conn=db,
            )
        with pytest.raises(HTTPException) as exc:
            create_import_session(
                user_id=SEED_USER_ID,
                lab_id=SEED_LAB_ID,
                file_bytes=b"a,b\n1,2\n",
                file_name="overflow.csv",
                file_format="csv",
                conn=db,
            )
    assert exc.value.status_code == 409
    _cleanup_sessions()


# ── get / list ─────────────────────────────────────────────────────


def test_get_session_for_user_returns_metadata():
    _cleanup_sessions()
    with get_db() as db:
        session = create_import_session(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            file_bytes=b"a,b\n1,2\n",
            file_name="t.csv",
            file_format="csv",
            conn=db,
        )
        out = get_session_for_user(session["id"], SEED_USER_ID, db)
    assert out["id"] == session["id"]
    _cleanup_sessions()


def test_get_session_other_user_returns_404():
    from fastapi import HTTPException

    _cleanup_sessions()
    with get_db() as db:
        session = create_import_session(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            file_bytes=b"a,b\n1,2\n",
            file_name="t.csv",
            file_format="csv",
            conn=db,
        )
        with pytest.raises(HTTPException) as exc:
            get_session_for_user(session["id"], 999_999, db)
    assert exc.value.status_code == 404
    _cleanup_sessions()


def test_get_session_expired_returns_410():
    from fastapi import HTTPException

    _cleanup_sessions()
    with get_db() as db:
        session = create_import_session(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            file_bytes=b"a,b\n1,2\n",
            file_name="t.csv",
            file_format="csv",
            conn=db,
        )
        execute_write(
            "UPDATE import_sessions SET expires_at = NOW() - INTERVAL '1 hour' WHERE id = :id",
            {"id": session["id"]},
            conn=db,
        )
        with pytest.raises(HTTPException) as exc:
            get_session_for_user(session["id"], SEED_USER_ID, db)
    assert exc.value.status_code == 410
    _cleanup_sessions()


# ── update_import_session ──────────────────────────────────────────


def test_update_import_session_sets_field():
    _cleanup_sessions()
    with get_db() as db:
        session = create_import_session(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            file_bytes=b"a,b\n1,2\n",
            file_name="t.csv",
            file_format="csv",
            conn=db,
        )
        updated = update_import_session(
            session_id=session["id"],
            user_id=SEED_USER_ID,
            fields={"column_mapping": {"a": "sample_id"}},
            conn=db,
        )
    assert updated["column_mapping"] == {"a": "sample_id"}
    assert updated["current_step"] == STEP_COLUMN_MAPPING
    _cleanup_sessions()


def test_update_import_session_invalidates_downstream_cached_state():
    _cleanup_sessions()
    with get_db() as db:
        session = create_import_session(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            file_bytes=b"a,b\n1,2\n",
            file_name="t.csv",
            file_format="csv",
            conn=db,
        )
        # Seed downstream cached state.
        execute_write(
            "UPDATE import_sessions SET preview_results = '{\"x\": 1}'::jsonb, "
            "diff_results = '{\"y\": 2}'::jsonb, current_step = 6 WHERE id = :id",
            {"id": session["id"]},
            conn=db,
        )
        # Patch an earlier-step field; downstream cache should clear.
        updated = update_import_session(
            session_id=session["id"],
            user_id=SEED_USER_ID,
            fields={"column_mapping": {"a": "sample_id"}},
            conn=db,
        )
    assert updated["preview_results"] is None
    assert updated["diff_results"] is None
    assert updated["current_step"] == STEP_COLUMN_MAPPING
    _cleanup_sessions()


def test_update_import_session_other_user_returns_404():
    from fastapi import HTTPException

    _cleanup_sessions()
    with get_db() as db:
        session = create_import_session(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            file_bytes=b"a,b\n1,2\n",
            file_name="t.csv",
            file_format="csv",
            conn=db,
        )
        with pytest.raises(HTTPException) as exc:
            update_import_session(
                session_id=session["id"],
                user_id=999_999,
                fields={"column_mapping": {}},
                conn=db,
            )
    assert exc.value.status_code == 404
    _cleanup_sessions()


def test_update_import_session_rejects_unknown_field():
    from fastapi import HTTPException

    _cleanup_sessions()
    with get_db() as db:
        session = create_import_session(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            file_bytes=b"a,b\n1,2\n",
            file_name="t.csv",
            file_format="csv",
            conn=db,
        )
        with pytest.raises(HTTPException) as exc:
            update_import_session(
                session_id=session["id"],
                user_id=SEED_USER_ID,
                fields={"file_bytes": b"hax"},
                conn=db,
            )
    assert exc.value.status_code == 422
    _cleanup_sessions()


# ── convert_to_csv ──────────────────────────────────────────────────


def test_convert_to_csv_produces_jackpot_format():
    _cleanup_sessions()
    blob = b"Sample ID,Country,FASTQ R1,FASTQ R2\nEX-001,USA,r1.fq.gz,r2.fq.gz\n"
    with get_db() as db:
        session = create_import_session(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            file_bytes=blob,
            file_name="t.csv",
            file_format="csv",
            conn=db,
        )
        update_import_session(
            session_id=session["id"],
            user_id=SEED_USER_ID,
            fields={
                "column_mapping": {
                    "Sample ID": "sample_id",
                    "Country": "collection_location_country",
                },
                "file_reference_pattern": {
                    "type": "path_columns",
                    "config": {"r1_column": "FASTQ R1", "r2_column": "FASTQ R2"},
                    "storage_intent": "EXTERNAL",
                },
            },
            conn=db,
        )
        full = get_session_for_user(session["id"], SEED_USER_ID, db)
        csv_text = convert_to_csv(full, db)
    assert "sample_id" in csv_text
    assert "collection_location_country" in csv_text
    assert "files" in csv_text
    assert "EX-001" in csv_text
    assert "r1.fq.gz;r2.fq.gz" in csv_text
    assert "storage_intent" in csv_text
    _cleanup_sessions()


def test_convert_to_csv_handles_value_mapping():
    _cleanup_sessions()
    blob = b"Sample ID,Source\nEX-001,Hosp\n"
    with get_db() as db:
        session = create_import_session(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            file_bytes=blob,
            file_name="t.csv",
            file_format="csv",
            conn=db,
        )
        update_import_session(
            session_id=session["id"],
            user_id=SEED_USER_ID,
            fields={
                "column_mapping": {"Sample ID": "sample_id", "Source": "sector"},
                "value_mapping": {"sector": {"Hosp": "clinical"}},
            },
            conn=db,
        )
        full = get_session_for_user(session["id"], SEED_USER_ID, db)
        csv_text = convert_to_csv(full, db)
    # Source value 'Hosp' must be translated to 'clinical' in the
    # output.
    assert "clinical" in csv_text
    assert "Hosp" not in csv_text or csv_text.count("Hosp") == 0
    _cleanup_sessions()


# ── compute_preview / compute_diff ──────────────────────────────────


def test_compute_preview_returns_per_row_validation():
    _cleanup_sessions()
    blob = b"Sample ID\nEX-001\nEX-002\n"
    with get_db() as db:
        session = create_import_session(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            file_bytes=blob,
            file_name="t.csv",
            file_format="csv",
            conn=db,
        )
        update_import_session(
            session_id=session["id"],
            user_id=SEED_USER_ID,
            fields={"column_mapping": {"Sample ID": "sample_id"}},
            conn=db,
        )
        full = get_session_for_user(session["id"], SEED_USER_ID, db)
        result = compute_preview(full, db)
    assert result["sample_size"] == 20
    assert result["total_rows"] == 2
    assert len(result["rows"]) == 2
    # Both rows should be flagged invalid (missing required fields).
    assert all(r["valid"] is False for r in result["rows"])
    # current_step should advance to PREVIEW.
    after = get_session_for_user(session["id"], SEED_USER_ID, get_db().__enter__())
    assert after["current_step"] == STEP_PREVIEW
    _cleanup_sessions()


def test_compute_diff_identifies_new_and_changed_samples():
    _cleanup_sessions()
    prefix = "I1-DIFF-"
    _cleanup_samples(prefix)
    # Pre-create one sample so the diff finds a change.
    execute_write(
        """
        INSERT INTO samples (
            sample_id, lab_id, project_id, owner_id, source_type, organism_name,
            type_of_experiment, library_preparation_method, sequencing_protocol,
            sequencing_platform, sequencing_lab, date_collected, date_sequenced,
            collection_facility, collection_location_country, sharing_level,
            fastq_r1_uri, sector
        ) VALUES (
            :sid, 1, 1, 1, 'Human', 'old organism',
            'WGS', 'ARTIC', 'https://www.protocols.io/view/x',
            'Illumina', 'Example Sequencing Lab', '2026-01-15', '2026-01-17',
            'Example Hospital', 'United States', 'PRIVATE',
            'gs://test/R1.fq.gz', 'clinical'
        )
        """,
        {"sid": f"{prefix}EXIST"},
    )
    blob = f"Sample ID,Organism\n{prefix}EXIST,new organism\n{prefix}NEW,fresh\n".encode()
    with get_db() as db:
        session = create_import_session(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            file_bytes=blob,
            file_name="t.csv",
            file_format="csv",
            conn=db,
        )
        update_import_session(
            session_id=session["id"],
            user_id=SEED_USER_ID,
            fields={
                "column_mapping": {
                    "Sample ID": "sample_id",
                    "Organism": "organism_name",
                }
            },
            conn=db,
        )
        full = get_session_for_user(session["id"], SEED_USER_ID, db)
        diff = compute_diff(full, db)
    assert f"{prefix}NEW" in diff["new"]
    assert any(c["sample_id"] == f"{prefix}EXIST" for c in diff["changed"])
    assert diff["total"] == 2
    _cleanup_samples(prefix)
    _cleanup_sessions()


# ── abandon ────────────────────────────────────────────────────────


def test_abandon_session_marks_status():
    _cleanup_sessions()
    with get_db() as db:
        session = create_import_session(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            file_bytes=b"a,b\n1,2\n",
            file_name="t.csv",
            file_format="csv",
            conn=db,
        )
        out = abandon_session(session["id"], SEED_USER_ID, db)
    assert out["status"] == "abandoned"
    _cleanup_sessions()


# ── list ───────────────────────────────────────────────────────────


def test_list_sessions_returns_only_user_in_progress():
    _cleanup_sessions()
    with get_db() as db:
        s1 = create_import_session(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            file_bytes=b"a,b\n1,2\n",
            file_name="a.csv",
            file_format="csv",
            conn=db,
        )
        # Mark one terminal — should be excluded.
        execute_write(
            "UPDATE import_sessions SET status = 'imported' WHERE id = :id",
            {"id": s1["id"]},
            conn=db,
        )
        s2 = create_import_session(
            user_id=SEED_USER_ID,
            lab_id=SEED_LAB_ID,
            file_bytes=b"a,b\n3,4\n",
            file_name="b.csv",
            file_format="csv",
            conn=db,
        )
        rows = list_user_sessions(SEED_USER_ID, db)
    ids = {r["id"] for r in rows}
    assert s2["id"] in ids
    assert s1["id"] not in ids
    _cleanup_sessions()


def test_max_rows_per_import_constant_sane():
    # Sanity check — design notes say 10,000.
    assert MAX_ROWS_PER_IMPORT == 10_000


def test_step_constants_are_in_canonical_order():
    # Just enough to catch a copy-paste mistake when adding a step.
    assert STEP_COLUMN_MAPPING < STEP_FILE_REFERENCE < STEP_PREVIEW < STEP_IMPORT
