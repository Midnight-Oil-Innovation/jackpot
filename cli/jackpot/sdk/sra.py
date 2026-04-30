"""
jackpot.sdk.sra
~~~~~~~~~~~~~~~
SRAModule — fetch SRA accessions to workspace or import into JACKPOT.

Accessed via session.sra.
"""
from __future__ import annotations

from pathlib import Path

from jackpot.core.client import JACKPOTClient


class SRAModule:
    """SDK module for SRA operations."""

    def __init__(self, client: JACKPOTClient) -> None:
        self._client = client

    def fetch(
        self,
        accession: str,
        dest_dir: str | Path = ".",
        threads: int = 4,
    ) -> list[Path]:
        """
        Download SRA FASTQs to the workspace PVC using fasterq-dump.
        Returns list of local paths to downloaded files.

        In pipeline context, use sra:// URIs instead — they are resolved
        on the compute node without downloading to the workspace.

        Args:
            accession: SRA accession (SRR, ERR, DRR)
            dest_dir: Local destination directory (default: current dir)
            threads: fasterq-dump thread count
        """
        # TODO: implement in Month 2 — shells out to fasterq-dump
        # which is available in the Bioinformatician workspace profile
        raise NotImplementedError(
            "fetch() will be implemented with workspace SDK in Month 2"
        )

    def import_to_jackpot(
        self,
        accession: str,
        metadata: dict | None = None,
        project_id: int | None = None,
    ) -> dict:
        """
        Import an SRA accession into JACKPOT as a sample.
        Fetches metadata from NCBI E-utilities and creates a stub sample record.
        The FASTQ files are stored as sra:// URIs — not physically downloaded
        unless a pipeline needs them.

        Args:
            accession: SRA or BioProject accession
            metadata: Additional metadata to supplement NCBI's metadata
            project_id: Project to associate with

        Returns:
            Sample dict with sample_id, quality_status, ncbi metadata
        """
        # TODO: implement in Month 1 — calls POST /api/v1/ingest/accession
        raise NotImplementedError(
            "import_to_jackpot() will be implemented with the accession import endpoint"
        )
