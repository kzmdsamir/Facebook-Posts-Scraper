"""Error taxonomy for the Facebook Posts Scraper extraction layer.

Every failure that can cross the ``scraper`` package boundary is an instance of
:class:`ScraperError` (or a subclass) and carries:

* ``.code``    - a stable, machine-readable string (used in API error payloads)
* ``.message`` - a human-readable explanation
* ``.to_dict()`` - ``{"code": ..., "message": ...}`` convenience for the API layer

The classes listed in the project contract are:

* ``InvalidUrl``        - the input is not a valid Facebook URL at all
* ``UnsupportedUrl``    - Facebook URL, but of a kind we refuse to scrape
                         (login/consent paths, non-page entities, robots-declined)
* ``PageUnavailable``   - the page is not publicly reachable (404 / removed / 5xx)
* ``AuthRequired``      - Facebook served a login wall; we never bypass this
* ``RateLimited``       - Facebook rate-limited / served a traffic check
* ``Timeout``           - hard request timeout exhausted
* ``ExtractionFailure`` - HTML was fetched but could not be turned into posts

``OperationCancelled`` is an internal signal used when a caller-supplied
``cancel_event`` is set mid-scrape; it is still a ``ScraperError`` so the
existing error plumbing handles it uniformly.

Compliance context: the taxonomy exists so the API layer can map failures to
stable codes and so the scraper NEVER silently fabricates a result when
Facebook denies access.  Login walls, rate limits and traffic checks are
reported, never worked around.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = [
    "ScraperError",
    "InvalidUrl",
    "UnsupportedUrl",
    "PageUnavailable",
    "AuthRequired",
    "RateLimited",
    "Timeout",
    "ExtractionFailure",
    "OperationCancelled",
]


class ScraperError(Exception):
    """Base class for all scraper-layer failures."""

    #: Stable machine-readable code.  Subclasses override with their default.
    code = "scraper_error"
    #: Default human-readable message when the caller does not provide one.
    default_message = "Generic scraper error."

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Build a scraper error.

        :param message: human-readable explanation (falls back to the class default).
        :param code: optional custom machine code (e.g. ``robots_disallowed``).
                     Defaults to the class-level ``code``.
        :param context: optional extra structured context (never required by the
                        public contract; used for debugging only).
        """
        self.message = message if message is not None else self.default_message
        if code is not None:
            self.code = code
        self.context = dict(context or {})
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, str]:
        """Serialize to the ``{"code": ..., "message": ...}`` shape used in
        ``SourceResult.errors`` entries and by the API error responses."""
        return {"code": self.code, "message": self.message}

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.code}: {self.message}"

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<{type(self).__name__} code={self.code!r} message={self.message!r}>"


class InvalidUrl(ScraperError):
    """Not a valid Facebook URL (wrong scheme, wrong host, malformed, ...)."""

    code = "invalid_url"
    default_message = "The provided URL is not a valid Facebook URL."


class UnsupportedUrl(ScraperError):
    """A Facebook URL we deliberately refuse to treat as a scrape source:
    login/consent/auth paths, non-page/profile entities (events, groups,
    watch, posts given directly), or a path disallowed by robots.txt."""

    code = "unsupported_url"
    default_message = "The URL is not a supported Facebook page or profile URL."


class PageUnavailable(ScraperError):
    """The page is not publicly available: HTTP 404/410/451, a Facebook
    'content not found' page, or persistent server errors (5xx)."""

    code = "page_unavailable"
    default_message = "The Facebook page is not publicly available."


class AuthRequired(ScraperError):
    """Facebook served a login wall for every fetched variant.

    Per product spec 6/9/10 the scraper NEVER logs in, never sends session
    cookies and never bypasses authentication; this error stops the source.
    """

    code = "auth_required"
    default_message = (
        "This page requires authentication (login wall). "
        "Login and anti-bot bypass are out of scope by design."
    )


class RateLimited(ScraperError):
    """Facebook rate-limited the request (HTTP 429) after retries, or served
    an automated-traffic / security-check page on every variant."""

    code = "rate_limited"
    default_message = "Facebook rate-limited the request; retries were exhausted."


class Timeout(ScraperError):
    """The hard request timeout (``SCRAPER_TIMEOUT_SECONDS``, default 20 s)
    was exceeded and retries were exhausted."""

    code = "timeout"
    default_message = "The Facebook request timed out."


class ExtractionFailure(ScraperError):
    """The page HTML was fetched but could not be parsed into a usable result
    (no post containers found, oversized body, network-level transport error).
    May carry a more specific ``code`` such as ``network_error``."""

    code = "extraction_failure"
    default_message = "Could not extract content from the fetched page."


class OperationCancelled(ScraperError):
    """Internal signal: the caller set ``cancel_event`` while a scrape was in
    progress.  ``scrape_source`` catches this, records a ``cancelled`` error
    entry and returns whatever partial result was already extracted."""

    code = "cancelled"
    default_message = "The scrape was cancelled by the user."