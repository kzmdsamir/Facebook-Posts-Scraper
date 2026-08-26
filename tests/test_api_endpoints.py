"""Group 5 — API endpoint contracts (POST /api/scrape, GET /api/jobs/...).

Request/response shape tests: 201 {job_id, status:queued}, 400 invalid URL
envelope, 422 validation errors (spec §17), 404 unknown job, DELETE 204 ->
404, GET /api/health.  Pagination is tested against jobs seeded directly
through the models; "full mocked scrape" correctness lives in
test_job_state_machine.py.
"""
from __future__ import annotations

import time

from helpers import (
    PAGE_URL,
    error_envelope,
    insert_completed_job,
    install_fake_scraper,
    make_source_result,
    sample_posts,
    wait_for_job,
)

VALID_URLS = ["https://www.facebook.com/example"]


def test_health_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_scrape_valid_returns_201_queued(client, monkeypatch):
    install_fake_scraper(
        monkeypatch,
        results=[make_source_result(PAGE_URL, posts=sample_posts(1))],
    )
    resp = client.post(
        "/api/scrape", json={"urls": VALID_URLS, "post_type": "text"}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert isinstance(body["job_id"], str) and body["job_id"]
    # let the worker finish so nothing leaks past the monkeypatch
    wait_for_job(client, body["job_id"])


def test_scrape_invalid_urls_400_envelope(client):
    resp = client.post("/api/scrape", json={"urls": ["not a url"]})
    assert resp.status_code == 400
    err = error_envelope(resp.json())
    assert err["code"] == "invalid_input"
    assert err["message"]


def test_scrape_empty_urls_rejected(client):
    for payload in ({"urls": []}, {"urls": ["   "]}):
        resp = client.post("/api/scrape", json=payload)
        assert resp.status_code == 400, f"payload {payload!r} accepted?!"
        error_envelope(resp.json())


def test_scrape_partially_invalid_records_error(client, monkeypatch):
    install_fake_scraper(
        monkeypatch,
        results=[make_source_result(PAGE_URL, posts=sample_posts(1))],
    )
    resp = client.post(
        "/api/scrape",
        json={
            "urls": [PAGE_URL, "https://example.com/not-facebook"],
            "post_type": "text",
        },
    )
    assert resp.status_code == 201, resp.text
    job_id = resp.json()["job_id"]
    final = wait_for_job(client, job_id)
    assert final["errors"] >= 1
    codes = {e["code"] for e in final["error_details"]}
    assert "invalid_url" in codes
    assert final["pages_total"] == 1


def test_scrape_bad_date_returns_400(client):
    """Spec §17: bad dates -> 400 (app error envelope convention)."""
    resp = client.post(
        "/api/scrape",
        json={"urls": VALID_URLS, "start_date": "01/08/2026"},
    )
    assert resp.status_code == 400, (
        f"expected 400 for malformed ISO date, got {resp.status_code}: {resp.text}"
    )
    error_envelope(resp.json())


def test_scrape_bad_end_date_order_returns_400(client):
    resp = client.post(
        "/api/scrape",
        json={"urls": VALID_URLS, "start_date": "2026-09-01", "end_date": "2026-01-01"},
    )
    assert resp.status_code == 400, (
        f"expected 400 for start>end, got {resp.status_code}: {resp.text}"
    )
    error_envelope(resp.json())


def test_scrape_bad_post_type_returns_400(client):
    resp = client.post(
        "/api/scrape",
        json={"urls": VALID_URLS, "post_type": "gif"},
    )
    assert resp.status_code == 400, (
        f"expected 400 for unknown post_type, got {resp.status_code}: {resp.text}"
    )
    error_envelope(resp.json())


def test_scrape_max_posts_bounds_400(client):
    resp = client.post("/api/scrape", json={"urls": VALID_URLS, "max_posts": 0})
    assert resp.status_code == 400, (
        f"expected 400 for max_posts=0, got {resp.status_code}: {resp.text}"
    )


def test_scrape_missing_urls_field_400(client):
    resp = client.post("/api/scrape", json={})
    assert resp.status_code == 400
    err = error_envelope(resp.json())
    assert err["code"] == "validation_error"


def test_get_unknown_job_404(client):
    resp = client.get("/api/jobs/definitely-not-a-job")
    assert resp.status_code == 404
    err = error_envelope(resp.json())
    assert err["code"] == "not_found"


def test_job_status_shape_when_inserted_directly(client):
    job_id = insert_completed_job(sample_posts(2), pages_total=1, pages_completed=1)
    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == job_id
    assert body["status"] == "completed"
    assert body["pages_total"] == 1
    assert body["pages_completed"] == 1
    assert body["posts_processed"] == 2
    assert body["posts_found"] == 2
    assert body["duplicates"] == 0
    assert "error_details" in body


def test_posts_pagination(client):
    posts = sample_posts(5)
    job_id = insert_completed_job(posts)

    r1 = client.get(f"/api/jobs/{job_id}/posts?page=1&page_size=2")
    assert r1.status_code == 200, r1.text
    b1 = r1.json()
    assert b1["total"] == 5
    assert b1["page"] == 1
    assert b1["page_size"] == 2
    assert len(b1["items"]) == 2

    r2 = client.get(f"/api/jobs/{job_id}/posts?page=3&page_size=2")
    b2 = r2.json()
    assert len(b2["items"]) == 1
    assert b2["total"] == 5

    # newest first by published_at (2026-08-03 > 08-02 > 08-01 ...)
    assert b1["items"][0]["published_at"] > b1["items"][1]["published_at"]

    r3 = client.get(f"/api/jobs/{job_id}/posts?page=99&page_size=2")
    assert r3.json()["items"] == []


def test_posts_pagination_defaults_and_caps(client):
    job_id = insert_completed_job(sample_posts(3))
    resp = client.get(f"/api/jobs/{job_id}/posts")
    body = resp.json()
    assert body["page"] == 1 and body["page_size"] == 50
    assert len(body["items"]) == 3

    # page_size > 200 is clamped/rejected by the API (max 200)
    resp200 = client.get(f"/api/jobs/{job_id}/posts?page_size=500")
    assert resp200.status_code == 400  # FastAPI Query le=200 -> validation error
    error_envelope(resp200.json())


def test_posts_unknown_job_404(client):
    resp = client.get("/api/jobs/nope/posts")
    assert resp.status_code == 404
    error_envelope(resp.json())


def test_stats_bonus_endpoint(client):
    job_id = insert_completed_job(sample_posts(3))
    resp = client.get(f"/api/jobs/{job_id}/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_posts"] == 3
    assert body["total_likes"] == 36  # 12 per post
    assert body["post_type_counts"]["text"] == 1
    assert body["post_type_counts"]["image"] == 1
    assert body["post_type_counts"]["video"] == 1


def test_delete_job_204_then_404(client, monkeypatch):
    install_fake_scraper(
        monkeypatch,
        results=[make_source_result(PAGE_URL, posts=sample_posts(1))],
    )
    resp = client.post(
        "/api/scrape", json={"urls": VALID_URLS, "post_type": "text"}
    )
    job_id = resp.json()["job_id"]
    wait_for_job(client, job_id)  # finish first -> deterministic delete

    resp_delete = client.delete(f"/api/jobs/{job_id}")
    assert resp_delete.status_code == 204, resp_delete.text
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert client.get(f"/api/jobs/{job_id}/posts").status_code == 404


def test_delete_unknown_job_404(client):
    resp = client.delete("/api/jobs/ghost")
    assert resp.status_code == 404
    error_envelope(resp.json())