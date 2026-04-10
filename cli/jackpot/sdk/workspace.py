"""
jackpot.sdk.workspace
~~~~~~~~~~~~~~~~~~~~~
WorkspaceModule — workspace pod utilities.

Accessed via session.workspace.
"""
from __future__ import annotations

from jackpot.core.client import JACKPOTClient


class WorkspaceModule:
    """SDK module for workspace pod utilities."""

    def __init__(self, client: JACKPOTClient) -> None:
        self._client = client

    def add_package(self, package: str) -> None:
        """
        Add a Python package to the workspace environment.
        Appends the package to ~/requirements.txt and installs it immediately
        via pip so it's available in the current session and on future restarts.

        Args:
            package: Package spec (e.g. "biopython==1.83", "scikit-learn>=1.4")

        Example:
            session.workspace.add_package("biopython==1.83")
        """
        from pathlib import Path
        import subprocess

        req_file = Path.home() / "requirements.txt"

        # Append to requirements.txt for persistence across pod restarts
        with req_file.open("a") as f:
            f.write(f"{package}\n")

        # Install immediately in the current session
        result = subprocess.run(
            ["pip", "install", package],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to install {package}:\n{result.stderr}"
            )
        print(f"Installed {package} and added to ~/requirements.txt")

    def session_info(self) -> dict:
        """
        Return information about the current workspace session.
        Includes project_id, lab_id, pod profile, and API URL.
        """
        import os
        return {
            "api_url":    self._client.api_url,
            "project_id": os.environ.get("JACKPOT_PROJECT_ID"),
            "lab_id":     os.environ.get("JACKPOT_LAB_ID"),
            "profile":    os.environ.get("JACKPOT_WORKSPACE_PROFILE", "unknown"),
        }
