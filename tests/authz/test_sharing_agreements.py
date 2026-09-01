"""M4-A — sharing agreements become peer grants (access_model.md §7.3).

Against the real container schema, because the tables are net-new in this
revision and the point of most of these assertions is that the migration
actually created them with the constraints claimed.

Everything here is dark in production at M4-A: no route loads a peer principal
yet. What is being pinned is the translation — agreement in, grant out — so
that M4-B's wiring has something already proven underneath it.
"""

import uuid

import pytest
from sqlalchemy import text

from backend.authz import Context, Decision, Resource, permit
from backend.authz.engine import PrincipalKind
from backend.authz.principal import load_peer_principal
from backend.authz.reseed import AGREEMENT_SOURCE, GRANT_SOURCE, sync_agreement_grants
from backend.authz.scope import scope_uri
from backend.database import _get_engine


class World:
    def __init__(self, conn):
        self.conn = conn
        self.org = conn.execute(
            text("INSERT INTO organizations (display_name) VALUES ('Agr Org') RETURNING id")
        ).scalar_one()
        self.lab = conn.execute(
            text(
                "INSERT INTO labs (organization_id, display_name) "
                "VALUES (:o, 'Agr Lab') RETURNING id"
            ),
            {"o": self.org},
        ).scalar_one()
        self.peer = self._instance("peer-a")
        self.other_peer = self._instance("peer-b")

    def _instance(self, name: str) -> str:
        return str(
            self.conn.execute(
                text(
                    "INSERT INTO federated_instances "
                    "(name, base_url, role, federation_enabled, api_key_secret_name) "
                    "VALUES (:n, 'https://example.invalid', 'spoke', TRUE, :s) RETURNING id"
                ),
                {"n": f"{name}-{uuid.uuid4().hex[:8]}", "s": f"secret-{uuid.uuid4().hex[:8]}"},
            ).scalar_one()
        )

    def agreement(self, peer: str, *, direction="OUTBOUND", active=True) -> str:
        return str(
            self.conn.execute(
                text(
                    "INSERT INTO sharing_agreements "
                    "(peer_instance_id, direction, rationale, active) "
                    "VALUES (:p, :d, 'test agreement', :a) RETURNING id"
                ),
                {"p": peer, "d": direction, "a": active},
            ).scalar_one()
        )

    def grant(self, agreement: str, capability: str, scope: str, *, conditions="{}"):
        self.conn.execute(
            text(
                "INSERT INTO sharing_agreement_grants "
                "(agreement_id, capability, scope_ref, conditions) "
                "VALUES (:a, :c, :s, CAST(:cond AS JSONB))"
            ),
            {"a": agreement, "c": capability, "s": scope, "cond": conditions},
        )

    def lab_scope(self) -> str:
        return scope_uri(org=self.org, lab=self.lab)


@pytest.fixture
def world():
    engine, _ = _get_engine()
    with engine.begin() as conn:
        trans = conn.begin_nested()
        try:
            yield World(conn)
        finally:
            trans.rollback()


def test_a_peer_with_no_agreement_holds_nothing(world):
    """§7.3 default-deny: peering authenticates, it does not authorize."""
    assert sync_agreement_grants(world.conn, peer_instance_id=world.peer) == 0
    principal = load_peer_principal(world.peer, conn=world.conn)
    assert principal.grants == []
    assert principal.kind is PrincipalKind.PEER_INSTANCE
    assert (
        permit(
            principal,
            "sample:read",
            Resource(scope=world.lab_scope()),
            Context(conditions={}),
            policies=[],
        )
        is Decision.DENY
    )


def test_an_agreement_grant_reaches_permit(world):
    """The whole point: 'Peer X may read Lab 3' is a sample:read at lab scope."""
    a = world.agreement(world.peer)
    world.grant(a, "sample:read", world.lab_scope())
    assert sync_agreement_grants(world.conn, peer_instance_id=world.peer) == 1

    principal = load_peer_principal(world.peer, conn=world.conn)
    assert (
        permit(
            principal,
            "sample:read",
            Resource(scope=world.lab_scope()),
            Context(conditions={}),
            policies=[],
        )
        is Decision.ALLOW
    )


def test_the_grant_is_scoped_not_instance_wide(world):
    """A lab-scoped agreement must not reach a sibling lab."""
    other_lab = world.conn.execute(
        text(
            "INSERT INTO labs (organization_id, display_name) VALUES (:o, 'Agr Lab 2') RETURNING id"
        ),
        {"o": world.org},
    ).scalar_one()
    a = world.agreement(world.peer)
    world.grant(a, "sample:read", world.lab_scope())
    sync_agreement_grants(world.conn, peer_instance_id=world.peer)

    principal = load_peer_principal(world.peer, conn=world.conn)
    assert (
        permit(
            principal,
            "sample:read",
            Resource(scope=scope_uri(org=world.org, lab=other_lab)),
            Context(conditions={}),
            policies=[],
        )
        is Decision.DENY
    )


def test_conditions_survive_the_projection(world):
    """§7.3's finer slicing — organism == 'Salmonella' — is a grant condition.

    It has to arrive in the grant row intact or the agreement silently widens:
    a condition that does not survive the sync is a grant with no filter.
    """
    a = world.agreement(world.peer)
    world.grant(a, "sample:read", world.lab_scope(), conditions='{"organism": "Salmonella"}')
    sync_agreement_grants(world.conn, peer_instance_id=world.peer)

    principal = load_peer_principal(world.peer, conn=world.conn)
    assert principal.grants[0].conditions == {"organism": "Salmonella"}

    resource = Resource(scope=world.lab_scope())
    assert (
        permit(
            principal,
            "sample:read",
            resource,
            Context(conditions={"organism": "Salmonella"}),
            policies=[],
        )
        is Decision.ALLOW
    )
    assert (
        permit(
            principal,
            "sample:read",
            resource,
            Context(conditions={"organism": "Listeria"}),
            policies=[],
        )
        is Decision.DENY
    )


def test_deactivating_an_agreement_withdraws_exactly_its_grants(world):
    """Two agreements, one deactivated. The other must survive untouched.

    This is why the sync reconciles the peer rather than one agreement: the
    question the decision path asks is "what does this peer hold", and no
    single agreement can answer it.
    """
    keep = world.agreement(world.peer)
    drop = world.agreement(world.peer)
    world.grant(keep, "sample:read", world.lab_scope())
    world.grant(drop, "sample:read_detail", world.lab_scope())
    assert sync_agreement_grants(world.conn, peer_instance_id=world.peer) == 2

    world.conn.execute(
        text("UPDATE sharing_agreements SET active = FALSE WHERE id = :id"), {"id": drop}
    )
    assert sync_agreement_grants(world.conn, peer_instance_id=world.peer) == 1

    held = {g.capability for g in load_peer_principal(world.peer, conn=world.conn).grants}
    assert held == {"sample:read"}


def test_one_peers_sync_leaves_another_peer_alone(world):
    a1 = world.agreement(world.peer)
    world.grant(a1, "sample:read", world.lab_scope())
    a2 = world.agreement(world.other_peer)
    world.grant(a2, "sample:read", world.lab_scope())
    sync_agreement_grants(world.conn, peer_instance_id=world.peer)
    sync_agreement_grants(world.conn, peer_instance_id=world.other_peer)

    world.conn.execute(
        text("UPDATE sharing_agreements SET active = FALSE WHERE id = :id"), {"id": a1}
    )
    sync_agreement_grants(world.conn, peer_instance_id=world.peer)

    assert load_peer_principal(world.peer, conn=world.conn).grants == []
    assert len(load_peer_principal(world.other_peer, conn=world.conn).grants) == 1


def test_sync_does_not_touch_reseed_sourced_grants(world):
    """Source scoping, the same guard the other two syncs carry.

    A peer id and a user id are different namespaces today, but the delete is
    predicated on principal_id AND source, and only the source half is what
    stops this from being a landmine if they ever collide.
    """
    world.conn.execute(
        text(
            "INSERT INTO authz_capability_grants "
            "(principal_id, capability, scope_ref, source) "
            "VALUES (:p, 'sample:read_detail', :s, :src)"
        ),
        {"p": str(world.peer), "s": world.lab_scope(), "src": GRANT_SOURCE},
    )
    a = world.agreement(world.peer)
    world.grant(a, "sample:read", world.lab_scope())
    sync_agreement_grants(world.conn, peer_instance_id=world.peer)

    by_source = dict(
        world.conn.execute(
            text(
                "SELECT source, COUNT(*) FROM authz_capability_grants "
                "WHERE principal_id = :p GROUP BY source"
            ),
            {"p": str(world.peer)},
        ).fetchall()
    )
    assert by_source == {GRANT_SOURCE: 1, AGREEMENT_SOURCE: 1}


def test_sync_is_idempotent(world):
    a = world.agreement(world.peer)
    world.grant(a, "sample:read", world.lab_scope())
    first = sync_agreement_grants(world.conn, peer_instance_id=world.peer)
    second = sync_agreement_grants(world.conn, peer_instance_id=world.peer)
    assert first == second == 1
    assert len(load_peer_principal(world.peer, conn=world.conn).grants) == 1


def test_duplicate_grant_in_one_agreement_is_rejected(world):
    """The unique index. Two identical grants would disagree with the count
    authz_capability_grants ends up holding, since its own arbiter dedupes."""
    from sqlalchemy.exc import IntegrityError

    a = world.agreement(world.peer)
    world.grant(a, "sample:read", world.lab_scope())
    sp = world.conn.begin_nested()
    with pytest.raises(IntegrityError):
        world.grant(a, "sample:read", world.lab_scope())
    sp.rollback()


def test_agreement_dies_with_its_peer(world):
    """ON DELETE CASCADE. A dangling agreement would grant to a principal that
    can no longer authenticate — invisible, and wrong if the id is reused."""
    a = world.agreement(world.peer)
    world.grant(a, "sample:read", world.lab_scope())
    world.conn.execute(text("DELETE FROM federated_instances WHERE id = :id"), {"id": world.peer})
    remaining = world.conn.execute(
        text("SELECT COUNT(*) FROM sharing_agreements WHERE peer_instance_id = :p"),
        {"p": world.peer},
    ).scalar_one()
    assert remaining == 0
    orphan_grants = world.conn.execute(
        text("SELECT COUNT(*) FROM sharing_agreement_grants WHERE agreement_id = :a"),
        {"a": a},
    ).scalar_one()
    assert orphan_grants == 0


def test_direction_is_constrained(world):
    from sqlalchemy.exc import IntegrityError

    sp = world.conn.begin_nested()
    with pytest.raises(IntegrityError):
        world.agreement(world.peer, direction="SIDEWAYS")
    sp.rollback()
