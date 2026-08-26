"""Job status / posts / deletion endpoints.

* GET    /api/jobs/{job_id}          — live status + progress counters (spec §8)
* GET    /api/jobs/{job_id}/posts    — paginated normalized posts (spec §14)
* GET    /api/jobs/{job_id}/stats    — aggregated KPIs (bonus, for the dashboard)
* DELETE /api/jobs/{job_id}          — best-effort cancel + delete rows (204)

All unknown jobs return 404 {"error": {"code": "not_found", ...}}.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from backend.core.config import get_settings
from backend.core.database import get_db
from backend.core.exceptions import NotFoundError
from backend.core.job_manager import JobManager
from backend.models.errors import ScrapeError
from backend.models.posts import Post
from backend.models.scrape_jobs import ScrapeJob
from backend.schemas.jobs import (
    ErrorDetail,
    JobStatsResponse,
    JobStatusResponse,
    PostOut,
    PostPageResponse,
)
from backend.services import serialization, stats as stats_service

router = APIRouter(tags=["jobs"])


def _get_job_or_404(db: Session, job_id: str) -> ScrapeJob:
    job = db.get(ScrapeJob, job_id)
    if job is None:
        raise NotFoundError(f"Job {job_id} not found")
    return job


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status & live progress",
)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    """Return the job's state machine position, counters and recent errors."""
    job = _get_job_or_404(db, job_id)
    error_rows = db.scalars(
        select(ScrapeError)
        .where(ScrapeError.job_id == job_id)
        .order_by(ScrapeError.id.desc())
        .limit(50)
    ).all()
    error_details = [
        ErrorDetail(
            url=e.source_url or None,
            post_url=e.post_url,
            code=e.code,
            message=e.message,
        )
        for e in error_rows
    ]
    return JobStatusResponse(
        job_id=job.id,
        status=job.status if job.status in ("queued", "running", "completed", "failed") else "failed",
        pages_total=job.pages_total,
        pages_completed=job.pages_completed,
        posts_found=job.posts_found,
        posts_processed=job.posts_processed,
        duplicates=job.duplicates,
        errors=job.errors_count,
        error_details=error_details,
        posts_skipped=job.posts_skipped,
        posts_failed=job.posts_failed,
        cancel_requested=job.cancel_requested,
        created_at=serialization.iso_format(job.created_at),
        completed_at=serialization.iso_format(job.completed_at),
    )


@router.get(
    "/jobs/{job_id}/posts",
    response_model=PostPageResponse,
    summary="List extracted posts (paginated)",
)
def list_posts(
    job_id: str,
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page (max 200)"),
    db: Session = Depends(get_db),
) -> PostPageResponse:
    """Return extracted posts for the job, newest first, paginated."""
    _get_job_or_404(db, job_id)
    settings = get_settings()
    page_size = min(page_size, settings.page_size_max)

    total = int(
        db.scalar(select(func.count()).select_from(Post).where(Post.job_id == job_id))
        or 0
    )
    stmt = (
        select(Post)
        .where(Post.job_id == job_id)
        .options(selectinload(Post.engagement), selectinload(Post.media))
        .order_by(Post.published_at.desc().nulls_last(), Post.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    posts = db.scalars(stmt).all()
    return PostPageResponse(
        items=[PostOut(**serialization.post_to_dict(post)) for post in posts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/jobs/{job_id}/stats",
    response_model=JobStatsResponse,
    summary="Aggregated KPIs for the dashboard (bonus endpoint)",
)
def get_job_stats(
    job_id: str,
    db: Session = Depends(get_db),
) -> JobStatsResponse:
    """Return KPI aggregates (totals by type and engagement) for the job."""
    return JobStatsResponse(**stats_service.aggregate_job_stats(db, job_id))


@router.delete(
    "/jobs/{job_id}",
    status_code=204,
    summary="Cancel (best-effort) and delete a job",
)
def delete_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> Response:
    """Request cancellation, wait briefly for the worker, then delete rows.

    Cancellation is best-effort: the worker receives a cancel event it checks
    between sources (the event is also forwarded to ``scrape_source`` so an
    in-flight pagination loop can stop). After up to ``cancel_wait_seconds``
    the job and all dependent rows are deleted (ON DELETE CASCADE); a worker
    still running afterwards simply finds the rows gone and stops writing.
    """
    job = _get_job_or_404(db, job_id)
    job.cancel_requested = True
    db.commit()

    manager = JobManager.get()
    manager.cancel(job.id, wait_seconds=get_settings().cancel_wait_seconds)

    db.execute(delete(ScrapeJob).where(ScrapeJob.id == job_id))
    db.commit()
    return Response(status_code=204)