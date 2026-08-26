# Facebook Posts Scraper

A job-based web service that extracts publicly accessible posts from Facebook
pages and profiles. It fetches public HTML over the public web with a single
honest user agent, **respects `robots.txt`**, and **throttles every request**
(2.5 s minimum by default).

Two extraction modes:

- **HTTP mode (default):** Fast (~3s), no browser needed, gets 1-2 posts per page.
- **Browser mode (`--browser`):** Uses Playwright headless Chromium to execute
  JavaScript, scroll the page, and load more posts. Supports authenticated
  scraping via saved cookies for full content access.

The system is a FastAPI backend with a background job manager, a Next.js
dashboard, a standalone CLI, and JSON / CSV / XLSX exports.

> **Compliance framing — read this first.** This tool exists to collect
> data Facebook already publishes to the world. It deliberately **does not**
> bypass authentication, consent screens, rate limits, or anti-bot
> protections. Using it still binds you to Facebook/Meta's Terms of Service,
> applicable laws, and the `robots.txt` / scraping policies of the sites you
> target. See **[COMPLIANCE.md](./COMPLIANCE.md)** for the full permitted-use
> statement.

---

## Table of contents

- [Features](#features)
- [Quick start](#quick-start)
- [CLI usage](#cli-usage)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Repository structure](#repository-structure)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Exports](#exports)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)
- [Compliance summary](#compliance-summary)

---

## Features

- Scrape multiple Facebook **page / profile URLs** per job
- **Two modes:** fast HTTP scraping or full browser-based scraping with Playwright
- **Authenticated browser scraping:** login once via CLI, cookies saved for
  subsequent requests to bypass login walls and load more posts
- Job-based async model with live progress (API + dashboard)
- Background worker pool, per-source lifecycle, best-effort job cancellation
- Normalized 33-key post schema — missing fields are `null`/`[]`, never fabricated
- Date-range, post-type (`text/image/video/link/all`) and `max_posts` filters
- Two-layer deduplication (post-id + SHA-256 fingerprint)
- Dashboard: URL entry, live progress, KPI cards, post table, detail drawer, exports
- Exports: **JSON** (nested), **CSV** (Excel-friendly), **XLSX** (styled workbook)
- SQLite out of the box; PostgreSQL via `DATABASE_URL`
- Consistent error envelope `{"error": {"code", "message"}}` on every failure

## Quick start

### Path A — CLI (simplest)

```bash
cd facebook-posts-scraper
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Unix: source .venv/bin/activate
pip install -r backend/requirements.txt playwright
playwright install chromium

# HTTP mode (fast, 1-2 posts)
python cli.py scrape https://www.facebook.com/<public-page> --export json

# Browser mode (more posts, slower)
python cli.py scrape https://www.facebook.com/<public-page> --browser --max-posts 20 --export xlsx

# Authenticated browser mode (full content)
python cli.py login                          # opens browser, log in, cookies saved
python cli.py scrape <url> --browser         # uses saved cookies
```

### Path B — Docker Compose (full stack)

```bash
docker compose up --build
```

| URL | What |
|---|---|
| http://localhost:3000 | Dashboard (Next.js) |
| http://localhost:8000/api | API root |
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/api/health | Health check |

### Path C — Backend only

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

### Path D — Frontend only

```bash
cd frontend && npm install && npm run dev   # → http://localhost:3000
```

## CLI usage

```
python cli.py login                          # Open browser to log into Facebook
python cli.py scrape <url> [url ...] [options]
```

### Scrape options

| Flag | Default | Description |
|---|---|---|
| `--browser` | off | Use Playwright headless browser (slower, more posts) |
| `--max-posts N` | 50 | Max posts per URL |
| `--scrolls N` | 40 | Max scroll rounds in browser mode |
| `--export csv\|json\|xlsx` | *(none)* | Export results to file |
| `--output FILE` | auto | Output file path |

### Examples

```bash
# Quick HTTP scrape → terminal output
python cli.py scrape https://www.facebook.com/kzsamir849

# Browser scrape with export
python cli.py scrape https://www.facebook.com/ashraful.islam333 \
    --browser --max-posts 30 --scrolls 15 --export xlsx --output results.xlsx

# Scrape multiple pages
python cli.py scrape https://www.facebook.com/page1 https://www.facebook.com/page2 \
    --browser --export json
```

## Architecture

```
┌─────────────────────────────────┐       ┌──────────────────────────────────┐
│  CLI (cli.py)                   │       │  Next.js dashboard (:3000)        │
│  --browser → Playwright         │       │  URL input / progress / KPIs      │
│  -- (default) → HTTP (httpx)    │       │  posts table / export buttons     │
└────────────┬────────────────────┘       └────────────┬─────────────────────┘
             │ direct import                          │ HTTP (CORS)
             └────────────┬───────────────────────────┘
                          ▼
         ┌─────────────────────────────────────┐
         │      FastAPI backend (:8000)         │
         │  POST /api/scrape → queues job       │
         │  GET /api/jobs/{id} (live poll)      │
         │  GET /api/jobs/{id}/posts            │
         │  GET …/export/{json|csv|excel}       │
         └────────────────┬────────────────────┘
                          │ ThreadPoolExecutor
         ┌────────────────▼────────────────────┐
         │  Job manager (queued → running →     │
         │  completed | failed)                 │
         │  ┌──────────┐  ┌──────────────────┐  │
         │  │ scraper   │  │ exporters        │  │
         │  │ (httpx +  │  │ json/csv/xlsx    │  │
         │  │ robots +  │  │ → data/exports   │  │
         │  │ throttle) │  └──────────────────┘  │
         │  │ OR        │                        │
         │  │ Playwright│                        │
         │  │ (browser) │                        │
         │  └──────────┘                         │
         └────────────────┬────────────────────┘
                          │
         ┌────────────────▼────────────────────┐
         │  SQLite / PostgreSQL                 │
         └─────────────────────────────────────┘
```

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+ · FastAPI 0.115 · Uvicorn 0.34 · Pydantic v2 |
| Data | SQLAlchemy 2.0 · SQLite (default) / PostgreSQL (optional) |
| Scraper (HTTP) | httpx · BeautifulSoup4 (lxml) · brotli · stdlib `urllib.robotparser` |
| Scraper (Browser) | Playwright (Chromium headless) |
| Exports | stdlib `json`/`csv` · openpyxl (XLSX) |
| Frontend | Next.js 14 (App Router) · React 18 · TypeScript · Tailwind CSS 3.4 |
| Ops | Docker (multi-stage), docker-compose |

## Repository structure

```
facebook-posts-scraper/
├── cli.py                     # Standalone CLI (login + scrape)
├── Dockerfile                 # backend (:8000) + frontend (:3000)
├── docker-compose.yml
├── .env.example
├── COMPLIANCE.md              # Permitted-use + Meta compliance
├── README.md
│
├── backend/
│   ├── main.py                # FastAPI app factory, CORS, error handlers
│   ├── requirements.txt       # Pinned deps (including brotli, playwright)
│   ├── api/                   # scrape, jobs, exports, health routers
│   ├── core/                  # config, database, exceptions, job_manager, logging
│   ├── models/                # SQLAlchemy: jobs, sources, posts, media, errors
│   ├── schemas/               # Pydantic request/response models
│   ├── services/              # job_service, export_service, serialization
│   ├── scraper/               # fetcher, parser, normalizer, dedup, browser_scraper
│   └── exporters/             # json/csv/xlsx exporters
│
├── frontend/                  # Next.js 14 dashboard
│   ├── app/                   # page.tsx, layout, globals
│   ├── components/            # header, url-input, progress, KPI cards, posts table
│   └── lib/                   # api.ts, hooks.ts, types.ts, utils.ts
│
├── data/                      # Runtime: SQLite DB + exports + fb_cookies.json
├── examples/                  # Shipped example exports
└── tests/                     # pytest suite (mocked responses)
```

## Configuration

All backend variables are read by pydantic-settings (env vars **or** `.env`).

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/facebook_scraper.db` | SQLAlchemy DSN |
| `DATA_DIR` | `./data` | Runtime data directory |
| `EXPORT_BASE_DIR` | `./data/exports` | Export output root |
| `WORKER_THREADS` | `4` | Parallel scrape workers |
| `MAX_URLS_PER_JOB` | `100` | Max URLs per request |
| `DEFAULT_MAX_POSTS` | *(none)* | Per-source post cap |
| `DEFAULT_POST_TYPE` | `all` | Default type filter |
| `DEBUG` | `false` | Verbose logging |
| `CORS_ORIGINS` | `["http://localhost:3000","http://127.0.0.1:3000"]` | Allowed origins |
| `SCRAPER_DELAY_SECONDS` | `2.5` | Min delay between requests |
| `SCRAPER_TIMEOUT_SECONDS` | `20` | Per-request timeout |
| `SCRAPER_MAX_RETRIES` | `3` | Retries with backoff |
| `SCRAPER_ROBOTS` | `1` | Enforce robots.txt |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL (build-time for Next.js) |

## API reference

Base URL: `http://localhost:8000/api`. Docs: http://localhost:8000/docs

**Error envelope:** `{"error": {"code": "<code>", "message": "<human>"}}`

| HTTP | Codes | Meaning |
|---|---|---|
| 400 | `invalid_input`, `validation_error` | Bad request |
| 404 | `not_found` | Unknown job |
| 409 | `job_running`, `conflict` | Job not finished |
| 500 | `internal_error` | Unhandled error |
| 503 | `scraper_unavailable`, `database_unavailable` | Dependency down |

### `POST /api/scrape` — start a job

```json
{
  "urls": ["https://www.facebook.com/greencitydhaka"],
  "max_posts": 200,
  "start_date": "2026-01-01",
  "end_date": "2026-08-01",
  "post_type": "all"
}
```

Response `201`: `{ "job_id": "a1b2c3d4…", "status": "queued" }`

### `GET /api/jobs/{job_id}` — status & progress

Poll until `status` is `completed` or `failed`. Returns `pages_total`,
`pages_completed`, `posts_found`, `posts_processed`, `duplicates`, `errors`,
`error_details`, `posts_skipped`, `posts_failed`.

### `GET /api/jobs/{job_id}/posts` — paginated posts

`?page=1&page_size=200`. Returns normalized 33-key post objects.

### `GET /api/jobs/{job_id}/export/{json|csv|excel}` — download results

### `DELETE /api/jobs/{job_id}` — cancel & delete

### `GET /api/health` — liveness probe

## Exports

| Format | Shape |
|---|---|
| **JSON** | Nested, pretty-printed, full 33-key schema per post |
| **CSV** | Flattened, UTF-8 BOM, Excel-friendly |
| **XLSX** | Styled 4-sheet workbook (Posts, Engagement, Media, Metadata) |

## Testing

```bash
pip install pytest
pytest -q
```

Tests use mocked scraper responses — no live network access.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "API unreachable" banner | Backend not running; rebuild frontend if `NEXT_PUBLIC_API_URL` changed |
| CORS error | `CORS_ORIGINS` doesn't include your frontend origin |
| 0 posts, no errors | Modern Facebook `www` is JS-rendered; try `--browser` mode or check login wall |
| `auth_required` in errors | Page requires login; run `python cli.py login` then use `--browser` |
| `rate_limited` | Too many requests; raise `SCRAPER_DELAY_SECONDS` |
| `scraper_unavailable` | Backend scraper module incomplete |
| SQLite `database is locked` | Reduce `WORKER_THREADS` or use PostgreSQL |
| Browser login not detected | Cookies expired; run `python cli.py login` again |

## Limitations

1. **HTTP mode gets 1-2 posts.** Modern Facebook `www` pages embed minimal
   data in initial HTML. Use `--browser` for more.
2. **Browser mode without login gets ~3 posts.** Facebook limits unauthenticated
   viewing. Run `python cli.py login` for authenticated scraping.
3. **Browser mode with login gets more but not unlimited.** Facebook's React
   pagination still throttles scroll depth; the tool stops when no new content
   loads.
4. **Post text may be `null`** even in browser mode — some post types (pure
   images, shared links) don't include text in Facebook's embedded JSON.
5. **Reaction breakdown, `video_url`, `transcript`** are usually unavailable
   on public pages — kept in schema for forward-compatibility.
6. **Heuristic parsing.** Facebook changes markup frequently; one malformed
   post never crashes a source (per-post error collection).
7. **Rate-limiting risk.** Aggressive use can trigger Meta's rate limits.
   Respect the defaults.
8. **Cookies expire.** Facebook session cookies typically last 1-2 weeks.
   Re-run `login` when they expire.

## Compliance summary

- **Permitted:** public pages/profiles only, respects `robots.txt`, throttled,
  single honest UA, exponential backoff, cookies cleared per response.
  Browser mode uses saved cookies for authentication — you are responsible for
  how you use this capability.
- **Deliberately excluded:** CAPTCHA/anti-bot bypass, UA rotation, private/
  restricted content, groups/events/watch sources.
- **Your responsibility:** obey Facebook/Meta's Terms of Service, applicable
  law (GDPR, etc.), and the target site's `robots.txt`.

**Full detail: [COMPLIANCE.md](./COMPLIANCE.md)**

## License

MIT (placeholder). Add a license file before public distribution.
