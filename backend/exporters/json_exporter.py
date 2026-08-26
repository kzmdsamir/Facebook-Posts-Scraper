"""JSON export: lossless nested serialization, streamed post-by-post.

The normalized post dicts are emitted exactly as produced by the scraper
layer — no flattening, no column mapping, no dropped keys. Output is a
pretty-printed UTF-8 JSON array written incrementally (one post per chunk)
so peak memory stays proportional to a single post rather than the whole
result set.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from .safety import safe_filename

EXPORT_FILENAME = "facebook_posts.json"


class PostJSONEncoder(json.JSONEncoder):
    """JSON encoder that also handles ``datetime``/``date`` values.

    The normalized post dict is JSON-native (str/int/float/bool/None/list/
    dict), so this is purely defensive for values produced by other layers:
    dates render as ISO-8601 strings; any other unknown object degrades to
    ``str()`` rather than crashing a whole export.
    """

    def default(self, o: Any) -> Any:
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return str(o)


def export_json(posts: Iterable[dict[str, Any]], out_path: str | Path) -> Path:
    """Write ``posts`` as a pretty-printed UTF-8 JSON array to ``out_path``.

    Every key/value of each normalized post dict is preserved verbatim
    (lists, nested dicts, numbers, ``None``). Each post is serialized as an
    independent chunk, so memory use is bounded. Returns the resolved
    absolute output path.
    """
    out = Path(out_path)
    safe_filename(out.name)
    first = True
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("[\n")
        for post in posts:
            if not isinstance(post, dict):
                raise TypeError(
                    f"each item to export must be a dict, got {type(post).__name__}"
                )
            chunk = json.dumps(post, cls=PostJSONEncoder, ensure_ascii=False, indent=2)
            fh.write("" if first else ",\n")
            fh.write(chunk)
            fh.write("\n")
            first = False
        fh.write("]\n")
    return out.resolve()