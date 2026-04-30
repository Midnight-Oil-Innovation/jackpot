"""
jackpot.sdk.references
~~~~~~~~~~~~~~~~~~~~~~
ReferencesModule — download reference genomes to workspace.

Accessed via session.references.
Reference genomes are stored on a lab-shared read-only GCS volume
mounted at /ref/{org_slug}/{lab_slug}/ in all workspace pods.
"""

from __future__ import annotations

from pathlib import Path

from jackpot.core.client import JACKPOTClient

# Mount point for the lab-shared reference genome volume in workspace pods
REFERENCE_MOUNT = Path("/ref")


class ReferencesModule:
    """SDK module for reference genome operations."""

    def __init__(self, client: JACKPOTClient) -> None:
        self._client = client

    def list(self, organism: str | None = None) -> list[dict]:
        """
        List available reference genomes.

        Args:
            organism: Filter by organism name (optional)

        Returns:
            List of dicts with accession, organism_name, genome_version, fasta_uri
        """
        # TODO: implement when GET /api/v1/admin/reference-genomes/ is built
        raise NotImplementedError("list() not yet implemented")

    def download(
        self,
        accession: str,
        dest_dir: str | Path | None = None,
    ) -> Path:
        """
        Download a reference genome FASTA to the workspace.

        If the reference is already present on the lab-shared volume at
        /ref/{org}/{lab}/, returns that path directly without downloading.
        Otherwise downloads from GCS to dest_dir.

        Args:
            accession: NCBI RefSeq or GenBank accession (e.g. GCF_000001405.40)
            dest_dir: Local destination (default: /ref/{org}/{lab}/ if available)

        Returns:
            Local path to the FASTA file.
        """
        # TODO: implement in Month 2 — check lab-shared volume first,
        # then fall back to downloading from GCS via presigned URL
        raise NotImplementedError("download() will be implemented with workspace SDK in Month 2")

    def get_path(self, accession: str) -> Path | None:
        """
        Return the local path if the reference genome is already available
        on the lab-shared volume. Returns None if not cached.
        """
        # TODO: implement in Month 2
        raise NotImplementedError("get_path() not yet implemented")
