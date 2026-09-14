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
import hashlib

from bs4 import BeautifulSoup
from backend.scraper.parser import find_post_roots

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
            # A login without --account is stored under the plain default
            # file rather than the credentials index; fall back to it so
            # account_name="default" still unlocks the session.
            if account_name == "default":
                path = COOKIES_PATH
            else:
                logger.warning("Account '%s' not found in credentials", account_name)
                return None
        else:
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
    progress_callback: Optional[Callable[..., None]] = None,
) -> str:
    """Load a Facebook page in a headless browser, scroll to load posts,
    and return the full rendered HTML."""
    from playwright.sync_api import sync_playwright

    def _report(found: int) -> None:
        if progress_callback:
            try:
                progress_callback(posts_found=found)
            except Exception:
                pass

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

            # Page hub layout: click the "All" / "Posts" timeline tab so the
            # real feed renders, else scroll only works on a thin stub.
            try:
                clicked = page.evaluate("""
                    () => {
                        const els = Array.from(document.querySelectorAll('[role="tab"]'));
                        const t = els.find(e => /^\\s*(All|Posts)\\s*$/i.test((e.innerText || "").trim()));
                        if (t) { t.click(); return true; }
                        return false;
                    }
                """)
                if clicked:
                    page.wait_for_timeout(1500)
            except Exception:
                pass

            # Scroll to load more posts. Facebook virtualizes the feed: only a
            # few cards stay mounted at a time while scrolling, so we must
            # snapshot each round and accumulate the unique post containers
            # rather than grab a single final page.content() (which would only
            # hold whatever is mounted at scroll-end).
            def _snapshot_fingerprint(text: str) -> str:
                return hashlib.sha1(
                    text.encode("utf-8", "surrogatepass")
                ).hexdigest()[:24]

            # Facebook's Comet feed loads the next batch of stories via
            # POST /api/graphql/ responses, not new DOM in the page.  Capture
            # those payloads (they carry full post IDs, timestamps, texts and
            # engagement counts) and embed them into the returned snapshot.
            graphql_payloads: List[str] = []
            graphql_post_ids: set = set()

            def _on_response(response):
                try:
                    if not response.url.endswith("/api/graphql/"):
                        return
                    body = response.text()
                except Exception:
                    return
                if '"post_id"' not in body or "creation_time" not in body:
                    return
                new_ids = set(
                    re.findall(r'"post_id"\s*:\s*"(\d+)"', body)
                )
                if not new_ids - graphql_post_ids:
                    return
                graphql_post_ids.update(new_ids)
                graphql_payloads.append(body)

            page.on("response", _on_response)

            dom_pool: List[str] = []
            dom_seen: set = set()
            script_pool: List[str] = []
            script_seen: set = set()
            stale_rounds = 0

            for i in range(scroll_rounds):
                if cancel_event and cancel_event.is_set():
                    break

                gql_before = len(graphql_post_ids)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(int(SCROLL_DELAY * 1000))

                soup = BeautifulSoup(page.content(), "lxml")
                roots = find_post_roots(soup)
                fresh_new = 0

                for root in roots:
                    aria = root.get("aria-label") or ""
                    if aria.startswith("Comment by"):
                        continue
                    text = root.get_text(" ", strip=True)[:4000]
                    if not text or len(text) < 20:
                        continue
                    # Drop comment previews rendered inside the feed (they look
                    # like "Name · 2h … Like Reply").
                    if re.search(r"\bLike\s*Reply\b", text):
                        continue
                    key = _snapshot_fingerprint(text)
                    if key in dom_seen:
                        continue
                    dom_seen.add(key)
                    dom_pool.append(str(root))
                    fresh_new += 1

                # Capture embedded Comet/Relay JSON that carries post data.
                for tag in soup.find_all("script"):
                    data = tag.string or ""
                    if '"post_id"' in data and len(data) < 200_000:
                        key = _snapshot_fingerprint(data)
                        if key in script_seen:
                            continue
                        script_seen.add(key)
                        script_pool.append(str(tag))
                        fresh_new += 1

                # When the Comet feed is unreachable (login wall), the only
                # posts come from the rendered DOM; keep scrolling longer
                # instead of giving up after only 3 quiet rounds.
                stale_limit = 3 if graphql_post_ids else 6
                if fresh_new == 0 and len(graphql_post_ids) == gql_before:
                    stale_rounds += 1
                    if stale_rounds >= stale_limit:
                        logger.info(
                            "Browser: no new posts after %d scrolls, stopping",
                            stale_rounds,
                        )
                        break
                else:
                    stale_rounds = 0
                    logger.info(
                        "Browser: scroll %d - %d posts accumulated "
                        "(%d DOM, %d script, %d graphql responses, %d post_ids)",
                        i + 1,
                        len(dom_pool) + len(script_pool) + len(graphql_post_ids),
                        len(dom_pool),
                        len(script_pool),
                        len(graphql_payloads),
                        len(graphql_post_ids),
                    )
                    _report(
                        len(dom_pool) + len(script_pool) + len(graphql_post_ids)
                    )

                if max_posts is not None and (
                    len(dom_pool) + len(graphql_post_ids) >= max_posts
                ):
                    logger.info(
                        "Browser: reached %d posts (target: %d)",
                        len(dom_pool) + len(graphql_post_ids), max_posts,
                    )
                    break

            gql_blocks = "".join(
                '<script type="application/json" data-fb-graphql-feed="1">'
                + payload
                + "</script>"
                for payload in graphql_payloads
            )
            # Append the final fully-scrolled DOM too. The accumulated roots
            # and graphql blocks usually carry enough, but Facebook's feed is
            # heavily virtualized and the last page state holds the freshest
            # React/Relay store (scripts far larger than the snapshot cap) —
            # the parser extracts far more from the whole document.
            try:
                final_dom = page.content()
            except Exception:
                final_dom = ""
            # Marker: the Comet feed (graphql blocks generally carry the real
            # timeline) never loaded.  A handful of DOM stubs alone means a
            # partial/walled view, and the caller should not report it as a
            # clean scrape.
            feed_marker = (
                "<!-- fb-scrape-feed-missing -->"
                if not graphql_payloads
                else ""
            )
            html_result = (
                "<html><body>"
                + "".join(dom_pool)
                + "".join(script_pool)
                + gql_blocks
                + feed_marker
                + final_dom
                + "</body></html>"
            )
            logger.info(
                "Browser: accumulated snapshot %d bytes (%d DOM, %d script, "
                "%d graphql blocks)",
                len(html_result), len(dom_pool), len(script_pool),
                len(graphql_payloads),
            )

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

    # Rich Comet feed payloads captured from the browser's own /api/graphql/
    # requests (post IDs, exact timestamps, texts and engagement counts).
    from backend.scraper.parser import extract_posts_from_graphql
    gql_posts = []
    try:
        gql_posts = extract_posts_from_graphql(html, page_url)
    except Exception as exc:
        post_errors.append({
            "post_url": "",
            "code": "extraction_failure",
            "message": f"graphql extraction failed: {exc!r}",
        })

    # Merge: use graphql posts as primary (richest data), then script posts
    # whose id isn't already covered, then DOM posts not yet seen.
    seen_ids = set()
    for post in gql_posts:
        if post.post_id:
            seen_ids.add(post.post_id)
        posts.append(post)

    for post in script_posts:
        if post.post_id and post.post_id in seen_ids:
            continue
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

    # Drop unidentifiable containers (FB renders empty teaser divs)
    def _has_signal(post) -> bool:
        return bool(post.post_id or post.text or post.thumbnail_url
                    or post.media_url or post.video_url
                    or post.has_image or post.has_video)
    unique_posts = [p for p in unique_posts if _has_signal(p)]

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


def scrape_source_browser(
    url: str,
    *,
    max_posts: Optional[int] = None,
    scroll_rounds: Optional[int] = None,
    account_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    post_type: Optional[str] = None,
    cancel_event: Optional[threading.Event] = None,
    progress_callback: Optional[Callable[..., None]] = None,
) -> "SourceResult":
    """Scrape one source through the headless browser (GraphQL feed) and return
    a :class:`~backend.scraper.SourceResult` with canonical normalized posts.

    Mirrors the CLI ``--browser`` path so the job worker and the CLI share one
    entry point.  ``scroll_rounds`` defaults to :data:`MAX_SCROLL_ROUNDS`.
    ``start_date`` / ``end_date`` / ``post_type`` filter the results exactly
    like the HTTP path (posts without a proven timestamp are skipped when a
    date range is given).
    """
    from backend.scraper import ScrapeOptions, SourceResult, _handle_of, _passes_filters, validate_or_raise
    from backend.scraper.dedup import dedup_posts
    from backend.scraper.normalizer import normalize_post

    def _is_wall(html: str) -> bool:
        if not html:
            return True
        # Real feed content is the strongest signal — embedded React/Relay
        # JSON contains "post_id" references; a wall has none.
        if '"post_id"' in html:
            return False
        # A large rendered document that isn't the full feed but has no
        # post markers (e.g. a fully-formed page) is still not a login wall.
        if len(html) > 100000:
            return False
        # classic login wall markers on small stub pages
        if 'input name="email"' in html or 'id="email"' in html:
            return True
        if 'checkpoint' in html.lower() and 'login' in html.lower():
            return True
        return True

    errors: List[Dict[str, str]] = []
    try:
        normalized_url = validate_or_raise(url)
    except Exception as exc:  # invalid URL -> per-job validation error
        return SourceResult(
            url=url,
            errors=[{"url": url, "code": "invalid_url", "message": str(exc)}],
        )

    # Try up to 2 times — Facebook sometimes serves a login wall on first
    # load.  Attempt 1 uses the saved session; if that walls, attempt 2
    # retries with an anonymous context (FB sometimes leaks the full feed).
    html = ""
    for attempt in range(2):
        html = fetch_with_browser(
            normalized_url,
            max_posts=max_posts,
            scroll_rounds=scroll_rounds if scroll_rounds is not None else MAX_SCROLL_ROUNDS,
            cancel_event=cancel_event,
            account_name=account_name,
            use_cookies=(attempt == 0),
            progress_callback=progress_callback,
        )
        if html and not _is_wall(html):
            break
        logger.warning("Browser attempt %d: login wall detected, retrying...", attempt + 1)

    if not html:
        return SourceResult(
            url=url,
            errors=[
                {"url": url, "code": "fetch_failed",
                 "message": "Browser returned empty HTML after retries"}
            ],
        )
    if _is_wall(html):
        return SourceResult(
            url=url,
            errors=[
                {"url": url, "code": "login_wall",
                 "message": "Facebook login wall still present after retries. Run 'python cli.py login' to refresh cookies."}
            ],
        )

    page = parse_browser_page(
        html,
        page_url=normalized_url,
        handle=_handle_of(normalized_url),
    )
    # The saved session page never yielded the GraphQL feed (only DOM
    # stubs).  Surface it as a partial result instead of a clean scrape so
    # the caller knows the post set is incomplete.
    if "fb-scrape-feed-missing" in html and page.posts:
        logger.warning(
            "Browser: feed missing for %s — only %d DOM-only post(s) recovered",
            normalized_url, len(page.posts),
        )
        errors.append({
            "url": url,
            "code": "partial_feed",
            "message": (
                "Facebook's timeline feed was not loaded (login wall / "
                "limited session); only DOM-rendered posts were recovered. "
                "Refresh cookies with 'python cli.py login' and retry."
            ),
        })
    if progress_callback:
        try:
            progress_callback(posts_found=len(page.posts), posts_extracted=len(page.posts))
        except Exception:
            pass

    normalized: List[Dict[str, Any]] = []
    for parsed_post in page.posts:
        try:
            normalized.append(
                normalize_post(
                    parsed_post,
                    page_name=page.page_name,
                    page_id=page.page_id,
                    facebook_url=normalized_url,
                )
            )
        except Exception as exc:
            errors.append({
                "post_url": parsed_post.post_url or url,
                "code": "extraction_failure",
                "message": f"normalize failed: {exc!r}",
            })

    kept, duplicates = dedup_posts(normalized)

    filters = ScrapeOptions(
        urls=[url],
        start_date=start_date,
        end_date=end_date,
        post_type=post_type,
    )
    kept = [p for p in kept if _passes_filters(p, filters)]

    if max_posts is not None and len(kept) > max_posts:
        kept = kept[:max_posts]

    if progress_callback:
        try:
            progress_callback(
                posts_found=len(page.posts),
                posts_extracted=len(kept),
                duplicates_removed=duplicates,
                posts_failed=len(page.post_errors) + len(errors),
            )
        except Exception:
            pass

    return SourceResult(
        url=url,
        page_name=page.page_name,
        page_id=page.page_id,
        posts=kept,
        stats={
            "posts_discovered": len(page.posts),
            "posts_extracted": len(kept),
            "duplicates_removed": duplicates,
            "posts_skipped": 0,
            "posts_failed": len(page.post_errors) + len(errors),
        },
        errors=[dict(e) for e in page.post_errors] + errors,
    )
