import hmac
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request
from jose import jwt

from backend.authz.engine import Context, Decision, Resource, permit
from backend.authz.policy import ACTIVE_POLICIES
from backend.authz.principal import (
    lab_resource_scope,
    load_principal,
    project_resource_scope,
    sample_resource,
)
from backend.authz.scope import scope_uri
from backend.config import get_settings
from backend.credentials import CredentialError, CredentialNotFoundError, credentials
from backend.database import execute_query

logger = logging.getLogger(__name__)

FEDERATION_KEY_HEADER = "X-JACKPOT-Federation-Key"


def get_current_user(request: Request) -> dict:
    settings = get_settings()
    if settings.env == "local":
        rows = execute_query(
            "SELECT * FROM users WHERE email = :e AND is_active = TRUE LIMIT 1",
            {"e": settings.mock_user_email},
        )
        return (
            rows[0]
            if rows
            # No legacy role flags. This dict used to carry
            # is_platform_admin=True and that was how the fallback identity
            # got its authority; since M2-B1 nothing decides on the flag, so
            # the fallback's authority is whatever grants user 1 holds. Adding
            # the key back would not restore a bypass, it would only re-create
            # a field that reads like one (M2-DROP-PRE slice 5).
            else {
                "id": 1,
                "email": settings.mock_user_email,
                "name": "Dev User",
                "is_active": True,
                "organization_id": 1,
            }
        )

    token = request.cookies.get("access")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    # Resolve the signing key separately: a credential-backend failure is a
    # 503 (service issue), not a 401 (bad token), and must not leak a raw
    # stack trace to the caller.
    try:
        signing_key = credentials.get("jwt_signing_key")
    except CredentialError as exc:
        logger.error("auth: jwt signing key unavailable: %s", exc)
        raise HTTPException(
            status_code=503, detail="Authentication temporarily unavailable."
        ) from exc
    try:
        payload = jwt.decode(token, signing_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Access token expired.") from exc
    except jwt.JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token.") from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type.")

    rows = execute_query(
        "SELECT id, email, name, is_active, organization_id FROM users "
        "WHERE id = :uid AND is_active = TRUE LIMIT 1",
        {"uid": payload["sub"]},
    )
    if not rows:
        raise HTTPException(status_code=401, detail="User not found or inactive.")
    return rows[0]


def get_user_lab_membership(user_id: int, lab_id: int) -> dict | None:
    rows = execute_query(
        "SELECT lm.*, pg.name AS permission_group_name, lm.is_lab_director "
        "FROM lab_membership lm "
        "JOIN permission_groups pg ON pg.id = lm.permission_group_id "
        "WHERE lm.user_id = :uid AND lm.lab_id = :lid LIMIT 1",
        {"uid": user_id, "lid": lab_id},
    )
    return rows[0] if rows else None


def _allows(
    principal,
    capability: str,
    resource: Resource,
    conditions: dict | None = None,
) -> bool:
    """One place where a decision is made, so the guard cannot drift from it.

    ``ACTIVE_POLICIES`` rather than ``policies=[]``: the sample plane's
    permissive rungs — PUBLIC, surveillance relevance, ownership, and the
    invitation a DISCOVERABLE sample extends to request access — are facts
    about the row, not about the caller's memberships, so no grant can carry
    them.

    **M3 changed what passing this set on every call means.** It used to be
    free because the set held no DENY: it could only widen, and only for a
    sample. `deletion.separation_of_duties` is a DENY, and the old safety
    argument — "a resource carrying no attributes matches nothing" — holds for
    an equality predicate but inverts for a negation one, since absent is not
    equal to anything. The invariant that replaces it, enforced by the comment
    on ``DELETION_POLICIES``: a DENY here may only read attributes
    ``SAMPLE_ATTRIBUTE_COLUMNS`` loads, and may only key on a capability whose
    routes resolve a Sample resource. Under that rule a lab- or
    instance-scoped call still cannot trip a DENY, because no DENY names its
    capability.

    ``conditions`` carries request facts the policies read — today only
    ``platform_admin_self_approve`` for §6.2-1b's audited escape. It is a
    parameter rather than ambient state so the escape is visible at the call
    site that grants it.
    """
    return (
        permit(
            principal,
            capability,
            resource,
            # A real clock, so a lapsed grant is refused at decision time —
            # the legacy ladder compared access_expires_at against NOW() and
            # did not wait for the nightly expiry job (M2-B2-PRE-C).
            Context(conditions=conditions or {}, now=datetime.now(UTC)),
            policies=ACTIVE_POLICIES,
        )
        is Decision.ALLOW
    )


def require_capability(capability: str):
    """Guard factory: returns a callable raising HTTP 403 unless the current
    user holds ``capability`` at a scope covering the resource.

    M2-B1: enforcement is ``permit()`` (access_model.md §5). The legacy
    structural ladder — platform-admin bypass, lab membership, the
    project→lab join, the director flag — is gone from this function. What
    replaces each rung:

    - platform admin        -> an ``instance://self`` grant from the §8.2
                               Instance Administrator preset, which contains
                               every lab path by ordinary prefix containment
                               (ADR 0015). No bypass branch.
    - lab membership        -> lab-scoped grants from the member presets
    - directorship          -> the Lab Lead preset's enumerated capabilities
    - project→lab join      -> nothing. Project-only members hold no grants;
                               reseed's pre-flight guard counts them so an
                               operator sees the loss before it happens
                               (``project_only_membership``).

    M2-B2 adds the attribute half. A route naming a ``sample_id`` is decided
    against the row's attributes as well as its scope, under the static
    ``LADDER_POLICIES`` set — that is what keeps a PUBLIC sample readable by a
    non-member and a DISCOVERABLE one requestable by a stranger, neither of
    which any grant expresses. DB-backed policy loading still waits for M3;
    the list path, where the same rules have to be compiled into SQL rather
    than evaluated per row, is M2-B7.
    """

    # ``row_attributes`` is for a caller that has already loaded the row — the
    # BYOP plane, whose rows come through SQLAlchemy in a test harness with no
    # database for a resolver to query. The sample path deliberately does NOT
    # work this way: it fetches its own attributes, so a route cannot hand the
    # guard a row that says something the database does not.
    #
    # Named for its provenance because that IS the contract, and the contract
    # cannot be checked here: values must be read straight off a persisted
    # row, never off a request body. Passing body data would let a caller
    # assert the very attribute a policy is about to trust.
    # ponytail: docstring-and-name is the whole fence. A TrustedRow wrapper
    # type would make it checkable; not worth a new type for one call site,
    # but revisit if a second plane needs this.
    def _guard(
        current_user: dict | None,
        lab_id: int | None = None,
        sample_id: int | None = None,
        project_id: int | None = None,
        row_attributes: dict | None = None,
        conditions: dict | None = None,
    ) -> dict:
        if current_user is None:
            raise HTTPException(status_code=403, detail=f"capability '{capability}' required")
        named = [
            n
            for n, v in (("lab_id", lab_id), ("sample_id", sample_id), ("project_id", project_id))
            if v is not None
        ]
        if len(named) > 1:
            # Ambiguous: each produces a different scope, and silently
            # preferring one would make the route's check quietly weaker or
            # stronger than it reads.
            raise ValueError(f"pass exactly one of lab_id / sample_id / project_id, got {named}")

        principal = load_principal(current_user["id"])

        try:
            if sample_id is not None:
                # Carries the row's attributes, not just its scope — the
                # attribute-policies are the only path by which a non-member
                # reads a PUBLIC sample or a stranger requests access to a
                # DISCOVERABLE one.
                resource = sample_resource(sample_id)
            elif project_id is not None:
                resource = Resource(
                    scope=project_resource_scope(project_id), attributes=row_attributes or {}
                )
            else:
                scope = lab_resource_scope(lab_id) if lab_id is not None else scope_uri()
                resource = Resource(scope=scope, attributes=row_attributes or {})
        except ValueError:
            # No such lab/sample. Whether the caller may learn that depends on
            # their reach: someone holding the capability instance-wide can
            # already enumerate, so let them through and let the route answer
            # 404. For everyone else the answer is the same 403 a real-but-
            # denied resource produces — under org isolation existence is
            # itself the secret (§3.2: another org must not learn of a lab's
            # data, users, "or existence").
            if _allows(principal, capability, Resource(scope=scope_uri()), conditions):
                return current_user
            logger.info(
                "authz: DENY user=%s capability=%s unknown lab_id=%s sample_id=%s project_id=%s",
                current_user.get("id"),
                capability,
                lab_id,
                sample_id,
                project_id,
            )
            raise HTTPException(
                status_code=403, detail=f"capability '{capability}' required"
            ) from None

        if _allows(principal, capability, resource, conditions):
            return current_user

        logger.info(
            "authz: DENY user=%s capability=%s scope=%s",
            current_user.get("id"),
            capability,
            resource.scope,
        )
        raise HTTPException(status_code=403, detail=f"capability '{capability}' required")

    return _guard


def permits(
    user: dict,
    capability: str,
    *,
    lab_id=None,
    sample_id=None,
    project_id=None,
    row_attributes: dict | None = None,
    conditions: dict | None = None,
) -> bool:
    """``require_capability`` as a boolean, for routes that answer with
    something other than the guard's 403.

    Several sample-plane routes deliberately do not surface a denial as a 403:
    the file routes collapse it into ``FILE_NOT_FOUND`` so existence is not
    leaked, and ``sample-access`` answers with a message naming the sharing
    level. Each was writing its own ``try/except HTTPException`` around the
    guard; this is that shape once, so a future change to how the guard
    signals denial does not have to be found in three places.
    """
    try:
        require_capability(capability)(
            user,
            lab_id=lab_id,
            sample_id=sample_id,
            project_id=project_id,
            row_attributes=row_attributes,
            conditions=conditions,
        )
    except HTTPException:
        return False
    return True


def authenticate_federation_peer(request: Request, conn: Any = None) -> dict[str, Any] | None:
    # FED-E: validate X-JACKPOT-Federation-Key against every enabled row in
    # federated_instances. The expected key is resolved per-row through the
    # credentials facade (GCP Secret Manager in prod, InMemoryBackend in
    # tests). Comparisons are constant-time. Disabled instances are
    # excluded by the SQL filter so their keys cannot authenticate even if
    # the secret backend still resolves them.
    presented = request.headers.get(FEDERATION_KEY_HEADER)
    if not presented:
        return None

    rows = execute_query(
        "SELECT * FROM federated_instances WHERE federation_enabled = TRUE",
        conn=conn,
    )
    for row in rows:
        secret_name = row.get("api_key_secret_name")
        if not secret_name:
            continue
        try:
            expected = credentials.get(secret_name)
        except (CredentialNotFoundError, CredentialError) as exc:
            logger.warning(
                "federation auth: credential lookup failed for instance %s: %s",
                row.get("name"),
                exc,
            )
            continue
        # Strip surrounding whitespace: secrets created via shell `echo`
        # or an editor often carry a trailing newline in the store, which
        # would otherwise permanently fail the constant-time comparison and
        # lock out a correctly-configured peer.
        if hmac.compare_digest(presented.strip(), expected.strip()):
            return row
    return None


def require_federation_peer(request: Request, conn: Any = None) -> dict[str, Any]:
    # FED-E: thin wrapper that raises 401 when the X-JACKPOT-Federation-Key
    # header is missing or does not match any enabled instance. Routers that
    # also need to cross-check origin (e.g. /access-requests matching
    # requesting_instance_id) call authenticate_federation_peer directly so
    # they can produce a 403 instead of a 401.
    instance_row = authenticate_federation_peer(request, conn)
    if not instance_row:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing federation key.",
        )
    return instance_row
