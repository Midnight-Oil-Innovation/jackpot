> **Status:** Canonical — architectural decision record.

# Cloud SQL for PostgreSQL, not a self-managed VM

Scenario C's operational database is Cloud SQL for PostgreSQL 16, not
PostgreSQL installed on a Compute Engine VM. This ADR is written
retroactively — no design doc or discussion thread captured the reasoning
at the time, so this is a reconstruction from the constraints already
committed elsewhere in the codebase, not a decision made fresh here.

## Context

PostgreSQL 16 is the metadata database across all four scenarios (§4,
`docs/architecture.md`). It runs containerized in Scenario A, host-installed
where an operator prefers it, and as Cloud SQL in Scenario C. A VM running
Postgres directly was the only alternative actually available on GCP —
Cloud SQL and self-managed are the two ways to run Postgres on that
platform; there was never a third managed-Postgres option in scope.

## Decision

Use Cloud SQL for PostgreSQL in Scenario C. Never run production Postgres
on a bare Compute Engine VM.

## Rationale

Three constraints already written into this codebase point the same
direction, independently of each other:

- **Critical Rule 35** requires PITR never be disabled and calls it "the
  primary defense against bad migrations." Cloud SQL provides automated
  backups and point-in-time recovery as a managed feature. A self-managed
  VM would require building and maintaining the equivalent (WAL archiving,
  a tool like pgBackRest, tested restore procedure) as application-team
  responsibility rather than infrastructure the platform already provides.
- **Critical Rule 37** forbids manual GCP console configuration outside
  Terraform for storage, on the grounds that hand-operated infrastructure
  drifts from IaC. The same argument applies to a hand-administered
  database VM: OS patching, Postgres version upgrades, and failover are
  now operational surface the team owns instead of config GCP manages.
  §16.4 of `docs/architecture.md` specifies "highly-available regional
  configuration for production" — Cloud SQL exposes that as a
  configuration flag; replicating synchronous standby and automatic
  failover on a VM (Patroni or repmgr plus a floating IP) is a
  nontrivial project in itself.
- **Team shape.** The frontend architecture section of `CLAUDE.md`
  describes a solo developer on a 3-month prototype timeline. Cloud SQL's
  per-vCPU premium over a bare VM buys out of the ops labor (patching,
  backup verification, failover drills) that a team this size does not
  have slack for.

## Consequences

Migration paths (local Postgres to Cloud SQL) are a connection-string
change and nothing else, per the Tech Stack section of `CLAUDE.md` — this
only holds because Scenario C never diverges into VM-specific operational
tooling that Scenario A's containerized Postgres wouldn't also need.

Cost is materially higher per compute unit than a self-managed VM. This
ADR treats that premium as bought-down operational risk, not overhead to
optimize away — do not "fix" it by moving to a VM without revisiting the
PITR, HA, and patching obligations that decision would reopen.

## Considered options

**Self-managed PostgreSQL on a Compute Engine VM.** Rejected: shifts PITR,
patching, and HA failover from a managed feature to team-owned operational
work, against a solo-developer team shape and Rule 35's requirement that
PITR never lapse.

**A different managed Postgres provider outside GCP** (e.g. a
Postgres-as-a-service vendor). Not seriously considered — out of scope for
a GCP-native Scenario C whose object storage, IAM, and compute are already
GCP services; introducing a second cloud vendor for the database alone
would fragment the credential and networking model Rule 62 and Rule 37
already establish.
