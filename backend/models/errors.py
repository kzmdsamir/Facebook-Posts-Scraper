"""ScrapeError ORM model — the ``errors`` table.

One row per failure: an invalid submitted URL (validation-time), a per-source
scraping failure (exceptions raised by the scraper engine), per-post extraction
errors reported inside the scraper result, or a job cancellation.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScrapeError(Base):
    __tablename__ = "errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("scrape_jobs.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True, nullable=True
    )

    source_url: Mapped[str] = mapped_column(String(2048))
    post_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    code: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    job = relationship("ScrapeJob", back_populates="errors")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ScrapeError id={self.id} code={self.code!r}>"