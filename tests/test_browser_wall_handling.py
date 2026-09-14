"""Browser wall handling: anonymous retry, and feed-less partial surfacing."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import backend.scraper.browser_scraper as bs
from backend.scraper.parser import ParsedPage, ParsedPost


def _valid_html() -> str:
    return (
        '<html><body>'
        '<script type="application/json" data-fb-graphql-feed="1">'
        '{"data":{"nodes":[{"post_id":"123"}]}}'
        "</script>"
        '<div data-testid="post">' + "x" * 3000 + "</div>"
        "</body></html>"
    )


def _wall_html() -> str:
    return '<html><body><input name="email" id="email"></body></html>'


def _feed_missing_html() -> str:
    return (
        '<html><body><!-- fb-scrape-feed-missing -->'
        '<div data-testid="post">' + "x" * 3000 + "</div>"
        '"post_id":"987"'
        "</body></html>"
    )


def _parsed_page(n_posts: int = 3) -> ParsedPage:
    posts = [
        ParsedPost(
            post_id=f"p{i}",
            published_at=datetime.now(timezone.utc),
        )
        for i in range(n_posts)
    ]
    return ParsedPage(
        page_name="Test Page",
        page_id="123",
        posts=posts,
        fetched_url="https://www.facebook.com/test",
    )


def test_wall_first_attempt_retries_anonymous():
    seen = []
    real_fetch = bs.fetch_with_browser

    def fake_fetch(*args, **kwargs):
        seen.append(kwargs.get("use_cookies"))
        if len(seen) == 1:
            return _wall_html()
        return _valid_html()

    with patch.object(bs, "fetch_with_browser", side_effect=fake_fetch), \
         patch.object(bs, "parse_browser_page", return_value=_parsed_page()):
        result = bs.scrape_source_browser(
            "https://www.facebook.com/test",
            max_posts=10,
            account_name="default",
        )
    # attempt 1 uses cookies, attempt 2 drops them
    assert seen == [True, False]
    assert result.errors == []
    assert len(result.posts) == 3


def test_feed_missing_partial_surfaces_error():
    with patch.object(bs, "fetch_with_browser", return_value=_feed_missing_html()), \
         patch.object(bs, "parse_browser_page", return_value=_parsed_page()):
        result = bs.scrape_source_browser("https://www.facebook.com/test")
    codes = [e.get("code") for e in result.errors]
    assert "partial_feed" in codes
    # partial DOM posts are still kept so the caller can store what exists
    assert len(result.posts) == 3


def test_clean_feed_has_no_partial_error():
    with patch.object(bs, "fetch_with_browser", return_value=_valid_html()), \
         patch.object(bs, "parse_browser_page", return_value=_parsed_page()):
        result = bs.scrape_source_browser("https://www.facebook.com/test")
    assert result.errors == []
    assert len(result.posts) == 3