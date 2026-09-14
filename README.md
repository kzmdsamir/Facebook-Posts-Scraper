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
dashboard, a standalone CLI, and JSON / CSV / XLSX / JSONL exports.

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
- **Pause / resume** running jobs from the dashboard or API
- Two-layer deduplication (post-id + SHA-256 fingerprint)
- **Configurable proxy support** for all HTTP requests
- **Rate limiter** with token-bucket pacing and circuit breaker
- **Retry manager** with exponential backoff on 429/5xx
- **CrawlState checkpointing** for crash recovery and resume
- Dashboard: URL entry, live progress, KPI cards, post table, detail drawer, exports
- Exports: **JSON**, **CSV**, **XLSX**, **JSONL** (streaming)
- SQLite out of the box; PostgreSQL via `DATABASE_URL`
- Consistent error envelope `{"error": {"code", "message"}}` on every failure
- Health endpoint with database latency check

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

> **Docker notes**
> - Both containers run as a non-root user against a **read-only root filesystem**
>   with all capabilities dropped and resource limits set. The SQLite DB and
>   exports live in the compose **named volume `data`** (`docker compose
>   down -v` would delete it — don't run that with real data).
> - The scraper keeps job state in in-process worker threads, so the backend
>   must run as a **single replica** behind your reverse proxy.
> - `NEXT_PUBLIC_API_URL` is baked into the frontend JS at build time; override
>   it via `.env`, then rebuild (`docker compose up --build`) when you expose
>   the API on a real host.
> - On Linux, add your user to the `docker` group (`sudo usermod -aG docker $USER`)
>   and re-login so `docker compose` works without `sudo`.

### Path C — Backend only

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --reload-dir backend --port 8000
```

### Path D — Frontend only

```bash
cd frontend && npm install && npm run dev   # → http://localhost:3000
```

### Run both (recommended)

```bash
# Terminal 1 — backend
uvicorn backend.main:app --reload --reload-dir backend --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

Then open **http://localhost:3000** in your browser.

## CLI usage

```
python cli.py login                          # Open browser to log into Facebook
python cli.py scrape <url> [url ...] [options]
```

### Scrape options

| Flag | Default | Description |
|---|---|---|
| `--browser` | off | Use Playwright headless browser (slower, more posts) |
| `--max-posts N` | *(none)* | Max posts per URL (no default cap) |
| `--scrolls N` | 40 | Max scroll rounds in browser mode |
| `--export csv\|json\|jsonl\|xlsx` | *(none)* | Export results to file |
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
│  -- (default) → HTTP (httpx)    │       │  posts table / pause / export     │
└────────────┬────────────────────┘       └────────────┬─────────────────────┘
             │ direct import                          │ HTTP (CORS)
             └────────────┬───────────────────────────┘
                          ▼
         ┌─────────────────────────────────────┐
         │      FastAPI backend (:8000)         │
         │  POST /api/scrape → queues job       │
         │  GET /api/jobs/{id} (live poll)      │
         │  GET /api/jobs/{id}/posts            │
         │  POST /api/jobs/{id}/pause           │
         │  POST /api/jobs/{id}/resume          │
         │  GET …/export/{json|csv|excel|jsonl} │
         │  GET /api/health                     │
         └────────────────┬────────────────────┘
                          │ ThreadPoolExecutor (4 workers)
         ┌────────────────▼────────────────────┐
         │  Job manager (queued → running →     │
         │  paused → completed | failed)        │
         │  ┌──────────┐  ┌──────────────────┐  │
         │  │ scraper   │  │ exporters        │  │
         │  │ (httpx +  │  │ json/csv/xlsx/   │  │
         │  │ robots +  │  │ jsonl            │  │
         │  │ throttle +│  │ → data/exports   │  │
         │  │ proxy +   │  └──────────────────┘  │
         │  │ retry +   │                        │
         │  │ rate)     │                        │
         │  │ OR        │                        │
         │  │ Playwright│                        │
         │  │ (browser) │                        │
         │  └──────────┘                         │
         │  ┌──────────────────────────────────┐ │
         │  │ CrawlState checkpointing          │ │
         │  │ (resume on crash / restart)       │ │
         │  └──────────────────────────────────┘ │
         └────────────────┬────────────────────┘
                          │
         ┌────────────────▼────────────────────┐
         │  SQLite (WAL) / PostgreSQL           │
         └─────────────────────────────────────┘
```

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+ · FastAPI 0.115 · Uvicorn 0.34 · Pydantic v2 |
| Data | SQLAlchemy 2.0 · SQLite WAL (default) / PostgreSQL (optional) |
| Scraper (HTTP) | httpx · BeautifulSoup4 (lxml) · brotli · stdlib `urllib.robotparser` |
| Scraper (Browser) | Playwright (Chromium headless) |
| Resilience | RateLimiter (token-bucket) · RetryManager (circuit breaker) · ProxyManager |
| Exports | stdlib `json`/`csv` · openpyxl (XLSX) · streaming JSONL |
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
│   ├── models/                # SQLAlchemy: jobs, sources, posts, media, errors, crawl_state
│   ├── schemas/               # Pydantic request/response models
│   ├── services/              # job_service, export_service, crawl_state_service, serialization
│   ├── scraper/
│   │   ├── __init__.py        # scrape_source() orchestrator
│   │   ├── fetcher.py         # HTTP fetcher (proxy + retry + delay)
│   │   ├── http_client.py     # Shared httpx factory, BROWSER_HEADERS, retry_get()
│   │   ├── rate_limiter.py    # Token-bucket RateLimiter, RetryManager (circuit breaker)
│   │   ├── proxy_manager.py   # Proxy rotation, health checking, fallback
│   │   ├── pagination.py      # Generic pagination engine
│   │   ├── crawler.py         # Transport-agnostic Crawler class
│   │   ├── adapters/          # Facebook HTTP + Browser transport adapters
│   │   ├── parser.py          # Facebook HTML/JSON post parser
│   │   ├── normalizer.py      # 33-key post schema normalization
│   │   ├── dedup.py           # Post-ID + SHA-256 dedup, cross-source dedup
│   │   ├── browser_scraper.py # Playwright browser scraper
│   │   ├── stats.py           # Scrape statistics counters
│   │   └── url_validator.py   # Facebook URL validation + normalization
│   └── exporters/
│       ├── json.py            # Nested JSON export
│       ├── csv_export.py      # Flat CSV export
│       ├── xlsx_export.py     # Styled XLSX workbook
│       ├── jsonl_exporter.py  # Streaming JSONL export
│       ├── safety.py          # Filename allowlist, path safety
│       └── __init__.py        # export_posts() dispatcher
│
├── frontend/                  # Next.js 14 dashboard
│   ├── app/                   # page.tsx, layout, globals
│   ├── components/            # header, url-input, progress, KPI cards, posts table
│   └── lib/                   # api.ts (pause/resume), hooks.ts, types.ts, utils.ts
│
├── data/                      # Runtime: SQLite DB + exports + fb_cookies.json
├── examples/                  # Shipped example exports
└── tests/                     # 105+ tests (mocked responses)
    ├── test_api_endpoints.py
    ├── test_dedup_stats.py
    ├── test_export_api.py
    ├── test_fetcher.py
    ├── test_integration.py
    ├── test_job_state_machine.py
    ├── test_parser_extractors.py
    ├── test_post_processing.py
    ├── test_scraper_api.py
    ├── test_infrastructure.py  # RateLimiter, RetryManager, ProxyManager, dedup
    ├── test_e2e_integration.py # Full pipeline integration tests
    └── test_exporters.py
```

## Configuration

All backend variables are read by pydantic-settings (env vars **or** `.env`).

### General

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
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL (build-time for Next.js) |

### Scraper

| Variable | Default | Description |
|---|---|---|
| `SCRAPER_DELAY_SECONDS` | `2.5` | Min delay between requests per source |
| `SCRAPER_TIMEOUT_SECONDS` | `20` | Per-request timeout |
| `SCRAPER_MAX_RETRIES` | `3` | Retries with exponential backoff |
| `SCRAPER_ROBOTS` | `1` | Enforce robots.txt |

### Proxy

| Variable | Default | Description |
|---|---|---|
| `PROXY_URL` | *(none)* | Single HTTP proxy URL (e.g. `http://127.0.0.1:8080`) |
| `PROXY_URLS` | `[]` | List of proxies for rotation |

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

Poll until `status` is `completed`, `failed`, or `paused`. Returns `pages_total`,
`pages_completed`, `posts_found`, `posts_processed`, `duplicates`, `errors`,
`error_details`, `posts_skipped`, `posts_failed`.

### `GET /api/jobs/{job_id}/posts` — paginated posts

`?page=1&page_size=200`. Returns normalized 33-key post objects.

### `POST /api/jobs/{job_id}/pause` — pause a running job

Response `200`: `{ "status": "paused" }`

### `POST /api/jobs/{job_id}/resume` — resume a paused job

Response `200`: `{ "status": "queued" }`

### `GET /api/jobs/{job_id}/export/{json|csv|excel|jsonl}` — download results

### `DELETE /api/jobs/{job_id}` — cancel & delete

### `GET /api/health` — liveness probe

```json
{ "status": "ok", "database": "ok", "version": "1.0.0" }
```

## Exports

| Format | Shape |
|---|---|
| **JSON** | Nested, pretty-printed, full 33-key schema per post |
| **CSV** | Flattened, UTF-8 BOM, Excel-friendly |
| **XLSX** | Styled 4-sheet workbook (Posts, Engagement, Media, Metadata) |
| **JSONL** | One JSON object per line, streaming (memory-safe for large datasets) |

## Testing

```bash
pip install pytest
pytest -q --ignore=tests/test_exporters.py
```

Tests use mocked scraper responses — no live network access.

**105+ tests** covering:
- API endpoints (scrape, jobs, exports, health)
- Scraper pipeline (fetcher, parser, normalizer, dedup)
- Job state machine (lifecycle, cancel, pause/resume)
- Infrastructure (RateLimiter, RetryManager, ProxyManager)
- End-to-end integration (full pipeline, proxy wiring)

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
| Proxy not working | Check `PROXY_URL` in config; verify proxy is running |
| Job stuck in `running` | Use `POST /api/jobs/{id}/pause` then `/resume` to unstick |

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
