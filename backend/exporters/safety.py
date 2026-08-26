"""Path-safety helpers for the export layer.

Every value that influences a filesystem path in this package must pass
through one of these helpers first. ``export_posts`` never interpolates raw
user input into paths:

* the output filename is looked up from a fixed allow-list per format
  (``ALLOWED_EXPORT_FILENAMES``) — it is never derived from user input;
* the ``job_id`` path component is sanitized with :func:`safe_filename`;
* the final path is re-verified with :func:`assert_safe_relative_path`.

Any traversal attempt (``..``, absolute paths, drive-letter escapes, NUL
bytes, symlink escapes) raises :class:`ValueError` instead of writing
outside the intended base directory.
"""

from __future__ import annotations

import re
from pathlib import Path

# Fixed allow-list of the exact filenames the export layer may write.
# Keys are the public format names; "excel" and "xlsx" are aliases for the
# same workbook output.
ALLOWED_EXPORT_FILENAMES: dict[str, str] = {
    "json": "facebook_posts.json",
    "csv": "facebook_posts.csv",
    "excel": "facebook_posts.xlsx",
    "xlsx": "facebook_posts.xlsx",
    "jsonl": "facebook_posts.jsonl",
}

_SAFE_BASENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_FORBIDDEN_NAMES = frozenset({"", ".", ".."})


def safe_filename(name: str) -> str:
    """Return ``name`` if it is a safe, portable, non-traversing filename.

    Raises :class:`ValueError` otherwise. Rejected inputs include:

    * the empty string, ``"."``, ``".."`` and dotfiles
    * any path separator (``/`` or ``\\``), NUL bytes, absolute paths,
      drive/UNC prefixes (``C:\\...``, ``\\\\server\\...``)
    * characters outside ``[A-Za-z0-9._-]`` and names longer than 200 chars
    """
    if not isinstance(name, str):
        raise ValueError(f"filename must be a str, got {type(name).__name__}")
    if name in _FORBIDDEN_NAMES:
        raise ValueError(f"unsafe filename: {name!r}")
    if _SAFE_BASENAME_RE.fullmatch(name) is None:
        raise ValueError(
            f"unsafe filename {name!r}: must match {_SAFE_BASENAME_RE.pattern!r}"
        )
    # Belt and braces: Path.name must equal the input, proving it is a single
    # path component (the regex already forbids separators; this catches any
    # platform quirk where a weird string still resolves to a different name).
    if Path(name).name != name:
        raise ValueError(f"unsafe filename (not a single component): {name!r}")
    return name


def assert_safe_relative_path(rel_path: str, base_dir: str | Path) -> Path:
    """Resolve ``rel_path`` under ``base_dir`` and require strict containment.

    Guards against absolute paths, drive-letter/UNC escapes, ``..`` traversal
    and symlink escapes (both sides are fully resolved before the containment
    check, so symlinks pointing outside the base directory are rejected too).

    Returns the resolved absolute :class:`Path` inside ``base_dir``.
    Raises :class:`ValueError` on any violation.
    """
    if not isinstance(rel_path, str) or not rel_path:
        raise ValueError("rel_path must be a non-empty string")
    if "\x00" in rel_path:
        raise ValueError("rel_path contains a NUL byte")
    if rel_path.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", rel_path):
        raise ValueError(f"rel_path must be relative, got {rel_path!r}")

    base = Path(base_dir).resolve()
    candidate = (base / rel_path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise ValueError(
            f"rel_path {rel_path!r} escapes base directory {str(base)!r}"
        ) from None
    if candidate == base:
        raise ValueError("rel_path resolves to the base directory itself")
    return candidate