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
from typing import Dict, List, Tuple

__all__ = ["make_fingerprint", "dedup_posts", "dedup_key"]

#: How many characters of the text participate in the fallback fingerprint.
#: Long enough to be discriminating, short enough to bound memory.
_TEXT_FINGERPRINT_LEN = 200


def _stringify(value: object) -> str:
    return str(value) if value is not None else ""


def make_fingerprint(post: Dict[str, object]) -> str:
    """SHA-256 fingerprint for posts without a ``post_id``.

    Fingerprint = sha256 of ``page_id | published_at | text[:200]``.
    """
    page_id = _stringify(post.get("page_id"))
    published_at = _stringify(post.get("published_at"))
    text = _stringify(post.get("text"))[:_TEXT_FINGERPRINT_LEN]
    payload = f"{page_id}|{published_at}|{text}"
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()


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
    seen = set()
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