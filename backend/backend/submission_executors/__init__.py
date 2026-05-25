# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""Backend submission executors.

I-3b ships a Seqsender subprocess executor for NCBI submissions.
Future executors (TOSTADAS-via-Nextflow, ENA Webin-CLI, etc.) plug in
alongside it. The public entry point is the ``execute_submission``
async job in :mod:`backend.jobs`; this package holds the per-executor
implementation details.
"""

from backend.submission_executors.seqsender import (
    SeqsenderRunResult,
    build_execution_log,
    redact_command_for_logging,
    run_seqsender,
    write_seqsender_config,
)

__all__ = [
    "SeqsenderRunResult",
    "build_execution_log",
    "redact_command_for_logging",
    "run_seqsender",
    "write_seqsender_config",
]
