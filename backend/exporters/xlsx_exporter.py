"""XLSX export: styled 4-sheet workbook via openpyxl.

Sheets:
    * **Posts**      — the flat rows (``csv_exporter.FLAT_COLUMNS``, same
      names/order as the CSV export); primary key ``post_id``.
    * **Engagement** — ``post_id`` + every engagement/reaction numeric field.
    * **Media**      — ``post_id`` + ``media_type``/``thumbnail_url``/
      ``media_url``/``video_url``.
    * **Metadata**   — export/job info: ``exported_at``, ``source``,
      ``posts_count``, ``schema_version``, generator, ...

Formatting: frozen header row (``freeze_panes="A2"``), auto-filter over the
used range, readable capped column widths, bold header with fill, date
number format ``yyyy-mm-dd hh:mm:ss`` for ``published_at``, and hyperlink
style for URL columns (required for ``post_url``, applied to all ``*_url``
columns for consistency).

Scaling note (why normal mode, not write_only):
    ``Workbook(write_only=True)`` is the openpyxl path for very large
    outputs, but it drops workbook-level conveniences (freeze panes,
    auto-filters, column widths) unless you post-process the XML — which is
    exactly the delicate part we want to avoid. openpyxl's normal mode
    comfortably handles tens of thousands of rows (the *.xlsx* format limit
    is ~1,048,576 rows), so this module deliberately uses normal mode with
    per-cell styles, which is simple, obviously correct, and fast enough for
    thousands of rows. If a deployment ever exceeds ~100k posts, switch the
    sheet writers to ``write_only`` and re-apply panes/filters/widths through
    the sheet-view XML after writing (document the change in this docstring).

openpyxl is the only third-party dependency of the export layer; the import
is guarded so JSON/CSV exports keep working even if it is missing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import csv_exporter
from .safety import safe_filename

EXPORT_FILENAME = "facebook_posts.xlsx"

#: Engagement sheet: post_id + all engagement/reaction numbers.
ENGAGEMENT_COLUMNS: list[str] = [
    "post_id",
    "likes",
    "reactions",
    "comments_count",
    "shares",
    "views_count",
    "reaction_like_count",
    "reaction_love_count",
    "reaction_care_count",
    "reaction_haha_count",
    "reaction_wow_count",
    "reaction_sad_count",
    "reaction_angry_count",
]

#: Media sheet: post_id + media fields (per spec §5).
MEDIA_COLUMNS: list[str] = [
    "post_id",
    "media_type",
    "thumbnail_url",
    "media_url",
    "video_url",
]

#: Version of the normalized-post schema (and flat schema) this module emits.
SCHEMA_VERSION = "1.0"

DATE_FORMAT = "yyyy-mm-dd hh:mm:ss"
_HEADER_FILL_COLOR = "4472C4"
_HYPERLINK_COLOR = "0563C1"
_WRAP_COLUMNS = {"text", "transcript", "hashtags", "mentions", "external_links"}

try:  # openpyxl is optional at import time so JSON/CSV still work without it
    from openpyxl import Workbook  # noqa: F401
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: F401
    _OPENPYXL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only on minimal installs
    _OPENPYXL_AVAILABLE = False

if _OPENPYXL_AVAILABLE:
    _HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
    _HEADER_FILL = PatternFill("solid", fgColor=_HEADER_FILL_COLOR)
    _HEADER_BORDER = Border(
        left=Side(style="thin", color="2F5597"),
        right=Side(style="thin", color="2F5597"),
        top=Side(style="thin", color="2F5597"),
        bottom=Side(style="medium", color="1F3864"),
    )
    _HYPERLINK_FONT = Font(color=_HYPERLINK_COLOR, underline="single")
    _WRAP_TOP = Alignment(vertical="top", wrap_text=True)
    _TOP = Alignment(vertical="top")
    _CENTER = Alignment(horizontal="center", vertical="center")


def _require_openpyxl() -> None:
    if not _OPENPYXL_AVAILABLE:
        raise ImportError(
            "xlsx export requires openpyxl — install it with: pip install openpyxl"
        )


def _xcell(value: Any) -> Any:
    """Normalize one field for a spreadsheet cell.

    ``None`` stays ``None`` (blank cell, not ``""``); lists join by ``"|"``;
    ints/floats stay numeric so Excel treats them as numbers.
    """
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return "|".join("" if item is None else str(item) for item in value)
    return value


def _iso_to_datetime(value: Any) -> datetime | None:
    """Best-effort ISO-8601 -> datetime (handles ``+hh:mm`` and ``Z``)."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _column_widths(header: list[str], rows: list[list[Any]]) -> dict[int, int]:
    """Widths from header length and actual cell lengths, capped at 80."""
    widths: dict[int, int] = {i: len(str(h)) for i, h in enumerate(header)}
    for row in rows:
        for i, value in enumerate(row):
            if value is None:
                continue
            length = len(str(value))
            if length > widths.get(i, 0):
                widths[i] = min(length, 80)
    return {i: max(8, w + 2) for i, w in widths.items()}


def _write_sheet(
    ws: Any,
    header: list[str],
    rows: list[list[Any]],
    *,
    date_column: str | None = None,
    wrap_columns: set[str] | None = None,
    url_columns: set[str] | None = None,
    freeze: str = "A2",
    auto_filter: bool = True,
) -> None:
    _require_openpyxl()
    wrap_columns = wrap_columns or set()
    url_columns = url_columns or set()

    # Header row: bold white on blue, centered, bordered.
    for col_idx, name in enumerate(header, start=1):
        cell = ws.cell(row=1, column=col_idx, value=name)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _CENTER
        cell.border = _HEADER_BORDER
    ws.row_dimensions[1].height = 22

    # Data rows.
    for r, row in enumerate(rows, start=2):
        for c, value in enumerate(row, start=1):
            name = header[c - 1]
            cell = ws.cell(row=r, column=c)
            if name == date_column:
                parsed = _iso_to_datetime(value)
                if parsed is not None:
                    # openpyxl rejects aware datetimes ("Excel does not
                    # support timezones"); strip tz so the local wall time
                    # from the ISO string is displayed as-is.
                    if parsed.tzinfo is not None:
                        parsed = parsed.replace(tzinfo=None)
                    cell.value = parsed
                    cell.number_format = DATE_FORMAT
                else:
                    cell.value = value  # unparseable -> raw string fallback
            else:
                cell.value = _xcell(value)
            if name in wrap_columns and cell.value not in (None, ""):
                cell.alignment = _WRAP_TOP
            else:
                cell.alignment = _TOP
            if (
                name in url_columns
                and isinstance(cell.value, str)
                and cell.value.startswith(("http://", "https://"))
            ):
                cell.hyperlink = cell.value
                cell.font = _HYPERLINK_FONT

    if freeze:
        ws.freeze_panes = freeze
    if auto_filter:
        ws.auto_filter.ref = ws.dimensions
    for col_idx, width in _column_widths(header, rows).items():
        ws.column_dimensions[_letter(col_idx)].width = width


def _letter(col_idx: int) -> str:
    """0-based column index -> Excel column letter (AA, AB, ...)."""
    letters = ""
    n = col_idx + 1
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _pick(post: dict[str, Any], columns: list[str]) -> list[Any]:
    return [_xcell(post.get(key)) for key in columns]


def _write_metadata(
    ws: Any,
    *,
    job_id: str,
    source: str,
    exported_at: datetime,
    posts_count: int,
    schema_version: str,
) -> None:
    _require_openpyxl()
    rows: list[tuple[str, Any]] = [
        ("exported_at", exported_at.isoformat(timespec="seconds")),
        ("job_id", job_id),
        ("source", source),
        ("format", "xlsx"),
        ("filename", EXPORT_FILENAME),
        ("posts_count", posts_count),
        ("sheets", "Posts, Engagement, Media, Metadata"),
        ("schema_version", schema_version),
        ("generator", "postharvest backend.exporters.xlsx_exporter"),
    ]
    for col_idx, name in enumerate(("key", "value"), start=1):
        cell = ws.cell(row=1, column=col_idx, value=name)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _CENTER
    for r, (key, value) in enumerate(rows, start=2):
        ws.cell(row=r, column=1, value=key).alignment = _TOP
        cell = ws.cell(row=r, column=2, value=value)
        cell.alignment = _WRAP_TOP
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            cell.hyperlink = value
            cell.font = _HYPERLINK_FONT
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 80


def export_xlsx(
    posts: Iterable[dict[str, Any]],
    out_path: str | Path,
    *,
    job_id: str = "local",
    source: str = "postharvest",
    exported_at: datetime | None = None,
    schema_version: str = SCHEMA_VERSION,
) -> Path:
    """Write ``posts`` to a styled 4-sheet XLSX workbook at ``out_path``.

    Returns the resolved absolute path. ``job_id``/``source``/``exported_at``
    are recorded in the Metadata sheet.
    """
    _require_openpyxl()
    out = Path(out_path)
    safe_filename(out.name)

    rows = list(posts) if isinstance(posts, (list, tuple)) else list(posts)
    exported_at = exported_at or datetime.now(timezone.utc)

    wb = Workbook()
    ws_posts = wb.active
    ws_posts.title = "Posts"
    url_columns = {c for c in csv_exporter.FLAT_COLUMNS if c.endswith("_url")}
    _write_sheet(
        ws_posts,
        csv_exporter.FLAT_COLUMNS,
        [[_xcell(p.get(c)) for c in csv_exporter.FLAT_COLUMNS] for p in rows],
        date_column="published_at",
        wrap_columns=_WRAP_COLUMNS,
        url_columns=url_columns,
    )

    ws_eng = wb.create_sheet("Engagement")
    _write_sheet(ws_eng, ENGAGEMENT_COLUMNS, [_pick(p, ENGAGEMENT_COLUMNS) for p in rows])

    ws_media = wb.create_sheet("Media")
    _write_sheet(
        ws_media,
        MEDIA_COLUMNS,
        [_pick(p, MEDIA_COLUMNS) for p in rows],
        url_columns=set(MEDIA_COLUMNS) - {"post_id", "media_type"},
    )

    ws_meta = wb.create_sheet("Metadata")
    _write_metadata(
        ws_meta,
        job_id=job_id,
        source=source,
        exported_at=exported_at,
        posts_count=len(rows),
        schema_version=schema_version,
    )

    wb.save(out)
    return out.resolve()