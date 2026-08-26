"""Media ORM model — one or more media items per post.

The canonical normalized dict carries a single flat ``media_type`` /
``thumbnail_url`` / ``media_url`` / ``video_url`` set. That primary media item
becomes one ``Media`` row per post; any additional entries in an optional
``media`` list in the source dict are stored as extra rows so exporters can
render a full media array.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class Media(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )

    media_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    post = relationship("Post", back_populates="media")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Media id={self.id} post_id={self.post_id} type={self.media_type!r}>"