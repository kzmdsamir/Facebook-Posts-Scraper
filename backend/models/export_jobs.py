"""ExportJob ORM model — audit record of every export request (JSON/CSV/XLSX)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("scrape_jobs.id", ondelete="CASCADE"), index=True
    )

    format: Mapped[str] = mapped_column(String(16))  # json | csv | excel
    status: Mapped[str] = mapped_column(String(16), default="pending")
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    job = relationship("ScrapeJob", back_populates="export_jobs")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ExportJob id={self.id} job_id={self.job_id!r} format={self.format!r} status={self.status!r}>"