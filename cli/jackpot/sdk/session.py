"""
jackpot.sdk.session
~~~~~~~~~~~~~~~~~~~
Session — the entry point for all JACKPOT SDK usage.

Usage in a workspace notebook:
    from jackpot import Session

    # Picks up JACKPOT_API_URL and JACKPOT_API_TOKEN env vars automatically.
    # These are pre-set in all JACKPOT workspace pods via context injection.
    session = Session()

    # Explicitly specify credentials (for non-workspace use):
    session = Session(api_url="https://api.your-jackpot-instance.org", token="jk_live_...")

    # Work with a specific project (overrides JACKPOT_PROJECT_ID):
    session = Session(project_id=42)
"""

from __future__ import annotations

import os

from jackpot.cli.config import get_client_credentials
from jackpot.core.client import JACKPOTClient
from jackpot.core.exceptions import ConfigError
from jackpot.sdk.datasets import DatasetsModule
from jackpot.sdk.files import FilesModule
from jackpot.sdk.pipelines import PipelinesModule
from jackpot.sdk.references import ReferencesModule
from jackpot.sdk.samples import SamplesModule
from jackpot.sdk.sra import SRAModule
from jackpot.sdk.submissions import SubmissionsModule
from jackpot.sdk.workspace import WorkspaceModule


class Session:
    """
    JACKPOT SDK session. All SDK operations go through this object.

    Credentials resolution order:
      1. Explicit api_url / token arguments
      2. JACKPOT_API_URL / JACKPOT_API_TOKEN environment variables
         (pre-set in workspace pods via context injection)
      3. ~/.jackpot/config.toml (CLI config file)

    Project and lab context resolution order:
      1. Explicit project_id / lab_id arguments
      2. JACKPOT_PROJECT_ID / JACKPOT_LAB_ID environment variables
      3. None (operations that require project_id will raise ValueError)
    """

    def __init__(
        self,
        api_url: str | None = None,
        token: str | None = None,
        project_id: int | None = None,
        lab_id: int | None = None,
    ) -> None:
        # Resolve credentials
        if api_url and token:
            self._api_url = api_url
            self._token = token
        else:
            try:
                self._api_url, self._token = get_client_credentials()
            except ConfigError:
                raise ConfigError(
                    "No JACKPOT credentials found.\n"
                    "In a workspace pod, credentials are injected automatically.\n"
                    "Outside a pod: set JACKPOT_API_URL + JACKPOT_API_TOKEN,\n"
                    "or run `jackpot auth login` to configure the CLI."
                )

        # Resolve project/lab context
        self.project_id = project_id or _int_env("JACKPOT_PROJECT_ID")
        self.lab_id = lab_id or _int_env("JACKPOT_LAB_ID")

        # Construct shared HTTP client
        self._client = JACKPOTClient(api_url=self._api_url, token=self._token)

        # Initialise SDK modules — lazy instantiation via properties below
        self._samples = None
        self._pipelines = None
        self._datasets = None
        self._sra = None
        self._references = None
        self._workspace = None
        self._files = None
        self._submissions = None

    # ── Module accessors ────────────────────────────────────────────────────

    @property
    def samples(self) -> SamplesModule:
        if self._samples is None:
            self._samples = SamplesModule(self._client, self.project_id)
        return self._samples

    @property
    def pipelines(self) -> PipelinesModule:
        if self._pipelines is None:
            self._pipelines = PipelinesModule(self._client, self.project_id)
        return self._pipelines

    @property
    def datasets(self) -> DatasetsModule:
        if self._datasets is None:
            self._datasets = DatasetsModule(self._client, self.project_id)
        return self._datasets

    @property
    def sra(self) -> SRAModule:
        if self._sra is None:
            self._sra = SRAModule(self._client)
        return self._sra

    @property
    def references(self) -> ReferencesModule:
        if self._references is None:
            self._references = ReferencesModule(self._client)
        return self._references

    @property
    def workspace(self) -> WorkspaceModule:
        if self._workspace is None:
            self._workspace = WorkspaceModule(self._client)
        return self._workspace

    @property
    def files(self) -> FilesModule:
        if self._files is None:
            self._files = FilesModule(self._client)
        return self._files

    @property
    def submissions(self) -> SubmissionsModule:
        if self._submissions is None:
            self._submissions = SubmissionsModule(self._client)
        return self._submissions

    # ── Representation ──────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"Session(api_url={self._api_url!r}, "
            f"project_id={self.project_id}, "
            f"lab_id={self.lab_id})"
        )


def _int_env(var: str) -> int | None:
    """Read an environment variable as int, return None if not set or invalid."""
    val = os.environ.get(var)
    if val is None:
        return None
    try:
        return int(val)
    except ValueError:
        return None
