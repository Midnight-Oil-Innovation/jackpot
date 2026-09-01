"""M2-SAMPLE-ACCESS-SYNC — per-sample access grants track the access tables.

Runs against the real container schema rather than a hand-built SQLite one:
a Sample scope needs the whole ``org/lab/project/sample`` path (ADR 0015), so
a fixture that stubbed the tables would be asserting against a scope shape the
deployment never produces.

Every test seeds inside a savepoint that is rolled back, so the shared
container keeps its migrated state.

What these cover that the router tests cannot: the deletion lifecycle's bulk
revoke/restore, isolation from membership grants at the same principal, and
idempotence. The router tests cover the approve path end to end.
"""

import contextlib

import pytest
from sqlalchemy import text

from backend.authz.reseed import (
    DIRECT_SOURCE,
    GRANT_SOURCE,
    SAMPLE_ACCESS_CAPABILITIES,
    sample_scope,
    sync_sample_access_grants,
)
from backend.authz.scope import scope_uri
from backend.database import _get_engine

_SAMPLE_SQL = """
INSERT INTO samples (
    sample_id, lab_id, project_id, owner_id, source_type, organism_name,
    type_of_experiment, library_preparation_method, sequencing_protocol,
    sequencing_platform, sequencing_lab, date_collected, date_sequenced,
    collection_facility, collection_location_country, sharing_level,
    fastq_r1_uri, surveillance_relevant
) VALUES (
    :sid, :lab, :proj, :owner, 'Human',
    'Severe acute respiratory syndrome coronavirus 2',
    'WGS', 'ARTIC', 'https://www.protocols.io/view/artic-v4-1',
    'Illumina', 'Example Sequencing Lab', '2026-01-15', '2026-01-17',
    'Example Hospital', 'United States', 'PRIVATE',
    'gs://sync-test/R1.fastq.gz', FALSE
) RETURNING id
"""


class World:
    def __init__(self, conn):
        self.conn = conn
        self.org = conn.execute(
            text("INSERT INTO organizations (display_name) VALUES ('Sync Org') RETURNING id")
        ).scalar_one()
        self.lab = conn.execute(
            text(
                "INSERT INTO labs (organization_id, display_name) "
                "VALUES (:o, 'Sync Lab') RETURNING id"
            ),
            {"o": self.org},
        ).scalar_one()
        self.project = conn.execute(
            text(
                "INSERT INTO projects (lab_id, display_name) "
                "VALUES (:l, 'Sync Project') RETURNING id"
            ),
            {"l": self.lab},
        ).scalar_one()
        self.owner = self._user("sync-owner@example.org")
        self.alice = self._user("sync-alice@example.org")
        self.bob = self._user("sync-bob@example.org")
        self.sample = conn.execute(
            text(_SAMPLE_SQL),
            {"sid": "SYNC-001", "lab": self.lab, "proj": self.project, "owner": self.owner},
        ).scalar_one()

    def _user(self, email: str) -> int:
        return self.conn.execute(
            text(
                "INSERT INTO users (email, name, organization_id, is_active) "
                "VALUES (:e, :e, :o, TRUE) RETURNING id"
            ),
            {"e": email, "o": self.org},
        ).scalar_one()

    def grant_access(self, user_id: int, *, expires: str | None = "30 days", revoked=False):
        expiry = f"NOW() + INTERVAL '{expires}'" if expires else "NULL"
        self.conn.execute(
            text(
                "INSERT INTO sample_access_grants "
                "(sample_id, requester_id, granted_by_id, access_expires_at, revoked, revoked_at) "
                f"VALUES (:sid, :uid, :uid, {expiry}, :rev, "
                "CASE WHEN :rev THEN NOW() ELSE NULL END)"
            ),
            {"sid": self.sample, "uid": user_id, "rev": revoked},
        )

    def capabilities_of(self, user_id: int, *, source: str = DIRECT_SOURCE) -> set[str]:
        scope = sample_scope(self.conn, self.sample)
        return {
            r[0]
            for r in self.conn.execute(
                text(
                    "SELECT capability FROM authz_capability_grants "
                    "WHERE principal_id = :p AND scope_ref = :s AND source = :src"
                ),
                {"p": str(user_id), "s": scope, "src": source},
            ).fetchall()
        }


@pytest.fixture
def world():
    engine, _ = _get_engine()
    with engine.begin() as conn:
        trans = conn.begin_nested()
        try:
            yield World(conn)
        finally:
            trans.rollback()


def test_active_grant_becomes_capability_grants(world):
    world.grant_access(world.alice)
    issued = sync_sample_access_grants(world.conn, sample_id=world.sample)
    assert issued == len(SAMPLE_ACCESS_CAPABILITIES)
    assert world.capabilities_of(world.alice) == set(SAMPLE_ACCESS_CAPABILITIES)


def test_revoked_grant_conveys_nothing(world):
    world.grant_access(world.alice, revoked=True)
    assert sync_sample_access_grants(world.conn, sample_id=world.sample) == 0
    assert world.capabilities_of(world.alice) == set()


def test_expired_grant_conveys_nothing(world):
    world.grant_access(world.alice, expires="-1 day")
    assert sync_sample_access_grants(world.conn, sample_id=world.sample) == 0
    assert world.capabilities_of(world.alice) == set()


def test_revoking_after_a_sync_removes_the_capability_grants(world):
    """The reconcile direction that fails OPEN if it is missing.

    A grant left behind after revocation lets `permit()` allow a read the
    access table has already withdrawn — the one failure mode in this file
    that is a security problem rather than an inconvenience.
    """
    world.grant_access(world.alice)
    sync_sample_access_grants(world.conn, sample_id=world.sample)
    assert world.capabilities_of(world.alice)

    world.conn.execute(
        text(
            "UPDATE sample_access_grants SET revoked = TRUE, revoked_at = NOW() "
            "WHERE sample_id = :sid"
        ),
        {"sid": world.sample},
    )
    sync_sample_access_grants(world.conn, sample_id=world.sample)
    assert world.capabilities_of(world.alice) == set()


def test_sync_is_idempotent(world):
    world.grant_access(world.alice)
    first = sync_sample_access_grants(world.conn, sample_id=world.sample)
    second = sync_sample_access_grants(world.conn, sample_id=world.sample)
    assert first == second
    assert world.capabilities_of(world.alice) == set(SAMPLE_ACCESS_CAPABILITIES)
    dupes = world.conn.execute(
        text(
            "SELECT COUNT(*) FROM authz_capability_grants WHERE principal_id = :p AND source = :src"
        ),
        {"p": str(world.alice), "src": DIRECT_SOURCE},
    ).scalar_one()
    assert dupes == len(SAMPLE_ACCESS_CAPABILITIES)


def test_requester_filter_leaves_other_principals_alone(world):
    """Narrowing to one requester must not sweep the sample's other holders."""
    world.grant_access(world.alice)
    world.grant_access(world.bob)
    sync_sample_access_grants(world.conn, sample_id=world.sample)
    assert world.capabilities_of(world.bob)

    world.conn.execute(
        text(
            "UPDATE sample_access_grants SET revoked = TRUE, revoked_at = NOW() "
            "WHERE sample_id = :sid AND requester_id = :uid"
        ),
        {"sid": world.sample, "uid": world.alice},
    )
    sync_sample_access_grants(world.conn, sample_id=world.sample, requester_id=world.alice)

    assert world.capabilities_of(world.alice) == set()
    assert world.capabilities_of(world.bob) == set(SAMPLE_ACCESS_CAPABILITIES)


def test_sync_does_not_touch_membership_grants(world):
    """Isolation from the membership plane, which shares the principal.

    `sync_membership_grants` writes at LAB scope; this writes at SAMPLE scope
    and deletes only `source='direct'` rows at that one scope. So a Lab
    Reader's membership grants must survive every change to their per-sample
    access — otherwise revoking one shared sample would silently strip their
    lab access.

    (The two can never collide on the same row anyway: the uniqueness arbiter
    is `(principal_id, capability, scope_ref)` with no `source` column, and the
    scopes differ by construction. This pins the scoping, not the index.)
    """
    lab_scope_ref = scope_uri(org=world.org, lab=world.lab)
    world.conn.execute(
        text(
            "INSERT INTO authz_capability_grants "
            "(principal_id, capability, scope_ref, source) "
            "VALUES (:p, 'sample:read', :s, :src)"
        ),
        {"p": str(world.alice), "s": lab_scope_ref, "src": GRANT_SOURCE},
    )

    world.grant_access(world.alice)
    sync_sample_access_grants(world.conn, sample_id=world.sample)
    assert world.capabilities_of(world.alice) == set(SAMPLE_ACCESS_CAPABILITIES)

    # Now revoke and re-sync — the delete half is where a bad scope predicate
    # would reach across and take the membership grant with it.
    world.conn.execute(
        text(
            "UPDATE sample_access_grants SET revoked = TRUE, revoked_at = NOW() "
            "WHERE sample_id = :sid"
        ),
        {"sid": world.sample},
    )
    sync_sample_access_grants(world.conn, sample_id=world.sample)

    assert world.capabilities_of(world.alice) == set()
    survived = world.conn.execute(
        text(
            "SELECT capability FROM authz_capability_grants "
            "WHERE principal_id = :p AND scope_ref = :s AND source = :src"
        ),
        {"p": str(world.alice), "s": lab_scope_ref, "src": GRANT_SOURCE},
    ).fetchall()
    assert [r[0] for r in survived] == ["sample:read"]


def test_approved_request_without_a_grant_row_still_conveys_access(world):
    """The documented pre-grants-table fallback, preserved by the shared query."""
    world.conn.execute(
        text(
            "INSERT INTO sample_access_requests "
            "(sample_id, requester_id, owner_id, status, justification, "
            "requested_duration_days) "
            "VALUES (:sid, :uid, :owner, 'APPROVED', 'legacy row', 30)"
        ),
        {"sid": world.sample, "uid": world.alice, "owner": world.owner},
    )
    sync_sample_access_grants(world.conn, sample_id=world.sample)
    assert world.capabilities_of(world.alice) == set(SAMPLE_ACCESS_CAPABILITIES)


def test_missing_sample_is_not_an_error(world):
    """The deletion lifecycle syncs samples it is in the middle of removing."""
    with contextlib.suppress(Exception):
        assert sync_sample_access_grants(world.conn, sample_id=999_999_999) == 0
    assert sync_sample_access_grants(world.conn, sample_id=999_999_999) == 0


def test_none_connection_opens_its_own_transaction():
    """``conn=None`` is a supported call shape, not an AttributeError.

    ``approve_deletion`` and the rest of the deletion lifecycle accept a None
    connection — ``execute_write`` documents it as "an auto-committed internal
    transaction" — so a sync wired into those paths has to accept it too.
    Wiring this function in without that broke
    ``test_approve_deletion_enqueues_tombstone_events``.

    Uses a sample id that cannot exist so the call commits nothing to the
    shared container: the branch under test is the connection handling, and
    the early return keeps this test from leaking rows past its own scope.
    """
    assert sync_sample_access_grants(None, sample_id=999_999_999) == 0
