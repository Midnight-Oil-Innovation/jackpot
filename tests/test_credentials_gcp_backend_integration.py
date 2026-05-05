"""C-1: gated integration test against a real GCP Secret Manager.

Skipped unless JACKPOT_GCP_INTEGRATION_TEST=1. Reads a known-existing
test secret. CI does not run this; operators run it on demand.

Required env to enable:
    JACKPOT_GCP_INTEGRATION_TEST=1
    JACKPOT_GCP_PROJECT_ID=<your-test-project>
    JACKPOT_GCP_TEST_SECRET_KEY=<credential-key>      (e.g. ci_test_secret)
    JACKPOT_GCP_TEST_SECRET_VALUE=<expected-value>    (string the secret stores)
    JACKPOT_GCP_TEST_PREFIX=<prefix>                  (default "jackpot-cred-")
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("JACKPOT_GCP_INTEGRATION_TEST") != "1",
    reason="GCP integration test gated on JACKPOT_GCP_INTEGRATION_TEST=1",
)


def test_real_secret_manager_read():
    from backend.credentials.gcp_backend import GCPSecretManagerBackend

    project = os.environ["JACKPOT_GCP_PROJECT_ID"]
    key = os.environ["JACKPOT_GCP_TEST_SECRET_KEY"]
    expected = os.environ["JACKPOT_GCP_TEST_SECRET_VALUE"]
    prefix = os.environ.get("JACKPOT_GCP_TEST_PREFIX", "jackpot-cred-")
    backend = GCPSecretManagerBackend(project_id=project, secret_prefix=prefix)
    assert backend.get(key) == expected
