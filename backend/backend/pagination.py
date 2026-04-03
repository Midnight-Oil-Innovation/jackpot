from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    results: list[T]
    total_count: int
    limit: int
    offset: int
    has_more: bool
