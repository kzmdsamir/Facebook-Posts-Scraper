# API Reference

Base URL: `http://localhost:8000/api` (in the Docker stack the frontend calls
the same origin and the `/api` prefix is already included by the client).

Interactive docs: **`http://localhost:8000/docs`** (Swagger UI).

## Error contract

Every failure returns the same envelope:

```json
{ "error": { "code": "<machine-code>", "message": "<human message>" } }
```

| HTTP | `code` | Meaning |
|---|---|---|
| 400 | `invalid_input` | validation / bad payload |
| 404 | `not_found` | unknown job / account |
| 409 | `invalid_state` | illegal state transition (e.g. pause a completed job) |
| 409 | `job_busy` | conflicting concurrent operation |
| 503 | `service_unavailable` | worker unavailable |

## Endpoints

### Health checks

#### `GET /api/health`

Liveness + DB probe.

```json
{ "status": "ok", "database": "ok", "version": "1.0.0" }
```

### Scraping

#### `POST /api/scrape`

Queue a scraping job. Returns immediately with the job id; work happens in the
background.

Request body:

| Field | Type | Required | Notes |
|---|---|---|---|
| `urls` | `string[]` | ✅ | 1..100 Facebook page/profile URLs. Empty entries stripped; invalid URLs don't fail the job — they become `error_details` (400 only if *no* URL survives). |
| `max_posts` | `int` | – | per-source cap (1..100 000) |
| `start_date` | `string` | – | ISO `YYYY-MM-DD`, inclusive lower bound |
| `end_date` | `string` | – | ISO `YYYY-MM-DD`, inclusive upper bound; must be ≥ `start_date` |
| `post_type` | `string` | – | `text \| image \| video \| link \| all` (case-insensitive) |
| `use_browser` | `bool` | – | `true` = Playwright browser scraper (captures Facebook's Comet GraphQL feed; far more posts than the anonymous HTML path) |
| `account` | `string` | – | saved session name (from `python cli.py login --account NAME`); cookies unlock the logged-in feed |
| `scrolls` | `int` | – | browser scroll rounds (1..300, default 40) |

Response **201**:

```json
{ "job_id": "7f9c…", "status": "queued" }
```

### Jobs

#### `GET /api/jobs`

List recent jobs, newest first. Query params: `page` (default 1), `page_size`
(default 25, max 100).

```json
{
  "items": [
    {
      "job_id": "7f9c…",
      "status": "completed",
      "pages_total": 1, "pages_completed": 1,
      "posts_found": 42, "posts_processed": 42,
      "duplicates": 2, "errors": 0,
      "urls": ["https://www.facebook.com/somepage"],
      "max_posts": null, "post_type": "all",
      "created_at": "2026-09-14T09:54:10.595300", "completed_at": "…"
    }
  ],
  "total": 12, "page": 1, "page_size": 25
}
```

#### `GET /api/jobs/{job_id}`

Live status + progress + recent errors (max 50).

```json
{
  "job_id": "7f9c…",
  "status": "running",
  "pages_total": 1, "pages_completed": 0,
  "posts_found": 10, "posts_processed": 10,
  "duplicates": 1, "errors": 0,
  "error_details": [],
  "posts_skipped": 0, "posts_failed": 0,
  "cancel_requested": false,
  "created_at": "…", "completed_at": null
}
```

#### `GET /api/jobs/{job_id}/posts`

Paginated, newest-first posts. Query params: `page` (default 1), `page_size`
(default 50, max 200).

Each item is the **normalized 33-key post dict** — every key always present,
unavailable fields are `null`/`[]`, never fabricated:

```
post_id, facebook_url, post_url, page_name, page_id, profile_url, post_type,
published_at, timestamp, text, caption, hashtags, mentions, external_links,
likes, reactions, comments_count, shares, views_count,
reaction_like_count, reaction_love_count, reaction_care_count,
reaction_haha_count, reaction_wow_count, reaction_sad_count, reaction_angry_count,
media_type, thumbnail_url, media_url, video_url,
transcript, transcript_language, scraped_at
```

#### `GET /api/jobs/{job_id}/stats`

Dashboard KPIs: `total_posts`, engagement totals, `videos/images/links/texts`,
`post_type_counts`, `first_post_at`, `last_post_at`.

#### `POST /api/jobs/{job_id}/pause`

Pause a `queued`/`running` job (409 elsewhere). Worker stops after the current
source completes. → `200 {"job_id","status":"paused"}`.

#### `POST /api/jobs/{job_id}/resume`

Resume a `paused` job (409 elsewhere); continues from the CrawlState
checkpoint. → `200 {"job_id","status":"queued"}`.

#### `DELETE /api/jobs/{job_id}`

Best-effort cancel (waits up to `CANCEL_WAIT_SECONDS`), then deletes the job +
all dependent rows. → **204** no body.

### Exports

#### `GET /api/jobs/{job_id}/export/{fmt}`

`fmt` is one of `json | csv | excel`. Downloads the file
`facebook_posts.<ext>` built from the job's posts. (JSONL exists in the
exporter layer but is **not** exposed over HTTP — use the CLI `--export jsonl`.)

### Accounts (Facebook sessions)

#### `GET /api/accounts`

List saved sessions (metadata only, no cookies).

```json
{
  "items": [
    { "name": "default", "cookies_file": "fb_cookies_default.json",
      "saved_at": "2026-09-15T09:04:16.967271" }
  ],
  "total": 1
}
```

#### `DELETE /api/accounts/{account_name}`

Delete a saved session + its index entry. → **204**.

## Pagination

List endpoints return `{items, total, page, page_size}`. Page bounds are
enforced server-side (`page_size_max = 200`).

## CORS

Allowed origins default to `["http://localhost:3000", "http://127.0.0.1:3000"]`
and are overridable via `CORS_ORIGINS` (JSON array in env).

## Auth

**None today** — every route is unauthenticated and shared. Multi-tenant auth
(Firebase ID tokens on every `/api` route, `owner_id` scoping) is planned; see
[ARCHITECTURE.md](./ARCHITECTURE.md) and [ROADMAP.md](../ROADMAP.md).