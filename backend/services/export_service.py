"""Export wiring service.

Delegates file generation to ``backend.exporters.export_posts`` (owned by
SA03). The only value forwarded to the exporters is the whitelisted ``fmt``
string — the route validates it as a ``Literal["json", "csv", "excel"]`` so
there is no path-traversal surface here. ``base_dir`` comes from settings.

Every export request is recorded in the ``export_jobs`` table (pending ->
completed | failed) as an audit trail.

Phase 18: Added batch loading for large datasets to limit memory usage.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Generator, List

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.core.config import get_settings
from backend.core.database import SessionLocal
from backend.core.exceptions import AppError, JobBusyError, NotFoundError
from backend.core.logging import get_logger
from backend.models.export_jobs import ExportJob
from backend.models.posts import Post
from backend.models.scrape_jobs import ScrapeJob
from backend.services import serialization

logger = get_logger("services.export_service")

EXPORT_FORMATS = ("json", "csv", "excel", "xlsx", "jsonl")

# Default batch size for streaming exports (balances memory vs. DB round-trips)
_BATCH_SIZE = 500


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _posts_loader_for_job(job_id: str) -> Callable[[], List[dict]]:
    """Build a posts loader for the exporters ``posts_loader`` parameter.

    The loader opens its own short-lived session so it never depends on the
    request-scoped session lifetime, and caches the loaded list in a closure
    (exporters may iterate the loader result multiple times).
    """
    cache: dict = {}

    def _load() -> List[dict]:
        if cache.get("posts") is not None:
            return cache["posts"]
        with SessionLocal() as db:
            rows = db.scalars(
                select(Post)
                .where(Post.job_id == job_id)
                .options(selectinload(Post.engagement), selectinload(Post.media))
                .order_by(Post.published_at.desc().nulls_last(), Post.id.desc())
            ).all()
            posts = [serialization.post_to_dict(post) for post in rows]
        cache["posts"] = posts
        return posts

    return _load


def _posts_loader_batch(
    job_id: str,
    batch_size: int = _BATCH_SIZE,
) -> Generator[List[dict], None, None]:
    """Yield posts in batches for memory-efficient processing.

    Each batch opens and closes its own session.  Use this for large datasets
    where loading all posts into memory at once would be problematic.

    Yields:
        Lists of post dicts, each containing at most ``batch_size`` items.
    """
    offset = 0
    while True:
        with SessionLocal() as db:
            rows = db.scalars(
                select(Post)
                .where(Post.job_id == job_id)
                .options(selectinload(Post.engagement), selectinload(Post.media))
                .order_by(Post.published_at.desc().nulls_last(), Post.id.desc())
                .offset(offset)
                .limit(batch_size)
            ).all()
            if not rows:
                break
            posts = [serialization.post_to_dict(post) for post in rows]
            yield posts
            if len(rows) < batch_size:
                break
            offset += batch_size


def count_posts_for_job(job_id: str) -> int:
    """Return the total number of posts for a job (lightweight count query)."""
    from sqlalchemy import func

    with SessionLocal() as db:
        count = db.scalar(
            select(func.count(Post.id)).where(Post.job_id == job_id)
        )
        return count or 0


def build_export(
    db: Session, job_id: str, fmt: str, base_dir: str | None = None
) -> Path:
    """Generate an export file and record it; returns the file path."""
    if fmt not in EXPORT_FORMATS:
        raise AppError(
            f"Unsupported export format '{fmt}'. Use one of: {', '.join(EXPORT_FORMATS)}",
            status_code=400,
            code="invalid_input",
        )

    job = db.get(ScrapeJob, job_id)
    if job is None:
        raise NotFoundError(f"Job {job_id} not found")
    if job.status in ("queued", "running"):
        raise JobBusyError("Export is only available after the job has finished running")

    # Lazy import so the API stays up even if the exporters package is
    # temporarily missing; a clear 500 is returned in that case.
    try:
        from backend.exporters import export_posts  # noqa: PLC0415 - lazy import
    except ImportError as exc:
        logger.exception("backend.exporters is not available")
        raise AppError(
            "The export module is not available. Check the backend deployment.",
            status_code=500,
            code="export_unavailable",
        ) from exc

    base = Path(base_dir or get_settings().export_base_dir)
    base.mkdir(parents=True, exist_ok=True)

    export_row = ExportJob(job_id=job_id, format=fmt, status="pending")
    db.add(export_row)
    db.commit()
    db.refresh(export_row)

    try:
        # Contract with SA03 (actual signature):
        # export_posts(posts_loader=None, job_id="local", fmt="json",
        #              base_dir=None, posts_path=None) -> Path
        path = export_posts(
            posts_loader=_posts_loader_for_job(job_id),
            job_id=job_id,
            fmt=fmt,
            base_dir=str(base),
        )
    except Exception as exc:  # noqa: BLE001 - any exporter failure -> 500 + row
        logger.exception("Export failed (job %s, format %s)", job_id, fmt)
        export_row.status = "failed"
        export_row.error_code = "export_failed"
        export_row.error_message = str(exc)
        export_row.completed_at = _now()
        db.commit()
        raise AppError(
            f"Export failed for job {job_id}: {exc}",
            status_code=500,
            code="export_failed",
        ) from exc

    result = Path(path)
    export_row.status = "completed"
    export_row.file_path = str(result)
    export_row.completed_at = _now()
    db.commit()
    logger.info("Export ready (job %s, format %s): %s", job_id, fmt, result)

    if not result.is_file():
        raise AppError(
            f"Exporter returned a non-file path: {result}",
            status_code=500,
            code="export_failed",
        )
    return result