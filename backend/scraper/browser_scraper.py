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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger("scraper.browser")

COOKIES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "fb_cookies.json"
CREDENTIALS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "fb_credentials.json"

MAX_SCROLL_ROUNDS = 40
SCROLL_DELAY = 1.5


def _has_browser() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def save_cookies(cookies: list, account_name: str | None = None) -> None:
    """Persist browser cookies to disk.

    If ``account_name`` is given, saves to ``data/fb_cookies_<account_name>.json``
    and also updates the credentials index file.
    """
    data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    if account_name:
        path = data_dir / f"fb_cookies_{account_name}.json"
    else:
        path = COOKIES_PATH

    with open(path, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2, ensure_ascii=False)
    logger.info("Saved %d cookies to %s", len(cookies), path)

    # Update credentials index
    if account_name:
        _update_credentials_index(account_name, path)


def _update_credentials_index(account_name: str, cookies_path: Path) -> None:
    """Add/update an account in the credentials index."""
    index = load_credentials()
    index[account_name] = {
        "cookies_file": str(cookies_path.name),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    logger.info("Updated credentials index: %s", account_name)


def load_credentials() -> dict:
    """Load the credentials index: {account_name: {cookies_file, saved_at}}."""
    if not CREDENTIALS_PATH.exists():
        return {}
    try:
        with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def list_accounts() -> list[str]:
    """Return names of all saved Facebook accounts."""
    return list(load_credentials().keys())


def load_cookies(account_name: str | None = None) -> Optional[list]:
    """Load saved cookies from disk, or None if not found.

    If ``account_name`` is given, loads that specific account's cookies.
    Otherwise loads the default cookies file.
    """
    if account_name:
        creds = load_credentials()
        if account_name not in creds:
            logger.warning("Account '%s' not found in credentials", account_name)
            return None
        path = CREDENTIALS_PATH.parent / creds[account_name]["cookies_file"]
    else:
        path = COOKIES_PATH

    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        if cookies:
            logger.info("Loaded %d cookies from %s", len(cookies), path)
        return cookies if cookies else None
    except Exception:
        return None


def login_with_browser(timeout_seconds: int = 120, account_name: str | None = None) -> bool:
    """Open a visible browser for the user to log into Facebook.

    Polls for Facebook session cookies to appear (indicating successful login).
    Returns True if cookies were saved successfully.

    :param timeout_seconds: how long to wait for login (default 120s).
    :param account_name: optional label to save cookies under a specific name.
    """
    from playwright.sync_api import sync_playwright

    label = f" for account '{account_name}'" if account_name else ""
    print(f"\nA browser window will open. Please log into Facebook{label}.")
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
        save_cookies(cookies, account_name=account_name)
        fb_cookies = [c for c in cookies if "facebook.com" in c.get("domain", "")]
        print(f"Login successful! Saved {len(fb_cookies)} Facebook cookies.")
        if account_name:
            print(f"Account saved as '{account_name}'. Use --account {account_name} to scrape with it.")
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
    account_name: Optional[str] = None,
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
            cookies = load_cookies(account_name=account_name)
            if cookies:
                context.add_cookies(cookies)
                logger.info("Browser: loaded %d cookies (account=%s)", len(cookies), account_name or "default")

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
                if not load_cookies(account_name=account_name):
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

    # Always try DOM-based extraction first
    roots = find_post_roots(soup)
    dom_posts = []
    if roots:
        for root in roots:
            try:
                dom_posts.append(_parse_post_root(root, page_url))
            except Exception as exc:
                post_errors.append({
                    "post_url": "",
                    "code": "extraction_failure",
                    "message": f"DOM parse failed: {exc!r}",
                })

    # Always try script-based extraction (modern Facebook embeds JSON in scripts)
    from backend.scraper.parser import _extract_posts_from_scripts
    script_posts = []
    try:
        script_posts = _extract_posts_from_scripts(html, page_url)
    except Exception as exc:
        post_errors.append({
            "post_url": "",
            "code": "extraction_failure",
            "message": f"script extraction failed: {exc!r}",
        })

    # Merge: use script posts as primary (they have richer data),
    # add any DOM posts whose post_id isn't already found in script results
    seen_ids = set()
    for post in script_posts:
        if post.post_id:
            seen_ids.add(post.post_id)
        posts.append(post)

    for post in dom_posts:
        if post.post_id and post.post_id in seen_ids:
            continue
        seen_ids.add(post.post_id or "")
        posts.append(post)

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
