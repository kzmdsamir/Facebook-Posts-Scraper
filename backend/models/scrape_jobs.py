"""ScrapeJob ORM model — one row per user-submitted scraping run."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScrapeJob(Base):
    """Lifecycle + aggregated progress counters for one scraping job.

    ``status`` uses the API contract vocabulary:
    ``queued -> running -> completed | failed``.
    """

    __tablename__ = "scrape_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)

    pages_total: Mapped[int] = mapped_column(Integer, default=0)
    pages_completed: Mapped[int] = mapped_column(Integer, default=0)

    posts_found: Mapped[int] = mapped_column(Integer, default=0)
    posts_processed: Mapped[int] = mapped_column(Integer, default=0)
    posts_skipped: Mapped[int] = mapped_column(Integer, default=0)
    posts_failed: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    # DB-level duplicate collisions (posts rejected by the per-source unique
    # constraint that the scraper's own dedup did not catch). Kept separate so
    # progress recomputes of ``duplicates`` do not lose them.
    storage_duplicates: Mapped[int] = mapped_column(Integer, default=0)
    errors_count: Mapped[int] = mapped_column(Integer, default=0)

    # Snapshot of the user-submitted options {urls, max_posts, start_date,
    # end_date, post_type} used by the worker to build ScrapeOptions.
    options: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sources = relationship(
        "ScrapeSource",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="ScrapeSource.id",
    )
    posts = relationship("Post", back_populates="job", cascade="all, delete-orphan")
    errors = relationship(
        "ScrapeError", back_populates="job", cascade="all, delete-orphan"
    )
    export_jobs = relationship(
        "ExportJob", back_populates="job", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ScrapeJob id={self.id!r} status={self.status!r}>"