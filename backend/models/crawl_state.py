"""CrawlState ORM model — persistent checkpoint for long-running crawls.

Tracks the resumable state of a per-source crawl so that if the process
crashes or is cancelled, the crawler can pick up where it left off instead
of re-fetching from scratch.

Lifecycle:
    created -> running -> (paused | completed | failed)
                                    ^
                                    |
                          can resume from paused/completed (for re-crawl)

The ``cursor`` field stores an opaque pagination token (e.g. Facebook's
``after`` parameter, a timestamp, a URL fragment) that the transport layer
understands.  The ``meta`` JSON field stores adapter-specific checkpoint
data (scroll position, seen post IDs, etc.).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CrawlState(Base):
    """One row per (source, crawl session) — the authoritative checkpoint."""

    __tablename__ = "crawl_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[str] = mapped_column(
        ForeignKey("scrape_jobs.id", ondelete="CASCADE"), index=True
    )

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(16), default="created", index=True
    )  # created | running | paused | completed | failed

    # Pagination checkpoint — opaque token understood by the adapter
    cursor: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Counters
    pages_fetched: Mapped[int] = mapped_column(Integer, default=0)
    posts_extracted: Mapped[int] = mapped_column(Integer, default=0)
    posts_stored: Mapped[int] = mapped_column(Integer, default=0)

    # Adapter-specific checkpoint data (scroll position, seen IDs, etc.)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Error tracking for the current attempt
    consecutive_errors: Mapped[int] = mapped_column(Integer, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    source = relationship("ScrapeSource", back_populates="crawl_states")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<CrawlState id={self.id} source_id={self.source_id} "
            f"status={self.status!r} pages={self.pages_fetched}>"
        )
