"""EngagementMetric ORM model — engagement counters for a post (0..1 rows per post)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class EngagementMetric(Base):
    __tablename__ = "engagement_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), unique=True, index=True
    )

    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reactions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    reaction_like_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reaction_love_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reaction_care_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reaction_haha_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reaction_wow_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reaction_sad_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reaction_angry_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    post = relationship("Post", back_populates="engagement")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<EngagementMetric post_id={self.post_id} likes={self.likes!r}>"