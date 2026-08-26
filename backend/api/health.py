"""GET /api/health — liveness probe with a database round-trip."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.database import get_db
from backend.core.exceptions import ServiceUnavailableError
from backend.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """Return {"status": "ok"} when the app + database are healthy."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - any DB failure means unhealthy
        raise ServiceUnavailableError(
            "Database unavailable", code="database_unavailable"
        ) from exc
    return HealthResponse(status="ok", database="ok", version=get_settings().version)