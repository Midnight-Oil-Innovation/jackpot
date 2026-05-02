"""Tests for validator.compute_scrub_status — moved here from
routers/ingest.py per Critical Rule 18 (P0e E.1)."""

from backend.validator import compute_scrub_status


class TestComputeScrubStatus:
    def test_fastq_pair_returns_pending(self):
        # Both R1 and R2 are FASTQ — scrubber will run.
        result = compute_scrub_status({"S1_R1.fastq.gz": "gs://x", "S1_R2.fastq.gz": "gs://y"})
        assert result == "PENDING"

    def test_single_fastq_returns_pending(self):
        result = compute_scrub_status({"S1_R1.fastq.gz": "gs://x"})
        assert result == "PENDING"

    def test_fasta_only_returns_skipped(self):
        # Already-assembled consensus — nothing to scrub.
        result = compute_scrub_status({"S1.consensus.fasta": "gs://x"})
        assert result == "SKIPPED"

    def test_mixed_fastq_and_fasta_returns_pending(self):
        # Even one FASTQ flips it to PENDING.
        result = compute_scrub_status({"S1_R1.fastq.gz": "gs://x", "S1.consensus.fasta": "gs://y"})
        assert result == "PENDING"

    def test_accepts_list_of_filenames(self):
        # Convenience: callers can pass a flat list instead of a dict.
        result = compute_scrub_status(["S1_R1.fastq.gz", "S1_R2.fastq.gz"])
        assert result == "PENDING"

    def test_empty_input_returns_skipped(self):
        # No files = nothing to scrub.
        assert compute_scrub_status({}) == "SKIPPED"
        assert compute_scrub_status([]) == "SKIPPED"

    def test_unknown_extension_returns_skipped(self):
        # Anything that isn't FASTQ doesn't trigger the scrubber.
        result = compute_scrub_status({"unknown.bam": "gs://x"})
        assert result == "SKIPPED"
