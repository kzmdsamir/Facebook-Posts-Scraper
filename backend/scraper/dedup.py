"""Deduplication for normalized posts.

Rules (per product spec):

* Primary key: ``post_id`` (Facebook's numeric id extracted from the
  permalink).  Two posts with the same ``post_id`` are duplicates.
* Fallback key when ``post_id`` is ``None``: a SHA-256 fingerprint of
  ``page_id | published_at | text[:200]``.  This is stable across re-scrapes
  and does not depend on document order.
* First occurrence wins; later duplicates are dropped and counted.
* Operates on **normalized** posts (the canonical dict), so call it AFTER
  ``normalizer.normalize_post`` has run (``published_at`` must already be a
  canonical ISO string etc.).
"""

from __future__ import annotations

import hashlib
from typing import Dict, List, Set, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

__all__ = ["make_fingerprint", "dedup_posts", "dedup_key", "normalize_post_url"]

#: How many characters of the text participate in the fallback fingerprint.
#: Long enough to be discriminating, short enough to bound memory.
_TEXT_FINGERPRINT_LEN = 200


def _stringify(value: object) -> str:
    return str(value) if value is not None else ""


def normalize_post_url(url: str | None) -> str | None:
    """Normalize a Facebook post URL to catch slight variations.

    Strips tracking params (fbclid, ref, etc.), normalizes path separators,
    and removes trailing slashes.  This allows URL-based dedup to catch the
    same post linked with different query strings.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    # Strip common tracking params
    tracked_params = {
        "fbclid", "ref", "source", " Medium", "medium",
        "__cft__", "__tn__", "hc_entry", "action_type",
    }
    qs = parse_qs(parsed.query, keep_blank_values=False)
    cleaned_qs = {k: v for k, v in qs.items() if k.lower() not in tracked_params}
    cleaned_query = urlencode(cleaned_qs, doseq=True) if cleaned_qs else ""
    # Normalize path: remove trailing slash, collapse double slashes
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, cleaned_query, ""))


def make_fingerprint(post: Dict[str, object]) -> str:
    """SHA-256 fingerprint for posts without a ``post_id``.

    Fingerprint = sha256 of ``page_id | published_at | text[:200]``.
    """
    page_id = _stringify(post.get("page_id"))
    published_at = _stringify(post.get("published_at"))
    text = _stringify(post.get("text"))[:_TEXT_FINGERPRINT_LEN]
    payload = f"{page_id}|{published_at}|{text}"
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()


def make_content_fingerprint(post: Dict[str, object]) -> str:
    """Cross-source content fingerprint — identifies the same post
    regardless of which page shared it.

    Uses text hash + timestamp + approximate engagement to detect
    the same content reposted or shared across pages.
    """
    text = _stringify(post.get("text"))[:_TEXT_FINGERPRINT_LEN]
    published_at = _stringify(post.get("published_at"))
    text_hash = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"{text_hash}|{published_at}"


def dedup_key(post: Dict[str, object]) -> str:
    """Return the dedup key for one post: ``post_id`` when present, else the
    fingerprint.  The ``id:`` / ``fp:`` prefixes keep the namespaces apart so
    a numeric post_id can never collide with a hex fingerprint."""
    post_id = _stringify(post.get("post_id"))
    if post_id:
        return f"id:{post_id}"
    return f"fp:{make_fingerprint(post)}"


def dedup_posts(posts: List[Dict[str, object]]) -> Tuple[List[Dict[str, object]], int]:
    """Deduplicate sequentially; keep first occurrences.

    :returns: ``(kept_posts, duplicates_removed)``.  ``kept_posts`` preserve
              the input order; ``duplicates_removed`` is the number of posts
              dropped.
    """
    seen: Set[str] = set()
    kept: List[Dict[str, object]] = []
    duplicates_removed = 0
    for post in posts:
        key = dedup_key(post)
        if key in seen:
            duplicates_removed += 1
            continue
        seen.add(key)
        kept.append(post)
    return kept, duplicates_removed


def dedup_posts_across_sources(
    *source_posts: List[Dict[str, object]],
) -> Tuple[List[Dict[str, object]], int]:
    """Deduplicate posts across multiple sources within the same job.

    First deduplicates within each source, then deduplicates across sources
    using both post_id and content fingerprinting.

    :returns: ``(kept_posts, duplicates_removed)`` across all sources.
    """
    seen_ids: Set[str] = set()
    seen_content: Set[str] = set()
    all_kept: List[Dict[str, object]] = []
    total_duplicates = 0

    for posts in source_posts:
        kept, within_dupes = dedup_posts(posts)
        total_duplicates += within_dupes

        for post in kept:
            key = dedup_key(post)
            if key in seen_ids:
                total_duplicates += 1
                continue

            content_fp = make_content_fingerprint(post)
            if content_fp in seen_content:
                total_duplicates += 1
                continue

            seen_ids.add(key)
            seen_content.add(content_fp)
            all_kept.append(post)

    return all_kept, total_duplicates