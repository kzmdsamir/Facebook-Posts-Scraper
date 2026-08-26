"""Health-check response model."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """GET /api/health response body."""

    status: Literal["ok"] = "ok"
    database: Literal["ok"] = "ok"
    version: str = "1.0.0"