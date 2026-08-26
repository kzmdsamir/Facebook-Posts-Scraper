"""Facebook-specific transport adapters.

Provides two implementations of the :class:`crawler.Transport` protocol:
  * :class:`FacebookHttpTransport` — single HTTP fetch via ``Fetcher``.
  * :class:`FacebookBrowserTransport` — Playwright headless browser with
    scrolling, cookie injection, and popup dismissal.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from ..crawler import FetchResult
from ..fetcher import Fetcher

logger = logging.getLogger("scraper.adapters.facebook")


# ---------------------------------------------------------------------------
# HTTP transport (single page fetch)
# ---------------------------------------------------------------------------

class FacebookHttpTransport:
    """Transport that fetches a single page via HTTP (like the original scraper).

    Uses :class:`fetcher.Fetcher` — the same httpx-based fetcher that
    already handles throttling, backoff, robots.txt, and brotli decoding.
    """

    def __init__(self, cancel_event: Optional[threading.Event] = None) -> None:
        self._cancel_event = cancel_event
        self._fetcher: Optional[Fetcher] = None

    def fetch(self, url: str, *, cancel_event: Optional[threading.Event] = None) -> FetchResult:
        evt = cancel_event or self._cancel_event
        self._fetcher = Fetcher(cancel_event=evt)
        try:
            result = self._fetcher.fetch_page(url)
            return FetchResult(
                html=result.html,
                final_url=result.final_url,
                meta={
                    "variant": result.variant,
                    "status_code": result.status_code,
                },
            )
        finally:
            self._fetcher.close()

    def close(self) -> None:
        if self._fetcher is not None:
            self._fetcher.close()
            self._fetcher = None


# ---------------------------------------------------------------------------
# Browser transport (Playwright with scrolling)
# ---------------------------------------------------------------------------

class FacebookBrowserTransport:
    """Transport that renders the page in a headless browser.

    Delegates to ``browser_scraper.fetch_with_browser`` for scrolling and
    cookie management, then returns the rendered HTML for parsing.
    """

    def __init__(
        self,
        *,
        use_cookies: bool = True,
        scroll_rounds: int = 40,
        max_posts: Optional[int] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> None:
        self.use_cookies = use_cookies
        self.scroll_rounds = scroll_rounds
        self.max_posts = max_posts
        self._cancel_event = cancel_event

    def fetch(self, url: str, *, cancel_event: Optional[threading.Event] = None) -> FetchResult:
        from ..browser_scraper import fetch_with_browser

        evt = cancel_event or self._cancel_event
        html = fetch_with_browser(
            url,
            max_posts=self.max_posts,
            scroll_rounds=self.scroll_rounds,
            cancel_event=evt,
            use_cookies=self.use_cookies,
        )
        return FetchResult(
            html=html,
            final_url=url,
            meta={"transport": "browser"},
        )

    def close(self) -> None:
        pass  # browser is closed inside fetch_with_browser


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_facebook_transport(
    *,
    use_browser: bool = False,
    cancel_event: Optional[threading.Event] = None,
    **kwargs,
):
    """Create the appropriate Facebook transport.

    :param use_browser: if True, use Playwright; if False, use HTTP.
    :param cancel_event: optional cancellation signal.
    :param kwargs: passed to the transport constructor.
    """
    if use_browser:
        return FacebookBrowserTransport(cancel_event=cancel_event, **kwargs)
    return FacebookHttpTransport(cancel_event=cancel_event)
