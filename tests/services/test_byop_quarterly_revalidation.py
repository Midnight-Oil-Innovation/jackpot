# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Tests for the P0f B-BYOP-6 quarterly BYOP revalidation job.

In-memory SQLite via the router's ``ByopPipeline`` model (mirrors
``tests/routers/test_byop.py``). Stage 1 (``_run_stage1``) and the
registrar notification are monkeypatched — no Docker, no network, no
schema file reads.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.routers.byop import Base, ByopPipeline
from backend.services import byop_quarterly_revalidation as reval
from backend.services.byop_validator import CheckResult, ValidationReport

MANIFEST = """\
api_version: v1
kind: pipeline
metadata:
  name: tb-typer
  display_name: TB Typer
  version: 1.2.3
  license: MIT
engine:
  type: nextflow
  version: "23.10"
  entrypoint: main.nf
containers:
  - image: quay.io/tb/typer:1.2.3
"""


@pytest.fixture()
def db() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _pipeline(name: str, status: str = "ACTIVE") -> ByopPipeline:
    return ByopPipeline(
        name=name,
        display_name=name,
        version="1.0.0",
        engine_type="nextflow",
        engine_version="23.10",
        source_type="git",
        manifest_yaml=MANIFEST,
        pipeline_status=status,
        registered_by_user_id="1",
        registered_at=datetime.now(UTC),
        license_spdx="MIT",
    )


def _report(passed: bool, failing_check: str = "") -> ValidationReport:
    checks = [CheckResult(check_name="schema_conformance", passed=True, message="ok")]
    if not passed:
        checks.append(CheckResult(check_name=failing_check, passed=False, message="gone"))
    return ValidationReport(manifest_id="tb-typer@1.0.0", passed=passed, checks=checks)


@pytest.fixture()
def no_notify(monkeypatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr(reval, "create_notification", mock)
    return mock


def test_happy_path_all_pass(db, monkeypatch, no_notify):
    for name in ("p1", "p2"):
        db.add(_pipeline(name))
    db.commit()
    monkeypatch.setattr(reval, "_run_stage1", lambda manifest: _report(True))

    counters = reval.revalidate_active_byop_pipelines(db)

    assert counters == {"checked": 2, "passed": 2, "deactivated": 0, "errors": 0}
    for pipeline in db.query(ByopPipeline).all():
        assert pipeline.pipeline_status == "ACTIVE"
        assert pipeline.last_validated_at is not None
        assert "[ROT]" not in (pipeline.validation_log or "")
    no_notify.assert_not_called()


@pytest.mark.parametrize(
    ("failing_check", "rot"),
    [
        ("container_references", "deleted_container"),
        ("license", "expired_license"),
        ("reference_data", "vanished_reference_data_url"),
    ],
)
def test_upstream_rot_flags_and_deactivates(db, monkeypatch, no_notify, failing_check, rot):
    db.add(_pipeline("rotten"))
    db.add(_pipeline("healthy"))
    db.commit()

    # rotten fails, healthy passes — keyed off insertion order
    reports = iter([_report(False, failing_check), _report(True)])
    monkeypatch.setattr(reval, "_run_stage1", lambda manifest: next(reports))

    counters = reval.revalidate_active_byop_pipelines(db)

    assert counters["deactivated"] == 1
    assert counters["passed"] == 1
    rotten = db.query(ByopPipeline).filter_by(name="rotten").one()
    assert rotten.pipeline_status == "DEACTIVATED"
    assert rotten.deactivated_at is not None
    assert rot in rotten.validation_log
    healthy = db.query(ByopPipeline).filter_by(name="healthy").one()
    assert healthy.pipeline_status == "ACTIVE"
    assert "[ROT]" not in healthy.validation_log
    no_notify.assert_called_once()
    assert no_notify.call_args.kwargs["event_type"] == "BYOP_REVALIDATION_FAILED"


def test_no_active_pipelines(db, monkeypatch, no_notify):
    db.add(_pipeline("archived", status="ARCHIVED"))
    db.add(_pipeline("deactivated", status="DEACTIVATED"))
    db.commit()
    stage1 = MagicMock()
    monkeypatch.setattr(reval, "_run_stage1", stage1)

    counters = reval.revalidate_active_byop_pipelines(db)

    assert counters == {"checked": 0, "passed": 0, "deactivated": 0, "errors": 0}
    stage1.assert_not_called()


def test_partial_failure_isolated(db, monkeypatch, no_notify):
    for name in ("a", "b", "c"):
        db.add(_pipeline(name))
    db.commit()
    reports = iter([_report(True), _report(False, "container_references"), _report(True)])
    monkeypatch.setattr(reval, "_run_stage1", lambda manifest: next(reports))

    counters = reval.revalidate_active_byop_pipelines(db)

    assert counters == {"checked": 3, "passed": 2, "deactivated": 1, "errors": 0}
    assert db.query(ByopPipeline).filter_by(name="b").one().pipeline_status == "DEACTIVATED"
    for name in ("a", "c"):
        row = db.query(ByopPipeline).filter_by(name=name).one()
        assert row.pipeline_status == "ACTIVE"
        assert "[ROT]" not in row.validation_log


def test_validator_exception_logged_and_continues(db, monkeypatch, no_notify, caplog):
    for name in ("boom", "fine"):
        db.add(_pipeline(name))
    db.commit()
    calls = iter([RuntimeError("registry exploded"), _report(True)])

    def stage1(manifest):
        item = next(calls)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(reval, "_run_stage1", stage1)

    with caplog.at_level("ERROR"):
        counters = reval.revalidate_active_byop_pipelines(db)

    assert counters == {"checked": 2, "passed": 1, "deactivated": 0, "errors": 1}
    assert any("continuing" in rec.message for rec in caplog.records)
    fine = db.query(ByopPipeline).filter_by(name="fine").one()
    assert fine.pipeline_status == "ACTIVE"
    assert fine.last_validated_at is not None


def test_quarterly_cadence_registration(monkeypatch):
    monkeypatch.delenv("JACKPOT_BYOP_REVALIDATION_INTERVAL_SECONDS", raising=False)
    scheduler = MagicMock()

    reval.register(scheduler)

    scheduler.add_job.assert_called_once()
    kwargs = scheduler.add_job.call_args.kwargs
    assert kwargs["seconds"] == 90 * 24 * 3600  # §5.4 default 90 days
    assert kwargs["id"] == "byop_quarterly_revalidation"
    assert scheduler.add_job.call_args.args == (
        reval.run_byop_quarterly_revalidation,
        "interval",
    )


def test_cadence_env_configurable(monkeypatch):
    monkeypatch.setenv("JACKPOT_BYOP_REVALIDATION_INTERVAL_SECONDS", "3600")
    assert reval.revalidation_interval_seconds() == 3600
