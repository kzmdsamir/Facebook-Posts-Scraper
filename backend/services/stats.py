"""Stats aggregation — KPI numbers for the dashboard.

Exposed through the bonus route ``GET /api/jobs/{job_id}/stats``; the
frontend computes its KPI cards either from this endpoint or from the
paginated posts list (the API contract does not mandate this endpoint).
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.exceptions import NotFoundError
from backend.models.engagement_metrics import EngagementMetric
from backend.models.posts import Post
from backend.models.scrape_jobs import ScrapeJob
from backend.services.serialization import iso_format


def aggregate_job_stats(db: Session, job_id: str) -> dict:
    """Return a KPI dict for a job (404 when the job is unknown)."""
    job = db.get(ScrapeJob, job_id)
    if job is None:
        raise NotFoundError(f"Job {job_id} not found")

    total_posts = int(
        db.scalar(select(func.count(Post.id)).where(Post.job_id == job_id)) or 0
    )

    engagement_row = db.execute(
        select(
            func.coalesce(func.sum(EngagementMetric.likes), 0),
            func.coalesce(func.sum(EngagementMetric.reactions), 0),
            func.coalesce(func.sum(EngagementMetric.comments_count), 0),
            func.coalesce(func.sum(EngagementMetric.shares), 0),
            func.coalesce(func.sum(EngagementMetric.views_count), 0),
        )
        .join(Post, EngagementMetric.post_id == Post.id)
        .where(Post.job_id == job_id)
    ).one()
    total_likes, total_reactions, total_comments, total_shares, total_views = (
        int(value or 0) for value in engagement_row
    )

    type_rows = db.execute(
        select(Post.post_type, func.count(Post.id))
        .where(Post.job_id == job_id)
        .group_by(Post.post_type)
    ).all()
    type_counts: dict[str, int] = {key: int(count) for key, count in type_rows if key}

    first_post_at, last_post_at = db.execute(
        select(func.min(Post.published_at), func.max(Post.published_at)).where(
            Post.job_id == job_id
        )
    ).one()

    return {
        "job_id": job_id,
        "total_posts": total_posts,
        "total_likes": total_likes,
        "total_reactions": total_reactions,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "total_views": total_views or None,
        # Type buckets come from post_type; videos additionally include posts
        # carrying a video_url even if post_type is not "video".
        "videos": type_counts.get("video", 0)
        + int(
            db.scalar(
                select(func.count(Post.id)).where(
                    Post.job_id == job_id,
                    Post.video_url.is_not(None),
                    Post.post_type.is_(None),
                )
            )
            or 0
        ),
        "images": type_counts.get("image", 0),
        "links": type_counts.get("link", 0),
        "texts": type_counts.get("text", 0),
        "post_type_counts": type_counts,
        "first_post_at": iso_format(first_post_at),
        "last_post_at": iso_format(last_post_at),
    }