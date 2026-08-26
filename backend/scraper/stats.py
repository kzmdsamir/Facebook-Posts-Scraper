"""Per-source statistics counters.

``SourceResult.stats`` always contains exactly these five keys:

* ``posts_discovered``    - posts/containers found in the public HTML
* ``posts_extracted``     - posts actually returned (== len(posts))
* ``duplicates_removed``  - posts dropped by deduplication
* ``posts_skipped``       - posts dropped by date/type filters, by the
                            max_posts cap, or as duplicates
* ``posts_failed``        - post containers that failed to parse

Bookkeeping invariant (agreed with the mainline plan):

    posts_discovered == posts_extracted + posts_skipped + posts_failed

``duplicates_removed`` is deliberately *separate* from this invariant: every
removed duplicate is also counted inside ``posts_skipped`` (it is a discovered
post that was not returned).  This keeps the invariant exact while still
exposing the dedup-specific number to the UI.
"""

from __future__ import annotations

from typing import Dict

__all__ = ["STATS_KEYS", "Stats"]

STATS_KEYS = (
    "posts_discovered",
    "posts_extracted",
    "duplicates_removed",
    "posts_skipped",
    "posts_failed",
)


class Stats:
    """Mutable per-source counters (single-threaded by design - the fetcher
    is concurrency-1 per source, so no locking is required)."""

    __slots__ = (
        "posts_discovered", "posts_extracted", "duplicates_removed",
        "posts_skipped", "posts_failed",
    )

    def __init__(self) -> None:
        self.posts_discovered = 0
        self.posts_extracted = 0
        self.duplicates_removed = 0
        self.posts_skipped = 0
        self.posts_failed = 0

    # -- incrementers ---------------------------------------------------
    def discovered(self, n: int = 1) -> None:
        self.posts_discovered += n

    def extracted(self, n: int = 1) -> None:
        self.posts_extracted += n

    def removed_duplicates(self, n: int = 1) -> None:
        self.duplicates_removed += n

    def skipped(self, n: int = 1) -> None:
        self.posts_skipped += n

    def failed(self, n: int = 1) -> None:
        self.posts_failed += n

    # -- reporting ------------------------------------------------------
    def to_dict(self) -> Dict[str, int]:
        return {
            "posts_discovered": self.posts_discovered,
            "posts_extracted": self.posts_extracted,
            "duplicates_removed": self.duplicates_removed,
            "posts_skipped": self.posts_skipped,
            "posts_failed": self.posts_failed,
        }

    def invariant_holds(self) -> bool:
        """``discovered == extracted + skipped + failed`` (dupes separate)."""
        return self.posts_discovered == (
            self.posts_extracted + self.posts_skipped + self.posts_failed
        )

    def explain(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"discovered={self.posts_discovered} "
            f"extracted={self.posts_extracted} "
            f"duplicates_removed={self.duplicates_removed} "
            f"skipped={self.posts_skipped} "
            f"failed={self.posts_failed} "
            f"[invariant={'OK' if self.invariant_holds() else 'BROKEN'}]"
        )