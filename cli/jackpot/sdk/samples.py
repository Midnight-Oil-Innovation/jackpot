"""
jackpot.sdk.samples
~~~~~~~~~~~~~~~~~~~
SamplesModule — search, retrieve, and download samples.

Accessed via session.samples:
    df = session.samples.search(organism="Salmonella enterica")
    sample = session.samples.get("AZ-2026-001")
    path = sample.download_fastq(r1=True)
"""
from __future__ import annotations

from pathlib import Path

from jackpot.core.client import JACKPOTClient


class Sample:
    """Represents a single JACKPOT sample record."""

    def __init__(self, data: dict, client: JACKPOTClient) -> None:
        self._data   = data
        self._client = client

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(f"Sample has no attribute '{name}'")

    def __repr__(self) -> str:
        return (
            f"Sample(sample_id={self._data.get('sample_id')!r}, "
            f"organism={self._data.get('organism_name')!r}, "
            f"quality_status={self._data.get('quality_status')!r})"
        )

    def download_fastq(
        self,
        r1: bool = True,
        dest_dir: str | Path = ".",
    ) -> Path:
        """
        Download the scrubbed FASTQ file to dest_dir.
        Returns the local path of the downloaded file.

        Raises ScrubPendingError if the file is not yet available.
        """
        # TODO: implement in Month 1 — get presigned URL from
        # GET /api/v1/samples/{sample_id}/files, stream to dest_dir
        raise NotImplementedError(
            "download_fastq() will be implemented with the sample files endpoint"
        )

    def to_dict(self) -> dict:
        return dict(self._data)


class SamplesModule:
    """
    SDK module for sample operations.
    Accessed via session.samples.
    """

    def __init__(self, client: JACKPOTClient, project_id: int | None) -> None:
        self._client     = client
        self._project_id = project_id

    def search(
        self,
        organism: str | None = None,
        source_type: str | None = None,
        sector: str | None = None,
        quality_status: str | None = None,
        surveillance_relevant: bool | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        project_id: int | None = None,
        lab_id: int | None = None,
        page: int = 1,
        per_page: int = 200,
    ) -> list[Sample]:
        """
        Search samples. Returns a list of Sample objects.

        Args:
            organism: Filter by organism name (partial match)
            source_type: Filter by source type (isolate, wastewater, etc.)
            sector: Filter by One Health sector
            quality_status: Filter by tier (PRELIMINARY, ANALYZABLE, SUBMITTABLE)
            surveillance_relevant: Filter by surveillance_relevant flag
            date_from: Filter by date_collected >= date_from (YYYY-MM-DD)
            date_to: Filter by date_collected <= date_to (YYYY-MM-DD)
            project_id: Filter by project (defaults to session project_id)
            lab_id: Filter by lab
            page: Page number (1-indexed)
            per_page: Results per page (max 200)
        """
        params = {
            k: v for k, v in {
                "organism_name":         organism,
                "source_type":           source_type,
                "sector":                sector,
                "quality_status":        quality_status,
                "surveillance_relevant": surveillance_relevant,
                "date_from":             date_from,
                "date_to":               date_to,
                "project_id":            project_id or self._project_id,
                "lab_id":                lab_id,
                "page":                  page,
                "per_page":              per_page,
            }.items()
            if v is not None
        }

        # TODO: implement in Month 1 — calls GET /api/v1/samples/
        raise NotImplementedError(
            "search() will be implemented when GET /api/v1/samples/ is built"
        )

    def get(self, sample_id: str) -> Sample:
        """
        Retrieve a single sample by ID.
        Raises NotFoundError if not found.
        Raises AuthError if not accessible.
        """
        # TODO: implement in Month 1 — calls GET /api/v1/samples/{sample_id}
        raise NotImplementedError(
            "get() will be implemented when GET /api/v1/samples/{id} is built"
        )

    def register_from_workspace(
        self,
        file_path: str | Path,
        metadata: dict,
    ) -> Sample:
        """
        Register a file from the workspace PVC into JACKPOT.
        Copies the file from the workspace to the JACKPOT sequences bucket
        server-side via a sidecar container — no local download required.

        Args:
            file_path: Path to file on the workspace PVC
            metadata: Sample metadata dict (same fields as GUI upload form)
        """
        # TODO: implement in Month 2 — calls POST /api/v1/ingest/workspace-promote
        raise NotImplementedError(
            "register_from_workspace() will be implemented with the workspace "
            "promotion endpoint"
        )
