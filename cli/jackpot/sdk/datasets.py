"""
jackpot.sdk.datasets
~~~~~~~~~~~~~~~~~~~~
DatasetsModule — create, manage, and register datasets.

Accessed via session.datasets.
"""

from __future__ import annotations

from jackpot.core.client import JACKPOTClient


class DatasetsModule:
    """SDK module for dataset operations."""

    def __init__(self, client: JACKPOTClient, project_id: int | None) -> None:
        self._client = client
        self._project_id = project_id

    def register_from_notebook(
        self,
        name: str,
        sample_ids: list[str],
        description: str = "",
        sharing_level: str = "LAB",
        project_id: int | None = None,
    ) -> dict:
        """
        Register a dataset from the current notebook's analysis.
        Creates a project-level dataset in JACKPOT linked to the given samples.
        This is the primary way to bring notebook analysis results back into
        the JACKPOT catalog so they can be shared and cited.

        Args:
            name: Dataset name
            sample_ids: Sample IDs included in this dataset
            description: Description of the analysis
            sharing_level: PRIVATE, LAB, DISCOVERABLE, or PUBLIC
            project_id: Project to associate with (defaults to session project_id)

        Returns:
            Dataset dict with id, name, sharing_level, created_at
        """
        # TODO: implement when POST /api/v1/datasets/ is built
        raise NotImplementedError(
            "register_from_notebook() will be implemented with the datasets endpoint"
        )

    def list(self, project_id: int | None = None) -> list[dict]:
        """List datasets for a project."""
        raise NotImplementedError("list() not yet implemented")

    def get(self, dataset_id: int) -> dict:
        """Retrieve a specific dataset."""
        raise NotImplementedError("get() not yet implemented")
