"""Pydantic schemas — request/response models for the API contract."""

from backend.schemas.health import HealthResponse
from backend.schemas.jobs import (
    ErrorDetail,
    JobStatsResponse,
    JobStatusResponse,
    PostOut,
    PostPageResponse,
)
from backend.schemas.scrape import ScrapeOptionsOut, ScrapeRequest, ScrapeResponse

__all__ = [
    "ScrapeRequest",
    "ScrapeResponse",
    "ScrapeOptionsOut",
    "JobStatusResponse",
    "JobStatsResponse",
    "PostOut",
    "PostPageResponse",
    "ErrorDetail",
    "HealthResponse",
]