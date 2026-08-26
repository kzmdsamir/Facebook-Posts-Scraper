"""Database engine, session factory and declarative base.

Storage strategy
----------------
* SQLite by default (``sqlite:///./data/facebook_scraper.db``) — the ``data/``
  directory is created automatically on startup.
* PostgreSQL is a runtime switch: set ``DATABASE_URL`` to a
  ``postgresql+psycopg://...`` DSN (install ``psycopg[binary]`` separately;
  see requirements.txt). No application code changes required.
* ``:memory:`` databases are given a static pool so background worker threads
  share one connection (useful for the test suite).
* For SQLite, ``PRAGMA foreign_keys=ON`` guarantees ON DELETE CASCADE works,
  and WAL mode allows reading while the worker thread writes.

Sessions
--------
Routes receive a request-scoped session via the ``get_db`` dependency; the
background job worker opens its own short-lived sessions (one per source and
per progress ping) so a long-scraping source never holds a transaction open.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


def _build_engine() -> Engine:
    settings = get_settings()
    url = settings.database_url.strip()
    kwargs: dict = {"pool_pre_ping": True}

    if url.startswith("sqlite"):
        # check_same_thread=False: FastAPI's threadpool and the background
        # worker threads both open sessions.
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if ":memory:" in url:
            # One shared connection across all threads so in-memory databases
            # behave consistently in the test suite.
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool
        elif url.startswith("sqlite:///"):
            raw_path = url[len("sqlite:///") :]
            if raw_path:
                Path(raw_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    elif url.startswith("postgresql"):
        kwargs.update({"pool_size": 10, "max_overflow": 20})
    elif url.startswith("mysql"):
        kwargs.update({"pool_size": 10, "max_overflow": 20})

    return create_engine(url, **kwargs)


engine = _build_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
    """Per-connection pragmas for SQLite (foreign keys + WAL + busy timeout)."""
    if engine.dialect.name != "sqlite":
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


def init_db() -> None:
    """Create all tables if they do not exist.

    Alembic migrations are optional for this project; create_all is the
    documented simple path. Importing ``backend.models`` registers every model
    on ``Base.metadata``.
    """
    from backend import models  # noqa: F401  (side effect: register models)

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency yielding a request-scoped session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()