"""Tests for the shared HTTP client, rate limiter, and proxy manager.

Phase 22-24: Crash/failure/stress tests for new infrastructure modules.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from backend.scraper.dedup import (
    dedup_posts,
    dedup_posts_across_sources,
    make_content_fingerprint,
    make_fingerprint,
    normalize_post_url,
)
from backend.scraper.proxy_manager import ProxyConfig, ProxyManager
from backend.scraper.rate_limiter import (
    CircuitState,
    RateLimiter,
    RetryConfig,
    RetryManager,
)


# ---------------------------------------------------------------------------
# Dedup enhancements
# ---------------------------------------------------------------------------


class TestNormalizePostUrl:
    def test_strips_fbclid(self):
        url = "https://www.facebook.com/photo.php?fbclid=abc123&id=123"
        result = normalize_post_url(url)
        assert "fbclid" not in result
        assert "id=123" in result

    def test_strips_multiple_tracking_params(self):
        url = "https://www.facebook.com/p/123?ref=home&__tn__=K-R"
        result = normalize_post_url(url)
        assert "ref=" not in result
        assert "__tn__=" not in result

    def test_preserves_non_tracking_params(self):
        url = "https://www.facebook.com/photo.php?id=123&v=456"
        result = normalize_post_url(url)
        assert "id=123" in result
        assert "v=456" in result

    def test_none_passthrough(self):
        assert normalize_post_url(None) is None

    def test_empty_string(self):
        assert normalize_post_url("") is None

    def test_trailing_slash_removed(self):
        url = "https://www.facebook.com/page/"
        result = normalize_post_url(url)
        assert not result.endswith("/")

    def test_invalid_url_passthrough(self):
        result = normalize_post_url("not-a-url")
        assert result == "not-a-url"


class TestContentFingerprint:
    def test_same_content_same_fingerprint(self):
        p1 = {"text": "Hello world", "published_at": "2024-01-01T00:00:00Z"}
        p2 = {"text": "Hello world", "published_at": "2024-01-01T00:00:00Z"}
        assert make_content_fingerprint(p1) == make_content_fingerprint(p2)

    def test_different_text_different_fingerprint(self):
        p1 = {"text": "Hello", "published_at": "2024-01-01T00:00:00Z"}
        p2 = {"text": "Goodbye", "published_at": "2024-01-01T00:00:00Z"}
        assert make_content_fingerprint(p1) != make_content_fingerprint(p2)

    def test_empty_text(self):
        p = {"text": "", "published_at": "2024-01-01T00:00:00Z"}
        fp = make_content_fingerprint(p)
        assert "|" in fp


class TestDedupAcrossSources:
    def test_deduplicates_by_post_id(self):
        s1 = [{"post_id": "123", "text": "A"}]
        s2 = [{"post_id": "123", "text": "A"}]
        kept, count = dedup_posts_across_sources(s1, s2)
        assert len(kept) == 1
        assert count == 1

    def test_deduplicates_by_content_fingerprint(self):
        s1 = [{"text": "Same post", "published_at": "2024-01-01T00:00:00Z"}]
        s2 = [{"text": "Same post", "published_at": "2024-01-01T00:00:00Z"}]
        kept, count = dedup_posts_across_sources(s1, s2)
        assert len(kept) == 1
        assert count == 1

    def test_keeps_different_posts(self):
        s1 = [{"post_id": "1", "text": "A"}]
        s2 = [{"post_id": "2", "text": "B"}]
        kept, count = dedup_posts_across_sources(s1, s2)
        assert len(kept) == 2
        assert count == 0

    def test_empty_sources(self):
        kept, count = dedup_posts_across_sources([], [])
        assert kept == []
        assert count == 0


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_acquire_when_tokens_available(self):
        rl = RateLimiter(rate=100, burst=5)
        rl.acquire(1)  # should not block
        assert rl.available >= 3

    def test_acquire_blocks_when_empty(self):
        rl = RateLimiter(rate=10, burst=1)
        rl.acquire(1)  # uses the burst token
        start = time.monotonic()
        rl.acquire(1)  # should wait ~0.1s
        elapsed = time.monotonic() - start
        assert elapsed >= 0.05  # at least some wait

    def test_burst_refills(self):
        rl = RateLimiter(rate=1000, burst=5)
        for _ in range(5):
            rl.acquire(1)
        time.sleep(0.05)  # let tokens refill
        assert rl.available > 0


# ---------------------------------------------------------------------------
# Retry manager
# ---------------------------------------------------------------------------


class TestRetryManager:
    def test_success_resets_failures(self):
        rm = RetryManager(config=RetryConfig(max_retries=3))
        rm.record_failure()
        rm.record_failure()
        rm.record_success()
        assert rm.state.consecutive_failures == 0
        assert rm.state.circuit_state == CircuitState.CLOSED

    def test_circuit_opens_after_threshold(self):
        cfg = RetryConfig(circuit_threshold=3)
        rm = RetryManager(config=cfg)
        for _ in range(3):
            rm.record_failure()
        assert rm.state.circuit_state == CircuitState.OPEN

    def test_circuit_rejects_when_open(self):
        cfg = RetryConfig(circuit_threshold=2)
        rm = RetryManager(config=cfg)
        rm.record_failure()
        rm.record_failure()
        assert not rm.should_retry(1, Exception("test"))

    def test_circuit_half_open_after_reset(self):
        cfg = RetryConfig(circuit_threshold=1, circuit_reset_seconds=0.01)
        rm = RetryManager(config=cfg)
        rm.record_failure()
        assert rm.state.circuit_state == CircuitState.OPEN
        time.sleep(0.02)
        assert rm.should_retry(1, Exception("test"))
        assert rm.state.circuit_state == CircuitState.HALF_OPEN

    def test_retry_history_tracked(self):
        rm = RetryManager(config=RetryConfig(max_retries=1))
        rm.wait_before_retry(1, Exception("test"))
        assert len(rm.state.retry_history) == 1
        assert rm.state.retry_history[0] > 0

    def test_should_retry_within_limit(self):
        cfg = RetryConfig(max_retries=3)
        rm = RetryManager(config=cfg)
        assert rm.should_retry(1, Exception("test"))
        assert rm.should_retry(3, Exception("test"))

    def test_should_not_retry_beyond_limit(self):
        cfg = RetryConfig(max_retries=2)
        rm = RetryManager(config=cfg)
        assert not rm.should_retry(3, Exception("test"))


# ---------------------------------------------------------------------------
# Proxy manager
# ---------------------------------------------------------------------------


class TestProxyManager:
    def test_disabled_returns_none(self):
        pm = ProxyManager(config=ProxyConfig(enabled=False))
        assert pm.get_proxy() is None

    def test_single_proxy(self):
        pm = ProxyManager(config=ProxyConfig(enabled=True, proxy_url="http://proxy:8080"))
        assert pm.get_proxy() == "http://proxy:8080"

    def test_rotation(self):
        pm = ProxyManager(config=ProxyConfig(
            enabled=True,
            proxy_urls=["http://p1:8080", "http://p2:8080"],
        ))
        p1 = pm.get_proxy()
        p2 = pm.get_proxy()
        assert p1 != p2

    def test_unhealthy_proxy_skipped(self):
        pm = ProxyManager(config=ProxyConfig(
            enabled=True,
            proxy_urls=["http://p1:8080", "http://p2:8080"],
        ))
        pm.record_failure("http://p1:8080")
        pm.record_failure("http://p1:8080")
        pm.record_failure("http://p1:8080")
        for _ in range(10):
            assert pm.get_proxy() == "http://p2:8080"

    def test_fallback_to_direct(self):
        pm = ProxyManager(config=ProxyConfig(
            enabled=True,
            proxy_url="http://proxy:8080",
            fallback_to_direct=True,
        ))
        pm.record_failure("http://proxy:8080")
        pm.record_failure("http://proxy:8080")
        pm.record_failure("http://proxy:8080")
        assert pm.get_proxy() is None  # fallback

    def test_stats(self):
        pm = ProxyManager(config=ProxyConfig(
            enabled=True,
            proxy_urls=["http://p1:8080"],
        ))
        pm.record_success("http://p1:8080")
        stats = pm.get_stats()
        assert stats["enabled"] is True
        assert stats["total_proxies"] == 1
        assert stats["proxies"][0]["total_requests"] == 1
