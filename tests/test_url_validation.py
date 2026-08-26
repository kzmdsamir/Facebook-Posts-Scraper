"""Group 1 — URL validation (backend.scraper.validate_facebook_url).

Asserts the real function, NOT a mock: the 9-accepted / 12-rejected behaviour
documented by the scraper layer, plus canonical-normalization checks.  Mirrors
``backend/scraper/url_validator.py`` acceptance/rejection rules.
"""
from __future__ import annotations

from backend.scraper import validate_facebook_url

ACCEPTED: list[tuple[str, str | None]] = [
    # (input, expected normalized url)
    ("https://www.facebook.com/example", "https://www.facebook.com/example"),
    ("https://facebook.com/example", "https://www.facebook.com/example"),
    ("https://m.facebook.com/example", "https://www.facebook.com/example"),
    ("https://mbasic.facebook.com/example", "https://www.facebook.com/example"),
    ("https://en-gb.facebook.com/example", "https://www.facebook.com/example"),
    ("https://www.facebook.com/pg/example", "https://www.facebook.com/example"),
    (
        "https://www.facebook.com/people/John-Doe/100012345678901",
        "https://www.facebook.com/people/John-Doe/100012345678901",
    ),
    (
        "https://www.facebook.com/profile.php?id=100012345678901",
        "https://www.facebook.com/profile.php?id=100012345678901",
    ),
    ("www.facebook.com/example", "https://www.facebook.com/example"),  # scheme-less
    ("https://www.facebook.com/example/photos", "https://www.facebook.com/example"),
]

REJECTED: list[str] = [
    "https://example.com/foo",                       # not facebook
    "https://twitter.com/facebook",                  # not facebook
    "ftp://www.facebook.com/foo",                    # scheme not http(s)
    "https://www.facebook.com",                      # empty path
    "https://www.facebook.com/",                     # empty path
    "https://www.facebook.com/login",                # auth flow
    "https://www.facebook.com/checkpoint",           # auth flow
    "https://www.facebook.com/recover",              # auth flow
    "https://www.facebook.com/consent",              # consent flow
    "https://www.facebook.com/watch",                # non-page entity
    "https://www.facebook.com/groups/1234",          # group
    "https://www.facebook.com/events/1234",          # event
    "https://www.facebook.com/marketplace",          # non-page entity
    "https://www.facebook.com/story.php?story_fbid=123456",   # direct post URL
    "https://www.facebook.com/photo.php?fbid=123456",         # direct photo URL
    "https://www.facebook.com/example/posts/1234567890123",   # deep post path
    "https://www.facebook.com/people/John-Doe",              # people w/o id
    "https://www.facebook.com/profile.php",                  # no id param
    "https://www.facebook.com/profile.php?id=abc",           # non-numeric id
    "not a url at all",                                       # garbage
    "https://www.facebook.com/foo bar",                       # whitespace handle
]


def test_accepts_page_profile_urls():
    for url, expected in ACCEPTED:
        verdict = validate_facebook_url(url)
        assert verdict["valid"] is True, f"should accept {url!r}: {verdict}"
        assert verdict["normalized_url"] == expected, f"bad normalization for {url!r}"
        assert verdict["reason"] is None


def test_rejects_garbage_and_non_scrape_paths():
    for url in REJECTED:
        verdict = validate_facebook_url(url)
        assert verdict["valid"] is False, f"should reject {url!r}: {verdict}"
        assert verdict["normalized_url"] is None
        assert verdict["reason"], f"missing rejection reason for {url!r}"


def test_never_raises_on_string_domain():
    # The function is typed ``url: str``; within that domain it never raises,
    # including empty/whitespace/None-ish strings.
    for weird in (None, "", "   "):
        verdict = validate_facebook_url(weird)  # type: ignore[arg-type]
        assert isinstance(verdict, dict)
        assert verdict["valid"] is False
        assert "reason" in verdict and verdict["reason"]


def test_reason_mentions_facebook_or_login_for_core_cases():
    assert "facebook.com" in validate_facebook_url("https://evil.com/x")["reason"]
    reason = validate_facebook_url("https://www.facebook.com/login")["reason"]
    assert "login" in reason.lower() or "page" in reason.lower()