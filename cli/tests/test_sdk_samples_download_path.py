# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""The download filename comes from the API response, so it is untrusted.

``Sample.download_fastq`` must land the bytes inside ``dest_dir`` whatever
the server calls the file — a traversing or absolute name would otherwise
let the API write anywhere the CLI user can.
"""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from jackpot.core.client import JACKPOTClient
from jackpot.sdk.samples import Sample

API_URL = "http://testserver"


@pytest.mark.parametrize(
    "served_name",
    ["../../escaped_R1.fastq.gz", "/etc/cron.d/evil_R1.fastq.gz"],
)
def test_download_stays_inside_dest_dir(served_name, tmp_path, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=f"{API_URL}/api/v1/samples/EX-1/files",
        json={"success": True, "data": [{"id": 1, "filename": served_name}]},
    )
    httpx_mock.add_response(
        url=f"{API_URL}/api/v1/samples/EX-1/download?file_id=1",
        json={"presigned_url": f"{API_URL}/signed/blob"},
    )
    httpx_mock.add_response(url=f"{API_URL}/signed/blob", content=b"ACGT")
    dest = tmp_path / "downloads"
    dest.mkdir()

    out = Sample(
        {"sample_id": "EX-1"}, JACKPOTClient(api_url=API_URL, token="jk_t")
    ).download_fastq(r1=True, dest_dir=dest)

    assert out.parent == dest.resolve()
    assert out.read_bytes() == b"ACGT"
