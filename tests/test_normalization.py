"""Group 2 — normalizer pipeline (backend.scraper.normalizer).

Exercises the ParsedPost -> canonical dict pipeline: post_type
classification, hashtag/mention/external-link extraction, date handling
(epoch / relative "3 h" / ISO), and None-honesty for fields the public HTML
can never provide (caption, transcript, reaction breakdowns).
"""
from __future__ import annotations

from datetime import datetime, timezone

from backend.scraper.normalizer import (
    NORMALIZED_KEYS,
    clean_text,
    extract_hashtags,
    extract_mentions,
    normalize_post,
)
from backend.scraper.parser import ParsedPost, parse_timestamp

FACEBOOK_URL = "https://www.facebook.com/example"


def _norm(**fields) -> dict:
    return normalize_post(
        ParsedPost(**fields),
        page_name="Example Page",
        page_id="123456789",
        facebook_url=FACEBOOK_URL,
    )


def test_canonical_keys_exact_and_ordered():
    post = _norm(text="Hi")
    assert list(post.keys()) == NORMALIZED_KEYS, "key set/order drifted from contract"
    assert len(post) == len(NORMALIZED_KEYS) == 33


def test_post_type_classification_text_image_video_link():
    text = _norm(text="just a status update")
    assert text["post_type"] == "text"

    image = _norm(text="look", has_image=True, thumbnail_url="https://t/img.jpg",
                  media_url="https://t/img_full.jpg")
    assert image["post_type"] == "image"
    assert image["media_type"] == "image"
    assert image["media_url"] == "https://t/img_full.jpg"
    assert image["video_url"] is None

    video = _norm(text="watch", has_video=True, video_url="https://v/v.mp4")
    assert video["post_type"] == "video"
    assert video["media_type"] == "video"
    assert video["video_url"] == "https://v/v.mp4"
    assert video["media_url"] is None

    link = _norm(text="read this",
                 has_link_preview=True,
                 external_links=["https://news.example/article"])
    assert link["post_type"] == "link"
    assert link["external_links"] == ["https://news.example/article"]

    # Text posts whose URL(s) were extracted by the parser (the parser owns
    # URL extraction; the normalizer passes them through) classify as "link".
    link_via_text = _norm(
        text="see https://news.example/x",
        external_links=["https://news.example/x"],
    )
    assert link_via_text["post_type"] == "link"
    assert link_via_text["external_links"] == ["https://news.example/x"]


def test_media_kept_and_type_upgraded_when_classified_text():
    # BUG-002: GraphQL can deliver media_url on a post the shallow classifier
    # calls "text". The media must survive and the type must upgrade, not be
    # dropped by a post_type gate.
    post = _norm(text="shares a photo", media_url="https://t/img_full.jpg",
                 thumbnail_url="https://t/img.jpg")
    assert post["post_type"] == "image"
    assert post["media_url"] == "https://t/img_full.jpg"
    assert post["thumbnail_url"] == "https://t/img.jpg"

    post = _norm(text="watch clip", video_url="https://v/v.mp4")
    assert post["post_type"] == "video"
    assert post["video_url"] == "https://v/v.mp4"
    assert post["media_url"] is None


def test_hashtags_mentions_external_links():
    post = _norm(
        text="Check #LaunchDay with @nasa and @spacex! Also #Space",
        mentions=["@nasa"],
        external_links=["https://news.example/article"],
    )
    assert post["hashtags"] == ["#LaunchDay", "#Space"]
    assert post["mentions"] == ["@nasa", "@spacex"]  # merged, deduped, ordered
    assert post["external_links"] == ["https://news.example/article"]  # passthrough


def test_extract_helpers_dedupe_and_strip_punctuation():
    assert extract_hashtags("a #tag, #tag #other!") == ["#tag", "#other"]
    assert extract_mentions("@a and @a again @b.") == ["@a", "@b"]
    assert clean_text("  multi\n  line   text  ") == "multi line text"
    assert clean_text(None) is None


def test_date_epoch_roundtrip():
    dt = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
    post = _norm(published_at=dt)
    assert post["published_at"] == "2026-08-01T12:00:00+00:00"
    assert post["timestamp"] == int(dt.timestamp())


def test_date_relative_3h():
    parsed = parse_timestamp("3 h")
    assert parsed is not None
    post = _norm(published_at=parsed)
    now = datetime.now(timezone.utc)
    expected = now.timestamp() - 3 * 3600
    assert abs(post["timestamp"] - expected) < 300, "3 h offset inaccurate"


def test_date_iso_string_via_parser():
    parsed = parse_timestamp("2026-08-01T12:00:00+00:00")
    assert parsed is not None
    post = _norm(published_at=parsed)
    assert post["published_at"] == "2026-08-01T12:00:00+00:00"
    assert post["timestamp"] == int(
        datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc).timestamp()
    )


def test_naive_datetime_treated_as_utc():
    naive = datetime(2026, 8, 1, 0, 0, 0)
    post = _norm(published_at=naive)
    assert post["published_at"].endswith("+00:00")
    assert post["timestamp"] == int(
        datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc).timestamp()
    )


def test_none_honesty_when_absent():
    post = _norm(text="only text")
    for key in (
        "caption",
        "transcript",
        "transcript_language",
        "likes",
        "reactions",
        "comments_count",
        "shares",
        "views_count",
        "media_type",
        "thumbnail_url",
        "media_url",
        "video_url",
    ):
        assert post[key] is None, f"{key} must stay None"
    for key in ("hashtags", "mentions", "external_links"):
        assert post[key] == [], f"{key} must default to []"
    for name in (
        "reaction_like_count",
        "reaction_love_count",
        "reaction_care_count",
        "reaction_haha_count",
        "reaction_wow_count",
        "reaction_sad_count",
        "reaction_angry_count",
    ):
        assert post[name] is None, f"{name} must stay None"


def test_never_fabricates_caption_or_transcript():
    post = _norm(text="text with no separate caption")
    assert post["caption"] is None
    assert post["transcript"] is None
    assert post["transcript_language"] is None


def test_reaction_total_falls_back_to_breakdown_sum():
    post = _norm(
        text="x",
        reactions=None,
        reaction_like_count=10,
        reaction_love_count=5,
        reaction_haha_count=1,
    )
    assert post["reactions"] == 16
    assert post["reaction_like_count"] == 10


def test_dict_input_supported():
    raw = {"text": "from a dict", "post_id": "dict-1"}
    post = normalize_post(raw, page_name="P", page_id=None, facebook_url=FACEBOOK_URL)
    assert post["text"] == "from a dict"
    assert post["post_id"] == "dict-1"
    assert post["post_type"] == "text"