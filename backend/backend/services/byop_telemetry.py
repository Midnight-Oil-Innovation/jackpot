# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2024-present Glen Otero
"""BYOP pipeline telemetry aggregation (P0f B-BYOP-10).

Design doc §10: per registered BYOP pipeline, operators see total runs,
success rate, walltime, and cost per run so they can spot pipelines that
"register fine but fail in production."

One in-database aggregation query over ``pipeline_results`` joined to
``byop_pipelines`` via the B-BYOP-9 ``byop_pipeline_id`` FK. Per-run
observations live in the ``pipeline_results.metrics`` JSONB column
(``status``, ``walltime_seconds``, ``cost_usd``) — ``pipeline_results``
has no dedicated columns for them. No Python-side aggregation.
"""

from __future__ import annotations

from backend.database import execute_query

_TELEMETRY_SQL = """
SELECT
    bp.id                                   AS pipeline_id,
    bp.name                                 AS name,
    bp.version                              AS version,
    COUNT(pr.id)                            AS total_runs,
    COUNT(*) FILTER (WHERE pr.metrics->>'status' = 'success')::float
        / NULLIF(COUNT(pr.id), 0)           AS success_rate,
    AVG((pr.metrics->>'walltime_seconds')::float)
                                            AS mean_walltime_seconds,
    PERCENTILE_CONT(0.95) WITHIN GROUP (
        ORDER BY (pr.metrics->>'walltime_seconds')::float)
                                            AS p95_walltime_seconds,
    AVG((pr.metrics->>'cost_usd')::float)   AS mean_cost_usd
FROM byop_pipelines bp
LEFT JOIN pipeline_results pr ON pr.byop_pipeline_id = bp.id
{where}
GROUP BY bp.id, bp.name, bp.version
ORDER BY bp.id
"""


def get_pipeline_telemetry(db, pipeline_id: int | None = None) -> list[dict]:
    """Aggregated telemetry per registered BYOP pipeline.

    One row per pipeline: ``pipeline_id``, ``name``, ``version``,
    ``total_runs``, ``success_rate`` (0.0–1.0, ``None`` when no runs),
    ``mean_walltime_seconds``, ``p95_walltime_seconds``, ``mean_cost_usd``
    (each ``None`` when no runs). ``pipeline_id=None`` returns all
    pipelines; an unknown id returns an empty list.
    """
    if pipeline_id is None:
        return execute_query(_TELEMETRY_SQL.format(where=""), conn=db)
    return execute_query(
        _TELEMETRY_SQL.format(where="WHERE bp.id = :pipeline_id"),
        {"pipeline_id": pipeline_id},
        conn=db,
    )
