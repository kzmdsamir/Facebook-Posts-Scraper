"""Export layer for the Facebook Posts Scraper.

Public entry point
------------------
``export_posts`` writes a job's normalized posts in one of three formats and
returns the path of the written file. It accepts either a callable returning
the posts (``posts_loader``) or a path to a JSON file containing the posts
array (``posts_path``)::

    from backend.exporters import export_posts

    # From a job (the API layer's typical usage — ``job.posts`` is a list of
    # normalized post dicts; a lambda defers loading until export time):
    path = export_posts(
        posts_loader=lambda: job.posts,
        job_id=str(job.id),
        fmt="excel",          # "json" | "csv" | "excel" | "xlsx"
        base_dir=config.export_dir,
    )

    # From a JSON file on disk (loader-less, e.g. CLI/local use):
    path = export_posts(job_id="local", fmt="json", posts_path="scan.json")

Behavior
--------
* ``fmt`` may be ``"json"``, ``"csv"``, ``"excel"`` or ``"xlsx"``
  (``"excel"`` and ``"xlsx"`` are aliases). Output filenames come from a
  fixed allow-list: ``facebook_posts.json`` / ``facebook_posts.csv`` /
  ``facebook_posts.xlsx``.
* Files land in ``<base_dir>/<job_id>/<filename>``; the default ``base_dir``
  is ``<project>/exports``. ``job_id`` is sanitized with ``safe_filename``
  and the final path re-verified with ``assert_safe_relative_path`` — path
  traversal is impossible to smuggle through either parameter.
* JSON preserves the complete nested structure; CSV flattens to
  ``csv_exporter.FLAT_COLUMNS`` (UTF-8 BOM); XLSX writes the styled 4-sheet
  workbook (Posts/Engagement/Media/Metadata).

Dependencies: stdlib only, plus ``openpyxl`` for ``fmt="excel"``/``"xlsx"``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from . import csv_exporter, json_exporter, jsonl_exporter, xlsx_exporter
from .safety import ALLOWED_EXPORT_FILENAMES, assert_safe_relative_path, safe_filename

__all__ = [
    "ALLOWED_EXPORT_FILENAMES",
    "SUPPORTED_FORMATS",
    "assert_safe_relative_path",
    "export_posts",
    "safe_filename",
]

SUPPORTED_FORMATS: tuple[str, ...] = ("json", "csv", "excel", "xlsx", "jsonl")


def _load_posts_array(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSON file containing an array of normalized post dicts."""
    p = Path(path)
    with open(p, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"posts file {p} must contain a JSON array, got {type(data).__name__}")
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise TypeError(f"posts file {p}: item {idx} is not a dict")
    return data


def _default_base_dir() -> Path:
    # backend/exporters/__init__.py -> <project root>/exports
    return Path(__file__).resolve().parent.parent.parent / "exports"


def export_posts(
    posts_loader: Callable[[], Iterable[dict[str, Any]]] | None = None,
    job_id: str = "local",
    fmt: str = "json",
    base_dir: str | Path | None = None,
    posts_path: str | Path | None = None,
) -> Path:
    """Export a job's posts to disk and return the written file's path.

    Args:
        posts_loader: zero-arg callable returning the normalized posts
            (a list, or any iterable of dicts). Evaluated lazily at export
            time so the job store is queried once, after the export starts.
        job_id: logical job identifier used as the per-job subdirectory
            (sanitized; e.g. a uuid4 works out of the box).
        fmt: ``"json"`` (nested, pretty, UTF-8), ``"csv"`` (flat, UTF-8 BOM)
            or ``"excel"``/``"xlsx"`` (styled 4-sheet workbook).
        base_dir: root directory for exports. Defaults to
            ``<project>/exports``.
        posts_path: alternative to ``posts_loader`` — a JSON file containing
            an array of normalized post dicts. Exactly one of
            ``posts_loader`` / ``posts_path`` must be provided.

    Returns:
        The absolute path of the written file.

    Raises:
        ValueError: unknown format, missing posts source, or any path
            traversal / unsafe filename attempt.
        TypeError: ``posts_loader`` not callable, or a post is not a dict.
        ImportError: openpyxl missing and format is ``excel``/``xlsx``.
    """
    key = str(fmt).lower()
    if key not in ALLOWED_EXPORT_FILENAMES:
        raise ValueError(
            f"unsupported export format {fmt!r}; expected one of {SUPPORTED_FORMATS}"
        )
    filename = ALLOWED_EXPORT_FILENAMES[key]
    safe_filename(filename)  # allow-list sanity check

    if posts_loader is not None and posts_path is not None:
        raise ValueError("provide only one of posts_loader / posts_path")
    if posts_loader is not None:
        if not callable(posts_loader):
            raise TypeError(
                f"posts_loader must be callable or None, got {type(posts_loader).__name__}"
            )
        posts: Iterable[dict[str, Any]] = posts_loader()
    elif posts_path is not None:
        posts = _load_posts_array(posts_path)
    else:
        raise ValueError("provide either posts_loader or posts_path")

    base = Path(base_dir) if base_dir is not None else _default_base_dir()
    out_dir = assert_safe_relative_path(safe_filename(job_id), base)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    if key == "json":
        return json_exporter.export_json(posts, out_path)
    if key == "csv":
        return csv_exporter.export_csv(posts, out_path)
    if key == "jsonl":
        return jsonl_exporter.export_jsonl(posts, out_path)
    return xlsx_exporter.export_xlsx(posts, out_path, job_id=job_id)