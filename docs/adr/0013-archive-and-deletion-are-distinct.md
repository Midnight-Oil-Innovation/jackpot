> **Status:** Canonical — architectural decision record.

# Archiving a sample is not deleting it

Archive removes a sample from working views and retains everything. Deletion
begins a lifecycle — request, tombstone, vacuum — that ends with the content
physically gone. These are separate operations with separate state, not two
names for one thing.

The code currently collapses them: the archive endpoint writes
`samples.is_deleted = TRUE` under the audit action `ARCHIVE_SAMPLE`, while the
sovereignty lifecycle column `deletion_status` has no writer at all. That
means an archived sample and a deleted sample are indistinguishable in the
data, and `deletion_status` reports `ACTIVE` for every archived row.

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
