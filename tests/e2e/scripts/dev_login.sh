#!/usr/bin/env bash
# E-1 — switch the active mock user via POST /api/v1/auth/dev-login.
#
# Usage
# -----
#   dev_login.sh <email> [<role>] [<lab_id>]
#
# Examples
# --------
#   dev_login.sh admin@example.org "Platform Admin"
#   dev_login.sh director@example.org "Lab Director" 1
#   dev_login.sh reader@example.org "Lab Reader" 1
#
# Roles
# -----
#   Platform Admin       (no lab_id)
#   Data Analyst         (no lab_id)
#   Lab Director         (lab_id required if more than one lab; defaults to 1)
#   Lab Collaborator     (")
#   Lab Reader           (")
#   Bioinformatics User  (")
#
# Successful output
# -----------------
# Pretty-printed JSON body with `user.email`, `active_role`, and the
# resulting `membership` block (or `null` for global roles).
#
# Exit codes
# ----------
#   0  switch succeeded
#   1  argument or HTTP error
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: dev_login.sh <email> [<role>] [<lab_id>]" >&2
  exit 1
fi

email="$1"
role="${2:-}"
lab_id="${3:-}"

api_url="${JACKPOT_API_URL:-http://localhost:8000}"

payload=$(python3 -c "
import json, sys
out = {'email': sys.argv[1]}
if sys.argv[2]:
    out['role'] = sys.argv[2]
if sys.argv[3]:
    out['lab_id'] = int(sys.argv[3])
print(json.dumps(out))
" "$email" "$role" "$lab_id")

resp=$(curl -fsS -X POST "${api_url%/}/api/v1/auth/dev-login" \
  -H 'Content-Type: application/json' \
  -d "$payload")

echo "$resp" | python3 -m json.tool
