"""
jackpot.sdk.samples
~~~~~~~~~~~~~~~~~~~
SamplesModule — search, retrieve, and download samples.

Accessed via session.samples:
    df = session.samples.search(organism="Salmonella enterica")
    sample = session.samples.get("EX-2026-001")
    path = sample.download_fastq(r1=True)
"""

from __future__ import annotations

from pathlib import Path

from jackpot.core.client import JACKPOTClient


class Sample:
    """Represents a single JACKPOT sample record."""

    def __init__(self, data: dict, client: JACKPOTClient) -> None:
        self._data = data
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

        Calls `GET /api/v1/samples/{sample_id}/files` to enumerate
        available files for the sample, then `GET /api/v1/samples/{id}/download`
        for the chosen file's bytes (the backend serves the scrubbed
        copy when one exists, raising 409 when the scrubber hasn't
        produced output yet).
        """
        sample_id = self._data.get("sample_id") or self._data.get("id")
        if sample_id is None:
            raise RuntimeError("Sample has neither sample_id nor id; cannot download")

        files_response = self._client.get(f"/api/v1/samples/{sample_id}/files")
        files = (
            files_response if isinstance(files_response, list) else files_response.get("data", [])
        )

        # Pick the R1 vs R2 file. Convention: filenames contain `_R1` / `_R2`
        # suffixes (per backend.file_detector — Critical Rule 11).
        marker = "_R1" if r1 else "_R2"
        chosen = next(
            (f for f in files if marker in f.get("filename", "")),
            None,
        )
        if chosen is None:
            raise FileNotFoundError(
                f"No {'R1' if r1 else 'R2'} file found for sample {sample_id!r}"
            )

        # Download the bytes — the backend's /download endpoint returns
        # a presigned URL or streams the bytes directly depending on
        # storage backend.
        download_response = self._client.get(
            f"/api/v1/samples/{sample_id}/download",
            params={"file_id": chosen.get("id")},
        )
        # Backend returns either bytes (local/MinIO) or a JSON
        # {"presigned_url": "https://..."} (GCS/S3). Handle both.
        dest_path = Path(dest_dir).resolve() / chosen["filename"]
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(download_response, dict) and "presigned_url" in download_response:
            # Stream from the presigned URL.
            import httpx

            with httpx.stream("GET", download_response["presigned_url"]) as r:
                r.raise_for_status()
                with dest_path.open("wb") as f:
                    for chunk in r.iter_bytes(chunk_size=8192):
                        f.write(chunk)
        elif isinstance(download_response, bytes | bytearray):
            dest_path.write_bytes(download_response)
        else:
            raise RuntimeError(
                f"Unexpected /download response type: {type(download_response).__name__}"
            )

        return dest_path

    def to_dict(self) -> dict:
        return dict(self._data)


class SamplesModule:
    """
    SDK module for sample operations.
    Accessed via session.samples.
    """

    def __init__(self, client: JACKPOTClient, project_id: int | None) -> None:
        self._client = client
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
            k: v
            for k, v in {
                "organism_name": organism,
                "source_type": source_type,
                "sector": sector,
                "quality_status": quality_status,
                "surveillance_relevant": surveillance_relevant,
                "date_from": date_from,
                "date_to": date_to,
                "project_id": project_id or self._project_id,
                "lab_id": lab_id,
                "page": page,
                "per_page": per_page,
            }.items()
            if v is not None
        }

        response = self._client.get("/api/v1/samples/", params=params)
        items = response if isinstance(response, list) else response.get("data", [])
        return [Sample(item, self._client) for item in items]

    def get(self, sample_id: str) -> Sample:
        """
        Retrieve a single sample by ID.
        Raises NotFoundError if not found.
        Raises AuthError if not accessible.
        """
        data = self._client.get(f"/api/v1/samples/{sample_id}")
        # Backend returns either the row directly or wrapped in
        # {"data": {...}} per the JACKPOT envelope (Critical Rule 24).
        if isinstance(data, dict) and "data" in data and "sample_id" not in data:
            data = data["data"]
        return Sample(data, self._client)

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
            "register_from_workspace() will be implemented with the workspace promotion endpoint"
        )
