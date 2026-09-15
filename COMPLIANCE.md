# COMPLIANCE — PostHarvest

**Permitted-use statement, engineering guardrails, and Meta/Facebook
compliance limitations** (product spec deliverable §14).

This document is a **statement of design intent**, not legal advice. It
describes what the software does, what it deliberately refuses to do, and the
obligations that remain with the *operator* of this tool. If you plan to
deploy this tool in a commercial, high-volume, or EU/UK context, consult a
lawyer and Meta's current Terms of Service (they change; this document is
accurate as of its writing date).

---

## 1. What this tool is

The PostHarvest extracts **posts that Facebook already publishes
to the public internet** — content visible to any unauthenticated visitor on
a page or profile URL. The extraction path is:

1. A plain HTTP `GET` of the public page, exactly as a browser without a
   session would see it (single constant user agent — no rotation, no
   impersonation).
2. Passive HTML parsing of that public response.
3. Normalization/dedup/storage of *only the fields Facebook itself renders
   publicly* (post text, timestamps, engagement counts, media links, …).

There is **no login, no session, no CAPTCHA solving, no anti-bot tooling, no
headless browser, and no circumvention of any technical protection measure**
at any layer of the system.

## 2. Engineering guardrails (enforced in code)

| Guardrail | Enforcement | Config |
|---|---|---|
| Public content only | URL validator accepts only page/profile URLs; rejects login/consent/non-page paths (`backend/scraper/url_validator.py`) | — |
| `robots.txt` respected | `urllib.robotparser` against `https://www.facebook.com/robots.txt`; disallowed paths → source error `robots_disallowed`. Best-effort fallback: if robots.txt is unreadable, only the documented public page/profile endpoints are fetched | `SCRAPER_ROBOTS=1` (default; `0` for tests only) |
| Hard throttle | Minimum `SCRAPER_DELAY_SECONDS` between requests per source (default **2.5 s**, floor 0.1 s); concurrency of 1 per source | `SCRAPER_DELAY_SECONDS` |
| Backoff on rate limits | Exponential backoff on 429/5xx/transport/timeout, max `SCRAPER_MAX_RETRIES` (default 3), **honors `Retry-After`** headers | `SCRAPER_MAX_RETRIES` |
| Hard timeout | Every request aborts after `SCRAPER_TIMEOUT_SECONDS` (default 20 s) | `SCRAPER_TIMEOUT_SECONDS` |
| No cookie persistence | Cookie jar explicitly cleared after **every** response, so no cross-request session state can accumulate | — |
| Login walls stop the source | A login wall / consent redirect → `AuthRequired` error; a traffic-check/429 → `RateLimited`; **both halt that source immediately**, no retry loop and no workaround | — |
| No credential handling | The application never stores, requests, or forwards Facebook credentials, cookies, or tokens | — |
| Error honesty | Every unavailable field is `null`/`[]` — the tool **never fabricates** text, captions, transcripts, or counts to fill gaps | — |

## 3. What this tool deliberately does NOT do

Read this list carefully — each item is a **hard line** in the implementation:

1. ❌ **No authentication bypass.** It does not log in, does not use stored
   sessions, and does not scrape anything behind a login wall.
2. ❌ **No CAPTCHA or anti-bot bypass.** No CAPTCHA solving, no
   `cf_clearance`-style token tricks, no challenge-response evasion.
3. ❌ **No rate-limit evasion.** No concurrent fan-out, no request
   bursting, no distributed proxies, no IP rotation, no "smart" delays tuned
   to dodge detection.
4. ❌ **No user-agent rotation or impersonation.** One constant UA string.
5. ❌ **No headless browser / JavaScript execution** to defeat client-side
   protections.
6. ❌ **No private or restricted content.** Members-only groups, event pages,
   watch pages, direct post permalinks, and age-gated content are rejected or
   honestly return empty/failed results.
7. ❌ **No personal-data enrichment.** It collects only what the page itself
   publishes; it does not combine, infer, or enrich data about individuals.
8. ❌ **No phishing, spam, or credential harvesting** — and nothing in the
   codebase can do these things even in principle (no login forms to submit,
   no auth endpoints).

## 4. Privacy posture

- **Data minimization:** only fields Facebook renders publicly are stored
  (post content, page name, timestamps, engagement counters, media URLs).
- **Nothing private:** no sessions, cookies, IP fingerprints, or visitor data
  are collected from or about Facebook users.
- **Honesty about gaps:** when public HTML omits something (e.g. post text on
  JS-rendered pages, raw video URLs, transcripts, reaction breakdowns), the
  tool stores `null` — it does **not** guess, fill, or extrapolate.
- **Storage is yours:** all data lives in your database
  (`data/postharvest.db` or your Postgres). The tool has no telemetry,
  no phone-home, and sends nothing except the public-page `GET` requests
  required for scraping.
- **Operator duty under GDPR/other privacy law:** if you export and
  redistribute content, remember that posts may contain personal data of
  individuals who did not consent to being scraped. Re-publishing personal
  data may require a lawful basis; anonymize/aggregate where possible and
  respect take-down requests.

## 5. User responsibilities

Operating this tool is lawful or unlawful **depending on how and where you
use it**. By deploying it you accept:

1. **Terms of Service.** Scraping may violate Facebook/Meta's Terms of
   Service even when technically compliant. Violations can lead to IP bans,
   account restrictions, or legal claims. The tool's safeguards reduce risk;
   they do not grant permission.
2. **`robots.txt` and technical signals.** Honor the site's stated crawling
   policy. If Facebook's robots.txt or rate-limit signals tell you to stop,
   **you stop** — this tool is engineered to do exactly that.
3. **High-volume caution.** Never run concurrent instances against the same
   targets; keep `SCRAPER_DELAY_SECONDS` at or above the default (2.5 s) in
   production. The tool's own backoff will raise effective delay under
   pressure, but operator discipline is the real throttle.
4. **Local law.** Some jurisdictions restrict automated data collection even
   of public data (e.g. EU *sui generis* database rights, Japan's unfair
   competition rules, CFAA-type computer-misuse statutes). Public ≠ free for
   any use.
5. **Data usage.** Respect the page owners' intention: if a page reposts
   something with "do not republish", don't republish it. Attribute sources.
6. **No warranty of access.** Facebook changes markup, retires `mbasic`,
   tightens rate limits, and may block datacenter IP ranges. Availability
   fluctuations are expected; the tool degrades honestly (empty results /
   typed errors) instead of circumventing.

## 6. Jurisdiction note

This tool was built with no claim about the legality of scraping in any
specific jurisdiction. It is most defensible where:

- the target content is **unambiguously public** (no auth, no paywall),
- collection is **low-volume and polite** (throttled, robots-aware),
- the data is used **internally for research/monitoring** rather than
  republished wholesale,
- and the operator **removes data on request**.

If any of those conditions fails, neither this document nor the tool's
engineering guardrails protect you.

## 7. Meta-specific: current known limitations (as of build date)

These are **platform realities**, documented here so nobody files them as
bugs:

| Capability | Public HTML status |
|---|---|
| Post text (`www` modern markup) | Often **absent** (JS-rendered) → `text: null` |
| Post text (`mbasic`/mobile variants) | Usually present — but Meta may retire `mbasic` at any time |
| Exact timestamps | Only when `abbr[data-utime]` exists; else parsed human strings stored as UTC-by-convention |
| Reaction breakdown counts | Usually **not** publicly rendered (`reaction_*` → `null`) |
| Raw video file URLs (`video_url`) | Almost always only via authenticated JS/Graph API |
| Transcripts / captions | Never public; `caption` is always `null` (no fabricated splits) |
| Age-gated / login-walled pages | `auth_required` — hard stop |
| Traffic-check / rate-limited responses | `rate_limited` — hard stop |

## 8. Supersession

If a future version adds a Graph API path (with proper app credentials and
permissions), this document must be revised — the "no authentication" lines
in §2/§3 would no longer describe the default path. Until then, the public-HTML
path described here is the only path that exists.

---

*This document accompanies the PostHarvest deliverable (§14 of the
product specification). It is a good-faith statement of design and usage
boundaries, not legal counsel.*