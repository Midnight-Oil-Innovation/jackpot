# PHIN VADS snapshot

Static reference data. Nothing in JACKPOT reads it yet.

CDC sunsets **all PHIN systems on 2026-11-30** and has named no successor
(<https://www.cdc.gov/phin/php/sunset/>). The value sets in here are CDC-authored
curation that stops being fetchable on that date, so the snapshot exists to beat
the deadline — the acquisition had one, the integration does not.

Produced by `scripts/pull_phinvads.py` from the FHIR STU3 endpoint at
`https://phinvads.cdc.gov/baseStu3`. Re-run it to refresh, while there is still
something to refresh from.

## Files

| File | What |
|---|---|
| `manifest.json` | Provenance: source, pull timestamp, per-file SHA-256, counts. The only place the counts are written down. |
| `value_sets.ndjson.gz` | Every `ValueSet`, concepts included. One JSON object per line. |
| `code_systems.ndjson.gz` | Every `CodeSystem`, with `concept` emptied and `count` kept. |
| `code_system_concepts/*.json.gz` | Full concept lists, PHIN-authored code systems only. |

Reading one:

```python
import gzip, json
with gzip.open("value_sets.ndjson.gz", "rt", encoding="utf-8") as fh:
    value_sets = [json.loads(line) for line in fh]
```

## What is deliberately absent

Concept lists for **LOINC, SNOMED CT, ICD-10-CM** and the other external
terminologies PHIN VADS republishes. Three reasons, and the first is the one
that matters:

1. They are not PHIN VADS content. They have their own publishers and outlive
   the sunset — nothing is lost by not snapshotting them here.
2. They carry their own redistribution terms. SNOMED CT requires an affiliate
   license; vendoring it into an AGPL-3.0 tree is a licensing decision, not a
   side effect of a data pull.
3. Size. SNOMED CT alone is 47 MB of JSON from this API, LOINC 15 MB.

The line is drawn on **authorship**, not usefulness: concepts are kept for OIDs
under the CDC arc `2.16.840.1.114222`, and dropped otherwise. A value set that
*references* SNOMED still lists the specific concepts in its subset — that
extract is CDC's curation and is kept.

`code_systems.ndjson.gz` keeps `count` for the excluded systems precisely so a
reader can tell "excluded on purpose" from "empty".

## Gzip

The raw value sets are ~84 MB, which every clone of this repository would carry
forever, and GitHub warns past 50 MB per file. NDJSON still streams a record at
a time through `gzip.open`, so nothing is given up for the tenfold saving.
