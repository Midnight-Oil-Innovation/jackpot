"""Phase P0h H-6 — pre-launch Slurm cluster reachability check.

H-1 through H-3 made it possible to launch a Slurm-targeted pipeline,
but did nothing to detect "the cluster is down" until Nextflow itself
hit the failure on the API host. The receiver / poller would then
mark the run FAILED and the operator would discover the problem only
after a queued sample had been waiting in PENDING for the full Slurm
client timeout (15 minutes for a typical config).

H-6 adds a fast pre-launch probe: when the resolved profile uses the
SLURM executor, run ``sinfo -h`` on the API host with a 10-second
timeout. Failure surfaces as a 400 SLURM_UNREACHABLE with a pointer
to ``jackpot doctor slurm --check-cluster`` so the operator can
diagnose without re-launching.

Cache
-----

A bulk launch (50 samples, 50 launches in 30 seconds) would otherwise
fire 50 ``sinfo`` subprocesses. The cache holds the most-recent
result for ``slurm_reachability_cache_seconds`` (default 60s) per
``(account, partition)`` key. Cluster-state truth doesn't change
mid-second, and 60s is short enough that an operator who fixed an
outage doesn't wait long before launches resume succeeding.

The cache is process-local (stored in module state). Multi-worker
deployments would each maintain their own cache; that's fine, as the
worst case is each worker pays the sinfo cost once per minute.

Test opt-out
------------

Set ``settings.slurm_reachability_check_enabled = False`` to bypass
the probe entirely. ``tests/conftest.py`` flips it off so the
existing SLURM-profile launch tests in ``test_launch_with_profile``
don't grow a sinfo dependency. The new H-6 tests opt back in
explicitly via monkeypatch.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass

from backend.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SlurmReachabilityResult:
    """Outcome of a reachability probe.

    ``reachable=True`` means ``sinfo -h`` returned 0 within the timeout.
    ``code`` is one of:
      - ``"OK"``
      - ``"SINFO_NOT_INSTALLED"``
      - ``"SINFO_FAILED"`` (non-zero exit; ``stderr`` carries detail)
      - ``"SINFO_TIMEOUT"`` (exceeded timeout)
      - ``"DISABLED"`` (settings flag off; no probe ran)
    """

    reachable: bool
    code: str
    detail: str = ""


_OK = SlurmReachabilityResult(reachable=True, code="OK")
_DISABLED = SlurmReachabilityResult(reachable=True, code="DISABLED")


# Cache + a lock so concurrent launches don't race the same probe. The
# cache key is the operator-supplied (account, partition) pair —
# different partitions on the same cluster might be reachable
# differently (e.g. a draining partition fails while compute is up).
_CACHE_LOCK = threading.Lock()
_CACHE: dict[tuple[str | None, str | None], tuple[SlurmReachabilityResult, float]] = {}


def _now() -> float:
    return time.monotonic()


def reset_cache() -> None:
    """Drop the cache. Test-only helper."""
    with _CACHE_LOCK:
        _CACHE.clear()


def _run_sinfo(timeout_s: float) -> SlurmReachabilityResult:
    if shutil.which("sinfo") is None:
        return SlurmReachabilityResult(
            reachable=False,
            code="SINFO_NOT_INSTALLED",
            detail="sinfo binary is not on the API host's PATH.",
        )
    try:
        proc = subprocess.run(  # noqa: S603,S607 — fixed argv, no shell
            ["sinfo", "-h"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return SlurmReachabilityResult(
            reachable=False,
            code="SINFO_TIMEOUT",
            detail=f"sinfo did not return within {timeout_s}s.",
        )
    if proc.returncode != 0:
        return SlurmReachabilityResult(
            reachable=False,
            code="SINFO_FAILED",
            detail=(proc.stderr or proc.stdout or "").strip()[:400],
        )
    return _OK


def check_slurm_reachability(
    *,
    account: str | None = None,
    partition: str | None = None,
) -> SlurmReachabilityResult:
    """Return the cached reachability result, refreshing if stale.

    The check is gated on ``settings.slurm_reachability_check_enabled``.
    When disabled, returns a ``DISABLED`` result with ``reachable=True``
    so callers can short-circuit without branching on the flag.

    ``account`` / ``partition`` participate in the cache key. They are
    *not* passed to ``sinfo`` itself — the probe is a global cluster-up
    check; per-partition failure is observed at run time. The key
    exists so a future H-* iteration that probes specific partitions
    can plug in without changing the call sites.
    """
    settings = get_settings()
    if not getattr(settings, "slurm_reachability_check_enabled", True):
        return _DISABLED

    key = (account, partition)
    ttl = float(getattr(settings, "slurm_reachability_cache_seconds", 60))
    timeout_s = float(getattr(settings, "slurm_reachability_timeout_seconds", 10))

    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            result, expires_at = cached
            if _now() < expires_at:
                return result

    # Probe outside the lock so a slow sinfo doesn't serialise every
    # concurrent launcher. A cache miss here means at most N
    # simultaneous sinfo subprocesses for N concurrent first-misses;
    # acceptable, and the second wave finds the cached entry below.
    result = _run_sinfo(timeout_s)
    with _CACHE_LOCK:
        _CACHE[key] = (result, _now() + ttl)
    return result
