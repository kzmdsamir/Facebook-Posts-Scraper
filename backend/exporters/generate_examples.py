"""Generate the shipped example export files from ``examples/sample_posts.json``.

Run from anywhere::

    python backend/exporters/generate_examples.py

Writes (overwriting) into ``examples/``:

    facebook_posts.json    nested, pretty-printed, UTF-8 (json_exporter)
    facebook_posts.csv     flat, UTF-8 with BOM (csv_exporter)
    facebook_posts.xlsx    styled 4-sheet workbook (xlsx_exporter)

Exit code 0 on success; 1 on error. Safe to re-run; no network access.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"
FIXTURE_PATH = EXAMPLES_DIR / "sample_posts.json"


def main() -> int:
    if not FIXTURE_PATH.is_file():
        print(f"error: fixture not found: {FIXTURE_PATH}", file=sys.stderr)
        return 1

    try:
        posts = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: cannot parse fixture: {exc}", file=sys.stderr)
        return 1
    if not isinstance(posts, list) or not isinstance(posts[0], dict):
        print("error: fixture must be a JSON array of objects", file=sys.stderr)
        return 1
    if not posts:
        print("error: fixture is empty", file=sys.stderr)
        return 1

    # Allow `from backend.exporters import ...` when run as a plain script
    # (works with or without backend/__init__.py thanks to namespace packages).
    sys.path.insert(0, str(PROJECT_ROOT))
    from backend.exporters import csv_exporter, json_exporter, xlsx_exporter

    exported_at = datetime.now(timezone.utc)
    outputs = [
        json_exporter.export_json(posts, EXAMPLES_DIR / json_exporter.EXPORT_FILENAME),
        csv_exporter.export_csv(posts, EXAMPLES_DIR / csv_exporter.EXPORT_FILENAME),
        xlsx_exporter.export_xlsx(
            posts,
            EXAMPLES_DIR / xlsx_exporter.EXPORT_FILENAME,
            job_id="example",
            source="examples/sample_posts.json",
            exported_at=exported_at,
        ),
    ]

    print(f"exported {len(posts)} posts from {FIXTURE_PATH.name}:")
    for path in outputs:
        print(f"  wrote {path} ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())