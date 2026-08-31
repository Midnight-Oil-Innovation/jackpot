"""M2 pre-cutover verification (access_model.md §11.3) — dark, additive.

Four areas, all against the real testcontainer PostgreSQL:

  2a. reseed() proof on PG: grant shape, idempotency, and the
      create-index-before-reseed ordering the staged migration relies on.
  2b. Guard equivalence matrix: legacy require_capability vs permit()
      with reseeded grants — zero UNEXPECTED divergences, every
      EXPECTED_DIVERGENCES key fires.
  2c. List-visibility equivalence: legacy permissions.visibility_sql_clause
      vs authz.visibility fragment. Safety invariant: the new machinery
      never over-grants (new ⊆ legacy per persona).
  2d. Map hygiene: docs/m2_preflight_report.md stays in sync with its
      generator. (# M2: flip to assert not gaps)

This file's skeleton becomes tests/authz/test_cutover.py at M2; the
EXPECTED_DIVERGENCES registry entries flip to "resolved" one by one.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from sqlalchemy import text

# `tests` is shadowed by cli/tests (a regular package from the editable cli
# install), so absolute `tests.authz.*` fails; pytest inserts tests/ on
# sys.path for this package (tests/authz has __init__.py, tests/ does not),
# making `authz.preflight` the resolvable name.
from authz.preflight import (
    EXPECTED_DIVERGENCES,
    SAMPLE_PREFIX,
    UNIQUE_INDEX_DDL,
    classify_legacy_only_visibility,
    lab_scope,
    load_principal,
    run_matrix,
    seed_world,
    teardown_world,
    user_dict,
)
from backend.authz.reseed import PRESET_GRANTS, reseed
from backend.authz.visibility import visibility_sql_clause as new_visibility_sql_clause
from backend.database import _get_engine, execute_query
from backend.permissions import visibility_sql_clause as legacy_visibility_sql_clause

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def world(test_db_url):
    # Module scope runs BEFORE the function-scoped autouse override_settings,
    # so point the engine at the container ourselves (same env override_settings
    # re-applies per test afterwards).
    from backend.config import get_settings
    from backend.database import reset_engine

    mp = pytest.MonkeyPatch()
    mp.setenv("DATABASE_URL", test_db_url)
    mp.setenv("ENV", "local")
    get_settings.cache_clear()
    reset_engine()

    engine, _ = _get_engine()
    with engine.begin() as conn:
        conn.execute(text(UNIQUE_INDEX_DDL))
    w = seed_world()
    with engine.begin() as conn:
        reseed(conn)
    yield w
    teardown_world(w)
    mp.undo()
    get_settings.cache_clear()
    reset_engine()


# ──────────────────────────────────────────────────────────────────────────
# 2a — reseed proof on real PostgreSQL
# ──────────────────────────────────────────────────────────────────────────


def _grants(world, pkey):
    return execute_query(
        "SELECT capability, scope_ref, conditions, source, id "
        "FROM authz_capability_grants WHERE principal_id = :p ORDER BY capability, scope_ref",
        {"p": str(world.personas[pkey].user_id)},
    )


EXPECTED_GRANT_SHAPE = {
    # persona -> {scope_kind: capability count}
    "P1": {"instance": len(PRESET_GRANTS["instance_administrator"])},
    "P2": {"instance": len(PRESET_GRANTS["surveillance_officer"])},
    "P3": {"instance": len(PRESET_GRANTS["instance_administrator"])},  # subsumption
    "P4": {"lab_a": len(PRESET_GRANTS["lab_lead"])},
    "P5": {"lab_a": len(PRESET_GRANTS["lab_member_rw"])},
    "P6": {"lab_a": len(PRESET_GRANTS["lab_member_ro"])},
    "P7": {"lab_a": len(PRESET_GRANTS["lab_member_rw"]) + 1},  # + pipeline:run
    "P8": {"lab_a": len(PRESET_GRANTS["lab_lead"]), "lab_b": len(PRESET_GRANTS["lab_member_ro"])},
    "P9": {},
    "P10": {},
    "P11": {"lab_a": len(PRESET_GRANTS["lab_member_rw"])},  # group name wins over flag
    "P12": {},
}


class TestReseedOnPostgres:
    def test_grant_counts_and_shape_per_persona(self, world):
        for pkey, expected in EXPECTED_GRANT_SHAPE.items():
            rows = _grants(world, pkey)
            by_scope: dict[str, int] = {}
            for r in rows:
                if r["scope_ref"] == "instance://self":
                    kind = "instance"
                elif r["scope_ref"] == lab_scope(world.lab_a):
                    kind = "lab_a"
                elif r["scope_ref"] == lab_scope(world.lab_b):
                    kind = "lab_b"
                else:
                    pytest.fail(f"{pkey}: unexpected scope_ref {r['scope_ref']!r}")
                by_scope[kind] = by_scope.get(kind, 0) + 1
            assert by_scope == expected, f"{pkey}: {by_scope} != {expected}"
            for r in rows:
                assert r["source"] == "reseed"
                # JSONB round-trip default — a shape SQLite never exercised.
                assert r["conditions"] in (None, {}), r
                assert r["id"] is not None

    def test_bioinformatics_user_gets_pipeline_run(self, world):
        caps = {r["capability"] for r in _grants(world, "P7")}
        assert "pipeline:run" in caps
        # and a plain collaborator does not:
        assert "pipeline:run" not in {r["capability"] for r in _grants(world, "P5")}

    def test_reseed_idempotent_on_pg_with_unique_index(self, world):
        engine, _ = _get_engine()
        before = execute_query("SELECT COUNT(*) AS c FROM authz_capability_grants", {})[0]["c"]
        with engine.begin() as conn:
            reseed(conn)
        after = execute_query("SELECT COUNT(*) AS c FROM authz_capability_grants", {})[0]["c"]
        assert after == before, "second reseed inserted rows — ON CONFLICT arbiter missing"

    def test_reseed_duplicates_without_index(self, world):
        """Pins the staged migration's create-index-BEFORE-reseed ordering as
        load-bearing: on the live chain (no unique index) a second reseed
        silently duplicates every grant."""
        engine, _ = _get_engine()
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                conn.execute(
                    text("DROP INDEX authz_capability_grants_principal_capability_scope_uniq")
                )
                before = conn.execute(
                    text("SELECT COUNT(*) FROM authz_capability_grants")
                ).scalar_one()
                reseed(conn)
                after = conn.execute(
                    text("SELECT COUNT(*) FROM authz_capability_grants")
                ).scalar_one()
                assert after > before, (
                    "expected duplicate grants without the unique index — if this "
                    "now fails, the live chain gained the index and the staged "
                    "migration's ordering note can be relaxed"
                )
            finally:
                trans.rollback()

    def test_unmapped_group_skipped_with_warning(self, world, caplog):
        engine, _ = _get_engine()
        with (
            caplog.at_level(logging.WARNING, logger="backend.authz.reseed"),
            engine.begin() as conn,
        ):
            reseed(conn)
        assert any("unmapped" in rec.message for rec in caplog.records)
        assert _grants(world, "P9") == []


# ──────────────────────────────────────────────────────────────────────────
# 2b — guard equivalence matrix
# ──────────────────────────────────────────────────────────────────────────


class TestGuardEquivalenceMatrix:
    def test_matrix_zero_unexpected_and_all_registry_keys_fire(self, world):
        cells, unexpected, fired = run_matrix(world)
        assert len(cells) == 12 * 13 * 3

        if unexpected:
            dump = json.dumps([c.__dict__ for c in unexpected], indent=2, default=str)
            pytest.fail(f"UNEXPECTED divergences ({len(unexpected)}):\n{dump}")

        stale = set(EXPECTED_DIVERGENCES) - fired
        assert not stale, (
            f"registry keys never fired: {stale} — behavior moved; "
            "update EXPECTED_DIVERGENCES and docs/m2_preflight_report.md"
        )

    def test_matched_cells_exist(self, world):
        cells, _, _ = run_matrix(world)
        matches = [c for c in cells if not c.diverged]
        # Sanity: the harness isn't comparing constants — both agreement and
        # divergence must occur in bulk.
        assert len(matches) > 200


# ──────────────────────────────────────────────────────────────────────────
# 2c — list-visibility equivalence on real PostgreSQL
# ──────────────────────────────────────────────────────────────────────────


def _legacy_visible(persona) -> set[str]:
    clause, params = legacy_visibility_sql_clause(user_dict(persona))
    rows = execute_query(
        f"SELECT s.sample_id FROM samples s WHERE {clause} "  # noqa: S608 — test fragment
        "AND s.sample_id LIKE :prefix",
        {**params, "prefix": f"{SAMPLE_PREFIX}%"},
    )
    return {r["sample_id"] for r in rows}


def _new_visible(persona) -> set[str]:
    principal = load_principal(persona.user_id)
    fragment, params = new_visibility_sql_clause(principal, "sample:read", "s", policies=[])
    rows = execute_query(
        "SELECT s.sample_id FROM "
        "(SELECT samples.*, 'lab://' || samples.lab_id AS scope FROM samples) s "
        f"WHERE {fragment} AND s.sample_id LIKE :prefix",  # noqa: S608
        {**params, "prefix": f"{SAMPLE_PREFIX}%"},
    )
    return {r["sample_id"] for r in rows}


class TestVisibilityEquivalence:
    def test_new_never_over_grants(self, world):
        """Unconditional safety invariant: new_visible ⊆ legacy_visible."""
        for pkey, persona in world.personas.items():
            over = _new_visible(persona) - _legacy_visible(persona)
            assert not over, f"{pkey}: new model over-grants {sorted(over)}"

    def test_every_legacy_only_row_is_attributed(self, world):
        for pkey, persona in world.personas.items():
            legacy_only = _legacy_visible(persona) - _new_visible(persona)
            for sid in sorted(legacy_only):
                key = sid.removeprefix(SAMPLE_PREFIX)
                cls = classify_legacy_only_visibility(persona, key)
                assert cls is not None, (
                    f"{pkey} legacy-only row {sid} unattributed — new divergence "
                    "class; register it in preflight.py + the report"
                )

    def test_members_see_their_lab_under_both_models(self, world):
        """Positive agreement: lab-A members see the lab-A sample both ways."""
        for pkey in ("P4", "P5", "P6", "P7"):
            persona = world.personas[pkey]
            assert f"{SAMPLE_PREFIX}A-PRIV" in _legacy_visible(persona)
            assert f"{SAMPLE_PREFIX}A-PRIV" in _new_visible(persona)

    def test_new_fragment_matches_permit_per_row_on_pg(self, world):
        """Extends the M1 SQLite zero-divergence proof to PG semantics
        (LIKE ... ESCAPE '\\'): a row is fragment-visible iff permit()
        allows sample:read on that row's scope."""
        from backend.authz import Context, Decision, Resource, permit

        samples = execute_query(
            "SELECT sample_id, lab_id FROM samples WHERE sample_id LIKE :p",
            {"p": f"{SAMPLE_PREFIX}%"},
        )
        for pkey, persona in world.personas.items():
            principal = load_principal(persona.user_id)
            visible = _new_visible(persona)
            for row in samples:
                allowed = (
                    permit(
                        principal,
                        "sample:read",
                        Resource(scope=lab_scope(row["lab_id"])),
                        Context(conditions={}),
                        policies=[],
                    )
                    is Decision.ALLOW
                )
                assert allowed == (row["sample_id"] in visible), (
                    f"DIVERGENCE {pkey} × {row['sample_id']}: "
                    f"permit={allowed}, sql_visible={row['sample_id'] in visible}"
                )


# ──────────────────────────────────────────────────────────────────────────
# 2d — map hygiene / report sync
# ──────────────────────────────────────────────────────────────────────────


class TestPreflightReport:
    def test_report_in_sync_with_generator(self):
        import sys

        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        try:
            from m2_preflight_report import generate_report, parse_map
        finally:
            sys.path.pop(0)

        rows = parse_map(REPO_ROOT / "docs" / "endpoint_capability_map.md")
        assert len(rows) == 124
        # Every row classifiable — parser guarantees the five classes.
        assert {r.klass for r in rows} <= {
            "require_capability",
            "auth_only",
            "auth_only_by_design",
            "public",
            "catalog_gap",
        }

        expected = generate_report(rows)
        committed = (REPO_ROOT / "docs" / "m2_preflight_report.md").read_text()
        assert committed == expected, (
            "docs/m2_preflight_report.md is stale — run "
            "`uv run python scripts/m2_preflight_report.py` and commit"
        )

    def test_gap_rows_reported_not_yet_fatal(self):
        import sys

        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        try:
            from m2_preflight_report import parse_map
        finally:
            sys.path.pop(0)

        rows = parse_map(REPO_ROOT / "docs" / "endpoint_capability_map.md")
        gaps = [r for r in rows if r.klass == "catalog_gap"]
        assert not gaps, f"unresolved catalog gaps: {[(r.method, r.path) for r in gaps]}"

        # The 29 gaps the ACCESS-GUARD-MAP pass found were resolved in review:
        # 20 took a capability, 9 were marked AUTH-ONLY BY DESIGN (self-scope,
        # stateless utility, public registry — see access_model.md §4.7).
        by_design = [r for r in rows if r.klass == "auth_only_by_design"]
        assert len(by_design) == 7
        # Every by-design row must justify itself in the notes, not just carry
        # the marker — the marker is a decision, and decisions carry reasons.
        for r in by_design:
            reason = r.notes.split("AUTH-ONLY BY DESIGN", 1)[1].strip(" —-")
            assert reason, f"{r.method} {r.path} carries the marker with no reason"
            assert r.capability == "—", "a by-design row cannot also name a capability"

        # PUBLIC sign-off complete: nothing pending intent verification, and the
        # two pipeline callbacks are token-authenticated, not public.
        assert not [r for r in rows if r.verify_intent]
        service_routes = {
            ("POST", "/api/v1/pipelines/events"),
            ("POST", "/api/v1/pipelines/{run_id}/results/{result_type}"),
        }
        for r in rows:
            if (r.method, r.path) in service_routes:
                assert r.klass != "public", f"{r.path} is token-authenticated, not PUBLIC"
                assert r.capability == "pipeline:write_results"

        # Split routes (self path ungated, cross-principal path guarded) keep
        # their capability and stay ROUTE_LOCAL — the guard still gets written.
        split = [r for r in rows if "AUTH-ONLY BY DESIGN" in r.notes and r.capability != "—"]
        assert {(r.method, r.path) for r in split} == {
            ("GET", "/api/v1/tokens/"),
            ("DELETE", "/api/v1/tokens/{token_id}"),
        }
        assert all(r.klass == "auth_only" for r in split)

        # Verbs the resolution added to the §4 catalog must actually be there.
        catalog = (REPO_ROOT / "docs" / "access_model.md").read_text()
        for verb in (
            "pipeline:read",
            "lab:read",
            "org:read",
            "import:read",
            "import:manage",
            "submission:prepare",
            "access:request",
            "token:manage",
        ):
            assert f"`{verb}`" in catalog, f"{verb} used in the map but absent from §4"
