"""Facebook Posts Scraper CLI.

Usage:
    python cli.py scrape <url> [url ...] [--browser] [--max-posts N] [--scrolls N] [--export csv|json|xlsx] [--output FILE]

Examples:
    python cli.py scrape https://www.facebook.com/ashraful.islam333 --max-posts 10 --export xlsx
    python cli.py scrape https://www.facebook.com/ashraful.islam333 --browser --max-posts 30 --scrolls 20

Modes:
    Default (HTTP):   Fast, 1-2 posts, no browser needed.
    --browser:        Uses Playwright headless browser, scrolls to load more posts.
"""
from __future__ import annotations

import argparse
import json
import sys
import io
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from backend.scraper import scrape_source, ScrapeOptions, SourceResult
from backend.scraper.normalizer import normalize_post, NORMALIZED_KEYS
from backend.scraper.parser import ParsedPage


def scrape_browser(
    url: str,
    max_posts: int,
    scroll_rounds: int,
    account_name: str | None = None,
) -> SourceResult:
    """Scrape using Playwright headless browser."""
    from backend.scraper.browser_scraper import fetch_with_browser, parse_browser_page
    from backend.scraper import validate_or_raise, _handle_of
    from backend.scraper.normalizer import normalize_post
    from backend.scraper.dedup import dedup_posts

    try:
        normalized_url = validate_or_raise(url)
    except Exception as exc:
        return SourceResult(url=url, errors=[{"url": url, "code": "invalid_url", "message": str(exc)}])

    print(f"  Launching browser...", end=" ", flush=True)
    t0 = time.time()
    browser_kwargs = {"scroll_rounds": scroll_rounds}
    if max_posts is not None:
        browser_kwargs["max_posts"] = max_posts
    if account_name:
        browser_kwargs["account_name"] = account_name
    html = fetch_with_browser(
        normalized_url,
        **browser_kwargs,
    )
    print(f"({time.time() - t0:.1f}s, {len(html)} bytes)")

    if not html:
        return SourceResult(url=url, errors=[{"url": url, "code": "fetch_failed", "message": "Browser returned empty HTML"}])

    print(f"  Parsing...", end=" ", flush=True)
    t1 = time.time()
    page = parse_browser_page(
        html,
        page_url=normalized_url,
        handle=_handle_of(normalized_url),
    )
    print(f"({time.time() - t1:.1f}s, {len(page.posts)} raw posts)")

    # Normalize and dedup
    normalized = []
    errors_list = [dict(e) for e in page.post_errors]
    for parsed_post in page.posts:
        try:
            post = normalize_post(
                parsed_post,
                page_name=page.page_name,
                page_id=page.page_id,
                facebook_url=normalized_url,
            )
            normalized.append(post)
        except Exception as exc:
            errors_list.append({
                "post_url": parsed_post.post_url or url,
                "code": "extraction_failure",
                "message": f"normalize failed: {exc!r}",
            })

    # Dedup
    kept, duplicates = dedup_posts(normalized)

    # Apply max_posts cap (only when explicitly specified)
    if max_posts is not None and len(kept) > max_posts:
        kept = kept[:max_posts]

    return SourceResult(
        url=url,
        page_name=page.page_name,
        page_id=page.page_id,
        posts=kept,
        stats={
            "posts_discovered": len(page.posts),
            "posts_extracted": len(kept),
            "duplicates_removed": duplicates,
            "posts_skipped": 0,
            "posts_failed": len(errors_list),
        },
        errors=errors_list,
    )


def cmd_scrape(args: argparse.Namespace) -> None:
    urls = args.urls
    max_posts = args.max_posts
    use_browser = args.browser
    scroll_rounds = args.scrolls

    # Resolve account list
    account_names = None
    if getattr(args, "accounts_all", False):
        from backend.scraper.browser_scraper import list_accounts
        account_names = list_accounts()
        if not account_names:
            print("ERROR: No saved accounts. Run 'python cli.py login --account <name>' first.")
            return
    elif args.account:
        account_names = [a.strip() for a in args.account.split(",") if a.strip()]

    mode = "browser" if use_browser else "HTTP"
    account_info = f" (accounts: {', '.join(account_names)})" if account_names else ""
    print(f"Scraping {len(urls)} URL(s) via {mode}{account_info}...\n")

    all_posts = []
    for i, url in enumerate(urls):
        # Rotate accounts: account1 for url1, account2 for url2, etc.
        account_name = None
        if account_names:
            account_name = account_names[i % len(account_names)]
            print(f"[{url}] (using account: {account_name})")
        else:
            print(f"[{url}]")
        t0 = time.time()

        if use_browser:
            result = scrape_browser(url, max_posts, scroll_rounds, account_name=account_name)
        else:
            options = ScrapeOptions(urls=[url], max_posts=max_posts)
            result = scrape_source(url, options)

        elapsed = time.time() - t0
        n = len(result.posts)
        print(f"  {n} post(s) in {elapsed:.1f}s")
        if result.errors:
            for e in result.errors:
                print(f"  ERROR: [{e.get('code')}] {e.get('message')}")
        if result.page_name:
            print(f"  Page: {result.page_name}")
        all_posts.extend(result.posts)
        print()

    if not all_posts:
        print("No posts extracted.")
        return

    print(f"Total: {len(all_posts)} post(s)\n")

    print("Posts:")
    print("-" * 80)
    for i, post in enumerate(all_posts, 1):
        pid = post.get("post_id") or "unknown"
        text = (post.get("text") or "")[:120]
        reactions = post.get("reactions_total") or 0
        shares = post.get("shares") or 0
        published = post.get("published_at") or "?"
        post_type = post.get("post_type") or "?"
        print(f"  #{i} [{post_type}] post_id={pid}")
        if text:
            print(f"       text: {text}")
        print(f"       reactions={reactions}  shares={shares}  published={published}")
        print()

    if args.export:
        export_path = export_posts(all_posts, args.export, args.output)
        print(f"Exported to: {export_path}")


def export_posts(posts: list, fmt: str, output: str | None) -> str:
    if fmt == "json":
        path = output or "posts.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(posts, f, indent=2, ensure_ascii=False, default=str)
        return path

    if fmt == "jsonl":
        path = output or "posts.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for post in posts:
                f.write(json.dumps(post, ensure_ascii=False, default=str) + "\n")
        return path

    rows = []
    for post in posts:
        row = {}
        for key in NORMALIZED_KEYS:
            val = post.get(key)
            if isinstance(val, (list, dict)):
                val = json.dumps(val, ensure_ascii=False)
            row[key] = val
        rows.append(row)

    if fmt == "csv":
        import csv
        path = output or "posts.csv"
        if rows:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
        return path

    if fmt == "xlsx":
        from openpyxl import Workbook
        path = output or "posts.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "Posts"
        if rows:
            headers = list(rows[0].keys())
            ws.append(headers)
            for row in rows:
                ws.append([row.get(h) for h in headers])
            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)
        wb.save(path)
        return path

    raise ValueError(f"Unknown format: {fmt}")


def cmd_login(args: argparse.Namespace) -> None:
    """Open browser for Facebook login and save cookies."""
    from backend.scraper.browser_scraper import login_with_browser
    login_with_browser(account_name=args.account)


def cmd_accounts(args: argparse.Namespace) -> None:
    """List saved Facebook accounts."""
    from backend.scraper.browser_scraper import list_accounts, load_credentials
    accounts = list_accounts()
    if not accounts:
        print("No saved accounts. Run: python cli.py login --account <name>")
        return
    creds = load_credentials()
    print(f"Saved accounts ({len(accounts)}):")
    for name in accounts:
        info = creds.get(name, {})
        saved = info.get("saved_at", "unknown")
        print(f"  - {name}  (saved: {saved})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Facebook Posts Scraper CLI",
    )
    sub = parser.add_subparsers(dest="command")

    # login command
    login_p = sub.add_parser("login", help="Open browser to log into Facebook (saves cookies)")
    login_p.add_argument("--account", type=str, help="Save cookies under this account name")

    # accounts command
    sub.add_parser("accounts", help="List saved Facebook accounts")

    # scrape command
    scrape_p = sub.add_parser("scrape", help="Scrape Facebook posts from URLs")
    scrape_p.add_argument("urls", nargs="+", help="Facebook page/profile URLs")
    scrape_p.add_argument("--browser", action="store_true", help="Use Playwright browser (more posts, slower)")
    scrape_p.add_argument("--max-posts", type=int, default=None, help="Max posts per URL (default: unlimited)")
    scrape_p.add_argument("--scrolls", type=int, default=40, help="Max scroll rounds in browser mode (default: 40)")
    scrape_p.add_argument("--export", choices=["csv", "json", "jsonl", "xlsx"], help="Export format")
    scrape_p.add_argument("--output", type=str, help="Output file path")
    scrape_p.add_argument("--account", type=str, help="Account name(s) to use — comma-separated for rotation (e.g. acc1,acc2,acc3)")
    scrape_p.add_argument("--accounts-all", action="store_true", help="Auto-rotate ALL saved accounts")

    args = parser.parse_args()
    if args.command == "login":
        cmd_login(args)
    elif args.command == "accounts":
        cmd_accounts(args)
    elif args.command == "scrape":
        cmd_scrape(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
