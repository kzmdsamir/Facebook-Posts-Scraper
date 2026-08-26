"""Crawler — transport-agnostic orchestrator for scraping a single source.

The :class:`Crawler` encapsulates the full pipeline:
  1. Validate the URL
  2. Fetch HTML via a pluggable transport (HTTP or browser)
  3. Parse HTML into posts
  4. Normalize, filter, dedup, cap

Transport adapters are injected via the ``transport`` parameter.  The
crawler never knows whether pages come from an httpx GET, a Playwright
browser, or a mock.

The existing ``scrape_source()`` function in ``__init__.py`` remains the
public API — it delegates to ``Crawler`` internally so existing callers
(workers, CLI, tests) are unaffected.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol

from .dedup import dedup_posts
from .errors import (
    InvalidUrl,
    OperationCancelled,
    ScraperError,
    UnsupportedUrl,
)
from .normalizer import normalize_post
from .parser import parse_page
from .stats import Stats
from .url_validator import validate_or_raise

logger = logging.getLogger("scraper.crawler")


# ---------------------------------------------------------------------------
# Transport protocol
# ---------------------------------------------------------------------------

@dataclass
class FetchResult:
    """Result of fetching one page of HTML from a transport."""

    html: str
    final_url: str
    meta: dict[str, Any] = field(default_factory=dict)


class Transport(Protocol):
    """Transport adapter contract — the crawler calls this to get HTML."""

    def fetch(
        self,
        url: str,
        *,
        cancel_event: Optional[threading.Event] = None,
    ) -> FetchResult:
        """Fetch the HTML for ``url``.  May raise ScraperError subclasses."""
        ...

    def close(self) -> None:
        """Release any resources held by the transport."""
        ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _handle_of(normalized_url: str) -> Optional[str]:
    """Best-effort handle from a normalized URL."""
    from urllib.parse import urlparse
    path = urlparse(normalized_url).path
    segments = [s for s in path.split("/") if s]
    if not segments:
        return None
    if segments[0] in ("profile.php", "people"):
        return None
    return segments[0]


def _passes_filters(post: Dict[str, Any], options: Any) -> bool:
    """Date-range and post-type filter evaluation."""
    from datetime import date, datetime

    if getattr(options, "post_type", None) is not None and post.get("post_type") != options.post_type:
        return False
    if getattr(options, "start_date", None) is not None or getattr(options, "end_date", None) is not None:
        iso = post.get("published_at")
        if not iso:
            return False
        try:
            d = datetime.fromisoformat(str(iso)).date()
        except ValueError:
            return False
        if getattr(options, "start_date", None) is not None and d < date.fromisoformat(options.start_date):
            return False
        if getattr(options, "end_date", None) is not None and d > date.fromisoformat(options.end_date):
            return False
    return True


ProgressCallback = Optional[Callable[[Dict[str, Any]], None]]


# ---------------------------------------------------------------------------
# Crawler
# ---------------------------------------------------------------------------

@dataclass
class CrawlResult:
    """Structured result from a single-source crawl."""

    url: str
    page_name: Optional[str] = None
    page_id: Optional[str] = None
    posts: List[Dict[str, Any]] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)
    errors: List[Dict[str, str]] = field(default_factory=list)


class Crawler:
    """Transport-agnostic orchestrator for scraping one Facebook source.

    Usage::

        crawler = Crawler(transport=MyTransport())
        result = crawler.crawl(url, options=opts, progress_cb=cb, cancel_event=evt)
    """

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def crawl(
        self,
        url: str,
        options: Any = None,
        progress_cb: ProgressCallback = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> CrawlResult:
        """Run the full validate → fetch → parse → normalize → dedup pipeline.

        Returns a :class:`CrawlResult` (never raises for source-level failures).
        """
        from ..scraper import ScrapeOptions

        if options is None:
            options = ScrapeOptions(urls=[url])
        elif isinstance(options, dict):
            options = ScrapeOptions.from_dict(options)

        stats = Stats()
        errors_list: List[Dict[str, str]] = []
        posts_out: List[Dict[str, Any]] = []
        handle_counter = 0

        def emit(stage: str) -> None:
            if progress_cb is None:
                return
            try:
                progress_cb({
                    "page": url,
                    "stage": stage,
                    "posts_found": stats.posts_discovered,
                    "posts_processed": handle_counter,
                })
            except Exception:
                pass

        emit("starting")

        # 1. Validate
        try:
            normalized_url = validate_or_raise(url)
        except (InvalidUrl, UnsupportedUrl) as exc:
            errors_list.append({"url": url, "code": exc.code, "message": exc.message})
            emit("failed")
            return CrawlResult(url=url, stats=stats.to_dict(), errors=errors_list)

        page_name: Optional[str] = None
        page_id: Optional[str] = None

        # 2. Fetch + parse via transport
        try:
            emit("fetching")
            fetch_result = self.transport.fetch(normalized_url, cancel_event=cancel_event)
            emit("parsing")
            page = parse_page(
                fetch_result.html,
                page_url=fetch_result.final_url,
                handle=_handle_of(normalized_url),
            )
        except OperationCancelled as exc:
            errors_list.append({"url": url, "code": exc.code, "message": exc.message})
            emit("failed")
            return CrawlResult(url=url, stats=stats.to_dict(), errors=errors_list)
        except ScraperError as exc:
            errors_list.append({"url": url, "code": exc.code, "message": exc.message})
            emit("failed")
            return CrawlResult(url=url, stats=stats.to_dict(), errors=errors_list)

        page_name = page.page_name
        page_id = page.page_id

        # 3. Normalize, filter, dedup, cap
        stats.discovered(len(page.posts) + len(page.post_errors))
        for entry in page.post_errors:
            stats.failed(1)
            handle_counter += 1
            errors_list.append({"url": url, **entry})

        pending: List[Dict[str, Any]] = []
        for parsed_post in page.posts:
            if cancel_event is not None and cancel_event.is_set():
                errors_list.append({
                    "url": url,
                    "code": OperationCancelled.code,
                    "message": OperationCancelled().message,
                })
                emit("failed")
                return CrawlResult(
                    url=url, page_name=page_name, page_id=page_id,
                    posts=posts_out, stats=stats.to_dict(), errors=errors_list)

            try:
                post = normalize_post(
                    parsed_post,
                    page_name=page_name,
                    page_id=page_id,
                    facebook_url=normalized_url,
                )
            except Exception as exc:
                stats.failed(1)
                handle_counter += 1
                errors_list.append({
                    "post_url": parsed_post.post_url or url,
                    "code": "extraction_failure",
                    "message": f"failed to normalize a post: {exc!r}",
                })
                emit("processing")
                continue

            if not _passes_filters(post, options):
                stats.skipped(1)
                handle_counter += 1
                emit("processing")
                continue
            pending.append(post)
            handle_counter += 1
            emit("processing")

        # dedup
        kept, duplicates = dedup_posts(pending)
        stats.removed_duplicates(duplicates)
        if duplicates:
            stats.skipped(duplicates)
            handle_counter += duplicates

        # max_posts cap
        if getattr(options, "max_posts", None) is not None and len(kept) > options.max_posts:
            trimmed = len(kept) - options.max_posts
            kept = kept[:options.max_posts]
            stats.skipped(trimmed)
            handle_counter += trimmed

        stats.extracted(len(kept))
        posts_out = kept
        emit("completed")

        return CrawlResult(
            url=url,
            page_name=page_name,
            page_id=page_id,
            posts=posts_out,
            stats=stats.to_dict(),
            errors=errors_list,
        )
