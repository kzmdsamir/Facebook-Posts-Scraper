"""Serialization helpers: ORM rows <-> the canonical normalized post dict.

The canonical dict format is the single source of truth shared with the
scraper layer and the exporters:

    {post_id, facebook_url, post_url, page_name, page_id, profile_url,
     post_type, published_at, timestamp, text, caption, hashtags, mentions,
     external_links, likes, reactions, comments_count, shares, views_count,
     reaction_like_count ... reaction_angry_count, media_type, thumbnail_url,
     media_url, video_url, transcript, transcript_language}

Missing fields MUST be None / [] — they are never fabricated.
"""
from __future__ import annotations

from datetime import datetime, timezone

from backend.models.posts import Post


def iso_format(dt: datetime | None) -> str | None:
    """Render a datetime as an ISO-8601 UTC string ending in ``Z``."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # SQLite returns naive datetimes; they are stored from UTC sources.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def post_to_dict(post: Post) -> dict:
    """Convert a stored :class:`Post` row back into a canonical dict.

    Engagement values are read from the optional 1:1
    :class:`~backend.models.engagement_metrics.EngagementMetric` row; all
    missing values serialize as None. Relationships should be loaded eagerly
    by the caller (selectinload) to avoid N+1 queries.
    """
    engagement = post.engagement

    def _val(name: str):
        return getattr(engagement, name, None) if engagement is not None else None

    return {
        "post_id": post.post_id,
        "facebook_url": post.facebook_url,
        "post_url": post.post_url,
        "page_name": post.page_name,
        "page_id": post.page_id,
        "profile_url": post.profile_url,
        "post_type": post.post_type,
        "published_at": iso_format(post.published_at),
        "timestamp": post.timestamp,
        "text": post.text,
        "caption": post.caption,
        "hashtags": post.hashtags or [],
        "mentions": post.mentions or [],
        "external_links": post.external_links or [],
        "likes": _val("likes"),
        "reactions": _val("reactions"),
        "comments_count": _val("comments_count"),
        "shares": _val("shares"),
        "views_count": _val("views_count"),
        "reaction_like_count": _val("reaction_like_count"),
        "reaction_love_count": _val("reaction_love_count"),
        "reaction_care_count": _val("reaction_care_count"),
        "reaction_haha_count": _val("reaction_haha_count"),
        "reaction_wow_count": _val("reaction_wow_count"),
        "reaction_sad_count": _val("reaction_sad_count"),
        "reaction_angry_count": _val("reaction_angry_count"),
        "media_type": post.media_type,
        "thumbnail_url": post.thumbnail_url,
        "media_url": post.media_url,
        "video_url": post.video_url,
        "transcript": post.transcript,
        "transcript_language": post.transcript_language,
        "scraped_at": iso_format(post.scraped_at),
    }