"""Group 3 — deduplication and the stats invariant.

* post_id dedup + fallback SHA-256 fingerprint; first occurrence wins.
* ``discovered == extracted + skipped + failed`` (duplicates tracked
  separately — each removed duplicate is also counted in skipped, exactly as
  ``backend.scraper.scrape_source`` accounts for it).
"""
from __future__ import annotations

from backend.scraper.dedup import dedup_key, dedup_posts, make_fingerprint
from backend.scraper.stats import Stats

from helpers import canonical_post


def test_post_id_dedup_first_occurrence_wins():
    a = canonical_post(post_id="42", text="first version")
    b = canonical_post(post_id="42", text="second version")
    kept, removed = dedup_posts([a, b])
    assert removed == 1
    assert len(kept) == 1
    assert kept[0]["text"] == "first version", "first occurrence must win"


def test_fallback_fingerprint_dedup():
    base = dict(
        canonical_post(post_id=None, text="same body"),
        timestamp=None,
        post_url=None,
    )
    dup = dict(base)
    kept, removed = dedup_posts([base, dup])
    assert removed == 1
    assert kept[0] is base


def test_fingerprint_distinguishes_different_text():
    a = dict(canonical_post(post_id=None, text="body A"), timestamp=None, post_url=None)
    b = dict(canonical_post(post_id=None, text="body B"), timestamp=None, post_url=None)
    kept, removed = dedup_posts([a, b])
    assert removed == 0 and len(kept) == 2


def test_order_preserved():
    posts = [
        canonical_post(post_id="1"),
        canonical_post(post_id="2"),
        canonical_post(post_id="1"),  # duplicate of first
        canonical_post(post_id="3"),
    ]
    kept, removed = dedup_posts(posts)
    assert removed == 1
    assert [p["post_id"] for p in kept] == ["1", "2", "3"]


def test_dedup_key_namespaces():
    assert dedup_key(canonical_post(post_id="42")).startswith("id:")
    none_id = dict(canonical_post(post_id=None), timestamp=None, post_url=None)
    assert dedup_key(none_id).startswith("fp:") and len(dedup_key(none_id)) == 3 + 64


def test_fingerprint_stable():
    p1 = dict(canonical_post(post_id=None), timestamp=None, post_url=None)
    p2 = dict(p1)
    assert make_fingerprint(p1) == make_fingerprint(p2)


def test_stats_invariant_with_duplicates_separate():
    """Mirror scrape_source's accounting: discovered == extracted + skipped +
    failed, with duplicates_removed separate AND also inside skipped."""
    stats = Stats()
    stats.discovered(5)          # 5 parsed containers
    stats.extracted(2)           # 2 returned
    stats.skipped(3)             # 2 filtered + 1 duplicate (see below)
    stats.removed_duplicates(1)  # the duplicate, tracked separately
    stats.failed(0)
    assert stats.invariant_holds()  # 5 == 2 + 3 + 0
    assert stats.duplicates_removed == 1
    total = stats.to_dict()
    assert set(total) == {
        "posts_discovered",
        "posts_extracted",
        "duplicates_removed",
        "posts_skipped",
        "posts_failed",
    }


def test_stats_invariant_broken_when_miscounted():
    stats = Stats()
    stats.discovered(5)
    stats.extracted(3)  # skipped+failed == 0 but extracted < discovered -> invariant false
    assert not stats.invariant_holds()