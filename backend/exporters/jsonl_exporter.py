"""JSONL (JSON Lines) export: one JSON object per line.

JSONL is ideal for:
- Streaming/processing large datasets line-by-line
- Importing into data tools (pandas, duckdb, bigquery)
- Append-friendly output (new posts can be added without rewriting the file)

Each line is a complete, valid JSON object representing one post.
Output is UTF-8 with no BOM.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from .safety import safe_filename

EXPORT_FILENAME = "facebook_posts.jsonl"


class PostJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime/date values."""

    def default(self, o: Any) -> Any:
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return str(o)


def export_jsonl(posts: Iterable[dict[str, Any]], out_path: str | Path) -> Path:
    """Write ``posts`` as JSONL (one JSON object per line) to ``out_path``.

    Memory-efficient: each post is serialized independently.  The output file
    can be read line-by-line without loading the entire file into memory.
    Returns the resolved absolute output path.
    """
    out = Path(out_path)
    safe_filename(out.name)
    count = 0
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        for post in posts:
            if not isinstance(post, dict):
                raise TypeError(
                    f"each item to export must be a dict, got {type(post).__name__}"
                )
            line = json.dumps(post, cls=PostJSONEncoder, ensure_ascii=False)
            fh.write(line)
            fh.write("\n")
            count += 1
    return out.resolve()
