# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""P0c — multi-tenancy middleware: org context on every request.

Per ``docs/access_model.md``:

* §2.3 / §3.2 — the Org *is* the isolation boundary ("tenant" and "org"
  are the same concept; multi-tenancy means one Instance hosting multiple
  Orgs walled off from each other).
* §3.3 — a tenant "must never see [another tenant's] data, users, or
  existence"; cross-org access therefore surfaces as 404, not 403, so
  resource existence never leaks across the wall.
* §5.4 — "Org-isolation is absolute. The tenant wall is a DENY policy
  keyed on cross-org access; no grant punches through it. P0c
  multi-tenancy is enforced here."

The tenant identifier is the authenticated principal's
``users.organization_id`` (resolved from the JWT cookie in production,
``MOCK_USER_EMAIL`` in local dev) — there is no separate tenant header;
inventing one would create a second identity source the JWT does not
vouch for.

Per-endpoint capability enforcement (``permit()``) is the M2 cutover
(access_model.md §10.3/§11), not P0c. P0c ships the request-context
carrier plus the org-isolation guard, and applies the guard to the
routers flagged in ``docs/endpoint_capability_map.md`` (the
endpoint→capability sweep) — byop.py's IDOR being the mandatory case.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from backend.auth.guards import get_current_user

logger = logging.getLogger(__name__)

# Tenant-exempt paths: the intentionally-public rows of
# docs/endpoint_capability_map.md (login flow, public templates, public
# settings, the never-raising weblog receiver per Critical Rule 60) plus
# the framework's own surface. The middleware is a no-op here — no
# principal resolution, no org context.
TENANCY_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/v1/auth/",
    "/api/v1/templates/",
    "/api/v1/dataharmonizer/templates/",
    "/api/v1/settings/public",
    "/api/v1/pipelines/events",
)


@dataclass(frozen=True)
class OrgContext:
    """The request's tenant: who is asking, and which Org walls them in."""

    user_id: int
    org_id: int | None
    is_platform_admin: bool


def _resolve_user(request: Request) -> dict | None:
    try:
        return get_current_user(request)
    except HTTPException:
        # Unauthenticated request — no tenant. Guards downstream decide
        # whether that is acceptable for the route.
        return None
    except Exception:  # noqa: BLE001 — fail-open by design: the middleware
        # must never take down a request; enforcement lives in the route
        # guards, which resolve the principal properly and raise cleanly.
        logger.warning("tenancy: org-context resolution failed", exc_info=True)
        return None


def resolve_org_context(request: Request) -> OrgContext | None:
    user = _resolve_user(request)
    if user is None:
        return None
    return OrgContext(
        user_id=user["id"],
        org_id=user.get("organization_id"),
        is_platform_admin=bool(user.get("is_platform_admin")),
    )


class TenancyMiddleware(BaseHTTPMiddleware):
    """Attach ``request.state.org_context`` to every non-exempt request."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        request.state.org_context = None
        path = request.url.path
        if not any(path.startswith(prefix) for prefix in TENANCY_EXEMPT_PREFIXES):
            # get_current_user is sync (DB lookup) — run off the event loop.
            request.state.org_context = await run_in_threadpool(resolve_org_context, request)
        return await call_next(request)


def get_org_context(request: Request) -> OrgContext:
    """FastAPI dependency: the request's org context, or 403 if none.

    Routes that operate on tenant-owned resources depend on this; a
    request that carries no resolvable tenant identifier cannot touch
    tenant-scoped state.
    """
    ctx = getattr(request.state, "org_context", None)
    if ctx is None:
        raise HTTPException(
            status_code=403,
            detail="No organization context — an authenticated tenant is required.",
        )
    return ctx


def require_org_access(ctx: OrgContext, resource_org_id: int | None) -> None:
    """The tenant wall (access_model.md §5.4): DENY cross-org access.

    404, not 403 — §3.3: another tenant's resources must not leak their
    existence. Platform admins hold Instance scope, which contains every
    Org (§3.1), so they pass. A resource with no org (None) is denied to
    non-admins by default-deny (§5.1).
    """
    if ctx.is_platform_admin:
        return
    if resource_org_id is None or ctx.org_id != resource_org_id:
        raise HTTPException(status_code=404, detail="Not found.")
