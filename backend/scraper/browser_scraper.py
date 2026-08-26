"""Playwright-based browser scraper for Facebook pages.

Uses a real headless browser to execute JavaScript, scroll the page,
and extract posts that are dynamically loaded via infinite scroll.

Supports authenticated scraping via saved cookies (from cli.py login).
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger("scraper.browser")

COOKIES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "fb_cookies.json"

MAX_SCROLL_ROUNDS = 40
SCROLL_DELAY = 1.5


def _has_browser() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def save_cookies(cookies: list) -> None:
    """Persist browser cookies to disk."""
    COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COOKIES_PATH, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2, ensure_ascii=False)
    logger.info("Saved %d cookies to %s", len(cookies), COOKIES_PATH)


def load_cookies() -> Optional[list]:
    """Load saved cookies from disk, or None if not found."""
    if not COOKIES_PATH.exists():
        return None
    try:
        with open(COOKIES_PATH, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        if cookies:
            logger.info("Loaded %d cookies from %s", len(cookies), COOKIES_PATH)
        return cookies if cookies else None
    except Exception:
        return None


def login_with_browser(timeout_seconds: int = 120) -> bool:
    """Open a visible browser for the user to log into Facebook.

    Polls for Facebook session cookies to appear (indicating successful login).
    Returns True if cookies were saved successfully.
    """
    from playwright.sync_api import sync_playwright

    print("\nA browser window will open. Please log into Facebook.")
    print(f"Waiting up to {timeout_seconds}s for login to complete...\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = context.new_page()
        page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=30000)

        # Poll for login: check every 3s for facebook session cookies
        deadline = time.monotonic() + timeout_seconds
        logged_in = False
        while time.monotonic() < deadline:
            cookies = context.cookies()
            fb_cookies = [c for c in cookies if "facebook.com" in c.get("domain", "")]
            # c_user is the main Facebook session indicator
            has_session = any(c["name"] == "c_user" for c in fb_cookies)
            if has_session:
                logged_in = True
                print("Login detected!")
                break
            time.sleep(3)

        cookies = context.cookies()
        browser.close()

    if logged_in and cookies:
        save_cookies(cookies)
        fb_cookies = [c for c in cookies if "facebook.com" in c.get("domain", "")]
        print(f"Login successful! Saved {len(fb_cookies)} Facebook cookies.")
        return True
    else:
        print("Login not detected. Please try again.")
        return False


def fetch_with_browser(
    url: str,
    *,
    max_posts: Optional[int] = None,
    scroll_rounds: int = MAX_SCROLL_ROUNDS,
    cancel_event: Optional[threading.Event] = None,
    use_cookies: bool = True,
) -> str:
    """Load a Facebook page in a headless browser, scroll to load posts,
    and return the full rendered HTML."""
    from playwright.sync_api import sync_playwright

    html_result = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )

        # Load saved cookies if available
        if use_cookies:
            cookies = load_cookies()
            if cookies:
                context.add_cookies(cookies)
                logger.info("Browser: loaded %d cookies", len(cookies))

        page = context.new_page()

        # Block unnecessary resources to speed up loading
        def route_handler(route):
            if route.request.resource_type in ("image", "media", "font"):
                route.abort()
            else:
                route.continue_()

        page.route("**/*", route_handler)

        try:
            logger.info("Browser: navigating to %s", url)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # Dismiss cookie/login popups if present
            for selector in [
                'button:has-text("Decline optional cookies")',
                'button:has-text("Accept all cookies")',
                'button:has-text("Not Now")',
                'div[role="dialog"] button[aria-label="Close"]',
                '[aria-label="Close"]',
            ]:
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.click()
                        page.wait_for_timeout(500)
                except Exception:
                    pass

            # Check if we hit a login wall
            login_check = page.evaluate("""
                () => {
                    const url = window.location.href;
                    const hasLoginForm = !!document.querySelector('input[name="email"]');
                    const isLoginPage = url.includes('login') || url.includes('checkpoint');
                    return {url, hasLoginForm, isLoginPage};
                }
            """)
            if login_check.get("isLoginPage") or login_check.get("hasLoginForm"):
                logger.warning("Browser: hit login wall at %s", login_check.get("url"))
                if not load_cookies():
                    print("  WARNING: Hit Facebook login wall. Run 'python cli.py login' first.")

            # Count initial posts
            prev_count = page.evaluate("""
                () => document.querySelectorAll('[role="article"]').length
            """)
            logger.info("Browser: initial article count: %d", prev_count)

            # Scroll to load more posts
            stale_rounds = 0
            for i in range(scroll_rounds):
                if cancel_event and cancel_event.is_set():
                    break

                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(int(SCROLL_DELAY * 1000))

                post_count = page.evaluate("""
                    () => document.querySelectorAll('[role="article"]').length
                """)

                if post_count == prev_count:
                    stale_rounds += 1
                    if stale_rounds >= 3:
                        logger.info("Browser: no new posts after %d scrolls, stopping", i)
                        break
                else:
                    stale_rounds = 0
                    logger.info("Browser: scroll %d - %d articles loaded", i + 1, post_count)

                prev_count = post_count

                if max_posts is not None and post_count >= max_posts:
                    logger.info("Browser: reached %d articles (target: %d)", post_count, max_posts)
                    break

            html_result = page.content()
            logger.info("Browser: got %d bytes of HTML", len(html_result))

        except Exception as exc:
            logger.warning("Browser error: %s", exc)
        finally:
            browser.close()

    return html_result


def parse_browser_page(
    html: str,
    page_url: str,
    handle: Optional[str] = None,
) -> "ParsedPage":
    """Parse browser-rendered HTML using DOM + script extraction."""
    from backend.scraper.parser import (
        ParsedPage,
        ParsedPost,
        parse_page,
        find_post_roots,
        _parse_post_root,
        _clean_name,
        _meta_content,
        _page_id_from_url,
    )

    if not html or not html.strip():
        return ParsedPage(page_name=handle, fetched_url=page_url)

    soup = BeautifulSoup(html, "lxml")

    og_title = _clean_name(_meta_content(soup, ("property", "og:title"), ("name", "og:title")))
    og_image = _meta_content(soup, ("property", "og:image"), ("name", "og:image"))
    og_url = _meta_content(soup, ("property", "og:url"), ("name", "og:url"))

    page_name = og_title or handle
    profile_url = og_url or page_url
    page_id = _page_id_from_url(profile_url) or _page_id_from_url(page_url)

    posts = []
    post_errors = []

    # Try DOM-based extraction first
    roots = find_post_roots(soup)
    if roots:
        for root in roots:
            try:
                posts.append(_parse_post_root(root, page_url))
            except Exception as exc:
                post_errors.append({
                    "post_url": "",
                    "code": "extraction_failure",
                    "message": f"DOM parse failed: {exc!r}",
                })

    # Also try script-based extraction for any posts we might have missed
    if not posts:
        from backend.scraper.parser import _extract_posts_from_scripts
        try:
            posts = _extract_posts_from_scripts(html, page_url)
        except Exception as exc:
            post_errors.append({
                "post_url": "",
                "code": "extraction_failure",
                "message": f"script extraction failed: {exc!r}",
            })

    # Deduplicate by post_id
    seen = set()
    unique_posts = []
    for post in posts:
        pid = post.post_id
        if pid and pid in seen:
            continue
        seen.add(pid)
        unique_posts.append(post)

    logger.info(
        "Browser parse: %d DOM roots, %d posts (deduped), %d errors",
        len(roots), len(unique_posts), len(post_errors),
    )

    return ParsedPage(
        page_name=page_name,
        page_id=page_id,
        profile_url=profile_url,
        og_image=og_image,
        posts=unique_posts,
        post_errors=post_errors,
        fetched_url=page_url,
    )
