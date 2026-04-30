"""
jackpot.sdk.pipelines
~~~~~~~~~~~~~~~~~~~~~
PipelinesModule — launch pipelines and poll for results.

Accessed via session.pipelines:
    run = session.pipelines.launch("nf-core/viralrecon", sample_ids=[...])
    run.wait(poll_interval=30)
    results = run.results()
"""
from __future__ import annotations

import time

from jackpot.core.client import JACKPOTClient


class PipelineRun:
    """Represents a single JACKPOT pipeline run."""

    def __init__(self, data: dict, client: JACKPOTClient) -> None:
        self._data   = data
        self._client = client

    @property
    def run_id(self) -> int:
        return self._data["id"]

    @property
    def status(self) -> str:
        return self._data.get("status", "unknown")

    @property
    def pipeline_name(self) -> str:
        return self._data.get("pipeline_name", "")

    def __repr__(self) -> str:
        return (
            f"PipelineRun(run_id={self.run_id}, "
            f"pipeline={self.pipeline_name!r}, "
            f"status={self.status!r})"
        )

    def refresh(self) -> "PipelineRun":
        """Refresh run status from the API."""
        # TODO: implement when GET /api/v1/pipelines/{run_id} is built
        raise NotImplementedError("refresh() not yet implemented")

    def wait(
        self,
        poll_interval: int = 30,
        timeout: int = 86400,
    ) -> "PipelineRun":
        """
        Block until the pipeline run reaches a terminal state.

        Args:
            poll_interval: Seconds between status checks (default 30)
            timeout: Maximum seconds to wait (default 24 hours)

        Returns:
            Self with refreshed status.
        Raises:
            TimeoutError if timeout is reached.
            JACKPOTError if the pipeline fails.
        """
        # TODO: implement when GET /api/v1/pipelines/{run_id} is built
        raise NotImplementedError("wait() not yet implemented")

    def results(self) -> list[dict]:
        """
        Return structured metrics from the pipeline run.
        Each item is a dict with sample_id and pipeline-specific metrics.
        """
        # TODO: implement when GET /api/v1/pipelines/{run_id}/results is built
        raise NotImplementedError("results() not yet implemented")

    def tasks(self) -> list[dict]:
        """
        Return the Nextflow task list for this run.
        Useful for debugging failed runs.
        """
        # TODO: implement when GET /api/v1/pipelines/{run_id}/tasks is built
        raise NotImplementedError("tasks() not yet implemented")


class PipelinesModule:
    """
    SDK module for pipeline operations.
    Accessed via session.pipelines.
    """

    def __init__(self, client: JACKPOTClient, project_id: int | None) -> None:
        self._client     = client
        self._project_id = project_id

    def launch(
        self,
        pipeline: str,
        sample_ids: list[str],
        params: dict | None = None,
        project_id: int | None = None,
        version: str | None = None,
    ) -> PipelineRun:
        """
        Launch a pipeline on a set of samples.

        Args:
            pipeline: Pipeline name or URI (e.g. "nf-core/viralrecon",
                     "GHRU assembly", or "github.com/myorg/mypipeline")
            sample_ids: List of JACKPOT sample IDs to process
            params: Pipeline parameters to override (optional)
            project_id: Project to associate the run with
                       (defaults to session project_id)
            version: Specific pipeline version/revision to use
                    (defaults to latest)

        Returns:
            PipelineRun object. Call .wait() to block until completion.
        """
        # TODO: implement when POST /api/v1/pipelines/launch is built
        raise NotImplementedError(
            "launch() will be implemented with the pipeline launch endpoint"
        )

    def list(
        self,
        project_id: int | None = None,
        status: str | None = None,
    ) -> list[PipelineRun]:
        """
        List pipeline runs for a project.

        Args:
            project_id: Filter by project (defaults to session project_id)
            status: Filter by status (queued, running, completed, failed)
        """
        # TODO: implement when GET /api/v1/pipelines/ is built
        raise NotImplementedError("list() not yet implemented")

    def get(self, run_id: int) -> PipelineRun:
        """Retrieve a specific pipeline run by ID."""
        # TODO: implement when GET /api/v1/pipelines/{run_id} is built
        raise NotImplementedError("get() not yet implemented")
