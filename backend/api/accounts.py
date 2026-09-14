"""Saved Facebook session (cookie) accounts endpoints.

* GET    /api/accounts                 — list saved sessions from the credentials index
* DELETE /api/accounts/{account_name}  — remove a saved session (cookies + index entry)

Built on top of browser_scraper's credentials helpers; never reads cookie
contents, only metadata (name, file, saved_at).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Response

from backend.core.exceptions import NotFoundError
from backend.scraper.browser_scraper import (
    CREDENTIALS_PATH,
    load_credentials,
)

router = APIRouter(tags=["accounts"])


def _normalize_name(name: str) -> str:
    # Account names are stored verbatim (they are CLI --account values).
    return name.strip()


def _account_dict(name: str, entry: dict) -> dict:
    cookies_file = entry.get("cookies_file") if isinstance(entry, dict) else None
    return {
        "name": name,
        "cookies_file": cookies_file,
        "saved_at": entry.get("saved_at") if isinstance(entry, dict) else None,
    }


@router.get(
    "/accounts",
    summary="List saved Facebook sessions",
)
def list_accounts() -> dict:
    """Return the saved sessions (metadata only, never cookies)."""
    creds = load_credentials()
    items = [_account_dict(name, entry) for name, entry in creds.items()]

    # The default session saved via `login` without --account lives in the
    # plain fb_cookies.json and is not part of the credentials index; surface
    # it as an implicit "default" account.
    default_path = CREDENTIALS_PATH.parent / "fb_cookies.json"
    if default_path.exists() and "default" not in creds:
        items.append(
            {
                "name": "default",
                "cookies_file": "fb_cookies.json",
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        items.sort(key=lambda item: item["name"])
    return {
        "items": items,
        "total": len(items),
    }


@router.delete(
    "/accounts/{account_name}",
    status_code=204,
    summary="Remove a saved Facebook session",
)
def delete_account(
    account_name: str,
) -> Response:
    """Delete the session's cookies file and credentials-index entry."""
    name = _normalize_name(account_name)
    creds = load_credentials()
    if name not in creds:
        # The default session may be implicit (plain fb_cookies.json without an
        # index entry); allow deleting it that way too.
        if name == "default":
            default_path = CREDENTIALS_PATH.parent / "fb_cookies.json"
            if not default_path.exists():
                raise NotFoundError(f"Account '{name}' not found")
            default_path.unlink(missing_ok=True)
            return Response(status_code=204)
        raise NotFoundError(f"Account '{name}' not found")

    data_dir: Path = CREDENTIALS_PATH.parent
    entry = creds[name]
    cookies_file = entry.get("cookies_file") if isinstance(entry, dict) else None
    if cookies_file:
        target = data_dir / cookies_file
        if target.exists():
            target.unlink()

    del creds[name]
    if creds:
        with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
            import json

            json.dump(creds, f, indent=2, ensure_ascii=False)
    else:
        CREDENTIALS_PATH.unlink(missing_ok=True)

    return Response(status_code=204)