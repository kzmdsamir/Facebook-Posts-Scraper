"""CrawlState service — persistent checkpointing and transactional safety.

Provides the CRUD operations for crawl state lifecycle management:
  - create: initialize a crawl state when a source starts
  - checkpoint: atomically persist progress + cursor + meta after each page
  - mark_running / mark_completed / mark_failed: lifecycle transitions
  - get_resume_state: load the last checkpoint for resume
  - reset_for_resume: reset a completed/failed state to re-crawl

All mutations are transactional — the checkpoint call atomically writes
counters, cursor, meta, and status in a single commit so a crash at any
point leaves a consistent resumable state.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.database import SessionLocal
from backend.models.crawl_state import CrawlState

logger = logging.getLogger("services.crawl_state")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create(
    db: Session,
    *,
    source_id: int,
    job_id: str,
    cursor: Optional[str] = None,
    meta: Optional[dict] = None,
) -> CrawlState:
    """Create a new crawl state for a source (status='created')."""
    state = CrawlState(
        source_id=source_id,
        job_id=job_id,
        status="created",
        cursor=cursor,
        meta=meta or {},
    )
    db.add(state)
    db.flush()
    logger.info(
        "Created crawl state %d for source %d (job %s)",
        state.id, source_id, job_id,
    )
    return state


def mark_running(db: Session, state: CrawlState) -> None:
    """Transition to running status."""
    state.status = "running"
    state.updated_at = _now()
    db.flush()


def checkpoint(
    db: Session,
    state: CrawlState,
    *,
    cursor: Optional[str] = None,
    pages_fetched: Optional[int] = None,
    posts_extracted: Optional[int] = None,
    posts_stored: Optional[int] = None,
    meta: Optional[dict] = None,
    consecutive_errors: Optional[int] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Atomically persist a checkpoint. All fields are optional — only
    provided fields are updated (others retain their current value).

    This is the core transactional safety primitive: a single flush + commit
    ensures the checkpoint is either fully written or not at all.
    """
    if cursor is not None:
        state.cursor = cursor
    if pages_fetched is not None:
        state.pages_fetched = pages_fetched
    if posts_extracted is not None:
        state.posts_extracted = posts_extracted
    if posts_stored is not None:
        state.posts_stored = posts_stored
    if meta is not None:
        state.meta = meta
    if consecutive_errors is not None:
        state.consecutive_errors = consecutive_errors
    if error_code is not None:
        state.last_error_code = error_code
    if error_message is not None:
        state.last_error_message = error_message
    state.updated_at = _now()
    state.status = "running"
    db.flush()


def mark_completed(db: Session, state: CrawlState) -> None:
    """Mark crawl state as completed."""
    state.status = "completed"
    state.completed_at = _now()
    state.updated_at = _now()
    db.flush()


def mark_failed(
    db: Session,
    state: CrawlState,
    *,
    error_code: str,
    error_message: str,
) -> None:
    """Mark crawl state as failed with error details."""
    state.status = "failed"
    state.last_error_code = error_code
    state.last_error_message = error_message
    state.consecutive_errors += 1
    state.updated_at = _now()
    state.completed_at = _now()
    db.flush()


def mark_paused(db: Session, state: CrawlState) -> None:
    """Mark crawl state as paused (for user-initiated pause)."""
    state.status = "paused"
    state.updated_at = _now()
    db.flush()


def get_resume_state(
    db: Session,
    *,
    source_id: int,
    job_id: str,
) -> Optional[CrawlState]:
    """Load the most recent crawl state for a source that can be resumed.

    Returns the state if status is 'paused', 'completed', or 'failed' (for
    retry). Returns None if no state exists or if the state is already
    'running' (another worker owns it).
    """
    stmt = (
        select(CrawlState)
        .where(
            CrawlState.source_id == source_id,
            CrawlState.job_id == job_id,
        )
        .order_by(CrawlState.id.desc())
        .limit(1)
    )
    state = db.scalars(stmt).first()
    if state is None:
        return None
    if state.status == "running":
        # Another worker may own this — don't resume
        return None
    return state


def reset_for_resume(db: Session, state: CrawlState) -> None:
    """Reset a completed/failed/paused state to 'created' for re-crawl."""
    state.status = "created"
    state.consecutive_errors = 0
    state.last_error_code = None
    state.last_error_message = None
    state.completed_at = None
    state.updated_at = _now()
    db.flush()
