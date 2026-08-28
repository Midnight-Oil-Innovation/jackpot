> **Status:** Canonical — architectural decision record.

# Keep JACKPOT's own ingest gates; expose the Loculus preprocessing contract as opt-in

`file_detector.py`, `validator.py`, `dlp_scanner.py`, and the
`sra-human-scrubber` integration together form a more thorough ingest path
than Loculus's preprocessing for JACKPOT's surveillance-focused operating
model. Rather than adopt Loculus preprocessing wholesale, JACKPOT keeps
in-process validation as the default and exposes the Loculus pluggable
preprocessing HTTP contract (`/extract-unprocessed-data`,
`/submit-processed-data`) as an opt-in for sophisticated operators.

## Considered options

Adopting the Loculus contract as the only path would have discarded working,
surveillance-specific gates — human-read scrubbing in particular, which no
other platform in the surveyed landscape ships integrated.
