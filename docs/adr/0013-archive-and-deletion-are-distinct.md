> **Status:** Canonical — architectural decision record.

# Archiving a sample is not deleting it

Archive removes a sample from working views and retains everything. Deletion
begins a lifecycle — request, tombstone, vacuum — that ends with the content
physically gone. These are separate operations with separate state, not two
names for one thing.

The code currently collapses them in *naming*, not in data: the archive
endpoint (`routers/samples.py`) writes `samples.is_deleted = TRUE` under the
audit action `ARCHIVE_SAMPLE`, and that is the only call site that writes the
column. The sovereignty lifecycle column `deletion_status` has no writer at
all.

The consequence is a column named `is_deleted` that has only ever meant
"archived", and a deletion lifecycle that exists in the schema with no way to
enter it.

**What is *not* wrong:** `deletion_status = 'ACTIVE'` on an archived row. Once
archive and deletion are accepted as distinct, an archived sample genuinely
has not been deletion-requested, so `ACTIVE` is the correct value. Nothing has
ever been deletion-requested because no code path can do it. The column is
vacuously correct, not lying — a point this ADR originally got wrong and which
cost a planned interim migration before it was caught.

## Consequences

This matters for CARE Principle "Authority to Control": a consent withdrawal
answered with `is_deleted = TRUE` leaves the sequence data sitting in the
bucket. Archiving must never be able to satisfy a deletion request.

`is_deleted` becomes `is_archived`; deletion lives only in `deletion_status`.
The rename ships together with the B-CARE-3 deletion implementation in P0c —
renaming first would silently remove deletion from the API, and implementing
first would leave both representations writable at once.

## Considered options

Mapping `is_deleted = TRUE` onto `DELETION_REQUESTED` was rejected: it would
retroactively reclassify every historical archive as a consent withdrawal.
Retiring `deletion_status` in favour of the boolean was rejected because it
abandons the lifecycle P0b just shipped and cannot express the difference
between tombstoned and vacuumed.

## Enforcement belongs with the implementation, not ahead of it

Enforcement of "VACUUMED means the content is actually gone" must be
mechanical rather than editorial — three documented-but-unenforced rules have
already failed in this repo (`spec.md` §3 contradicted Critical Rule 46 for
months; Phase 24.5's checkboxes stayed stale for four; "no code path writes
both representations" had nothing checking it).

It was originally planned as a standalone CHECK constraint shipped ahead of
the deletion implementation. That was dropped, for two reasons found on
inspection:

- `samples.fastq_r1_uri` is `TEXT NOT NULL` in the baseline migration
  (`5adf11b77c19`) and has never been altered. A constraint requiring content
  columns to be NULL when `VACUUMED` is unsatisfiable against it — no row
  could ever be vacuumed.
- Per Critical Rule 58, those URI columns are deprecated and sample content
  lives in `sample_files` → `file_references`. A single-table CHECK on
  `samples` therefore cannot see the thing it is meant to constrain.

The vacuum implementation is what decides where content lives at vacuum time
and whether `fastq_r1_uri` becomes nullable. The constraint and its
cross-table test are written against that decision, inside `B-CARE-3`, where
they can actually be exercised.
