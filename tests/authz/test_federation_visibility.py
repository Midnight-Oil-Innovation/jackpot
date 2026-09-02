"""M4-B — a peer sees exactly what its sharing agreements grant.

Two halves, both of which were missing rather than merely unwired:

* **L1 inbound query.** ``client._query_one`` was calling
  ``GET /api/v1/samples/`` on the partner, which authenticates a JWT cookie
  and nothing else — a real federated query would have 401'd. No test caught
  it because every federation-key test hit ``/api/v1/federation/*`` and the
  client tests mocked the partner. The route now exists, beside the two that
  already authenticate peers.
* **L2 push decision.** ``is_qualifying_sample`` applied three operational
  gates and asked no authorization question at all. ``may_push_sample`` adds
  the ``permit()`` half, which is what a DENY on ``federation:push`` can
  attach to.
"""

import uuid

import pytest
from sqlalchemy import text

from backend.authz import Context, Resource
from backend.authz.principal import load_peer_principal
from backend.authz.reseed import sync_agreement_grants
from backend.authz.scope import scope_uri
from backend.credentials import _reset_backend, _set_backend
from backend.credentials.test_helpers import InMemoryBackend
from backend.database import _get_engine
from backend.federation.push import FederationPushJob

PEER_KEY = "m4b-peer-secret"
SECRET_NAME = "fed/m4b/key"


@pytest.fixture
def fed_credentials():
    backend = InMemoryBackend()
    _set_backend(backend)
    backend.set(SECRET_NAME, PEER_KEY)
    yield backend
    _reset_backend()


class World:
    def __init__(self, conn):
        self.conn = conn
        self.org = conn.execute(
            text("INSERT INTO organizations (display_name) VALUES ('Fed Org') RETURNING id")
        ).scalar_one()
        self.lab = conn.execute(
            text(
                "INSERT INTO labs (organization_id, display_name) "
                "VALUES (:o, 'Fed Lab') RETURNING id"
            ),
            {"o": self.org},
        ).scalar_one()
        self.project = conn.execute(
            text(
                "INSERT INTO projects (lab_id, display_name) "
                "VALUES (:l, 'Fed Project') RETURNING id"
            ),
            {"l": self.lab},
        ).scalar_one()
        self.owner = conn.execute(
            text(
                "INSERT INTO users (email, name, organization_id, is_active) "
                "VALUES (:e, :e, :o, TRUE) RETURNING id"
            ),
            {"e": f"fed-owner-{uuid.uuid4().hex[:6]}@example.org", "o": self.org},
        ).scalar_one()
        self.peer = str(
            conn.execute(
                text(
                    "INSERT INTO federated_instances "
                    "(name, base_url, role, federation_enabled, api_key_secret_name) "
                    "VALUES (:n, 'https://peer.invalid', 'peer', TRUE, :s) RETURNING id"
                ),
                {"n": f"m4b-peer-{uuid.uuid4().hex[:6]}", "s": SECRET_NAME},
            ).scalar_one()
        )

    def sample(self, key: str, **overrides) -> int:
        fields = {
            "sharing_level": "PRIVATE",
            "quality_status": "SUBMITTABLE",
            "deletion_status": "ACTIVE",
            "surveillance_relevant": True,
        }
        fields.update(overrides)
        return self.conn.execute(
            text(
                """
                INSERT INTO samples (
                    sample_id, lab_id, project_id, owner_id, source_type, organism_name,
                    type_of_experiment, library_preparation_method, sequencing_protocol,
                    sequencing_platform, sequencing_lab, date_collected, date_sequenced,
                    collection_facility, collection_location_country, sharing_level,
                    fastq_r1_uri, surveillance_relevant, quality_status, deletion_status,
                    deletion_requested_at
                ) VALUES (
                    :sid, :lab, :proj, :owner, 'Human', 'Salmonella enterica',
                    'WGS', 'ARTIC', 'https://www.protocols.io/view/artic-v4-1',
                    'Illumina', 'Example Sequencing Lab', '2026-01-15', '2026-01-17',
                    'Example Hospital', 'United States', :share,
                    'gs://fed/R1.fastq.gz', :surv, :qual, :del,
                    -- samples_deletion_active_requested_chk: the timestamp and
                    -- the status must agree, so a non-ACTIVE fixture row has to
                    -- carry one or the row is not a state the system can reach.
                    CASE WHEN :del = 'ACTIVE' THEN NULL ELSE NOW() END
                ) RETURNING id
                """
            ),
            {
                "sid": key,
                "lab": self.lab,
                "proj": self.project,
                "owner": self.owner,
                "share": fields["sharing_level"],
                "surv": fields["surveillance_relevant"],
                "qual": fields["quality_status"],
                "del": fields["deletion_status"],
            },
        ).scalar_one()

    def agree(self, capability: str, scope: str) -> None:
        a = self.conn.execute(
            text(
                "INSERT INTO sharing_agreements (peer_instance_id, direction, rationale) "
                "VALUES (:p, 'OUTBOUND', 'test') RETURNING id"
            ),
            {"p": self.peer},
        ).scalar_one()
        self.conn.execute(
            text(
                "INSERT INTO sharing_agreement_grants (agreement_id, capability, scope_ref) "
                "VALUES (:a, :c, :s)"
            ),
            {"a": a, "c": capability, "s": scope},
        )
        sync_agreement_grants(self.conn, peer_instance_id=self.peer)

    def lab_scope(self) -> str:
        return scope_uri(org=self.org, lab=self.lab)

    def sample_scope(self, sample_id: int) -> str:
        return scope_uri(org=self.org, lab=self.lab, project=self.project, sample=sample_id)


@pytest.fixture
def world():
    engine, _ = _get_engine()
    with engine.begin() as conn:
        trans = conn.begin_nested()
        try:
            yield World(conn)
        finally:
            trans.rollback()


# ── L1: what the peer principal can see ──────────────────────────────────


def _visible(world, principal) -> set[str]:
    """The inbound route's filtering, exercised through the same compiler."""
    from backend.authz.visibility import sample_list_clause

    clause, params = sample_list_clause(principal)
    rows = world.conn.execute(
        text(
            "SELECT s.sample_id FROM samples s JOIN labs l ON l.id = s.lab_id "  # noqa: S608
            f"WHERE {clause} AND s.sample_id LIKE 'M4B-%'"
        ),
        params,
    ).fetchall()
    return {r[0] for r in rows}


def test_a_peer_without_an_agreement_sees_nothing(world):
    """§7.3 default-deny. A PRIVATE row is invisible without a grant."""
    world.sample("M4B-PRIV")
    assert _visible(world, load_peer_principal(world.peer, conn=world.conn)) == set()


def test_an_agreement_makes_the_lab_visible(world):
    world.sample("M4B-PRIV")
    world.agree("sample:read", world.lab_scope())
    assert _visible(world, load_peer_principal(world.peer, conn=world.conn)) == {"M4B-PRIV"}


def test_the_agreement_does_not_reach_a_sibling_lab(world):
    """The whole point of per-peer differential access."""
    other_lab = world.conn.execute(
        text(
            "INSERT INTO labs (organization_id, display_name) "
            "VALUES (:o, 'Other Fed Lab') RETURNING id"
        ),
        {"o": world.org},
    ).scalar_one()
    other_project = world.conn.execute(
        text("INSERT INTO projects (lab_id, display_name) VALUES (:l, 'P2') RETURNING id"),
        {"l": other_lab},
    ).scalar_one()
    world.conn.execute(
        text("UPDATE samples SET lab_id = :l, project_id = :p WHERE sample_id = :s"),
        {"l": other_lab, "p": other_project, "s": world.sample("M4B-OTHER") and "M4B-OTHER"},
    )
    world.sample("M4B-MINE")
    world.agree("sample:read", world.lab_scope())

    assert _visible(world, load_peer_principal(world.peer, conn=world.conn)) == {"M4B-MINE"}


def test_a_public_row_is_visible_without_an_agreement(world):
    """The PUBLIC ALLOW policy is not a peer concession — it is the same rung
    a local stranger gets, and it must keep working for a peer principal."""
    world.sample("M4B-PUB", sharing_level="PUBLIC")
    assert _visible(world, load_peer_principal(world.peer, conn=world.conn)) == {"M4B-PUB"}


# ── L2: the push decision ────────────────────────────────────────────────


def _may_push(world, principal, sample_row_id: int, **overrides) -> bool:
    fields = {
        "surveillance_relevant": True,
        "sharing_level": "PUBLIC",
        "quality_status": "SUBMITTABLE",
        "min_sharing_level_for_federation": "DISCOVERABLE",
    }
    fields.update(overrides)
    return FederationPushJob.may_push_sample(
        principal,
        Resource(scope=world.sample_scope(sample_row_id), attributes={"deletion_status": "ACTIVE"}),
        context=Context(conditions={}),
        **fields,
    )


def test_push_denied_without_an_agreement(world):
    """No federation:push grant, no push — regardless of the gates."""
    sid = world.sample("M4B-PUSH")
    assert _may_push(world, load_peer_principal(world.peer, conn=world.conn), sid) is False


def test_push_allowed_with_an_agreement(world):
    sid = world.sample("M4B-PUSH")
    world.agree("federation:push", world.lab_scope())
    assert _may_push(world, load_peer_principal(world.peer, conn=world.conn), sid) is True


def test_the_gates_still_apply_on_top_of_the_grant(world):
    """Authorization is necessary, not sufficient. A granted peer still
    cannot pull a PRELIMINARY row across the boundary."""
    sid = world.sample("M4B-PUSH")
    world.agree("federation:push", world.lab_scope())
    principal = load_peer_principal(world.peer, conn=world.conn)
    assert _may_push(world, principal, sid, quality_status="PRELIMINARY") is False
    assert _may_push(world, principal, sid, surveillance_relevant=False) is False


def test_is_qualifying_sample_is_unchanged(world):
    """The gates kept their own function and their own meaning.

    may_push_sample composes; it did not absorb. A caller that only wants the
    operational floor — and there is one, the sender-side check in the inbound
    push route — still gets it without a principal.
    """
    assert FederationPushJob.is_qualifying_sample(
        surveillance_relevant=True,
        sharing_level="PUBLIC",
        quality_status="SUBMITTABLE",
        min_sharing_level_for_federation="DISCOVERABLE",
    )


# ── §6.2-3 through the real decision function ────────────────────────────


def test_the_tombstone_guard_beats_a_valid_agreement(world):
    """M3-FEDERATION-DELETION-GUARD, end to end.

    The peer holds federation:push by agreement and every operational gate
    passes — this is a push that would otherwise go out. A sample in the
    deletion lifecycle must not, and deny-wins is what stops it. Testing this
    through may_push_sample rather than permit() directly is the point: the
    policy was deferred out of M3 precisely because asserting it against the
    engine alone would prove nothing about whether any code path consults it.
    """
    sid = world.sample("M4B-DEL", deletion_status="DELETION_REQUESTED")
    world.agree("federation:push", world.lab_scope())
    principal = load_peer_principal(world.peer, conn=world.conn)

    resource = Resource(
        scope=world.sample_scope(sid),
        attributes={"deletion_status": "DELETION_REQUESTED"},
    )
    assert (
        FederationPushJob.may_push_sample(
            principal,
            resource,
            context=Context(conditions={}),
            surveillance_relevant=True,
            sharing_level="PUBLIC",
            quality_status="SUBMITTABLE",
            min_sharing_level_for_federation="DISCOVERABLE",
        )
        is False
    )

    # The identical call on an ACTIVE row goes through — so the DENY is what
    # made the difference, not a gate or a missing grant.
    assert _may_push(world, principal, sid) is True
