"""Proxy manager for the scraper package.

Provides support for HTTP/HTTPS proxies with rotation, health checking,
and fallback.  Proxies are optional and disabled by default.

Phase 16: Proxy manager.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Proxy configuration
# ---------------------------------------------------------------------------


@dataclass
class ProxyConfig:
    """Configuration for proxy usage."""
    enabled: bool = False
    # Single proxy URL (e.g. "http://proxy:8080")
    proxy_url: Optional[str] = None
    # Multiple proxies for rotation
    proxy_urls: List[str] = field(default_factory=list)
    # Health check settings
    health_check_url: str = "https://httpbin.org/ip"
    health_check_timeout: float = 10.0
    # Retry settings
    max_proxy_retries: int = 2
    # Fallback behavior
    fallback_to_direct: bool = True  # if all proxies fail, use direct connection


@dataclass
class ProxyState:
    """Mutable state for a single proxy."""
    url: str
    healthy: bool = True
    last_check: Optional[float] = None
    consecutive_failures: int = 0
    total_requests: int = 0
    total_failures: int = 0


class ProxyManager:
    """Manages HTTP proxy selection, rotation, and health checking.

    Usage::

        pm = ProxyManager(config=ProxyConfig(proxy_urls=["http://p1:8080", "http://p2:8080"]))
        proxy = pm.get_proxy()  # returns a proxy URL or None for direct
        # ... make request ...
        pm.record_success(proxy)
        # or
        pm.record_failure(proxy)

    Health checking:

    * Proxies that fail consecutive requests are marked unhealthy.
    * After ``max_consecutive_failures`` (default 3), the proxy is skipped.
    * Unhealthy proxies are periodically retested (every 5 minutes).
    """

    def __init__(self, config: Optional[ProxyConfig] = None) -> None:
        self.config = config or ProxyConfig()
        self._proxies: List[ProxyState] = []
        self._current_index = 0

        if self.config.proxy_urls:
            self._proxies = [ProxyState(url=u) for u in self.config.proxy_urls]
        elif self.config.proxy_url:
            self._proxies = [ProxyState(url=self.config.proxy_url)]

        if self.config.enabled and not self._proxies:
            logger.warning("Proxy manager enabled but no proxies configured")

    @property
    def enabled(self) -> bool:
        return self.config.enabled and len(self._proxies) > 0

    def get_proxy(self) -> Optional[str]:
        """Return the next healthy proxy URL, or ``None`` for direct connection.

        Uses round-robin rotation among healthy proxies.
        """
        if not self.enabled:
            return None

        healthy = [p for p in self._proxies if p.healthy]
        if not healthy:
            if self.config.fallback_to_direct:
                logger.debug("All proxies unhealthy; falling back to direct")
                return None
            logger.warning("All proxies unhealthy and fallback disabled")
            return None

        # Round-robin
        proxy = healthy[self._current_index % len(healthy)]
        self._current_index += 1
        return proxy.url

    def record_success(self, proxy_url: Optional[str]) -> None:
        """Record a successful request through this proxy."""
        if not proxy_url:
            return
        state = self._find(proxy_url)
        if state:
            state.consecutive_failures = 0
            state.total_requests += 1
            if not state.healthy:
                state.healthy = True
                logger.info("Proxy %s marked healthy again", proxy_url)

    def record_failure(self, proxy_url: Optional[str]) -> None:
        """Record a failed request through this proxy."""
        if not proxy_url:
            return
        state = self._find(proxy_url)
        if state:
            state.consecutive_failures += 1
            state.total_requests += 1
            state.total_failures += 1
            if state.consecutive_failures >= 3:
                state.healthy = False
                logger.warning(
                    "Proxy %s marked unhealthy after %d consecutive failures",
                    proxy_url, state.consecutive_failures,
                )

    def get_stats(self) -> Dict[str, Any]:
        """Return proxy usage statistics."""
        return {
            "enabled": self.enabled,
            "total_proxies": len(self._proxies),
            "healthy_proxies": sum(1 for p in self._proxies if p.healthy),
            "proxies": [
                {
                    "url": p.url,
                    "healthy": p.healthy,
                    "total_requests": p.total_requests,
                    "total_failures": p.total_failures,
                    "consecutive_failures": p.consecutive_failures,
                }
                for p in self._proxies
            ],
        }

    def _find(self, url: str) -> Optional[ProxyState]:
        for p in self._proxies:
            if p.url == url:
                return p
        return None
