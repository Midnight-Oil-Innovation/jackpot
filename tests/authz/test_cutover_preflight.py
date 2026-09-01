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
    INSTANCE_SCOPE,
    MATRIX_CAPABILITIES,
    SAMPLE_PREFIX,
    UNIQUE_INDEX_DDL,
    classify_legacy_only_visibility,
    lab_scope,
    legacy_visibility_sql_clause,
    load_principal,
    run_matrix,
    seed_world,
    teardown_world,
    user_dict,
)
from backend.auth.guards import require_capability
from backend.authz import Context, Decision, Resource, permit, sample_resource_scope
from backend.authz.engine import _scope_contains
from backend.authz.policy import LADDER_POLICIES
from backend.authz.principal import SAMPLE_ATTRIBUTE_COLUMNS, sample_resource
from backend.authz.reseed import (
    PRESET_GRANTS,
    SAMPLE_ACCESS_CAPABILITIES,
    ReseedPreflightError,
    preflight_counts,
    reseed,
)
from backend.authz.scope import scope_sql, scope_uri
from backend.authz.visibility import visibility_sql_clause as new_visibility_sql_clause
from backend.database import _get_engine, execute_query

# The seeded world deliberately contains every condition the M2-PRE-4
# pre-flight guard aborts on — P9 (unmapped group), P11 (director flag vs
# Collaborator group), P12 (project-only membership) exist to MEASURE those
# divergences, so the harness opts past the guard rather than being blocked by
# the thing it is here to observe. TestReseedPreflightGuard covers the refusal
# path on the same world.
_FORCE_REASON = True

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
        reseed(conn, force=_FORCE_REASON)
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
    # A Bioinformatics User IS a Lab Member RW: §8.2 puts pipeline:run in
    # that preset, so there is no extra grant (corrected in M2-B3).
    "P7": {"lab_a": len(PRESET_GRANTS["lab_member_rw"])},
    "P8": {"lab_a": len(PRESET_GRANTS["lab_lead"]), "lab_b": len(PRESET_GRANTS["lab_member_ro"])},
    "P9": {},
    # P10 reaches two samples by per-sample access — one through
    # sample_access_grants, one through an APPROVED request with no grant row
    # (the documented fallback) — and M2-B2-PRE-C reseeds both as Sample-scoped
    # grants carrying sample:read + sample:read_detail.
    "P10": {"sample": 2 * len(SAMPLE_ACCESS_CAPABILITIES)},
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
                elif r["scope_ref"] == lab_scope(world.org_id, world.lab_a):
                    kind = "lab_a"
                elif r["scope_ref"].count("/sample/") == 1:
                    kind = "sample"
                elif r["scope_ref"] == lab_scope(world.org_id, world.lab_b):
                    kind = "lab_b"
                else:
                    pytest.fail(f"{pkey}: unexpected scope_ref {r['scope_ref']!r}")
                by_scope[kind] = by_scope.get(kind, 0) + 1
            assert by_scope == expected, f"{pkey}: {by_scope} != {expected}"
            for r in rows:
                # Provenance distinguishes the two kinds: role-derived grants
                # carry 'reseed', per-sample access carries 'direct' (§5), so
                # a later revoke can target the second without disturbing the
                # first.
                expected_source = "direct" if "/sample/" in r["scope_ref"] else "reseed"
                assert r["source"] == expected_source, r
                # JSONB round-trip default — a shape SQLite never exercised.
                assert r["conditions"] in (None, {}), r
                assert r["id"] is not None

    def test_pipeline_run_reaches_every_read_write_member(self, world):
        """M2-B3 corrected the preset. §8.2's Lab Member (read-write) block
        lists pipeline:run — "can run pipelines but not approve submissions or
        access requests" — so both the Bioinformatics User (P7) and the plain
        Collaborator (P5) hold it. This test previously asserted P5 did NOT,
        which is what let the exclusion survive.
        """
        assert "pipeline:run" in {r["capability"] for r in _grants(world, "P7")}
        assert "pipeline:run" in {r["capability"] for r in _grants(world, "P5")}
        # Read-only members still cannot launch.
        assert "pipeline:run" not in {r["capability"] for r in _grants(world, "P6")}

    def test_reseed_idempotent_on_pg_with_unique_index(self, world):
        engine, _ = _get_engine()
        before = execute_query("SELECT COUNT(*) AS c FROM authz_capability_grants", {})[0]["c"]
        with engine.begin() as conn:
            reseed(conn, force=_FORCE_REASON)
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
                reseed(conn, force=_FORCE_REASON)
                after = conn.execute(
                    text("SELECT COUNT(*) FROM authz_capability_grants")
                ).scalar_one()
                assert after > before, (
                    "expected duplicate grants once the unique index is dropped. "
                    "This test drops it deliberately, so a failure means reseed "
                    "stopped depending on it for dedup — not that the chain "
                    "gained the index (b2f47c1a9e30 creates it). The point is "
                    "that create-index-before-reseed is load-bearing ordering."
                )
            finally:
                trans.rollback()

    def test_unmapped_group_skipped_with_warning(self, world, caplog):
        engine, _ = _get_engine()
        with (
            caplog.at_level(logging.WARNING, logger="backend.authz.reseed"),
            engine.begin() as conn,
        ):
            reseed(conn, force=_FORCE_REASON)
        assert any("unmapped" in rec.message for rec in caplog.records)
        assert _grants(world, "P9") == []


# ──────────────────────────────────────────────────────────────────────────
# 2b — guard equivalence matrix
# ──────────────────────────────────────────────────────────────────────────


class TestReseedPreflightGuard:
    """M2-PRE-4 on PostgreSQL, against the world that really has the rows.

    The SQLite suite covers each condition in isolation; this asserts the
    guard fires on the seeded world — the closest thing available to a real
    operator database, since no deployment holds membership rows yet
    (instances/ contains only ci, and the baseline migration seeds one admin
    plus one Lab Director).
    """

    def test_guard_refuses_the_seeded_world(self, world):
        engine, _ = _get_engine()
        with engine.begin() as conn:
            trans = conn.begin_nested()
            try:
                with pytest.raises(ReseedPreflightError) as exc:
                    reseed(conn)
            finally:
                trans.rollback()

        # P11 director-flag mismatch, P9 unmapped group, P12 project-only.
        assert exc.value.counts["director_flag_group_mismatch"] >= 1
        assert exc.value.counts["unmapped_permission_group"] >= 1
        assert exc.value.counts["project_only_membership"] >= 1

    def test_guard_counts_match_the_divergence_classes(self, world):
        """The guard must find exactly the personas the matrix diverges on.

        If a persona diverges but the guard cannot see it, the migration would
        run silently on data the report says is broken.
        """
        engine, _ = _get_engine()
        with engine.begin() as conn:
            counts = preflight_counts(conn)
        assert counts["director_flag_group_mismatch"] == 1  # P11
        assert counts["unmapped_permission_group"] == 1  # P9
        assert counts["project_only_membership"] == 1  # P12


class TestRealGuardIsPermitBacked:
    """M2-B1 — the shipped guard and the engine must not diverge.

    The matrix below compares the new model against a frozen copy of the old
    ladder, which says what CHANGED. This says the change actually reached
    production: require_capability's verdict equals permit()'s on the same
    principal, capability and scope, for every cell. Without it the matrix
    could stay green while the guard quietly ran something else.
    """

    def test_guard_matches_permit_on_every_cell(self, world):
        from authz.preflight import real_guard

        principals = {k: load_principal(p.user_id) for k, p in world.personas.items()}
        lab_ids = {"A": world.lab_a, "B": world.lab_b, None: None}
        mismatches = []
        for pkey, persona in world.personas.items():
            for cap in MATRIX_CAPABILITIES:
                for lab_key, lab_id in lab_ids.items():
                    scope = (
                        lab_scope(world.org_id, lab_id) if lab_id is not None else INSTANCE_SCOPE
                    )
                    engine = (
                        permit(
                            principals[pkey],
                            cap,
                            Resource(scope=scope),
                            Context(conditions={}),
                            policies=[],
                        )
                        is Decision.ALLOW
                    )
                    if real_guard(persona, cap, lab_id) != engine:
                        mismatches.append((pkey, cap, lab_key, engine))
        assert not mismatches, f"guard/engine divergence: {mismatches}"

    def test_unknown_lab_is_indistinguishable_from_a_denied_lab(self, world):
        """Existence must not be observable through the status code.

        Answering 404 for an unknown lab and 403 for a known-but-denied one
        lets any authenticated caller enumerate lab ids. Under org isolation
        that is the secret itself — §3.2: another org must not learn of a
        lab's data, users, "or existence".
        """
        from fastapi import HTTPException

        reader = user_dict(world.personas["P6"])  # holds no org:manage anywhere

        with pytest.raises(HTTPException) as unknown:
            require_capability("org:manage")(reader, lab_id=987654321)
        with pytest.raises(HTTPException) as denied:
            require_capability("org:manage")(reader, lab_id=world.lab_a)

        assert unknown.value.status_code == denied.value.status_code == 403
        assert unknown.value.detail == denied.value.detail

    def test_instance_wide_caller_passes_through_to_the_route_on_unknown_lab(self, world):
        """Enumeration is only a leak for someone who could not already do it.

        A principal holding the capability instance-wide can list every lab
        anyway, so withholding a 404 from them protects nothing and turns an
        ordinary bad request into a confusing permission error. The guard lets
        them through and the route answers 404.
        """
        admin = user_dict(world.personas["P1"])
        assert require_capability("org:manage")(admin, lab_id=987654321) is admin

    def test_platform_admin_has_no_bypass_branch(self, world):
        """The admin passes on grants, not on is_platform_admin.

        Stripping the flag must change nothing: if it does, a bypass survived.
        """
        from authz.preflight import real_guard

        admin = world.personas["P1"]
        assert real_guard(admin, "org:manage", None)

        flagless = dict(user_dict(admin))
        flagless["is_platform_admin"] = False
        require_capability("org:manage")(flagless)  # grants alone must carry it


class TestSampleScopeResolution:
    """M2-B2-PRE-B on PostgreSQL — the lineage query the unit tests stub out."""

    def test_scope_matches_the_row_lineage(self, world):
        sample_pk = world.sample_ids["A-PRIV"]
        row = execute_query(
            "SELECT s.lab_id, s.project_id, l.organization_id "
            "FROM samples s JOIN labs l ON l.id = s.lab_id WHERE s.id = :sid",
            {"sid": sample_pk},
        )[0]
        assert sample_resource_scope(sample_pk) == scope_uri(
            org=row["organization_id"],
            lab=row["lab_id"],
            project=row["project_id"],
            sample=sample_pk,
        )

    def test_lab_grant_contains_the_sample_scope(self, world):
        """The lab-member path, end to end against real rows."""
        sample_pk = world.sample_ids["A-PRIV"]
        assert _scope_contains(
            lab_scope(world.org_id, world.lab_a), sample_resource_scope(sample_pk)
        )

    def test_unknown_sample_raises_rather_than_inventing_a_scope(self):
        """An invented scope would be contained by the instance grant and
        quietly authorize an admin against a sample that does not exist."""
        with pytest.raises(ValueError, match="unknown sample"):
            sample_resource_scope(987654321)


class TestGuardEquivalenceMatrix:
    def test_admin_reaches_lab_scope_structurally(self, world):
        """ADR 0015's payoff, measured on PostgreSQL.

        Before the canonical path scheme, ``instance://self`` did not contain
        ``lab://N``, so every lab-scoped admin cell denied under the new model
        while the legacy platform-admin bypass allowed it — the
        ``admin-bypass-vs-scoped-grants`` divergence that blocked the cutover.
        The admin's reseeded grants are unchanged; only their scope shape is.
        In-preset capabilities must now reach lab scope by plain containment,
        with no admin bypass and no wildcard policy.
        """
        cells, _, _ = run_matrix(world)
        admin_preset = set(PRESET_GRANTS["instance_administrator"])
        lab_cells = [
            c
            for c in cells
            if c.persona == "P1" and c.lab_key is not None and c.capability in admin_preset
        ]
        assert lab_cells, "matrix no longer covers admin × lab scope"
        denied = [c for c in lab_cells if not c.new]
        assert not denied, (
            "instance-scoped admin grants must contain lab scopes: "
            f"{[(c.capability, c.scope) for c in denied]}"
        )

    def test_admin_divergence_is_now_only_the_preset_narrowing(self, world):
        """What survives of admin-bypass-vs-scoped-grants after ADR 0015.

        The class had two halves: lab-scoped cells denying because the scopes
        shared no root, and instance-scoped cells denying because the §8.2
        preset enumerates capabilities rather than granting everything. The
        first half is gone by construction; the second is the intended
        narrowing and still fires. Pinned so a regression in either direction
        is visible.
        """
        cells, _, _ = run_matrix(world)
        admin_preset = set(PRESET_GRANTS["instance_administrator"])
        diverging = [c for c in cells if c.persona in {"P1", "P3"} and c.legacy and not c.new]
        assert diverging, "expected the preset-narrowing half to still fire"
        for c in diverging:
            assert c.capability not in admin_preset, (
                f"{c.capability} is in the admin preset but still denies at "
                f"{c.scope} — containment regression"
            )

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


_SCOPE_EXPR = scope_sql(samples="s", labs="l")


def _new_visible(persona, *, grants_only: bool = False) -> set[str]:
    """Rows the new model lists, via the production shape.

    No synthesized scope column: the scope is derived from the
    ``samples JOIN labs`` the real list query performs (ADR 0015), which is
    also what puts ``organization_id`` in reach for the org segment.

    M2-B7: the policy set and the attribute columns are the production ones.
    Passing ``policies=[]`` — as this harness did while the fragment was dark
    — measures grants alone, which is a strict subset of what the deployed
    list shows and would have made the equivalence proof describe something
    nobody runs. ``grants_only=True`` keeps the old reading for the one test
    that wants to see the two halves separately.
    """
    principal = load_principal(persona.user_id)
    fragment, params = new_visibility_sql_clause(
        principal,
        "sample:read",
        _SCOPE_EXPR,
        policies=[] if grants_only else LADDER_POLICIES,
        attribute_columns=SAMPLE_ATTRIBUTE_COLUMNS,
    )
    rows = execute_query(
        "SELECT s.sample_id FROM samples s JOIN labs l ON l.id = s.lab_id "
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

        samples = execute_query(
            "SELECT id, sample_id, lab_id FROM samples WHERE sample_id LIKE :p",
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
                        # The row's own scope AND its attributes. Comparing at
                        # lab scope would hide exactly the sample-scoped grants
                        # PRE-C issues — the approximation PRE-B exists to
                        # remove — and omitting the attributes would ask a
                        # different question than the fragment answers, since
                        # half the fragment's terms are attribute predicates.
                        sample_resource(row["id"]),
                        Context(conditions={}),
                        policies=LADDER_POLICIES,
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
        # most took a capability, the rest were marked AUTH-ONLY BY DESIGN
        # (self-scope, stateless utility, public registry — access_model.md
        # §4.7).
        #
        # 7 -> 10 on 2026-09-01 (M2-B3-PRE): the three BYOP catalog reads
        # joined them. The map had given them pipeline:read at Lab scope while
        # byop.py said reads are "INTENTIONALLY unscoped per design §9
        # (catalog browse)" — a contradiction between two documents, resolved
        # toward the router. Browsing pipeline definitions is the same shape as
        # the sequencing-lab registry this list already admits: every
        # bioinformatician needs it and a pipeline definition is not tenant
        # data. BYOP *mutations* stay tenancy-guarded.
        by_design = [r for r in rows if r.klass == "auth_only_by_design"]
        assert len(by_design) == 10
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
