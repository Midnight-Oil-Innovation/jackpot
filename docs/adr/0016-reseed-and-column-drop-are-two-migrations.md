> **Status:** Canonical — architectural decision record.

# The reseed and the column drop are two migrations

`access_model.md` §10.2 originally put the APGAP reseed and the removal of
`users.is_platform_admin`, `users.is_data_analyst`, and the PermissionGroups
enum in a single migration. They are split: an additive migration issues the
grants, and the M2 cutover migration re-runs the reseed, flips the guards, and
drops the legacy columns last.

## Why the original constraint does not require one migration

The stated reason for bundling them was that "there is never a window where
both the boolean and the grants are authoritative." That property survives the
split, because the migration boundary was never what provided it.

Authority comes from what *reads* the data. Between the two migrations,
`permissions.py`'s ladder still decides every request and nothing calls
`permit()` on a route — the grants exist and are inert. Inert data is not an
authority. A dual-authoritative window would require two things deciding, which
is precisely what the cutover migration prevents by flipping the guards and
dropping the columns in one step.

## What the split buys

The reseed is the one step whose output nobody can inspect under the original
plan: it reads the old roles and the columns are gone in the same transaction.
Splitting it means the grant rows can be examined before anything irreversible
happens — counts per preset, the three divergence counts from the pre-flight
guard (ADR-adjacent, `active_backlog.yaml` M2 deliverable (e)), spot-checks
against known users on whatever deployment is being cut over.

This matters more here than it would elsewhere because M2 has no rollback path
by design (§10, greenfield, no shim). Safety comes from having proven each
piece beforehand, and the reseed was the last piece that could not be proven
against real rows.

## Consequences

Memberships created through the old paths between the two migrations would have
no grants. Covered by re-running `reseed()` inside the cutover migration: it is
idempotent by construction, using `ON CONFLICT DO NOTHING` against the
`(principal_id, capability, scope_ref)` unique index. That index is created by
the additive migration rather than the cutover one — the dedup depends on it,
and `test_reseed_duplicates_without_index` pins the failure mode when it is
absent.

Cutover order becomes: re-run reseed → flip route guards → flip list endpoints
to `visibility_sql_clause` → drop the columns and enum **last**, so a failure at
any earlier step rolls back with the old model intact.

Cost: one extra migration in the chain, and a departure from the sequencing
`access_model.md` §10.2 specified. §10.2 is amended in place to describe the
split and to point here.
