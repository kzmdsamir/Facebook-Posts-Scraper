"""Group 7 — error handling paths.

* Per-post error entries are recorded while the job still completes.
  (Currently FAIL for the API path — see bug report.)
* Export of an unknown job -> 404; scraper_unavailable -> POST 503.
* Error-envelope shape on every failure path.
"""
from __future__ import annotations

import sys
import types

from helpers import (
    PAGE_URL,
    error_envelope,
    install_fake_scraper,
    make_source_result,
    sample_posts,
    wait_for_job,
)


def test_per_post_errors_recorded_and_job_completes(client, monkeypatch):
    """One good post + one post-error entry: job completes with errors==1 and
    the entry surfaced in error_details.  (Currently FAIL — see bug report:
    SourceResult.errors are dropped by job_service.)"""
    posts = sample_posts(1)
    install_fake_scraper(
        monkeypatch,
        results=[
            make_source_result(
                PAGE_URL,
                posts=posts,
                stats={
                    "posts_discovered": 2,
                    "posts_extracted": 1,
                    "duplicates_removed": 0,
                    "posts_skipped": 0,
                    "posts_failed": 1,
                },
                errors=[
                    {
                        "post_url": "https://www.facebook.com/example/posts/999",
                        "code": "extraction_failure",
                        "message": "container could not be normalized",
                    }
                ],
            )
        ],
    )
    resp = client.post(
        "/api/scrape", json={"urls": [PAGE_URL], "post_type": "text"}
    )
    assert resp.status_code == 201
    job_id = resp.json()["job_id"]
    final = wait_for_job(client, job_id)
    assert final["status"] == "completed"
    assert final["errors"] == 1, f"errors not counted: {final}"
    assert final["posts_failed"] == 1
    assert final["error_details"][0]["code"] == "extraction_failure"
    assert final["error_details"][0]["post_url"]


def test_scraper_unavailable_returns_503(client, monkeypatch):
    """backend.scraper missing its required symbols -> POST /api/scrape 503
    with the scraper_unavailable envelope.  Done by replacing the module in
    sys.modules (the app lazily imports it at call time)."""
    fake = types.ModuleType("backend.scraper")
    fake.__file__ = "<phantom>"
    fake.__package__ = "backend"

    import backend as backend_pkg

    monkeypatch.setitem(sys.modules, "backend.scraper", fake)
    monkeypatch.setattr(backend_pkg, "scraper", fake, raising=False)

    resp = client.post(
        "/api/scrape", json={"urls": [PAGE_URL], "post_type": "text"}
    )
    assert resp.status_code == 503, f"expected 503, got {resp.status_code}: {resp.text}"
    err = error_envelope(resp.json())
    assert err["code"] == "scraper_unavailable"


def test_export_unknown_job_404_envelope(client):
    resp = client.get("/api/jobs/ghost/export/json")
    assert resp.status_code == 404
    err = error_envelope(resp.json())
    assert err["code"] == "not_found"


def test_validation_errors_are_json_envelopes(client):
    # malformed JSON body -> FastAPI 400 shim with the envelope
    resp = client.post(
        "/api/scrape", content=b"{not json", headers={"content-type": "application/json"}
    )
    assert resp.status_code == 400
    error_envelope(resp.json())


def test_jobs_get_errors_shown_in_status(client, monkeypatch):
    install_fake_scraper(
        monkeypatch,
        results=[make_source_result(PAGE_URL, posts=sample_posts(1))],
    )
    resp = client.post(
        "/api/scrape",
        json={"urls": [PAGE_URL, "https://example.com/not-facebook"], "post_type": "text"},
    )
    job_id = resp.json()["job_id"]
    final = wait_for_job(client, job_id)
    # the invalid submitted URL is a validation-time error row
    codes = {e["code"] for e in final["error_details"]}
    assert "invalid_url" in codes
    assert final["errors"] >= 1