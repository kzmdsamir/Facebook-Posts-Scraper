"""GET /api/jobs/{job_id}/export/{json|csv|excel} — file download endpoint.

The ``fmt`` path segment is a FastAPI ``Literal`` so invalid formats fail with
a 400 validation error before any service code runs. Only the whitelisted fmt
string is forwarded to the exporters — no user-controlled path components
reach the filesystem layer (path-traversal guard, spec §10).
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.services.export_service import build_export

router = APIRouter(tags=["exports"])

MEDIA_TYPES = {
    "json": "application/json",
    "csv": "text/csv",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
FILENAMES = {
    "json": "facebook_posts.json",
    "csv": "facebook_posts.csv",
    "excel": "facebook_posts.xlsx",
}
_ExportFormat = Literal["json", "csv", "excel"]


@router.get(
    "/jobs/{job_id}/export/{fmt}",
    summary="Download job results as JSON/CSV/XLSX",
    responses={
        200: {"description": "File download"},
        404: {"description": "Unknown job"},
        409: {"description": "Job still running"},
        500: {"description": "Export failed / module unavailable"},
    },
)
def download_export(
    job_id: str,
    fmt: _ExportFormat,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Generate (or reuse) the export file and stream it to the client."""
    path = build_export(db, job_id, fmt)
    # Filename prefix uses the hex job id — safe to interpolate.
    return FileResponse(
        path=str(path),
        media_type=MEDIA_TYPES[fmt],
        filename=f"{job_id}_{FILENAMES[fmt]}",
    )