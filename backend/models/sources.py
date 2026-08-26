"""ScrapeSource ORM model — one row per validated page/profile URL in a job.

One source failure never fails the whole job: each source tracks its own
status (queued | running | completed | failed | cancelled) and stats.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScrapeSource(Base):
    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("job_id", "normalized_url", name="uq_sources_job_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("scrape_jobs.id", ondelete="CASCADE"), index=True
    )

    # Original user input and the canonical URL the scraper actually uses.
    url: Mapped[str] = mapped_column(String(2048))
    normalized_url: Mapped[str] = mapped_column(String(2048))

    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)

    page_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    page_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Per-source counters (mirror of the scraper SourceResult.stats contract).
    posts_discovered: Mapped[int] = mapped_column(Integer, default=0)
    posts_extracted: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_removed: Mapped[int] = mapped_column(Integer, default=0)
    posts_skipped: Mapped[int] = mapped_column(Integer, default=0)
    posts_failed: Mapped[int] = mapped_column(Integer, default=0)

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    job = relationship("ScrapeJob", back_populates="sources")
    posts = relationship("Post", back_populates="source", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ScrapeSource id={self.id} status={self.status!r} url={self.normalized_url!r}>"