"""CSV export: flat, Excel-friendly rows (UTF-8 with BOM).

Nested values (``hashtags``, ``mentions``, ``external_links``) are flattened
by joining their elements with ``"|"``; ``None`` becomes the empty string.
The file is written in ``utf-8-sig`` so Excel detects UTF-8 automatically,
and the :mod:`csv` module handles quoting/escaping of embedded commas,
quotes and newlines in long fields such as ``text`` and ``transcript``.

``FLAT_COLUMNS`` is the single source of truth for the flat schema and is
shared verbatim with the XLSX "Posts" sheet (see :mod:`xlsx_exporter`), so
CSV and the spreadsheet rows always agree on names and order.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable

from .safety import safe_filename

EXPORT_FILENAME = "facebook_posts.csv"

#: Shared flat schema — CSV columns and XLSX "Posts" sheet columns/order.
FLAT_COLUMNS: list[str] = [
    "post_id",
    "page_name",
    "post_url",
    "published_at",
    "text",
    "post_type",
    "likes",
    "comments_count",
    "shares",
    "views_count",
    "thumbnail_url",
    "media_url",
    "page_id",
    "profile_url",
    "reactions",
    "reaction_like_count",
    "reaction_love_count",
    "reaction_care_count",
    "reaction_haha_count",
    "reaction_wow_count",
    "reaction_sad_count",
    "reaction_angry_count",
    "hashtags",
    "mentions",
    "external_links",
    "media_type",
    "video_url",
    "transcript",
]

_LIST_JOIN_SEP = "|"


def _cell(value: Any) -> Any:
    """Normalize one field value for CSV: ``None`` -> ``""``, lists join by ``|``."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return _LIST_JOIN_SEP.join("" if item is None else str(item) for item in value)
    return value


def flatten_post(post: dict[str, Any]) -> list[Any]:
    """Flatten one normalized post dict into ``FLAT_COLUMNS`` order."""
    return [_cell(post.get(key)) for key in FLAT_COLUMNS]


def export_csv(posts: Iterable[dict[str, Any]], out_path: str | Path) -> Path:
    """Stream ``posts`` to a UTF-8-with-BOM CSV file.

    Rows are written one at a time (no full materialization) so this scales
    to arbitrarily large result sets. Returns the resolved absolute path.
    """
    out = Path(out_path)
    safe_filename(out.name)
    with open(out, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(FLAT_COLUMNS)
        for post in posts:
            writer.writerow(flatten_post(post))
    return out.resolve()