# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""B-CARE-4 — federation propagation of sovereignty deletion events (§9).

Implements the four §9 requirements from
``docs/architecture/sovereignty-compliant-deletion.md``:

1. Signed tombstone/vacuum events pushed to all federation peers within a
   configurable SLA (``enqueue_deletion_events`` at transition time +
   ``deliver_pending_events`` from the APScheduler job).
2. Signed acknowledgments collected (a delivery only counts as
   acknowledged when the peer returns a non-empty ``ack_signature`` —
   trust boundary: an unsigned receipt is not a receipt).
3. Non-compliance flagged: un-acknowledged tombstone events past the SLA
   and vacuum events past 2× the SLA become ``NON_COMPLIANT``, audited,
   and surfaced by notification to the principals holding
   ``federation:configure_peer`` at instance scope — the people who can
   actually act on the peer, rather than "platform admins" as a class.
4. Operator policy applied: ``alert_only`` / ``suspend_on_n`` /
   ``hard_fail`` (suspension clears ``federated_instances
   .federation_enabled`` so suspended peers receive no new shares).

The event payload is the §9 signed JSON document: sample ID, event
timestamp, deletion reason class, and a propagation token tying the
event to the peer agreement. The free-text ``deletion_reason`` is
internal and never leaves the instance. Signing uses the Track 1
``Ed25519Signer``; the peer receipt-signature format is owned by B-FED-1
and stored verbatim here.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from types import EllipsisType
from typing import Any, Protocol
from uuid import uuid4

import httpx
from pydantic import HttpUrl, TypeAdapter

from backend.audit import AuditActions, log_audit
from backend.authz.principal import capability_holders
from backend.authz.scope import scope_uri
from backend.config import get_settings
from backend.credentials import credentials
from backend.crypto.keys import load_keystore
from backend.crypto.signing import Ed25519Signer
from backend.database import execute_query, execute_write
from backend.federation.models import is_secure_url
from backend.notifications import create_notification

logger = logging.getLogger(__name__)

DELIVERY_TIMEOUT_SECONDS = 15.0

# §9 names a deletion reason *class* in the payload (never the free-text
# reason). The schema carries only the internal free-text
# ``samples.deletion_reason``; until a reason-class taxonomy lands, every
# propagated event carries this constant.
UNSPECIFIED_REASON_CLASS = "UNSPECIFIED"

_HTTP_URL = TypeAdapter(HttpUrl)


class HttpPoster(Protocol):
    """The one httpx.Client method delivery needs — injectable in tests."""

    def post(self, url: str, *, json: Any, headers: dict[str, str]) -> Any: ...


def canonical_payload_bytes(payload: dict) -> bytes:
    """Deterministic byte form of the payload — what gets signed/verified."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def get_federation_signer() -> Ed25519Signer | None:
    """Build the instance's Ed25519 event signer from operator config.

    Returns None (and logs) when the signing key is not configured —
    events are then enqueued unsigned and delivery is withheld, because
    §9 requires the event document to be signed.
    """
    settings = get_settings()
    signer = Ed25519Signer(
        load_keystore(settings.federation_keystore_backend),
        settings.federation_signing_key_id,
    )
    try:
        signer.public_key_bytes()  # probe key availability
    except Exception:
        logger.error(
            "federation propagation: signing key %r unavailable in %r keystore; "
            "deletion events will be enqueued unsigned and NOT delivered until "
            "the key is configured",
            settings.federation_signing_key_id,
            settings.federation_keystore_backend,
        )
        return None
    return signer


def build_event_payload(sample: dict, event_type: str, peer_instance_id, token: str) -> dict:
    """The §9 event document: sample ID, event timestamp, reason class,
    propagation token tying the event to the peer agreement."""
    timestamp = sample.get("vacuumed_at") if event_type == "VACUUM" else sample.get("tombstoned_at")
    return {
        "sample_id": sample["sample_id"],
        "event_type": event_type,
        "event_timestamp": str(timestamp or ""),
        "deletion_reason_class": UNSPECIFIED_REASON_CLASS,
        "propagation_token": token,
        "peer_instance_id": str(peer_instance_id),
    }


def enqueue_deletion_events(
    sample: dict,
    event_type: str,
    conn,
    *,
    signer: Ed25519Signer | None | EllipsisType = ...,
) -> int:
    """Record one propagation event per enabled peer, in the caller's
    transaction. Called at tombstone/vacuum time (backend.deletion).

    Delivery is asynchronous (the propagation job) so the deletion
    transaction never blocks on peer availability; the SLA clock
    (``flag_after``) starts here. Tombstone events flag at the SLA,
    vacuum events at 2× the SLA (§9).
    """
    if event_type not in ("TOMBSTONE", "VACUUM"):
        raise ValueError(f"Unknown federation deletion event type: {event_type!r}")
    peers = execute_query(
        "SELECT id, name FROM federated_instances WHERE federation_enabled = TRUE",
        conn=conn,
    )
    if not peers:
        return 0
    if signer is ...:
        signer = get_federation_signer()
    sla = get_settings().federation_propagation_sla_seconds
    flag_after = datetime.now(UTC) + timedelta(seconds=sla * (2 if event_type == "VACUUM" else 1))
    for peer in peers:
        token = str(uuid4())
        payload = build_event_payload(sample, event_type, peer["id"], token)
        signature = (
            signer.sign(canonical_payload_bytes(payload)).hex()
            if isinstance(signer, Ed25519Signer)
            else None
        )
        execute_write(
            "INSERT INTO federation_deletion_events "
            "(sample_id_fk, event_type, peer_instance_id, payload, signature, "
            "propagation_token, flag_after) VALUES "
            "(:sid, :et, :pid, CAST(:payload AS JSONB), :sig, :tok, :fa) RETURNING id",
            {
                "sid": sample["id"],
                "et": event_type,
                "pid": peer["id"],
                "payload": json.dumps(payload),
                "sig": signature,
                "tok": token,
                "fa": flag_after,
            },
            conn=conn,
        )
    log_audit(
        action=AuditActions.FEDERATION_PROPAGATE_DELETION,
        actor_id=None,
        resource_type="sample",
        resource_id=str(sample["id"]),
        before=None,
        after=None,
        metadata={
            "event_type": event_type,
            "peer_count": len(peers),
            "signed": isinstance(signer, Ed25519Signer),
        },
        db_conn=conn,
    )
    return len(peers)


def deliver_pending_events(conn=None, *, http_client: HttpPoster | None = None) -> dict:
    """Push pending signed events to their peers; collect signed receipts.

    Trust boundaries enforced per §9 + the federation registration rules:
      - unsigned events are never sent;
      - suspended peers (``federation_enabled = FALSE``) receive nothing;
      - plaintext (non-https, non-loopback) peers are skipped so the
        federation API key stays off the wire;
      - a response without a non-empty ``ack_signature`` is NOT an
        acknowledgment — the event stays PENDING and ages toward its
        non-compliance flag.
    """
    rows = execute_query(
        "SELECT e.id, e.payload, e.signature, e.peer_instance_id, "
        "fi.base_url, fi.name AS peer_name, fi.federation_enabled, "
        "fi.api_key_secret_name "
        "FROM federation_deletion_events e "
        "JOIN federated_instances fi ON fi.id = e.peer_instance_id "
        "WHERE e.status = 'PENDING' ORDER BY e.id",
        conn=conn,
    )
    delivered = 0
    owned: httpx.Client | None = None
    if http_client is None:
        owned = httpx.Client(timeout=DELIVERY_TIMEOUT_SECONDS)
    client: HttpPoster = http_client if http_client is not None else owned  # type: ignore[assignment]
    try:
        for row in rows:
            if not row["federation_enabled"]:
                continue  # suspended peers get no new traffic
            if not row["signature"]:
                logger.error(
                    "federation propagation: event %s has no signature; withholding "
                    "delivery (configure the federation signing key)",
                    row["id"],
                )
                continue
            try:
                url = _HTTP_URL.validate_python(row["base_url"])
            except ValueError:
                logger.warning(
                    "federation propagation: peer %s has an invalid base_url; skipping",
                    row["peer_name"],
                )
                continue
            if not is_secure_url(url):
                logger.warning(
                    "federation propagation: peer %s has a plaintext base_url; "
                    "skipping to keep the federation key off the wire",
                    row["peer_name"],
                )
                continue
            api_key = credentials.get_optional(row["api_key_secret_name"])
            if not api_key:
                logger.warning(
                    "federation propagation: no federation API key for peer %s "
                    "(credential %r); skipping",
                    row["peer_name"],
                    row["api_key_secret_name"],
                )
                continue
            base = str(row["base_url"]).rstrip("/")
            try:
                response = client.post(
                    f"{base}/api/v1/federation/deletion-events",
                    json={"payload": row["payload"], "signature": row["signature"]},
                    headers={"X-JACKPOT-Federation-Key": api_key},
                )
                response.raise_for_status()
                ack_signature = response.json().get("ack_signature")
            except Exception as exc:
                logger.warning(
                    "federation propagation: delivery to peer %s failed: %s",
                    row["peer_name"],
                    exc,
                )
                continue
            if not ack_signature:
                logger.warning(
                    "federation propagation: peer %s returned no ack_signature; "
                    "receipt rejected (§9 receipts must be signed)",
                    row["peer_name"],
                )
                continue
            execute_write(
                "UPDATE federation_deletion_events SET status = 'ACKNOWLEDGED', "
                "acknowledged_at = NOW(), ack_signature = :ack "
                "WHERE id = :id RETURNING id",
                {"ack": str(ack_signature), "id": row["id"]},
                conn=conn,
            )
            delivered += 1
    finally:
        if owned is not None:
            owned.close()
    return {"pending": len(rows), "delivered": delivered}


def flag_noncompliant_events(conn=None) -> dict:
    """Flag SLA-breached events and apply the operator non-compliance policy.

    Policies (§9, ``operator.yaml`` / env ``FEDERATION_NONCOMPLIANCE_POLICY``):
      - ``alert_only``: audit + notify platform admins, keep the link up.
      - ``suspend_on_n``: additionally suspend the peer once its
        NON_COMPLIANT event count reaches
        ``federation_suspend_after_n_failures``.
      - ``hard_fail``: suspend on the first non-compliant event
        (Scenario T default per §9).
    """
    flagged = execute_write(
        "UPDATE federation_deletion_events SET status = 'NON_COMPLIANT' "
        "WHERE status = 'PENDING' AND flag_after < NOW() "
        "RETURNING id, peer_instance_id, event_type",
        conn=conn,
    )
    if not flagged:
        return {"flagged": 0, "suspended": []}
    settings = get_settings()
    policy = settings.federation_noncompliance_policy
    if policy not in ("alert_only", "suspend_on_n", "hard_fail"):
        logger.warning(
            "federation propagation: unknown non-compliance policy %r; treating as alert_only",
            policy,
        )
        policy = "alert_only"
    suspended: list[str] = []
    peer_ids = {str(f["peer_instance_id"]) for f in flagged}
    for peer_id in sorted(peer_ids):
        peer = execute_query(
            "SELECT id, name, federation_enabled FROM federated_instances WHERE id = :id",
            {"id": peer_id},
            conn=conn,
        )[0]
        total = execute_query(
            "SELECT COUNT(*) AS n FROM federation_deletion_events "
            "WHERE peer_instance_id = :id AND status = 'NON_COMPLIANT'",
            {"id": peer_id},
            conn=conn,
        )[0]["n"]
        log_audit(
            action=AuditActions.FEDERATION_PEER_NONCOMPLIANT,
            actor_id=None,
            resource_type="federated_instance",
            resource_id=peer_id,
            before=None,
            after=None,
            metadata={"unacknowledged_events": total, "policy": policy},
            db_conn=conn,
        )
        _alert_operators(peer, total, conn)
        should_suspend = policy == "hard_fail" or (
            policy == "suspend_on_n" and total >= settings.federation_suspend_after_n_failures
        )
        if should_suspend and peer["federation_enabled"]:
            execute_write(
                "UPDATE federated_instances SET federation_enabled = FALSE "
                "WHERE id = :id RETURNING id",
                {"id": peer_id},
                conn=conn,
            )
            log_audit(
                action=AuditActions.FEDERATION_PEER_SUSPENDED,
                actor_id=None,
                resource_type="federated_instance",
                resource_id=peer_id,
                before={"federation_enabled": True},
                after={"federation_enabled": False},
                metadata={"unacknowledged_events": total, "policy": policy},
                db_conn=conn,
            )
            suspended.append(peer["name"])
    return {"flagged": len(flagged), "suspended": suspended}


def _alert_operators(peer: dict, unacknowledged: int, conn) -> None:
    """Notify whoever can act on a non-compliant peer (M2-DROP-PRE).

    "Act on" is the whole selection criterion, and it is why the lookup asks
    for ``federation:configure_peer`` rather than for admins: the alert exists
    because the peer may be about to be suspended, and suspension writes
    ``federated_instances.federation_enabled`` — a configure-peer act. Anyone
    holding that verb instance-wide can respond to this; anyone who does not,
    cannot, whatever else they are.

    Instance scope specifically: a peer is a principal, not a branch of the
    scope tree (ADR 0015), so there is no narrower scope to ask at. A holder
    granted the verb over one org is not an operator of the federation link.
    """
    operators = capability_holders("federation:configure_peer", scope_uri(), conn=conn)
    if not operators:
        # The audit row above is written either way, so the record survives;
        # what is lost is the push. Worth saying out loud, because the failure
        # is otherwise a notification that nobody notices not receiving.
        logger.warning(
            "federation: peer %s flagged non-compliant but no active principal holds "
            "federation:configure_peer at instance scope — no operator was notified",
            peer["name"],
        )
    for recipient_id in operators:
        create_notification(
            recipient_id=recipient_id,
            event_type="FEDERATION_PEER_NONCOMPLIANT",
            title=f"Federation peer {peer['name']} non-compliant",
            body=(
                f"{unacknowledged} sovereignty deletion event(s) to peer "
                f"{peer['name']} are un-acknowledged past their SLA."
            ),
            resource_type="federated_instance",
            resource_id=str(peer["id"]),
            action_url="/admin/federation",
            db_conn=conn,
        )
