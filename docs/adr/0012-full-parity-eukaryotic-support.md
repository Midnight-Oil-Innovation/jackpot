> **Status:** Canonical — architectural decision record.

# Eukaryotic pathogens get full parity, not a bolt-on

Support spans eight pathogen groups — Plasmodium, Leishmania, Trypanosoma,
Schistosoma, soil-transmitted helminths, filarial nematodes,
Cryptosporidium/Giardia, Toxoplasma/Entamoeba — with the same first-class
treatment bacterial and viral pathogens receive: organism enum values,
dedicated result tables, default zoo pipelines, dashboards, and
eukaryotic-aware tier validation.

The alternative — treating eukaryotes as a special case handled by generic
result blobs — would have made drug-resistance and typing results unqueryable,
which is the main thing operators need from them.

## Status

Schema landed in P0b (`c871b28bbdab`): enums, samples columns, and 38 organism
values. The eight dedicated result tables are deferred to their pipelines in
Phase 28. Eukaryotic-aware tier rules in `validator.py` are **not yet
implemented**.
