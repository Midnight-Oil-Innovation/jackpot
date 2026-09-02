# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""B-CARE-4 — federation propagation of sovereignty deletion events (§9).

Covers the four §9 requirements: signed tombstone/vacuum events enqueued
for every enabled federation peer at tombstone/vacuum time, signed
acknowledgments collected on delivery, non-compliance flagged past the
SLA (2× SLA for vacuum events), and the operator policy applied
(alert_only / suspend_on_n / hard_fail). Trust boundaries pinned here:
unsigned events are never delivered, an unsigned peer receipt is not an
acknowledgment, and suspended peers receive no new traffic.
"""

import os

import pytest

from backend.audit import AuditActions
from backend.config import get_settings
from backend.crypto.keys import KeystoreBackend
from backend.crypto.signing import Ed25519Signer
from backend.database import execute_query, execute_write
from backend.federation import deletion_propagation as dp
from backend.federation.deletion_propagation import (
    canonical_payload_bytes,
    deliver_pending_events,
    enqueue_deletion_events,
    flag_noncompliant_events,
)


class _SeedKeystore(KeystoreBackend):
    """Minimal keystore holding one fixed Ed25519 seed."""

    def __init__(self, seed: bytes) -> None:
        self._seed = seed

    def load_key(self, key_id: str) -> bytes:
        return self._seed

    def store_key(self, key_id: str, key_bytes: bytes, *, key_type: str = "signing") -> None:
        self._seed = key_bytes

    def list_keys(self) -> list[str]:
        return ["test-federation-signing"]

    def delete_key(self, key_id: str) -> None:
        return None


@pytest.fixture
def signer() -> Ed25519Signer:
    return Ed25519Signer(_SeedKeystore(os.urandom(32)), "test-federation-signing")


@pytest.fixture(autouse=True)
def _clean_bcare4_state():
    """Remove this module's peers/events/samples before AND after each test.

    The events table FKs federated_instances, so leftover rows would break
    other suites' blanket ``DELETE FROM federated_instances`` cleanups.
    """

    def _wipe() -> None:
        execute_write(
            "DELETE FROM federation_deletion_events WHERE peer_instance_id IN "
            "(SELECT id FROM federated_instances WHERE name LIKE 'bcare4-%')"
        )
        execute_write(
            "DELETE FROM federation_deletion_events WHERE sample_id_fk IN "
            "(SELECT id FROM samples WHERE sample_id LIKE 'BCARE4-%')"
        )
        execute_write("DELETE FROM federated_instances WHERE name LIKE 'bcare4-%'")

    _wipe()
    yield
    _wipe()


def _mk_peer(
    name: str, *, enabled: bool = True, base_url: str = "https://peer.example.org"
) -> dict:
    execute_write(
        "DELETE FROM federation_deletion_events WHERE peer_instance_id IN "
        "(SELECT id FROM federated_instances WHERE name = :n)",
        {"n": name},
    )
    execute_write("DELETE FROM federated_instances WHERE name = :n", {"n": name})
    return execute_write(
        "INSERT INTO federated_instances (name, base_url, role, federation_enabled, "
        "api_key_secret_name) VALUES (:n, :u, 'peer', :e, :s) RETURNING *",
        {"n": name, "u": base_url, "e": enabled, "s": f"fed_key_{name}"},
    )[0]


def _mk_sample(sid: str, *, status: str = "TOMBSTONED") -> dict:
    for r in execute_query("SELECT id FROM samples WHERE sample_id = :s", {"s": sid}):
        execute_write(
            "DELETE FROM federation_deletion_events WHERE sample_id_fk = :id", {"id": r["id"]}
        )
        execute_write("DELETE FROM sample_files WHERE sample_id_fk = :id", {"id": r["id"]})
        execute_write("DELETE FROM samples WHERE id = :id", {"id": r["id"]})
    row = execute_write(
        "INSERT INTO samples (sample_id, lab_id, project_id, owner_id, source_type, "
        "organism_name, type_of_experiment, library_preparation_method, "
        "sequencing_protocol, sequencing_platform, sequencing_lab, date_collected, "
        "date_sequenced, collection_facility, collection_location_country, sharing_level) "
        f"VALUES ('{sid}', 1, 1, 1, 'Human', "
        "'Severe acute respiratory syndrome coronavirus 2', 'WGS', 'ARTIC', "
        "'https://www.protocols.io/view/artic-v4-1', 'Illumina', "
        "'Example Sequencing Lab', '2026-01-15', '2026-01-17', 'Example Hospital', "
        "'United States', 'PRIVATE') RETURNING *",
    )[0]
    if status == "ACTIVE":
        return row
    # samples_deletion_active_requested_chk: non-ACTIVE requires requested_at.
    return execute_write(
        "UPDATE samples SET deletion_status = :st, deletion_requested_at = NOW(), "
        "tombstoned_at = NOW(), "
        "deletion_reason = 'consent withdrawn — free text stays internal' "
        "WHERE id = :id RETURNING *",
        {"st": status, "id": row["id"]},
    )[0]


def _events_for(sample_pk: int) -> list[dict]:
    return execute_query(
        "SELECT * FROM federation_deletion_events WHERE sample_id_fk = :id ORDER BY id",
        {"id": sample_pk},
    )


class _StubResponse:
    def __init__(self, body: dict) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._body


class _StubClient:
    """httpx.Client stand-in. `body` per post; raises when `exc` set."""

    def __init__(self, body: dict | None = None, exc: Exception | None = None) -> None:
        self.body = body or {}
        self.exc = exc
        self.calls: list[dict] = []

    def post(self, url, *, json, headers):
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self.exc is not None:
            raise self.exc
        return _StubResponse(self.body)


@pytest.fixture
def resolve_keys(monkeypatch):
    """Trust boundary seam: peer API-key auth resolved via CredentialFacade."""

    class _Creds:
        @staticmethod
        def get_optional(name: str) -> str | None:
            return f"resolved-{name}"

    monkeypatch.setattr(dp, "credentials", _Creds())


# ── enqueue: signed §9 payload, one event per enabled peer ───────────────────


def test_enqueue_signs_payload_for_every_enabled_peer(signer):
    peer_a = _mk_peer("bcare4-peer-a")
    peer_b = _mk_peer("bcare4-peer-b")
    disabled = _mk_peer("bcare4-peer-off", enabled=False)
    sample = _mk_sample("BCARE4-ENQ-01")

    count = enqueue_deletion_events(sample, "TOMBSTONE", None, signer=signer)
    assert count == 2

    events = _events_for(sample["id"])
    peer_ids = {str(e["peer_instance_id"]) for e in events}
    assert peer_ids == {str(peer_a["id"]), str(peer_b["id"])}
    assert str(disabled["id"]) not in peer_ids

    pub = signer.public_key_bytes()
    for event in events:
        assert event["status"] == "PENDING"
        payload = event["payload"]
        # §9 payload contract: sample ID, event timestamp, deletion reason
        # class, propagation token — never the internal free-text reason.
        assert payload["sample_id"] == sample["sample_id"]
        assert payload["event_type"] == "TOMBSTONE"
        assert payload["event_timestamp"]
        assert payload["deletion_reason_class"] == "UNSPECIFIED"
        assert payload["propagation_token"] == event["propagation_token"]
        assert "consent withdrawn" not in str(payload)
        # Signed JSON document: Ed25519 detached signature verifies.
        assert Ed25519Signer.verify(
            canonical_payload_bytes(payload), bytes.fromhex(event["signature"]), pub
        )

    audits = execute_query(
        "SELECT metadata FROM audit_log WHERE action = :a AND resource_id = :r "
        "ORDER BY id DESC LIMIT 1",
        {"a": AuditActions.FEDERATION_PROPAGATE_DELETION, "r": str(sample["id"])},
    )
    assert audits and audits[0]["metadata"]["peer_count"] == 2


def test_vacuum_events_flag_at_twice_the_sla(signer):
    _mk_peer("bcare4-peer-2x")
    sample = _mk_sample("BCARE4-ENQ-2X", status="VACUUMED")
    execute_write(
        "UPDATE samples SET vacuumed_at = NOW() WHERE id = :id RETURNING id",
        {"id": sample["id"]},
    )
    sample = execute_query("SELECT * FROM samples WHERE id = :id", {"id": sample["id"]})[0]

    enqueue_deletion_events(sample, "VACUUM", None, signer=signer)
    event = _events_for(sample["id"])[0]
    sla = get_settings().federation_propagation_sla_seconds
    delta = (event["flag_after"] - event["created_at"]).total_seconds()
    # §9: vacuum acknowledgments auto-flag at twice the SLA.
    assert delta == pytest.approx(2 * sla, abs=60)


# ── delivery: happy path collects signed receipts ────────────────────────────


def test_delivery_happy_path_acknowledges_all_peers(signer, resolve_keys):
    _mk_peer("bcare4-del-a")
    _mk_peer("bcare4-del-b")
    sample = _mk_sample("BCARE4-DEL-01")
    enqueue_deletion_events(sample, "TOMBSTONE", None, signer=signer)

    client = _StubClient(body={"ack_signature": "peer-ed25519-receipt"})
    deliver_pending_events(None, http_client=client)

    events = _events_for(sample["id"])
    assert len(events) == 2
    for event in events:
        assert event["status"] == "ACKNOWLEDGED"
        assert event["ack_signature"] == "peer-ed25519-receipt"
        assert event["acknowledged_at"] is not None
    calls = [c for c in client.calls if c["json"]["payload"]["sample_id"] == sample["sample_id"]]
    assert len(calls) == 2
    # Auth trust boundary: federation key header on every delivery.
    assert all(
        call["headers"]["X-JACKPOT-Federation-Key"].startswith("resolved-fed_key_")
        for call in calls
    )
    assert all("/api/v1/federation/deletion-events" in call["url"] for call in calls)


# ── delivery failure paths ───────────────────────────────────────────────────


def test_unreachable_peer_leaves_event_pending(signer, resolve_keys):
    _mk_peer("bcare4-del-down")
    sample = _mk_sample("BCARE4-DEL-02")
    enqueue_deletion_events(sample, "TOMBSTONE", None, signer=signer)

    client = _StubClient(exc=ConnectionError("peer unreachable"))
    deliver_pending_events(None, http_client=client)
    assert _events_for(sample["id"])[0]["status"] == "PENDING"


def test_unsigned_receipt_is_not_an_acknowledgment(signer, resolve_keys):
    # §9 trust boundary: peers MUST acknowledge with SIGNED receipts.
    _mk_peer("bcare4-del-unsigned-ack")
    sample = _mk_sample("BCARE4-DEL-03")
    enqueue_deletion_events(sample, "TOMBSTONE", None, signer=signer)

    client = _StubClient(body={"ok": True})  # no ack_signature
    deliver_pending_events(None, http_client=client)
    assert _events_for(sample["id"])[0]["status"] == "PENDING"


def test_unsigned_event_is_never_delivered(resolve_keys):
    # §9 trust boundary: the tombstone event is a SIGNED JSON document.
    _mk_peer("bcare4-del-nosig")
    sample = _mk_sample("BCARE4-DEL-04")
    enqueue_deletion_events(sample, "TOMBSTONE", None, signer=None)

    client = _StubClient(body={"ack_signature": "x"})
    deliver_pending_events(None, http_client=client)
    ours = [c for c in client.calls if c["json"]["payload"]["sample_id"] == sample["sample_id"]]
    assert ours == []
    assert _events_for(sample["id"])[0]["status"] == "PENDING"


def test_suspended_peer_receives_no_new_traffic(signer, resolve_keys):
    peer = _mk_peer("bcare4-del-suspended")
    sample = _mk_sample("BCARE4-DEL-05")
    enqueue_deletion_events(sample, "TOMBSTONE", None, signer=signer)
    execute_write(
        "UPDATE federated_instances SET federation_enabled = FALSE WHERE id = :id RETURNING id",
        {"id": peer["id"]},
    )
    client = _StubClient(body={"ack_signature": "x"})
    deliver_pending_events(None, http_client=client)
    ours = [c for c in client.calls if c["json"]["payload"]["sample_id"] == sample["sample_id"]]
    assert ours == []


# ── SLA breach → non-compliance flag + operator policy ──────────────────────


def _age_events(sample_pk: int) -> None:
    execute_write(
        "UPDATE federation_deletion_events SET flag_after = NOW() - INTERVAL '1 hour' "
        "WHERE sample_id_fk = :id RETURNING id",
        {"id": sample_pk},
    )


def test_sla_breach_flags_noncompliant_and_alerts(signer, monkeypatch):
    monkeypatch.setenv("FEDERATION_NONCOMPLIANCE_POLICY", "alert_only")
    get_settings.cache_clear()
    peer = _mk_peer("bcare4-flag-alert")
    sample = _mk_sample("BCARE4-FLAG-01")
    enqueue_deletion_events(sample, "TOMBSTONE", None, signer=signer)
    _age_events(sample["id"])

    result = flag_noncompliant_events(None)
    assert result["flagged"] >= 1
    assert _events_for(sample["id"])[0]["status"] == "NON_COMPLIANT"
    # alert_only keeps the federation link up.
    peer_row = execute_query(
        "SELECT federation_enabled FROM federated_instances WHERE id = :id",
        {"id": peer["id"]},
    )[0]
    assert peer_row["federation_enabled"] is True
    audits = execute_query(
        "SELECT id FROM audit_log WHERE action = :a AND resource_id = :r",
        {"a": AuditActions.FEDERATION_PEER_NONCOMPLIANT, "r": str(peer["id"])},
    )
    assert audits
    # Operator alert: whoever holds federation:configure_peer at instance
    # scope gets a notification. Asserted against the grant rather than
    # users.is_platform_admin — the flag is the thing M2-DROP removes, and a
    # test still standing on it would keep passing after the reader it covers
    # stopped existing.
    notes = execute_query(
        "SELECT n.id FROM notifications n "
        "JOIN authz_capability_grants g ON g.principal_id = CAST(n.recipient_id AS TEXT) "
        "WHERE n.event_type = 'FEDERATION_PEER_NONCOMPLIANT' "
        "AND n.resource_id = :peer_id "
        "AND g.capability = 'federation:configure_peer' "
        "AND g.scope_ref = 'instance://self'",
        {"peer_id": str(peer["id"])},
    )
    assert notes
    get_settings.cache_clear()


def test_the_alert_follows_the_grant(signer, monkeypatch):
    """The narrowing M2-DROP-PRE performed, pinned in both directions.

    Originally this contrasted a grant-holder with a FLAG-holder who had no
    grant — the baseline seeds admin@example.org holding both, so every "as
    admin" assertion passed whichever of the two the code read, and the
    conversion needed a principal holding exactly one.

    Nothing writes the column any more and M2-DROP removes it next, so
    "holds the flag but no grant" is no longer a state a test can construct,
    and that half of the narrowing became structural.
    What is still worth pinning is the other edge of the same property: a user
    who holds nothing is not alerted, so the alert cannot be selecting on
    something incidental like "is a user at all".
    """
    monkeypatch.setenv("FEDERATION_NONCOMPLIANCE_POLICY", "alert_only")
    get_settings.cache_clear()
    granted = execute_write(
        "INSERT INTO users (email, name, organization_id, is_active) "
        "VALUES ('fedop-granted@test.com', 'Granted', 1, TRUE) RETURNING id",
    )[0]["id"]
    ungranted = execute_write(
        "INSERT INTO users (email, name, organization_id, is_active) "
        "VALUES ('fedop-ungranted@test.com', 'Ungranted', 1, TRUE) RETURNING id",
    )[0]["id"]
    try:
        execute_write(
            "INSERT INTO authz_capability_grants "
            "(principal_id, capability, scope_ref, source) "
            "VALUES (:p, 'federation:configure_peer', 'instance://self', 'test')",
            {"p": str(granted)},
        )
        _mk_peer("bcare4-grant-narrowing")
        sample = _mk_sample("BCARE4-NARROW-01")
        enqueue_deletion_events(sample, "TOMBSTONE", None, signer=signer)
        _age_events(sample["id"])
        flag_noncompliant_events(None)

        def notified(user_id: int) -> bool:
            return bool(
                execute_query(
                    "SELECT id FROM notifications WHERE recipient_id = :u "
                    "AND event_type = 'FEDERATION_PEER_NONCOMPLIANT'",
                    {"u": user_id},
                )
            )

        assert notified(granted), "capability holder was not alerted"
        assert not notified(ungranted), "a principal holding nothing was alerted"
    finally:
        for uid in (granted, ungranted):
            execute_write("DELETE FROM notifications WHERE recipient_id = :u", {"u": uid})
            execute_write(
                "DELETE FROM authz_capability_grants WHERE principal_id = :p", {"p": str(uid)}
            )
            execute_write("DELETE FROM users WHERE id = :u", {"u": uid})
        get_settings.cache_clear()


def test_hard_fail_policy_suspends_peer_on_first_breach(signer, monkeypatch):
    monkeypatch.setenv("FEDERATION_NONCOMPLIANCE_POLICY", "hard_fail")
    get_settings.cache_clear()
    peer = _mk_peer("bcare4-flag-hard")
    sample = _mk_sample("BCARE4-FLAG-02")
    enqueue_deletion_events(sample, "TOMBSTONE", None, signer=signer)
    _age_events(sample["id"])

    result = flag_noncompliant_events(None)
    assert peer["name"] in result["suspended"]
    peer_row = execute_query(
        "SELECT federation_enabled FROM federated_instances WHERE id = :id",
        {"id": peer["id"]},
    )[0]
    assert peer_row["federation_enabled"] is False
    audits = execute_query(
        "SELECT id FROM audit_log WHERE action = :a AND resource_id = :r",
        {"a": AuditActions.FEDERATION_PEER_SUSPENDED, "r": str(peer["id"])},
    )
    assert audits
    get_settings.cache_clear()


def test_suspend_on_n_policy_waits_for_threshold(signer, monkeypatch):
    monkeypatch.setenv("FEDERATION_NONCOMPLIANCE_POLICY", "suspend_on_n")
    monkeypatch.setenv("FEDERATION_SUSPEND_AFTER_N_FAILURES", "2")
    get_settings.cache_clear()
    peer = _mk_peer("bcare4-flag-n")

    first = _mk_sample("BCARE4-FLAG-03A")
    enqueue_deletion_events(first, "TOMBSTONE", None, signer=signer)
    _age_events(first["id"])
    flag_noncompliant_events(None)
    assert (
        execute_query(
            "SELECT federation_enabled FROM federated_instances WHERE id = :id",
            {"id": peer["id"]},
        )[0]["federation_enabled"]
        is True
    )  # 1 breach < N=2

    second = _mk_sample("BCARE4-FLAG-03B")
    enqueue_deletion_events(second, "TOMBSTONE", None, signer=signer)
    _age_events(second["id"])
    result = flag_noncompliant_events(None)
    assert peer["name"] in result["suspended"]
    assert (
        execute_query(
            "SELECT federation_enabled FROM federated_instances WHERE id = :id",
            {"id": peer["id"]},
        )[0]["federation_enabled"]
        is False
    )
    get_settings.cache_clear()


# ── lifecycle triggers: tombstone/vacuum transitions enqueue events ──────────


def test_approve_deletion_enqueues_tombstone_events():
    from backend.deletion import approve_deletion

    _mk_peer("bcare4-trigger-tomb")
    sample = _mk_sample("BCARE4-TRIG-01", status="ACTIVE")
    requester = execute_write(
        "INSERT INTO users (email, name, organization_id, is_active) "
        "VALUES ('bcare4-req@example.org', 'Req', 1, TRUE) "
        "ON CONFLICT (email) DO UPDATE SET is_active = TRUE RETURNING id",
    )[0]["id"]
    sample = execute_write(
        "UPDATE samples SET deletion_status = 'DELETION_REQUESTED', "
        "deletion_requested_at = NOW(), deletion_requested_by_user_id = :u "
        "WHERE id = :id RETURNING *",
        {"u": requester, "id": sample["id"]},
    )[0]
    approver = execute_query(
        # The approver is identified by the grant, not by a dropped column.
        "SELECT u.id, u.email FROM users u "
        "JOIN authz_capability_grants g ON g.principal_id = u.id::text "
        "WHERE g.capability = 'user:manage' AND g.scope_ref = 'instance://self' LIMIT 1",
    )[0]

    approve_deletion(sample, approver, None)
    events = _events_for(sample["id"])
    assert events and all(e["event_type"] == "TOMBSTONE" for e in events)


def test_vacuum_sample_enqueues_vacuum_events():
    from backend.deletion import vacuum_sample

    _mk_peer("bcare4-trigger-vac")
    sample = _mk_sample("BCARE4-TRIG-02", status="TOMBSTONED")

    vacuum_sample(sample, None, None, trigger="scheduled")
    events = _events_for(sample["id"])
    assert [e["event_type"] for e in events] == ["VACUUM"]
