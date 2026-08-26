"""Response models for job status, posts and stats endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

JOB_STATUS = Literal["queued", "running", "completed", "failed"]


class ErrorDetail(BaseModel):
    """One entry of ``error_details`` in the job status response."""

    url: str | None = None
    post_url: str | None = None
    code: str
    message: str


class JobStatusResponse(BaseModel):
    """GET /api/jobs/{job_id} response (spec §8)."""

    job_id: str
    status: JOB_STATUS
    pages_total: int
    pages_completed: int
    posts_found: int
    posts_processed: int
    duplicates: int
    errors: int
    error_details: list[ErrorDetail] = Field(default_factory=list)

    # Informative extras (a superset of the spec §8 contract; harmless for
    # strict clients, useful for the dashboard).
    posts_skipped: int = 0
    posts_failed: int = 0
    cancel_requested: bool = False
    created_at: str | None = None
    completed_at: str | None = None


class PostOut(BaseModel):
    """Canonical normalized post dict (contract shared with the scraper layer).

    Every field is optional exactly like the scraper's normalized dict
    contract: missing/unavailable fields serialise as ``None`` / ``[]`` and are
    never fabricated. ``extra="allow"`` keeps the model tolerant of future
    fields added by the scraper layer.
    """

    model_config = ConfigDict(extra="allow")

    post_id: str | None = None
    facebook_url: str | None = None
    post_url: str | None = None
    page_name: str | None = None
    page_id: str | None = None
    profile_url: str | None = None
    post_type: str | None = None
    published_at: str | None = None
    timestamp: int | None = None

    text: str | None = None
    caption: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)
    external_links: list[str] = Field(default_factory=list)

    likes: int | None = None
    reactions: int | None = None
    comments_count: int | None = None
    shares: int | None = None
    views_count: int | None = None
    reaction_like_count: int | None = None
    reaction_love_count: int | None = None
    reaction_care_count: int | None = None
    reaction_haha_count: int | None = None
    reaction_wow_count: int | None = None
    reaction_sad_count: int | None = None
    reaction_angry_count: int | None = None

    media_type: str | None = None
    thumbnail_url: str | None = None
    media_url: str | None = None
    video_url: str | None = None
    transcript: str | None = None
    transcript_language: str | None = None

    scraped_at: str | None = None


class PostPageResponse(BaseModel):
    """Paginated posts response for GET /api/jobs/{job_id}/posts."""

    items: list[PostOut]
    total: int
    page: int
    page_size: int


class JobStatsResponse(BaseModel):
    """Aggregated KPIs for the dashboard (bonus endpoint, see services/stats.py)."""

    job_id: str
    total_posts: int
    total_likes: int
    total_reactions: int
    total_comments: int
    total_shares: int
    total_views: int | None = None
    videos: int
    images: int
    links: int
    texts: int
    post_type_counts: dict[str, int] = Field(default_factory=dict)
    first_post_at: str | None = None
    last_post_at: str | None = None