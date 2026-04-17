from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    results: list[T]
    total_count: int
    limit: int
    offset: int
    has_more: bool


# Columns that may be used in ORDER BY clauses.
# Add new sortable columns here as routers are implemented.
ALLOWED_SORT_COLUMNS = {
    "created_at",
    "updated_at",
    "ingest_timestamp",
    "date_collected",
    "date_sequenced",
    "sample_id",
    "organism_name",
    "quality_status",
    "sharing_level",
    "sector",
    "source_type",
    "display_name",
    "name",
    "email",
}


def paginate(
    query: str,
    params: dict | None,
    page: int,
    per_page: int,
    sort_by: str,
    sort_dir: str,
) -> tuple[list[dict], int]:
    """
    Execute a paginated query. Returns (results, total_count).
    query must be a SELECT without ORDER BY, LIMIT, or OFFSET — this
    function adds them. A COUNT(*) subquery is run first for the total.
    sort_by is validated against ALLOWED_SORT_COLUMNS to prevent SQL injection.
    """
    from backend.database import execute_query

    # Validate sort direction
    if sort_dir.lower() not in {"asc", "desc"}:
        sort_dir = "desc"

    # Validate sort column — fall back to created_at if not in whitelist
    if sort_by not in ALLOWED_SORT_COLUMNS:
        sort_by = "created_at"

    offset = (page - 1) * per_page

    count_query = f"SELECT COUNT(*) AS total FROM ({query}) AS _count_subquery"
    count_result = execute_query(count_query, params)
    total = count_result[0]["total"] if count_result else 0

    paged_query = f"{query} ORDER BY {sort_by} {sort_dir.upper()} LIMIT :_limit OFFSET :_offset"
    paged_params = {**(params or {}), "_limit": per_page, "_offset": offset}
    results = execute_query(paged_query, paged_params)

    return results, total
