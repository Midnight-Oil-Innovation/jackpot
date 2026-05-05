# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Public-safe deployment-settings exposure.

The Streamlit UI and any other unauthenticated frontend asset can call
``GET /api/v1/settings/public`` to learn which feature flags are turned
on for this deployment. The response is intentionally minimal — only
flags that gate UI behaviour land here. Anything secret-flavoured
(credentials, internal endpoints, infrastructure identifiers) stays
out.

Today this surfaces I-3 backend-execution settings; future feature
flags follow the same shape.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.config import get_settings
from backend.responses import success

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("/public")
def get_public_settings():
    """Return the operator-safe subset of deployment settings.

    The response is unauthenticated by design — any user agent that can
    reach the API can read it. The set of fields here must therefore
    only contain values that are safe to disclose to anyone with
    network reachability.
    """
    s = get_settings()
    return success(
        data={
            # I-3a/b/c: backend submission execution gates. The UI uses
            # these to decide whether to render the "Execute on backend"
            # button on the submission detail page.
            "allow_backend_submission": s.allow_backend_submission,
            "backend_submission_repos": list(s.backend_submission_repos),
        }
    )
