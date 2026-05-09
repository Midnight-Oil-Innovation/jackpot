"""Phase P0h H-5 — execution-profile work_dir validation.

A Slurm profile's ``work_dir`` must be a path visible to both the API
server (which renders the per-run config) and the compute nodes (which
execute Nextflow). When the operator misconfigures the path — typo,
missing NFS mount, wrong-side absolute path — every launch silently
queues a run that immediately fails on the cluster.

This module ships the validation predicate the operator's tooling
calls before persisting a profile. ``validate_work_dir_locally`` runs
on the API server and answers the half of the question the API host
can answer: does the path exist, is it a directory, can we write to
it? Cluster-side reachability (does the same path resolve identically
on the compute nodes) is the ``jackpot doctor`` command's job —
``jackpot doctor`` calls this function plus shells out to ``srun``.

G-5 integration TODO
--------------------

When P0g G-5 ships profile CRUD HTTP endpoints, wire
``validate_work_dir_locally`` into the POST / PATCH handlers so a
profile that fails validation is rejected at create / edit time
rather than at launch time. Until then, operators create profiles via
direct DB seed and run ``jackpot doctor`` separately to verify.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

# fsspec-supported URI schemes that ``validate_work_dir_locally`` does
# not stat — local filesystem checks don't apply to gs://, s3://, etc.
# (the cluster-side check still applies; that lives in ``jackpot
# doctor``, not here).
_REMOTE_SCHEMES: frozenset[str] = frozenset({"gs", "s3", "az", "abfs"})


@dataclass(frozen=True)
class ValidationFinding:
    """One observation about a profile's work_dir.

    ``severity`` is ``"warning"`` for things an operator should know
    about (path exists but isn't writable by the API user) and
    ``"error"`` for things that will definitely break (path missing,
    not a directory). The CLI maps "error" to a non-zero exit code.
    """

    severity: str  # "error" | "warning" | "info"
    code: str
    message: str


def _scheme_of(work_dir: str) -> str:
    """Return the URI scheme prefix (e.g. ``"gs"``, ``"s3"``, ``"file"``)
    or an empty string for a bare local path."""
    if "://" in work_dir:
        return work_dir.split("://", 1)[0].lower()
    return ""


def validate_work_dir_locally(work_dir: str) -> list[ValidationFinding]:
    """Inspect ``work_dir`` from the API server's perspective.

    Returns a list of findings; the empty list means everything looks
    reasonable. Bare paths and ``file://`` URIs are checked on the local
    filesystem; cloud URIs (``gs://``, ``s3://``, ``az://``, ``abfs://``)
    short-circuit to a single info-level finding because the local
    process has no jurisdiction over remote object stores.

    Findings the function emits:

    - ``MISSING`` (error) — the path does not exist.
    - ``NOT_A_DIRECTORY`` (error) — the path exists but is a file.
    - ``NOT_WRITABLE`` (warning) — the path exists and is a directory
      but the API user cannot create files inside it. The check is a
      ``tempfile.mkstemp`` + immediate unlink so symlink-following
      ACLs and quota-style errors are surfaced.
    - ``REMOTE_SCHEME`` (info) — the work_dir is a cloud URI; local
      filesystem checks do not apply. ``jackpot doctor`` is still
      meaningful (cluster-side ``srun`` would attempt the same URI).
    - ``EMPTY`` (error) — empty / whitespace-only string.
    """
    if not work_dir or not work_dir.strip():
        return [
            ValidationFinding(
                severity="error",
                code="EMPTY",
                message="work_dir is empty.",
            )
        ]

    scheme = _scheme_of(work_dir)
    if scheme in _REMOTE_SCHEMES:
        return [
            ValidationFinding(
                severity="info",
                code="REMOTE_SCHEME",
                message=(
                    f"work_dir uses '{scheme}://' — local filesystem checks "
                    "do not apply. Use `jackpot doctor` to verify cluster-"
                    "side reachability."
                ),
            )
        ]

    # file:// URIs and bare paths both refer to the local filesystem.
    path_str = work_dir.split("://", 1)[1] if scheme == "file" else work_dir
    path = Path(path_str).expanduser()

    findings: list[ValidationFinding] = []
    if not path.exists():
        findings.append(
            ValidationFinding(
                severity="error",
                code="MISSING",
                message=f"work_dir does not exist on the API server: {path}",
            )
        )
        return findings

    if not path.is_dir():
        findings.append(
            ValidationFinding(
                severity="error",
                code="NOT_A_DIRECTORY",
                message=f"work_dir exists but is not a directory: {path}",
            )
        )
        return findings

    # Probe writability via mkstemp to surface ACL / quota / read-only-
    # mount issues that a bare ``os.access`` would miss.
    try:
        fd, probe = tempfile.mkstemp(prefix=".jackpot_probe_", dir=str(path))
        os.close(fd)
        os.unlink(probe)
    except OSError as exc:
        findings.append(
            ValidationFinding(
                severity="warning",
                code="NOT_WRITABLE",
                message=(
                    f"work_dir is not writable by the API user: {path} "
                    f"({exc.__class__.__name__}: {exc})"
                ),
            )
        )

    return findings


def has_blocking_findings(findings: list[ValidationFinding]) -> bool:
    """Return True if any finding has severity == "error"."""
    return any(f.severity == "error" for f in findings)
