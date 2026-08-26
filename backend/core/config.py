"""Application configuration loaded from environment variables.

Every field can be overridden with an environment variable of the same name
(case-insensitive). Examples:

    DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/fb_scraper
    CORS_ORIGINS='["http://localhost:3000","http://127.0.0.1:3000"]'   # JSON list
    DEBUG=true
    WORKER_THREADS=8
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- application ----------------------------------------------------------
    app_name: str = "Facebook Posts Scraper API"
    version: str = "1.0.0"
    debug: bool = False
    api_prefix: str = "/api"

    # --- storage --------------------------------------------------------------
    # Defaults to a local SQLite file created under ./data.
    # For PostgreSQL, switch DATABASE_URL to a connection string such as
    # postgresql+psycopg://user:pass@host:5432/dbname (requires the
    # psycopg / psycopg[binary] package — see requirements.txt comments).
    # No code changes are needed: the engine is built from this value and
    # all models use portable SQLAlchemy types / JSON columns.
    database_url: str = "sqlite:///./data/facebook_scraper.db"
    data_dir: str = "./data"
    export_base_dir: str = "./data/exports"

    # --- worker / job manager ---------------------------------------------------
    worker_threads: int = 4
    max_urls_per_job: int = 100
    default_max_posts: int | None = None
    default_post_type: str = "all"
    # How long DELETE /api/jobs/{id} waits for the background worker to stop
    # before deleting the rows (best-effort cancellation).
    cancel_wait_seconds: float = 5.0

    # --- HTTP -------------------------------------------------------------------
    # Comma-free JSON array; e.g. CORS_ORIGINS='["http://localhost:3000"]'
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # --- pagination --------------------------------------------------------------
    page_size_default: int = 50
    page_size_max: int = 200

    # --- rate limiting / proxy (Phase 14-16) ------------------------------------
    scraper_delay_seconds: float = 2.5
    scraper_timeout_seconds: float = 20.0
    scraper_max_retries: int = 3
    scraper_robots: bool = True

    # --- proxy support (optional) -----------------------------------------------
    proxy_enabled: bool = False
    proxy_url: str | None = None
    proxy_urls: list[str] = []

    # --- logging ----------------------------------------------------------------
    log_level: str = "INFO"
    log_format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    def ensure_dirs(self) -> None:
        """Create runtime directories (data/, exports/)."""
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.export_base_dir).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton (cached)."""
    return Settings()