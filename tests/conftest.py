"""Shared pytest fixtures for the Facebook Posts Scraper test suite.

ORDER MATTERS — read before editing:

1. ``sys.path`` is modified FIRST so ``backend`` is importable no matter what
   working directory pytest is launched from.
2. ``DATABASE_URL`` / ``EXPORT_BASE_DIR`` / ``DATA_DIR`` /
   ``CANCEL_WAIT_SECONDS`` are set as environment variables BEFORE any
   ``backend.*`` module is imported.  The SQLAlchemy engine
   (``backend.core.database``) and the pydantic-settings singleton
   (``backend.core.config.get_settings``) are built exactly once per process,
   at first import — pointing them at a throw-away temp directory keeps the
   suite hermetic (no writes into the repository, no ``data/`` pollution).
3. A SINGLE session-scoped :class:`fastapi.testclient.TestClient` is shared by
   every test.  A TestClient triggers the FastAPI lifespan (``init_db()`` on
   enter, ``JobManager.get().shutdown()`` on exit) every time it is used as a
   context manager, and a :class:`ThreadPoolExecutor` cannot be restarted
   after ``shutdown()`` — creating more than one TestClient per process would
   leave the job manager permanently unable to schedule workers.
4. Rows are wiped between tests by an autouse fixture (children before
   parents, FK-safe) so tests are isolated while sharing one file DB.

Networking rule: tests NEVER hit the real network.  Every test that starts a
background job installs a fake ``backend.scraper.scrape_source`` (see
``helpers.install_fake_scraper``) and waits for the job to reach a terminal
state before returning, so no worker thread can outlive the monkeypatch.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. sys.path + hermetic environment (before ANY backend import)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_SESSION_TMP = Path(tempfile.mkdtemp(prefix="fbscraper_tests_"))
_SESSION_TMP.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = "sqlite:///" + (_SESSION_TMP / "test.db").as_posix()
os.environ["EXPORT_BASE_DIR"] = str(_SESSION_TMP / "exports")
os.environ["DATA_DIR"] = str(_SESSION_TMP / "data")
os.environ["CANCEL_WAIT_SECONDS"] = "2"  # keep DELETE/cancellation tests fast

import pytest  # noqa: E402

# Imported here so the smoke-check below runs at collection time.
import backend.scraper  # noqa: E402, F401


def _check_environment() -> None:
    """Fail fast with a clear message when the suite is misconfigured."""
    from backend.core.config import get_settings

    s = get_settings()
    assert _SESSION_TMP.as_posix() in s.database_url, "DATABASE_URL did not take effect"
    assert s.cancel_wait_seconds == 2.0, "CANCEL_WAIT_SECONDS did not take effect"


_check_environment()

# Deletion order: children before parents (SQLite FK pragma is ON).
_CLEANUP_MODELS = (
    "ExportJob",
    "ScrapeError",
    "Media",
    "EngagementMetric",
    "Post",
    "ScrapeSource",
    "ScrapeJob",
)


@pytest.fixture(scope="session")
def client():
    """One TestClient for the whole session (see module docstring, note 3)."""
    from backend.main import create_app
    from fastapi.testclient import TestClient

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_database():
    """Wipe every table between tests for deterministic isolation."""
    yield
    from sqlalchemy import delete

    from backend import models as m
    from backend.core.database import SessionLocal

    with SessionLocal() as db:
        for name in _CLEANUP_MODELS:
            db.execute(delete(getattr(m, name)))
        db.commit()