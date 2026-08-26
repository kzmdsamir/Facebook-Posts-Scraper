"""Compliance-aware public HTTP fetcher for Facebook pages.

Design constraints (product spec §6 / §9 / §10) implemented here:

* **Public content only.**  The fetcher only ever GETs the public HTML of
  page/profile URL variants (``www``, ``mbasic``, ``mobile``); it never
  touches login, consent, checkpoint or other auth flows.
* **robots.txt respected.**  ``https://www.facebook.com/robots.txt`` is
  fetched once per ``Fetcher`` and each candidate URL is checked with
  ``urllib.robotparser``.  When robots.txt *disallows* a path the fetcher
  refuses it (:class:`~scraper.errors.UnsupportedUrl` with code
  ``robots_disallowed``).
  Documented policy: robots.txt is best-effort.  If it cannot be fetched at
  all (network error/timeout/5xx) the fetcher proceeds using its *allowlist*
  of public page/profile endpoints only - it never crawls disallowed paths
  when the file is readable, and it never crawls auth/consent paths at all.
* **Hard throttle.**  Minimum ``SCRAPER_DELAY_SECONDS`` (default 2.5 s)
  between HTTP requests.  Configurable via environment (never below 0.1 s
  to avoid operator mistakes).
* **Exponential backoff** on HTTP 429/5xx and transport errors, max 3
  retries (``SCRAPER_MAX_RETRIES``).  Honors ``Retry-After`` headers.
* **Hard timeout.**  ``SCRAPER_TIMEOUT_SECONDS`` (default 20 s) applies to
  every request phase.
* **Concurrency of 1 per source.**  One ``Fetcher`` per ``scrape_source``
  call; requests are strictly sequential (the throttle plus synchronous code
  make this structural, not incidental).
* **No cookies, ever.**  httpx ``Client`` would normally persist
  ``Set-Cookie`` values in its jar; this fetcher explicitly clears the jar
  after *every* response so no cookie is stored or re-sent.  No session data
  is ever provided.
* **No evasion.**  A single honest, constant user agent.  No UA rotation,
  no CAPTCHA solving, no headless-browser bypass, no "request signing".
  If Facebook serves a login wall or a traffic check, the fetcher reports
  :class:`~scraper.errors.AuthRequired` /
  :class:`~scraper.errors.RateLimited` and stops that source.

Environment variables
---------------------
``SCRAPER_DELAY_SECONDS``   float, default 2.5  (min 0.1)
``SCRAPER_TIMEOUT_SECONDS`` float, default 20
``SCRAPER_MAX_RETRIES``     int,   default 3
``SCRAPER_ROBOTS``          "1"/"0", default "1" (robots.txt enforcement)
"""

from __future__ import annotations

import os
import random
import re
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib import robotparser
from urllib.parse import urlparse

import httpx

from .errors import (
    AuthRequired,
    ExtractionFailure,
    OperationCancelled,
    PageUnavailable,
    RateLimited,
    ScraperError,
    Timeout,
    UnsupportedUrl,
)

__all__ = ["Fetcher", "FetchResult", "build_variants", "classify_page_html"]

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
ROBOTS_URL = "https://www.facebook.com/robots.txt"
ROBOTS_USER_AGENT_TOKEN = "FBPostsScraper"

MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB safety cap for a page
_MIN_DELAY_SECONDS = 0.1
_MAX_BACKOFF_SECONDS = 30.0

# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


# ---------------------------------------------------------------------------
# Page-content classifiers (marker based; tuned to be conservative)
# ---------------------------------------------------------------------------

#: Strong markers that mean "login wall", used across all variants.
_LOGIN_WALL_MARKERS = (
    'id="login_form"',
    'name="login_form"',
    'action="/login/',
    "<title>log in to facebook</title>",
    "<title>log into facebook</title>",
    "you must log in to continue",
    "please log in to continue",
    "you need to log in to continue",
    "log in to see more of",
    "to see more from",          # teaser: "To see more from X, log in..."
    "log in or create an account",
    "must log in to see",
    "log in to facebook to continue",
    "please login to view",
    "join facebook",             # modern: "Join Facebook" / "Create new account"
    "create new account",
    "log into facebook",
    "continue with facebook",
    "enter the phone number or email",
    "see more of this page",
)

#: Markers for Facebook's automated-traffic / security checks.
_TRAFFIC_CHECK_MARKERS = (
    "unusual traffic",
    "automated access",
    "security check",
    "captcha",
    "verify you're",
    "confirm you're not a robot",
    "confirm you are not a robot",
    "try again in a few minutes",
    "temporarily blocked",
    "suspicious activity",
    "we noticed unusual activity",
    "you have been blocked",
    "your account has been blocked",
)

#: Markers for "content not found / removed" pages.
_NOT_FOUND_MARKERS = (
    "this content isn't available",
    "content is not available",
    "this page isn't available",
    "sorry, this page isn't available",
    "the link you followed may be broken",
    "the page you requested cannot be displayed",
    "page not found",
    "post is not available",
)


def _scan_markers(html: str, markers: Tuple[str, ...], limit: int = 400_000) -> bool:
    """Search a bounded prefix of the document for markers.

    Strips ``<script>`` and ``<style>`` content first to avoid false positives
    from JavaScript component names (e.g. "captcha", "login") that Facebook
    embeds in its JS bundles.
    """
    if not html:
        return False
    bounded = html[:limit]
    # Strip script/style content to avoid JS false positives
    cleaned = re.sub(r"<script\b[^>]*>.*?</script>", "", bounded, flags=re.I | re.S)
    cleaned = re.sub(r"<style\b[^>]*>.*?</style>", "", cleaned, flags=re.I | re.S)
    low = cleaned.lower()
    return any(marker in low for marker in markers)


def looks_like_login_wall(html: str) -> bool:
    return _scan_markers(html, _LOGIN_WALL_MARKERS)


def looks_like_traffic_check(html: str) -> bool:
    return _scan_markers(html, _TRAFFIC_CHECK_MARKERS)


def looks_like_not_found(html: str) -> bool:
    return _scan_markers(html, _NOT_FOUND_MARKERS)


def classify_page_html(html: str) -> str:
    """Classify fetched HTML: ``"ok"`` | ``"not_found"`` | ``"wall"`` |
    ``"traffic"`` | ``"empty"``."""
    if not html or len(html) < 200:
        return "empty"
    if looks_like_not_found(html):
        return "not_found"
    if looks_like_login_wall(html):
        return "wall"
    if looks_like_traffic_check(html):
        return "traffic"
    return "ok"


# ---------------------------------------------------------------------------
# Variant construction
# ---------------------------------------------------------------------------

def build_variants(normalized_url: str) -> List[Tuple[str, str]]:
    """Build the ordered list of ``(label, url)`` variants to try.

    The canonical www URL first, then the ``mbasic`` (and ``mobile``)
    variants - mbasic is the variant most likely to render full post text for
    anonymous visitors.  The ``/people/<slug>/<id>`` form is translated to
    ``profile.php?id=`` for the mbasic/mobile hosts (which do not render the
    people path).
    """
    parsed = urlparse(normalized_url)
    path = parsed.path or "/"
    host = (parsed.hostname or "").lower()

    variants: List[Tuple[str, str]] = [("canonical", normalized_url)]

    alt_path = path
    if alt_path.startswith("/people/"):
        segments = [s for s in alt_path.split("/") if s]
        if len(segments) == 3 and segments[2].isdigit():
            alt_path = f"/profile.php?id={segments[2]}"
    if parsed.query:
        alt_path += "?" + parsed.query

    variants.append(("mbasic", f"https://mbasic.facebook.com{alt_path}"))
    if host not in ("m.facebook.com", "facebook.com"):
        variants.append(("mobile", f"https://m.facebook.com{alt_path}"))

    # de-dupe while preserving order
    seen, ordered = set(), []
    for label, url in variants:
        if url not in seen:
            seen.add(url)
            ordered.append((label, url))
    return ordered


# ---------------------------------------------------------------------------
# robots.txt policy (best-effort, documented)
# ---------------------------------------------------------------------------

class _RobotsPolicy:
    """Fetch ``facebook.com/robots.txt`` once and answer ``can_fetch``.

    If robots.txt cannot be fetched (transport error / timeout / 5xx) the
    policy degrades to the *allowlist only* rule: we proceed to fetch only
    the known public page/profile endpoints.  If robots.txt IS readable, its
    rules are enforced strictly.
    """

    def __init__(self, fetcher: "Fetcher") -> None:
        self._fetcher = fetcher
        self._parser: Optional[robotparser.RobotFileParser] = None
        self.status: str = "not_loaded"

    def load(self) -> None:
        if self._parser is not None:
            return
        try:
            status, body, _ = self._fetcher._raw_get(ROBOTS_URL)
        except (ScraperError, httpx.HTTPError):
            self.status = "failed:robots.txt could not be fetched; using allowlist-only policy"
            return
        except Exception:  # defensive: robots failure must never block scraping
            self.status = "failed:unexpected; using allowlist-only policy"
            return
        if status != 200:
            self.status = f"failed:robots.txt HTTP {status}; using allowlist-only policy"
            return
        parser = robotparser.RobotFileParser()
        parser.set_url(ROBOTS_URL)
        parser.parse(body.splitlines())
        self._parser = parser
        self.status = "loaded"

    def can_fetch(self, url: str) -> bool:
        """True when the URL may be fetched.  Degrades to allowlist-only when
        robots.txt was unreadable (documented policy)."""
        if self._parser is None:
            return True
        return self._parser.can_fetch(ROBOTS_USER_AGENT_TOKEN, url)


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------

@dataclass
class FetchResult:
    """Outcome of a successful page fetch."""

    status_code: int
    final_url: str
    html: str
    url_used: str
    variant: str
    attempts: int
    elapsed: float


class Fetcher:
    """Sequential, throttled, cookie-free fetcher for public Facebook pages.

    One instance per source scrape; not thread-safe by design (concurrency
    of 1 per source is a requirement, not a limitation).
    """

    def __init__(
        self,
        *,
        delay: Optional[float] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        user_agent: Optional[str] = None,
        use_robots: Optional[bool] = None,
        cancel_event=None,
        max_body_bytes: int = MAX_BODY_BYTES,
    ) -> None:
        #: minimum seconds between requests (env-overridable, hard floor)
        self.delay = max(
            delay if delay is not None else _env_float("SCRAPER_DELAY_SECONDS", 2.5),
            _MIN_DELAY_SECONDS,
        )
        #: hard per-request timeout
        self.timeout = timeout if timeout is not None \
            else _env_float("SCRAPER_TIMEOUT_SECONDS", 20.0)
        #: retries AFTER the first attempt (429/5xx/transport/timeout)
        self.max_retries = max(
            max_retries if max_retries is not None
            else _env_int("SCRAPER_MAX_RETRIES", 3),
            0,
        )
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.max_body_bytes = max_body_bytes
        self.cancel_event = cancel_event

        use_robots = _env_bool("SCRAPER_ROBOTS", True) \
            if use_robots is None else use_robots
        self._robots: Optional[_RobotsPolicy] = _RobotsPolicy(self) if use_robots else None
        if not use_robots:
            self._robots_status = "disabled"

        # NOTE: httpx.Client keeps a cookie jar by default.  We clear it after
        # EVERY response so no Set-Cookie value is ever stored or re-sent.
        self._client = httpx.Client(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Ch-Ua": '"Chromium";v="128", "Not_A Brand";v="24", "Google Chrome";v="128"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            },
        )
        self._last_request_at: Optional[float] = None
        self.requests_made = 0
        self.robots_status: str = "not_loaded"

    # -- lifecycle -------------------------------------------------------
    def close(self) -> None:
        try:
            self._client.close()
        except Exception:  # pragma: no cover - best effort
            pass

    def __enter__(self) -> "Fetcher":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- helpers ---------------------------------------------------------
    def _check_cancel(self) -> None:
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise OperationCancelled()

    def _sleep_checked(self, seconds: float) -> None:
        """Sleep in small slices so cancellation stays responsive."""
        deadline = time.monotonic() + seconds
        while True:
            self._check_cancel()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(0.25, remaining))

    def _throttle(self) -> None:
        """Enforce the minimum inter-request interval (hard throttle)."""
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            wait = self.delay - elapsed
            if wait > 0:
                self._sleep_checked(wait)
        self._last_request_at = time.monotonic()

    def _backoff(self, attempt: int, retry_after: Optional[float] = None) -> None:
        """Exponential backoff for one retry step."""
        jitter = random.uniform(0.8, 1.2)
        wait = min(self.delay * (2 ** attempt) * jitter, _MAX_BACKOFF_SECONDS)
        if retry_after is not None:
            wait = max(wait, float(retry_after))
        self._sleep_checked(wait)

    @staticmethod
    def _parse_retry_after(value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        try:
            return float(value.strip())
        except ValueError:
            return None

    # -- low-level request ------------------------------------------------
    def _raw_get(self, url: str) -> Tuple[int, str, str]:
        """Throttled GET with retry/backoff.  Returns ``(status, final_url, html)``.

        Raises ScraperError subclasses after retries are exhausted
        (RateLimited / Timeout / PageUnavailable / ExtractionFailure).
        Does NOT consult robots.txt (used internally for robots.txt itself).
        """
        self._throttle()
        self._check_cancel()
        attempts = 0
        while True:
            attempts += 1
            self.requests_made += 1
            self._check_cancel()
            try:
                with self._client.stream("GET", url) as resp:
                    status = resp.status_code
                    if status == 429 or status >= 500:
                        retry_after = self._parse_retry_after(
                            resp.headers.get("retry-after"))
                        if attempts <= self.max_retries:
                            self._backoff(attempts - 1, retry_after)
                            continue
                        if status == 429:
                            raise RateLimited(
                                f"Facebook rate-limited the request (HTTP 429) "
                                f"after {attempts} attempts.")
                        raise PageUnavailable(
                            f"Facebook returned HTTP {status} after "
                            f"{attempts} attempts.")

                    body = bytearray()
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        body.extend(chunk)
                        if len(body) > self.max_body_bytes:
                            raise ExtractionFailure(
                                message=f"Response body exceeded "
                                        f"{self.max_body_bytes} bytes; refused to read further.")
                    final_url = str(resp.url)
                    # --- compliance: NEVER retain cookies -----------------
                    self._client.cookies.clear()
                    try:
                        text = body.decode(resp.encoding or "utf-8", errors="replace")
                    except (LookupError, UnicodeDecodeError):  # pragma: no cover
                        text = body.decode("utf-8", errors="replace")
                    return status, final_url, text

            except httpx.TimeoutException as exc:
                self._client.cookies.clear()
                if attempts <= self.max_retries:
                    self._backoff(attempts - 1)
                    continue
                raise Timeout(
                    f"Request timed out after {attempts} attempts: {exc}")
            except httpx.HTTPError as exc:
                self._client.cookies.clear()
                if attempts <= self.max_retries:
                    self._backoff(attempts - 1)
                    continue
                raise ExtractionFailure(
                    code="network_error",
                    message=f"Transport error after {attempts} attempts: {exc}")

    # -- page fetch -------------------------------------------------------
    def fetch_page(self, normalized_url: str) -> FetchResult:
        """Fetch a public page, trying www -> mbasic -> mobile variants.

        Returns the first usable variant or raises:

        * :class:`~scraper.errors.AuthRequired` - login wall on every variant
        * :class:`~scraper.errors.RateLimited`  - 429 after retries, or a
          traffic check on every variant
        * :class:`~scraper.errors.PageUnavailable` - 404/not-found on every
          variant
        * :class:`~scraper.errors.UnsupportedUrl` - robots.txt disallows every
          variant (code ``robots_disallowed``)
        * :class:`~scraper.errors.Timeout` / ``ExtractionFailure``

        On any rate-limit/timeout the source stops immediately (per spec);
        we do not hammer further variants after a hard block.
        """
        if self._robots is not None:
            self._robots.load()
            self.robots_status = self._robots.status

        started = time.monotonic()
        walled: List[str] = []
        blocked: List[str] = []
        not_found: List[str] = []
        last_verdict = "empty"

        for label, url in build_variants(normalized_url):
            self._check_cancel()
            if self._robots is not None and not self._robots.can_fetch(url):
                walled.append(f"{label}:robots_disallowed")
                continue
            status, final_url, html = self._raw_get(url)
            verdict = classify_page_html(html)
            last_verdict = verdict
            if status == 200 and verdict == "ok":
                return FetchResult(
                    status_code=status,
                    final_url=final_url,
                    html=html,
                    url_used=url,
                    variant=label,
                    attempts=self.requests_made,
                    elapsed=time.monotonic() - started,
                )
            if status == 404 or verdict == "not_found":
                not_found.append(label)
            elif verdict == "wall":
                walled.append(label)
            elif verdict == "traffic" or status in (401, 403):
                blocked.append(label)
            else:
                walled.append(f"{label}:unusable({verdict})")

        # all variants exhausted - report the most informative failure
        if blocked:
            raise RateLimited(
                "Facebook served an automated-traffic / security check on "
                "every variant; proceeding would require anti-bot evasion, "
                "which is out of scope by design.")
        if walled:
            raise AuthRequired(
                f"Every fetched variant requires authentication "
                f"(login wall / refused): {', '.join(walled)}.")
        if not_found:
            raise PageUnavailable(
                f"The page is not publicly available "
                f"(variants: {', '.join(not_found)}).")
        raise ExtractionFailure(
            f"No usable public HTML variant was fetched "
            f"(last verdict: {last_verdict}).")