> **Status:** Canonical — architectural decision record.

# BYOP supports four workflow engines, including a non-engine

Bring-your-own-pipeline accepts Nextflow, Snakemake, WDL, and
manifest-wrapped scripts (Bash/Python). The fourth is JACKPOT-specific and
deliberately not a workflow engine: it exists for users who have a working
script and do not want to learn a workflow language.

## Consequences

The manifest path trades away what workflow engines provide — parallelization,
resume, multi-container orchestration — in exchange for a much lower adoption
barrier. Expect manifest pipelines to be single-container and serial; that is
the deal, not a defect to fix later.
