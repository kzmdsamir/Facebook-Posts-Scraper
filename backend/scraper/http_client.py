"""Shared HTTP client for the scraper package.

Centralizes httpx client creation, default headers, cookie-clearing,
throttle/retry logic, and the no-zstd encoding constraint.  Used by
both the main ``Fetcher`` and the ``FacebookBrowserTransport``.
"""

from __future__ import annotations

import os
import random
import time
from typing import Any, Callable, Dict, Optional, Tuple

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

BROWSER_HEADERS: Dict[str, str] = {
    "User-Agent": DEFAULT_USER_AGENT,
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
}

# 10 MB safety cap for a page body
MAX_BODY_BYTES = 10 * 1024 * 1024
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
# Client factory
# ---------------------------------------------------------------------------


def make_client(
    *,
    timeout: float | None = None,
    user_agent: str | None = None,
    extra_headers: dict[str, str] | None = None,
    proxy_url: str | None = None,
) -> httpx.Client:
    """Create an ``httpx.Client`` with browser-like defaults.

    * ``Accept-Encoding`` never includes ``zstd`` (Facebook returns zstd
      when advertised, but Python's httpx/stdlib cannot decompress it).
    * ``User-Agent`` defaults to Chrome 128 on Windows.
    * Cookies are NOT cleared here — the caller should clear after each
      response to comply with our no-session policy.
    * If ``proxy_url`` is provided, requests are routed through that proxy.
    """
    headers = dict(BROWSER_HEADERS)
    if user_agent:
        headers["User-Agent"] = user_agent
    if extra_headers:
        headers.update(extra_headers)
    effective_timeout = timeout or _env_float("SCRAPER_TIMEOUT_SECONDS", 20.0)
    client_kwargs: dict = {
        "timeout": httpx.Timeout(effective_timeout),
        "follow_redirects": True,
        "headers": headers,
    }
    if proxy_url:
        client_kwargs["proxy"] = proxy_url
    return httpx.Client(**client_kwargs)


# ---------------------------------------------------------------------------
# Throttle / backoff helpers
# ---------------------------------------------------------------------------


def throttle(
    last_request_at: float | None,
    delay: float,
    cancel_event: Any = None,
) -> float:
    """Sleep if needed to respect ``delay`` seconds since ``last_request_at``.

    Returns the new ``last_request_at`` (now).  ``cancel_event`` is checked
    during the sleep so cancellation stays responsive.
    """
    now = time.monotonic()
    if last_request_at is not None:
        wait = delay - (now - last_request_at)
        if wait > 0:
            _sleep_checked(wait, cancel_event)
    return time.monotonic()


def backoff(
    attempt: int,
    delay: float,
    retry_after: float | None = None,
    cancel_event: Any = None,
) -> None:
    """Exponential backoff with jitter for one retry step."""
    jitter = random.uniform(0.8, 1.2)
    wait = min(delay * (2 ** attempt) * jitter, _MAX_BACKOFF_SECONDS)
    if retry_after is not None:
        wait = max(wait, float(retry_after))
    _sleep_checked(wait, cancel_event)


def _sleep_checked(seconds: float, cancel_event: Any = None) -> None:
    """Sleep in small slices so cancellation stays responsive."""
    deadline = time.monotonic() + seconds
    while True:
        if cancel_event is not None and cancel_event.is_set():
            from .errors import OperationCancelled
            raise OperationCancelled()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.25, remaining))


# ---------------------------------------------------------------------------
# Retry-aware GET
# ---------------------------------------------------------------------------


def retry_get(
    client: httpx.Client,
    url: str,
    *,
    max_retries: int = 3,
    delay: float = 2.5,
    max_body_bytes: int = MAX_BODY_BYTES,
    cancel_event: Any = None,
) -> Tuple[int, str, str]:
    """Throttled, retry-aware streaming GET.

    Returns ``(status_code, final_url, body_text)``.

    Raises:
        - ``RateLimited`` on HTTP 429 after retries exhausted
        - ``PageUnavailable`` on HTTP 5xx after retries exhausted
        - ``Timeout`` on timeout after retries exhausted
        - ``ExtractionFailure`` on transport error or oversized body
    """
    from .errors import ExtractionFailure, PageUnavailable, RateLimited, Timeout

    last_request_at: float | None = None
    attempts = 0
    while True:
        attempts += 1
        last_request_at = throttle(last_request_at, delay, cancel_event)
        if cancel_event is not None and cancel_event.is_set():
            from .errors import OperationCancelled
            raise OperationCancelled()
        try:
            with client.stream("GET", url) as resp:
                status = resp.status_code
                if status == 429 or status >= 500:
                    retry_after = _parse_retry_after(resp.headers.get("retry-after"))
                    if attempts <= max_retries:
                        backoff(attempts - 1, delay, retry_after, cancel_event)
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
                    if len(body) > max_body_bytes:
                        raise ExtractionFailure(
                            message=f"Response body exceeded "
                                    f"{max_body_bytes} bytes; refused to read further.")
                final_url = str(resp.url)
                client.cookies.clear()
                try:
                    text = body.decode(resp.encoding or "utf-8", errors="replace")
                except (LookupError, UnicodeDecodeError):
                    text = body.decode("utf-8", errors="replace")
                return status, final_url, text

        except httpx.TimeoutException as exc:
            client.cookies.clear()
            if attempts <= max_retries:
                backoff(attempts - 1, delay, cancel_event=cancel_event)
                continue
            raise Timeout(
                f"Request timed out after {attempts} attempts: {exc}")
        except httpx.HTTPError as exc:
            client.cookies.clear()
            if attempts <= max_retries:
                backoff(attempts - 1, delay, cancel_event=cancel_event)
                continue
            raise ExtractionFailure(
                code="network_error",
                message=f"Transport error after {attempts} attempts: {exc}")


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None
