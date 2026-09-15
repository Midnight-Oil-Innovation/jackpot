# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""The container images the test suite pulls, defined once.

CI pre-pulls these with retries before running pytest, because testcontainers
otherwise pulls them lazily mid-run, where a registry hiccup fails the whole
job with a traceback that has nothing to do with the diff. Two incidents in one
week prompted it, and they are not the same kind: `minio/minio` disappeared
when MinIO withdrew the Docker Hub namespace, which no retry can help (that one
was fixed by moving to quay.io); then quay.io 404'd transiently on a tag that
had worked an hour earlier, which is the class retries do fix.

The workflow reads this file by running it (`python tests/container_images.py`)
rather than repeating the names, so the pre-pull list cannot drift away from
what the fixtures actually start. A second copy would fail silently — the tests
would still pass, just without the retry protection, and nobody would notice
until a registry blip reddened an unrelated PR.
"""

from __future__ import annotations

# MinIO moved off Docker Hub; quay.io is their own registry. See #232.
MINIO = "quay.io/minio/minio:RELEASE.2024-09-13T20-26-02Z"

# Third-party personal namespace — same class of withdrawal risk as minio/minio
# had, with no mirror to move to if it happens.
FAKE_GCS = "fsouza/fake-gcs-server:1.49.2"

POSTGRES = "postgres:16"

ALL = (MINIO, FAKE_GCS, POSTGRES)


if __name__ == "__main__":
    print("\n".join(ALL))
