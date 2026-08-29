> **Status:** Reference — clarifies quality_status vs sharing_level orthogonality.

**PRELIMINARY / ANALYZABLE / SUBMITTABLE** describe *what the sample IS* — how complete the metadata is. That's `quality_status`, computed by the validator.

**PRIVATE / LAB / DISCOVERABLE / PUBLIC** describe *who can SEE the sample* — the access control level. That's `sharing_level`, set by the submitting researcher and governed by org policy.

Every sample has both at all times. They're orthogonal:

```
                    PRELIMINARY   ANALYZABLE   SUBMITTABLE
  PRIVATE               ✓             ✓            ✓
  LAB                   ✓             ✓            ✓
  DISCOVERABLE          ✓             ✓            ✓
  PUBLIC                ✓             ✓            ✓
```

A sample can be PRELIMINARY + PRIVATE (lab just uploaded it, still fixing metadata) or SUBMITTABLE + PUBLIC (fully curated, openly accessible).

For DISCOVERABLE specifically: all authenticated users can see a **safe subset** of metadata (organism, date, country/state, source_type, sector, quality_status) — enough to know the sample exists and decide whether to request access. Clinical fields stay masked. To see the full metadata or files, the user submits an access request through the `sample_access` router, which a Lab Director approves or denies.

That's exactly why `sample_access` lands high on the Month 2 priority list — without it, DISCOVERABLE samples are effectively unreachable. Researchers see them in search results but have no way to actually use them.
