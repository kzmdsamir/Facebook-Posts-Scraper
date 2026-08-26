"""Post ORM model — the normalized post record.

Deduplication strategy
----------------------
* ``dedup_key`` is the storage-level dedup identity for the post:
  - the Facebook ``post_id`` when available (the spec's preferred key), or
  - ``"fp:<sha256>"`` — a SHA-256 fingerprint of stable public fields when
    ``post_id`` is missing (spec §7 fallback; computed by the services layer).
* ``UniqueConstraint(source_id, dedup_key)`` guarantees at most one row per
  (job source, key). The scraper layer already dedups within a single result
  set; this constraint is the defensive second line and also lets duplicate
  inserts from *re-scraped* sources be counted reliably.

Indexes: ``post_id``, ``page_id``, ``published_at`` and ``job_id`` are all
indexed as required by the spec (§11); a composite (job_id, published_at)
index serves the paginated posts listing.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        UniqueConstraint("source_id", "dedup_key", name="uq_posts_source_dedup_key"),
        Index("ix_posts_job_published", "job_id", "published_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("scrape_jobs.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )

    # --- basic -----------------------------------------------------------------
    post_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    dedup_key: Mapped[str] = mapped_column(String(192), nullable=False)
    facebook_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    post_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    page_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    page_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    profile_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    post_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )
    timestamp: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # --- content ---------------------------------------------------------------
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    mentions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    external_links: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # --- media -----------------------------------------------------------------
    media_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_language: Mapped[str | None] = mapped_column(String(16), nullable=True)

    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    job = relationship("ScrapeJob", back_populates="posts")
    source = relationship("ScrapeSource", back_populates="posts")
    engagement = relationship(
        "EngagementMetric",
        back_populates="post",
        uselist=False,
        cascade="all, delete-orphan",
    )
    media = relationship("Media", back_populates="post", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Post id={self.id} post_id={self.post_id!r} type={self.post_type!r}>"