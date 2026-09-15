"""PostHarvest — backend package.

Package layout:
    backend.main          FastAPI application entry point (uvicorn backend.main:app)
    backend.api           HTTP route modules (scrape, jobs, exports, health)
    backend.core          config, database, logging, exceptions, job manager
    backend.models        SQLAlchemy ORM models (scrape_jobs, sources, posts,
                          engagement_metrics, media, export_jobs, errors)
    backend.schemas       Pydantic request/response models
    backend.services      job orchestration + stats aggregation
    backend.scraper       scraping engine (owned by SA02, consumed here)
    backend.exporters     export writers (owned by SA03, called from services)
"""

__version__ = "1.0.0"