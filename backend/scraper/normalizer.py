"""Normalizer: ParsedPost -> canonical normalized post dict.

The canonical normalized post dict (single source of truth, agreed with the
API / export / frontend agents) has exactly these keys:

    post_id, facebook_url, post_url, page_name, page_id, profile_url,
    post_type("text|image|video|link" or None), published_at(ISO), timestamp(int),
    text, caption, hashtags[], mentions[], external_links[],
    likes, reactions, comments_count, shares, views_count,
    reaction_like_count, reaction_love_count, reaction_care_count,
    reaction_haha_count, reaction_wow_count, reaction_sad_count,
    reaction_angry_count,
    media_type, thumbnail_url, media_url, video_url,
    transcript, transcript_language

Rules enforced here:

* Every key is ALWAYS present.  Missing/unavailable values are ``None``
  (scalars) or ``[]`` (lists) - never fabricated placeholders.
* ``published_at`` is a UTC ISO-8601 string; ``timestamp`` is the epoch int
  (seconds).  Naive datetimes from the parser are treated as UTC by
  convention (see ``parser.parse_timestamp``).
* ``post_type`` is classified from extraction signals - see
  :func:`classify_post_type`.
* ``caption`` is always ``None`` for public-HTMl scrapes: Facebook renders the
  post message as a single text block, there is no separate caption in the
  public markup, and fabricating a split is forbidden by the spec.
* ``transcript`` / ``transcript_language`` are always ``None``: transcripts
  are never exposed on public pages.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .parser import ParsedPost

__all__ = [
    "NORMALIZED_KEYS",
    "normalize_post",
    "classify_post_type",
    "clean_text",
]

NORMALIZED_KEYS: List[str] = [
    "post_id", "facebook_url", "post_url", "page_name", "page_id",
    "profile_url", "post_type", "published_at", "timestamp", "text",
    "caption", "hashtags", "mentions", "external_links", "likes", "reactions",
    "comments_count", "shares", "views_count", "reaction_like_count",
    "reaction_love_count", "reaction_care_count", "reaction_haha_count",
    "reaction_wow_count", "reaction_sad_count", "reaction_angry_count",
    "media_type", "thumbnail_url", "media_url", "video_url", "transcript",
    "transcript_language", "scraped_at",
]

#: list-typed keys default to [] instead of None
_LIST_KEYS = {"hashtags", "mentions", "external_links"}

_HASHTAG_RE = re.compile(r"#([A-Za-z0-9_\u0080-\uFFFF]+)")
_MENTION_RE = re.compile(r"@([A-Za-z0-9_.\-\u0080-\uFFFF]+)")


def _fix_surrogates(text: str) -> str:
    """Repair HTML-entity-decoded surrogate halves into valid UTF-8 text.
    """
    if not any(0xD800 <= ord(ch) <= 0xDFFF for ch in text):
        return text
    out: List[str] = []
    i, n = 0, len(text)
    while i < n:
        code = ord(text[i])
        if 0xD800 <= code <= 0xDBFF and i + 1 < n:
            low = ord(text[i + 1])
            if 0xDC00 <= low <= 0xDFFF:
                cp = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
                out.append(chr(cp))
                i += 2
                continue
        if 0xD800 <= code <= 0xDFFF:
            out.append("\uFFFD")
        else:
            out.append(text[i])
        i += 1
    return "".join(out)


def clean_text(raw: Optional[str]) -> Optional[str]:
    """Collapse whitespace, strip control characters, and repair
    surrogate halves (emoji from HTML entities) into valid UTF-8."""
    if raw is None:
        return None
    text = _fix_surrogates(str(raw))
    text = " ".join(text.split())
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text).strip()
    return text or None


def _uniq(seq: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def extract_hashtags(text: Optional[str]) -> List[str]:
    """``["#foo", "#bar"]`` from post text (deduped, order preserved)."""
    if not text:
        return []
    tags = ["#" + m.rstrip(".,;:!?") for m in _HASHTAG_RE.findall(text)]
    return _uniq(t for t in tags if len(t) > 1)


def extract_mentions(text: Optional[str]) -> List[str]:
    """``["@user"]`` from post text (deduped).  Anchored name mentions are
    added by the parser from profile links; this covers literal @handles."""
    if not text:
        return []
    return _uniq("@" + m.rstrip(".,;:!?") for m in _MENTION_RE.findall(text))


def classify_post_type(
    *,
    has_video: bool,
    video_url: Optional[str],
    has_image: bool,
    media_url: Optional[str],
    thumbnail_url: Optional[str],
    has_link_preview: bool,
    external_links: List[str],
    text: Optional[str],
) -> Optional[str]:
    """Classify the post into the canonical enum.

    Priority: video > link-preview > image > text-with-external-link > text.

    * ``video`` - a video player/watch anchor/URL was found.
    * ``link``  - an attachment (link-preview) card was found; or a text post
      that contains external URL(s) (Facebook renders those as link posts).
    * ``image`` - a content image was found (photo posts, shared images).
    * ``text``  - plain status update.
    * ``None``  - nothing identifiable (unexpected container).
    """
    if has_video or video_url:
        return "video"
    if has_link_preview or (external_links and not has_image and not has_video):
        return "link"
    if has_image or media_url or thumbnail_url:
        return "image"
    if external_links:
        return "link"
    if text:
        return "text"
    return None


def _to_iso_and_epoch(dt: Optional[datetime]) -> tuple[Optional[str], Optional[int]]:
    """(ISO-8601 UTC string, epoch int) from a datetime, or (None, None)."""
    if dt is None:
        return None, None
    if dt.tzinfo is None:
        # convention documented in parser.py: naive renderings are UTC
        dt = dt.replace(tzinfo=timezone.utc)
    aware = dt.astimezone(timezone.utc)
    return aware.isoformat(), int(aware.timestamp())


def normalize_post(
    parsed: object,
    *,
    page_name: Optional[str] = None,
    page_id: Optional[str] = None,
    facebook_url: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, object]:
    """Convert one ``ParsedPost`` (or a dict with the same shape) into the
    canonical normalized post dict.

    :param parsed: :class:`~scraper.parser.ParsedPost` or equivalent dict.
    :param page_name: page display name (from the fetched page).
    :param page_id: numeric page id, when publicly derivable.
    :param facebook_url: the canonical page URL the post was scraped from;
                         also used as ``profile_url`` (the source *is* a
                         page/profile URL by construction).
    :param now: injectable clock; used for ``scraped_at`` timestamp.
    """
    scraped_at = now or datetime.now(timezone.utc)
    if scraped_at.tzinfo is None:
        scraped_at = scraped_at.replace(tzinfo=timezone.utc)
    scraped_at_iso = scraped_at.isoformat()
    raw = parsed.to_dict() if isinstance(parsed, ParsedPost) else dict(parsed or {})

    text = clean_text(raw.get("text"))

    hashtags = extract_hashtags(text)
    mentions = _uniq([m for m in raw.get("mentions") or [] if m]
                     + extract_mentions(text))
    external = _uniq([u for u in raw.get("external_links") or [] if u])

    has_video = bool(raw.get("has_video") or raw.get("video_url"))
    has_image = bool(raw.get("has_image") or raw.get("thumbnail_url")
                     or raw.get("media_url"))
    has_link_preview = bool(raw.get("has_link_preview"))
    video_url = raw.get("video_url")
    thumbnail_url = raw.get("thumbnail_url")
    media_url = raw.get("media_url")
    post_type = classify_post_type(
        has_video=has_video,
        video_url=video_url,
        has_image=has_image,
        media_url=media_url,
        thumbnail_url=thumbnail_url,
        has_link_preview=has_link_preview,
        external_links=external,
        text=text,
    )

    published_at, timestamp = _to_iso_and_epoch(raw.get("published_at"))

    # Upgrade type: if media was extracted but classify returned "text",
    # keep the media and adjust the type accordingly.
    if post_type == "text":
        if video_url:
            post_type = "video"
        elif media_url or thumbnail_url:
            post_type = "image"

    # total reactions: explicit public total, else sum of a rendered
    # breakdown (only when at least one per-reaction count exists)
    reactions = raw.get("reactions")
    if reactions is None:
        breakdown_sum = sum(
            v for v in (raw.get(f"reaction_{name}_count")
                        for name in ("like", "love", "care", "haha",
                                     "wow", "sad", "angry"))
            if isinstance(v, int)
        )
        if breakdown_sum:
            reactions = breakdown_sum

    post: Dict[str, object] = {
        "post_id": raw.get("post_id"),
        "facebook_url": facebook_url,
        "post_url": raw.get("post_url"),
        "page_name": page_name,
        "page_id": page_id,
        "profile_url": facebook_url,  # source is a page/profile URL
        "post_type": post_type,
        "published_at": published_at,
        "timestamp": timestamp,
        "text": text,
        "caption": None,  # not separately present in public markup
        "hashtags": hashtags,
        "mentions": mentions,
        "external_links": external,
        "likes": raw.get("likes"),
        "reactions": reactions,
        "comments_count": raw.get("comments_count"),
        "shares": raw.get("shares"),
        "views_count": raw.get("views_count"),
        "reaction_like_count": raw.get("reaction_like_count"),
        "reaction_love_count": raw.get("reaction_love_count"),
        "reaction_care_count": raw.get("reaction_care_count"),
        "reaction_haha_count": raw.get("reaction_haha_count"),
        "reaction_wow_count": raw.get("reaction_wow_count"),
        "reaction_sad_count": raw.get("reaction_sad_count"),
        "reaction_angry_count": raw.get("reaction_angry_count"),
        "media_type": "video" if post_type == "video"
                      else ("image" if post_type == "image" else None),
        "thumbnail_url": thumbnail_url,
        "media_url": media_url,
        "video_url": video_url,
        "transcript": None,              # never public on HTML pages
        "transcript_language": None,     # never public on HTML pages
        "scraped_at": scraped_at_iso,
    }
    for key, value in list(post.items()):
        if isinstance(value, str):
            post[key] = _fix_surrogates(value)
        elif isinstance(value, list):
            post[key] = [_fix_surrogates(v) if isinstance(v, str) else v
                         for v in value]
    return post
