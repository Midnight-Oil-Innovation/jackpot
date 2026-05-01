# Production Deploy Runbook (DEPLOY-1)

This document covers the manual approval gate that protects production
deploys for any JACKPOT instance. It is operator-agnostic — the
GCP project ID, GKE cluster, namespace, reviewer list, and approver
identities are all per-instance configuration.

## Architecture

```
┌────────────────┐     ┌──────────────────────────┐     ┌──────────────┐
│ workflow_      │     │ GitHub Actions           │     │ Production   │
│ dispatch       │ →   │ `production` environment │ →   │ GKE cluster  │
│ (any maintainer│     │ blocks until a Required  │     │ (Helm        │
│  with Actions  │     │ Reviewer approves        │     │  upgrade)    │
│  perms)        │     │                          │     │              │
└────────────────┘     └──────────────────────────┘     └──────────────┘
```

The approval gate is **GitHub Actions environments + required reviewers**.
The workflow file (`.github/workflows/deploy-production.yml`) declares
`environment: name: production`; the per-environment Required Reviewers
list is configured in the repo's Settings UI (cannot be set in the YAML).

## One-time setup per instance

### 1. Create the `production` environment in GitHub

Repo → **Settings → Environments → New environment** → name it
`production`. Then under "Deployment protection rules":

- Tick **Required reviewers** and add at least one (recommend two:
  primary + backup) GitHub user/team. These are the only humans who can
  approve a production deploy.
- Optionally set a **Wait timer** (10–60 minutes) for an extra "are you
  sure?" buffer.
- Optionally restrict **Deployment branches** to `main` (default), or to
  protected release tags.

### 2. Configure environment-scoped vars and secrets

Under the same `production` environment in Settings, set:

| Var or Secret | Type | Purpose |
|---|---|---|
| `GCP_PROJECT_ID` | var | The production project (different from staging) |
| `GCP_CLUSTER_NAME` | var | The production GKE cluster |
| `GCP_NAMESPACE` | var | Production namespace (typically `jackpot-prod`) |
| `GCP_REGION` | var | e.g. `us-central1` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | var | Production WIF provider |
| `GCP_DEPLOY_SA` | var | Production deploy service account |
| `GCP_SECRET_PREFIX` | var | Prefix used in Secret Manager for the prod set |

These override any repo-level vars when the workflow runs in the
`production` environment.

### 3. Create `deploy/helm/jackpot-api/values-production.yaml`

The production deploy workflow points at this file. It does not yet
exist in the repo (production is not yet deployed for any instance);
each operator creates it as part of going-live, copying
`values-staging.yaml` and changing image registry, replica counts,
resource requests, and CORS origins for the production hostname.

## Approval procedure (every deploy)

### Who can approve

Anyone listed as a Required Reviewer for the `production` environment.
The approver MUST NOT be the same person who triggered the workflow
(GitHub enforces this when the environment is configured to require
"Prevent self-review" — recommended).

### What an approver should verify before clicking "Approve"

1. **Staging is green.** The same image tag has already deployed
   successfully to staging. Check the most recent `deploy-staging` run
   was successful and the image tag matches the production
   `workflow_dispatch` `image_tag` input.
2. **Smoke test passed in staging.** The staging deploy includes a
   `/health` smoke test (`scripts/staging_smoke_test.sh`); confirm it
   exited 0.
3. **Migration review.** If the diff between the currently deployed
   production image and the new tag includes Alembic migrations, read
   each migration. Watch for `op.drop_*`, lock-acquiring statements
   without `IF EXISTS` guards, or unconditional data backfills against
   large tables.
4. **Deploy reason is sane.** Read the `reason` input on the
   workflow_dispatch. If it's blank, vague, or "fix prod", ask before
   approving.
5. **Time of week / time of day.** Avoid approving deploys late on
   Friday or right before a weekend / holiday unless the reason
   specifically requires it.
6. **Runbook / PITR is current.** Confirm `docs/deploy/pitr-restore-drill.md`
   was last drilled within the past 90 days (DEPLOY-2). If not, run
   the drill before approving non-trivial schema changes.

### What an approver should NOT do

- Approve their own deploy.
- Approve based on Slack chatter alone — verify the staging run yourself.
- Bypass the gate by triggering a manual `kubectl rollout` outside the
  workflow.

## Cancelling a deploy mid-flight

If a deploy is running and you need to stop it (alerts firing, smoke
test failing partway, an approver realizes they shouldn't have
clicked):

1. **From GitHub:** open the running workflow, click **Cancel
   workflow**. The Helm upgrade will receive SIGTERM at the next step
   boundary; Helm will leave the release in whatever state it was in.
2. **Verify cluster state:** `helm -n <NAMESPACE> history jackpot-api`
   — note whether the upgrade reached `deployed` status or is `pending`.
3. If `pending`: `helm -n <NAMESPACE> rollback jackpot-api <previous-rev>`
   to revert to the last good release.

## Rollback procedure

After the deploy reaches the cluster but before the smoke test confirms
health, both the alembic pre-upgrade hook and the new Deployment may
have applied changes. Roll back in this order:

1. **Application rollback:** `helm -n <NAMESPACE> rollback jackpot-api`.
   Helm reverts the Deployment (and any ConfigMaps it manages) to the
   previous chart revision. New pods spin up with the prior image.
2. **Alembic downgrade:** if the new revision included migrations and
   they need to be reversed:
   ```
   kubectl -n <NAMESPACE> run alembic-downgrade --rm -i --tty \
     --image=<previous-image> --restart=Never \
     --overrides='{"spec":{"serviceAccountName":"jackpot-api"}}' \
     --command -- uv run alembic downgrade <prev-revision>
   ```
   Run this **only** if the migrations are reversible and downgrade was
   tested in staging. Many production migrations are not safely
   reversible (e.g. column drops); in that case the right move is to
   roll forward with a new fix, not downgrade.
3. **Verify health:** `curl -k https://api.<production-host>/health`
   should return `{"status":"ok","database":"connected"}`.
4. **Post-mortem:** open an issue in the repo within 24h. Note the
   commit, the trigger, the reason, the approver, and what went wrong.

## Audit trail

Every production deploy leaves four records:

1. The GitHub Actions run (in the repo's Actions tab — includes the
   `image_tag`, `reason`, the approver's GitHub identity, the
   timestamp).
2. Two `::notice::` lines in the run log (deploy reason + approver),
   surfaced in the Actions UI for quick scanning.
3. Helm history: `helm -n <NAMESPACE> history jackpot-api`.
4. The cluster's audit log (GKE control-plane audit logging if enabled
   in Terraform).

These should be cross-checked monthly to confirm no out-of-band
deploys happened.

## See also

- `docs/deploy/pitr-restore-drill.md` (DEPLOY-2) — quarterly restore
  drill that the production gate references.
- `docs/staging_access.md` — staging environment troubleshooting
  (the operator-agnostic version linked from the README runbook
  table; an older, narrower file at `deploy/docs/staging_access.md`
  remains for historical reference but should not be referenced for
  new operators).
- `.github/workflows/deploy-production.yml` — the workflow this runbook
  documents.
