"""Facebook URL validation and normalization for the extraction layer.

Public contract (consumed by the API layer):

    validate_facebook_url(url) -> {"valid": bool,
                                   "normalized_url": str | None,
                                   "reason": str | None}

What is accepted
----------------
* ``http/https`` URLs whose host is exactly ``facebook.com`` or any subdomain
  of it (``www.``, ``m.``, ``mbasic.``, ``touch.``, localized ``en-gb.``, ...).
* Page/profile URL shapes:
  * ``https://www.facebook.com/<handle>``             (username / vanity page)
  * ``https://www.facebook.com/<handle>/<page-tab>``  (tabs are stripped)
  * ``https://www.facebook.com/pg/<handle>``          (old Pages-Manager form)
  * ``https://www.facebook.com/people/<slug>/<id>``   (new profile form)
  * ``https://www.facebook.com/profile.php?id=<id>``  (numeric profile)
* Missing ``http(s)://`` schemes are tolerated and fixed (people paste bare
  host/path strings all the time).

What is rejected
----------------
* Non-Facebook hosts, non-http(s) schemes, empty paths, empty handles.
* Login / consent / auth paths (``/login``, ``/checkpoint``, ``/recover``,
  ``/reg``, ``/consent``, ...) and other reserved top-level Facebook paths
  (``/watch``, ``/reel``, ``/events``, ``/groups``, ``/marketplace``, ...).
* Direct *post* URLs, photo/video URLs and other non-page entities
  (we scrape *sources* - pages/profiles - never individual posts).
* Path-traversal-ish segments (``.`` / ``..``) and whitespace in handles.

Behavior on invalid input
-------------------------
``validate_facebook_url`` NEVER raises; it always returns the dictionary
above.  ``validate_or_raise()`` is the internal variant that raises
``InvalidUrl`` / ``UnsupportedUrl`` (used by ``scrape_source``).
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, quote, urlparse

__all__ = [
    "validate_facebook_url",
    "validate_or_raise",
    "is_facebook_url",
    "FACEBOOK_DOMAIN",
]

FACEBOOK_DOMAIN = "facebook.com"

# ---------------------------------------------------------------------------
# Reserved first path segments.  These are Facebook *application* paths, not
# page handles.  Treating them as a scrape source would either fail or hit an
# auth/consent flow - both are out of scope by design.
# ---------------------------------------------------------------------------
RESERVED_FIRST_SEGMENTS = frozenset(
    {
        # auth / consent / recovery
        "login", "login.php", "checkpoint", "recover", "reg", "register",
        "register.php", "r.php", "signup", "accounts", "dialog", "consent",
        "privacy", "privacycenter", "cookies", "cookie_policy", "terms",
        "legal", "policies", "help", "help.php", "settings", "settings.php",
        "security", "data", "download",
        # application / entity paths that are not pages or profiles
        "watch", "reel", "reels", "stories", "story", "story.php",
        "photo", "photo.php", "video", "videos", "video.php", "live",
        "gaming", "groups", "events", "marketplace", "jobs", "offers",
        "places", "pages", "showcase", "plugins", "share", "sharer",
        "sharer.php", "share.php", "search", "search.php", "findfriends",
        "find-friends", "friends", "messages", "messenger", "notifications",
        "business", "creators", "developers", "careers", "company",
        "climate", "graph", "api", "ajax", "oauth", "external", "intl",
        "fundraisers", "fundraising", "pay", "payments",
        # single-letter / internals that are definitely not page handles
        "m", "l", "d", "k", "i", "x", "t", "u", "q", "c", "n", "s",
        "permalink.php", "redir", "redirect",
    }
)

#: Page tab segments that may legally follow a handle; they are stripped from
#: the normalized URL because the *source* is the page/profile root.
PAGE_TAB_SEGMENTS = frozenset(
    {
        "about", "about_profile_transparency", "photos", "albums", "videos",
        "reels", "reels_tab", "posts", "followers", "following", "friends",
        "likes", "reviews", "events", "notes", "timeline", "featured",
        "shops", "shop", "community", "info", "mentions", "media", "map",
        "offers", "contact", "about_contact_and_basic_info", "about_places",
        "about_relationship", "about_family_and_relationships",
        "about_details", "about_work_and_education", "about_life_events",
        "about_username", "about_contact", "about_likes", "groups",
        "checkins", "maha_info", "professional_skills",
    }
)

#: Handles: 1-255 chars, no whitespace/control, no separators that would make
#: the segment something else.  Unicode page names are allowed.
_HANDLE_RE = re.compile(r"^[^\s/?#%\x00-\x1f\x7f()]{1,255}$")
#: Slug inside /people/<slug>/<id> - typically "Name-Numbers" or unicode.
_SLUG_RE = re.compile(r"^[^\s/?#\x00-\x1f]{1,200}$")
_ID_RE = re.compile(r"^\d{5,20}$")


def _candidate_url(url: str) -> str:
    """Tolerate scheme-less input (``www.facebook.com/foo``) and
    protocol-relative input (``//www.facebook.com/foo``)."""
    stripped = (url or "").strip()
    if not stripped:
        return stripped
    parsed = urlparse(stripped)
    if parsed.scheme:
        return stripped
    if stripped.startswith("//"):
        return "https:" + stripped
    return "https://" + stripped


def _classify(url: str) -> Tuple[bool, Optional[str], str]:
    """Lower-level classify.

    Returns ``(ok, normalized_url, reason_code)`` where ``reason_code`` is one
    of the stable values below (only meaningful when ``ok`` is False):

    ``scheme_not_http``, ``not_facebook``, ``empty_path``, ``missing_handle``,
    ``segments_invalid``, ``reserved_path``, ``invalid_people_path``,
    ``invalid_profile_id``, ``malformed``
    """
    candidate = _candidate_url(url)
    if not candidate:
        return False, None, "malformed"
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return False, None, "malformed"

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False, None, "scheme_not_http"

    host = (parsed.hostname or "").lower()
    if host != FACEBOOK_DOMAIN and not host.endswith("." + FACEBOOK_DOMAIN):
        return False, None, "not_facebook"

    # --- path analysis -----------------------------------------------------
    if parsed.path in ("", "/"):
        return False, None, "empty_path"

    # keep the raw path but decode percent-encoding for segment checks
    raw_path = parsed.path.split("#", 1)[0]
    segments = [seg for seg in raw_path.lstrip("/").split("/")]
    # drop a trailing slash artifact (e.g. "handle/" -> ["handle", ""])
    if segments and segments[-1] == "":
        segments.pop()
    if not segments:
        return False, None, "empty_path"

    def normalized(handle_or_path: str) -> str:
        return "https://www.facebook.com" + handle_or_path

    first = segments[0]

    # --- profile.php?id=<digits> ------------------------------------------
    if first == "profile.php":
        if len(segments) != 1:
            return False, None, "invalid_profile_id"
        q = parse_qs(parsed.query)
        ids = q.get("id", [])
        if len(ids) != 1 or not _ID_RE.match(ids[0]):
            return False, None, "invalid_profile_id"
        return True, normalized(f"/profile.php?id={ids[0]}"), ""

    # --- people/<slug>/<id> ------------------------------------------------
    if first == "people":
        if len(segments) != 3 or not _SLUG_RE.match(segments[1]) \
                or not _ID_RE.match(segments[2]):
            return False, None, "invalid_people_path"
        return True, normalized("/people/" + segments[1] + "/" + segments[2]), ""

    # --- /pg/<handle> -------------------------------------------------------
    if first == "pg":
        if len(segments) != 2:
            return False, None, "missing_handle"
        handle = segments[1]
        if not _HANDLE_RE.match(handle) or handle in ("", ".", ".."):
            return False, None, "segments_invalid"
        return True, normalized("/" + handle), ""

    # --- reserved / auth / consent paths ------------------------------------
    if first in RESERVED_FIRST_SEGMENTS:
        return False, None, "reserved_path"

    # --- plain /<handle>[/<tab>] --------------------------------------------
    handle = first
    if not _HANDLE_RE.match(handle) or handle in ("", ".", "..") \
            or handle.lower() in RESERVED_FIRST_SEGMENTS:
        return False, None, "segments_invalid"

    rest = segments[1:]
    for seg in rest:
        if seg == "":
            continue
        if seg.lower() not in PAGE_TAB_SEGMENTS:
            # deeper/non-tab paths are direct post/photo/video URLs or other
            # entities - those are not scrape sources
            return False, None, "reserved_path"

    return True, normalized("/" + handle), ""


_REASON_MESSAGES = {
    "scheme_not_http": "Only http(s) URLs are supported.",
    "not_facebook": "The URL does not belong to facebook.com.",
    "empty_path": "The URL does not identify a page or profile.",
    "missing_handle": "The URL does not contain a page/profile handle.",
    "segments_invalid": "The page/profile handle is invalid.",
    "reserved_path": (
        "The URL points to a Facebook login/consent flow or to a non-page "
        "entity (e.g. a single post, watch, group, event or marketplace); "
        "only public page/profile URLs are supported."
    ),
    "invalid_people_path": "The /people/<name>/<id> profile URL is malformed.",
    "invalid_profile_id": "The profile.php?id= URL is malformed.",
    "malformed": "The URL could not be parsed.",
}


def validate_facebook_url(url: str) -> Dict[str, Optional[str]]:
    """Public validator.  Never raises.

    Returns ``{"valid": bool, "normalized_url": str | None, "reason": str | None}``.
    ``normalized_url`` is only set when ``valid`` is True and always looks like
    ``https://www.facebook.com/<handle>`` (or the ``/people/`` / ``profile.php``
    canonical forms).  ``reason`` carries a human-readable explanation when
    ``valid`` is False.
    """
    ok, normalized, reason_code = _classify(url)
    if ok:
        return {"valid": True, "normalized_url": normalized, "reason": None}
    return {
        "valid": False,
        "normalized_url": None,
        "reason": _REASON_MESSAGES.get(reason_code, "Invalid Facebook URL."),
    }


def validate_or_raise(url: str) -> str:
    """Internal variant used by ``scrape_source``.

    Returns the normalized URL or raises:

    * :class:`~scraper.errors.InvalidUrl`      - non-Facebook / malformed
    * :class:`~scraper.errors.UnsupportedUrl`  - Facebook but unsupported shape
      (login/consent paths, non-page entities)
    """
    from .errors import InvalidUrl, UnsupportedUrl  # local import avoids cycle

    ok, normalized, reason_code = _classify(url)
    if ok:
        return normalized  # type: ignore[return-value]
    message = _REASON_MESSAGES.get(reason_code, "Invalid Facebook URL.")
    if reason_code in ("not_facebook", "scheme_not_http", "malformed",
                       "empty_path", "segments_invalid", "invalid_profile_id",
                       "invalid_people_path", "missing_handle"):
        raise InvalidUrl(message)
    raise UnsupportedUrl(message)


def is_facebook_url(url: str) -> bool:
    """Convenience boolean wrapper around :func:`validate_facebook_url`."""
    return validate_facebook_url(url)["valid"] is True