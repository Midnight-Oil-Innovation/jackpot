"""
Wastewater read endpoints for the B-WW-1 lineage-abundance dashboard.

The data is already landed by the existing parser-registration POST at
``/api/v1/pipelines/{run_id}/results/wastewater_lineage_abundance`` — these
GET endpoints surface the typed-result rows for the operator-facing
Streamlit page. Read-only, no new tables, no mutation.

Endpoints
---------

GET  /api/v1/wastewater/sites
    Distinct wastewater sampling sites (``wwtp_name``) the caller can see.

GET  /api/v1/wastewater/lineage-abundance
    Wastewater samples joined to their ``wastewater_lineage_abundance``
    rows. Filterable by date range, site, and lineage. One row per
    (sample, lineage). Visibility honours
    ``authz.visibility.sample_list_clause`` — the same grants and policies
    ``permit()`` reads (M2-B7).
"""

from fastapi import APIRouter, Depends, Query, Request

from backend.auth.guards import get_current_user
from backend.authz.principal import load_principal
from backend.authz.visibility import sample_list_clause
from backend.database import execute_query, get_db_dep
from backend.responses import success

router = APIRouter(prefix="/api/v1/wastewater", tags=["wastewater"])


def _serialise(row: dict) -> dict:
    out = dict(row)
    for k, v in out.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
    return out


@router.get("/sites")
def list_sites(
    request: Request,
    db=Depends(get_db_dep),  # noqa: B008
):
    user = get_current_user(request)
    vis_clause, vis_params = sample_list_clause(load_principal(user["id"]))
    rows = execute_query(
        f"""
        SELECT DISTINCT s.wwtp_name AS site
        FROM samples s
        JOIN labs l ON l.id = s.lab_id
        WHERE s.is_archived = FALSE
          AND s.sector = 'wastewater'
          AND s.wwtp_name IS NOT NULL
          AND {vis_clause}
        ORDER BY site ASC
        """,
        vis_params,
        conn=db,
    )
    return success(data=[r["site"] for r in rows if r["site"]])


@router.get("/lineage-abundance")
def list_lineage_abundance(
    request: Request,
    date_from: str | None = None,
    date_to: str | None = None,
    site: str | None = None,
    lineage: str | None = None,
    limit: int = Query(5000, ge=1, le=20000),
    db=Depends(get_db_dep),  # noqa: B008
):
    """
    One row per (sample, lineage). Joins ``samples`` (sector=wastewater)
    against ``wastewater_lineage_abundance`` on the textual ``sample_id``.
    """
    user = get_current_user(request)
    vis_clause, vis_params = sample_list_clause(load_principal(user["id"]))

    where = [
        "s.is_archived = FALSE",
        "s.sector = 'wastewater'",
        vis_clause,
    ]
    params: dict = dict(vis_params)

    if date_from:
        where.append("s.date_collected >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("s.date_collected <= :date_to")
        params["date_to"] = date_to
    if site:
        where.append("s.wwtp_name = :site")
        params["site"] = site
    if lineage:
        where.append("w.lineage = :lineage")
        params["lineage"] = lineage

    params["limit"] = limit
    rows = execute_query(
        f"""
        SELECT
            s.sample_id              AS sample_id,
            s.date_collected         AS date_collected,
            s.wwtp_name              AS site,
            s.flow_rate_mgd          AS flow_rate_mgd,
            s.population_served      AS population_served,
            w.lineage                AS lineage,
            w.abundance              AS abundance,
            w.confidence_interval_low  AS ci_low,
            w.confidence_interval_high AS ci_high,
            w.tool_name              AS tool_name,
            w.tool_version           AS tool_version,
            w.barcode_version        AS barcode_version
        FROM samples s
        JOIN labs l ON l.id = s.lab_id
        JOIN wastewater_lineage_abundance w
            ON w.sample_id = s.sample_id
        WHERE {" AND ".join(where)}
        ORDER BY s.date_collected ASC, s.sample_id ASC, w.abundance DESC
        LIMIT :limit
        """,
        params,
        conn=db,
    )
    return success(data=[_serialise(r) for r in rows])
