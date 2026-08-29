> **Status:** Canonical — architectural decision record.

# JACKPOT integrates with the surrounding stack rather than replacing it

JACKPOT occupies the genomics layer between LIMS below and downstream analysis
platforms above (NCBI Pathogen Detection, Pathoplexus, Pathogenwatch,
Nextstrain). It integrates with case-level epidemiology systems — NBS, eCR,
AIMS — and does not attempt to replace them.

This is a scope boundary as much as an architecture statement: features that
would duplicate a LIMS or a case-management system are out of scope by
construction, however reasonable they look in isolation.
