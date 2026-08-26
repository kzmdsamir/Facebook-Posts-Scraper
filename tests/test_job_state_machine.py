"""Group 6 — job state machine (queued -> running -> completed/failed) and
cancellation, exercised THROUGH the API with a fake scraper.

The fakes return real :class:`backend.scraper.SourceResult` instances — the
exact return type of the real ``scrape_source`` — so these tests double as
the first live integration check of the API layer against the scraper
contract.  See the bug report in subagent_05.md for the counter assertions
that correctly fail against the current backend.

NOTE on post_type: the default flow (no post_type in the request) currently
breaks — the API default is "all" but ``backend.scraper.ScrapeOptions``
rejects "all".  Tests that want a clean per-source success pass an explicit
post_type; a dedicated test pins the default-flow regression.
"""
from __future__ import annotations

import threading
import time

from backend.scraper import ScrapeOptions

from helpers import (
    PAGE_URL,
    canonical_post,
    install_fake_scraper,
    make_source_result,
    blocking_scraper,
    sample_posts,
    wait_for_job,
)


def _start(client, *, post_type="text", urls=None, **extra):
    payload = {"urls": urls or [PAGE_URL]}
    if post_type is not None:
        payload["post_type"] = post_type
    payload.update(extra)
    resp = client.post("/api/scrape", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["job_id"]


def test_queued_running_completed_with_progress(client, monkeypatch):
    """Full happy path: progress_cb drives live counters, the job completes.

    Expected final counters (spec §17 + stats convention):
        posts_found=4, posts_processed=3, duplicates=1, posts_skipped=1,
        posts_failed=0, errors=0, pages_completed=1.
    """
    posts = sample_posts(3)
    stats = {
        "posts_discovered": 4,
        "posts_extracted": 3,
        "duplicates_removed": 1,
        "posts_skipped": 1,
        "posts_failed": 0,
    }
    gate = threading.Event()
    events = [
        {"posts_found": 2, "posts_extracted": 1, "duplicates_removed": 0,
         "posts_skipped": 0, "posts_failed": 0},
        {"posts_found": 4, "posts_extracted": 3, "duplicates_removed": 1,
         "posts_skipped": 1, "posts_failed": 0},
    ]
    options_seen: list = []
    install_fake_scraper(
        monkeypatch,
        results=[make_source_result(PAGE_URL, posts=posts, stats=stats)],
        progress_events=events,
        progress_gap=1.2,  # >= 1s so the throttled progress persister keeps both
        gate=gate,
        options_seen=options_seen,
    )

    job_id = _start(client)
    # queued (or already running) immediately after POST
    queued = client.get(f"/api/jobs/{job_id}").json()
    assert queued["status"] in ("queued", "running")

    # Live progress must be visible: the second ping (found=4) persisted.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["posts_found"] >= 4:
            break
        time.sleep(0.05)
    assert body["posts_found"] >= 4, f"progress not visible: {body}"
    assert body["posts_processed"] >= 1
    assert body["status"] == "running"

    gate.set()
    final = wait_for_job(client, job_id)
    assert final["status"] == "completed"
    assert final["pages_total"] == 1
    assert final["pages_completed"] == 1
    assert len(options_seen) == 1 and isinstance(options_seen[0], ScrapeOptions)

    # ---- contract assertions (currently FAIL — see bug report) -----------
    assert final["posts_found"] == 4
    assert final["posts_processed"] == 3, (
        "Sources reported 3 extracted posts; job processed counter must "
        "equal the stored post count"
    )
    assert final["duplicates"] == 1
    assert final["posts_skipped"] == 1
    assert final["posts_failed"] == 0
    assert final["errors"] == 0
    # stats invariant: discovered == extracted + skipped + failed
    assert final["posts_found"] == (
        final["posts_processed"] + final["posts_skipped"] + final["posts_failed"]
    )
    # posts must actually be persisted and listable
    r = client.get(f"/api/jobs/{job_id}/posts")
    assert r.status_code == 200 and r.json()["total"] == 3
    stored = r.json()["items"]
    assert stored[0]["page_name"] == "Example Page"
    assert stored[0]["page_id"] == "123456789"
    assert {p["post_type"] for p in stored} == {"text", "image", "video"}


def test_default_flow_without_post_type(client, monkeypatch):
    """No post_type supplied -> API default is "all".  The scraper's own
    ScrapeOptions only accepts text|image|video|link, so the worker must map
    the default to something valid and the job must complete with its posts.
    (Currently FAIL — see bug report: ScrapeOptions rejects "all".)"""
    posts = sample_posts(2)
    install_fake_scraper(
        monkeypatch,
        results=[make_source_result(PAGE_URL, posts=posts)],
    )
    job_id = _start(client, post_type=None)
    final = wait_for_job(client, job_id)
    assert final["status"] == "completed"
    assert final["errors"] == 0, (
        f"default flow must not raise scraper errors, got {final['error_details']}"
    )
    assert final["posts_processed"] == 2


def test_source_failure_still_completes_job(client, monkeypatch):
    """A source that raises with a typed scraper code is recorded and the job
    still completes."""
    from backend.scraper.errors import RateLimited

    def _raising(url, options=None, progress_cb=None, cancel_event=None):
        raise RateLimited("simulated rate limit")

    install_fake_scraper(monkeypatch, result_factory=_raising)
    job_id = _start(client, urls=[PAGE_URL])
    final = wait_for_job(client, job_id)
    assert final["status"] == "completed"
    assert final["errors"] >= 1
    codes = {e["code"] for e in final["error_details"]}
    assert "rate_limited" in codes


def test_source_result_errors_recorded_job_completes(client, monkeypatch):
    """Per-source errors reported inside a SourceResult must be persisted and
    counted; the job still completes.  (Currently FAIL — see bug report.)"""
    posts = sample_posts(2)
    install_fake_scraper(
        monkeypatch,
        results=[
            make_source_result(
                PAGE_URL,
                posts=posts,
                stats={"posts_discovered": 2, "posts_extracted": 2,
                       "duplicates_removed": 0, "posts_skipped": 0,
                       "posts_failed": 1},
                errors=[
                    {
                        "post_url": "https://www.facebook.com/example/posts/1",
                        "code": "extraction_failure",
                        "message": "could not normalize a container",
                    }
                ],
            )
        ],
    )
    job_id = _start(client)
    final = wait_for_job(client, job_id)
    assert final["status"] == "completed"
    assert final["errors"] == 1
    assert final["error_details"][0]["code"] == "extraction_failure"
    assert final["error_details"][0]["post_url"]
    assert final["posts_failed"] == 1


def test_cancellation_blocks_then_delete_204_404(client, monkeypatch):
    """A scraper that blocks on the cancel_event: DELETE returns 204 and the
    job is gone afterwards.  The DELETE route waits for the worker, so by the
    time 204 is returned the rows are gone (best-effort cancellation)."""
    install_fake_scraper(
        monkeypatch, result_factory=blocking_scraper(None)
    )
    job_id = _start(client)
    # give the worker time to enter the blocking scraper
    time.sleep(0.3)
    resp = client.delete(f"/api/jobs/{job_id}")
    assert resp.status_code == 204, resp.text
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert client.get(f"/api/jobs/{job_id}/posts").status_code == 404