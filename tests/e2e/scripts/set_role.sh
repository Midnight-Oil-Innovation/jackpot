#!/usr/bin/env bash
# E-1 — alias for dev_login.sh for callers who think in role-switches.
#
# This is the recommended caller from the UAT walkthrough, where each
# per-role section starts with "set the active role to <X>". The
# semantics are identical to dev_login.sh: hits POST /auth/dev-login,
# mutates the cached settings.mock_user_email, returns the user body.
#
# Usage
# -----
#   set_role.sh <email> <role> [<lab_id>]
#
# Example
# -------
#   set_role.sh director@example.org "Lab Director" 1
set -euo pipefail
exec "$(dirname "$0")/dev_login.sh" "$@"
