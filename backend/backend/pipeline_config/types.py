"""
Lightweight in-memory representations of execution-profile rows.

The schema for ``execution_profiles`` lives in migration
``bac8dbb11c0b`` (P0g G-1+G-2). The renderer and resolver consume
profiles as plain dataclasses rather than ORM rows so unit tests can
build fixtures without touching a database, and so the resolver can
return a uniform shape regardless of whether the row came from a SQL
query, a fixture, or a future caching layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass
class ExecutionProfile:
    """One row of ``execution_profiles`` (P0g G-1+G-2)."""

    profile_id: UUID
    name: str
    executor_type: str
    container_engine: str
    work_dir: str
    config_overrides: dict[str, Any] = field(default_factory=dict)
    is_default: bool = False
    created_by_id: int | None = None
    created_at: datetime | None = None
    active: bool = True

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ExecutionProfile:
        """Build from a SQL row dict (psycopg2/SQLAlchemy mapping)."""
        overrides = row.get("config_overrides") or {}
        if isinstance(overrides, str):
            import json

            try:
                overrides = json.loads(overrides)
            except (ValueError, TypeError):
                overrides = {}
        return cls(
            profile_id=row["profile_id"],
            name=row["name"],
            executor_type=row["executor_type"],
            container_engine=row["container_engine"],
            work_dir=row["work_dir"],
            config_overrides=overrides,
            is_default=bool(row.get("is_default", False)),
            created_by_id=row.get("created_by_id"),
            created_at=row.get("created_at"),
            active=bool(row.get("active", True)),
        )
