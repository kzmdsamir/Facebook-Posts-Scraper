# syntax=docker/dockerfile:1
#
# Facebook Posts Scraper — single Dockerfile, two build targets.
#
#   Backend image:   docker build --target backend  -t fb-posts-scraper-backend  .
#   Frontend image:  docker build --target frontend -t fb-posts-scraper-frontend .
#
# docker-compose.yml builds both images from this file via `target:`.
#
# Notes
# -----
# * The frontend target produces a Next.js 14 **standalone** server
#   (`output: "standalone"` is already set in frontend/next.config.mjs), so the
#   runtime image is tiny and contains no source tree or node_modules beyond
#   the minimised production bundle Next emits.
# * NEXT_PUBLIC_* variables are inlined by Next.js at BUILD time — changing
#   the API URL requires a rebuild (see README "Configuration").
# * The backend runs as a non-root user (uid 10001). On Linux hosts, make the
#   bind-mounted `./data` directory writable by that uid (see README).
#
# Build order in docker-compose:
#   backend  -> target `backend`  (python:3.13-slim, FastAPI on :8000)
#   frontend -> target `frontend` (node:20-alpine, Next.js on :3000)

# =====================================================================
# STAGE: frontend-build — compile the Next.js app (build-time only)
# =====================================================================
FROM node:20-alpine AS frontend-build
WORKDIR /app

# NEXT_PUBLIC_API_URL is inlined by Next.js at build time.
# docker-compose passes it via build.args; the default matches local dev.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_TELEMETRY_DISABLED=1

# No package-lock.json is committed yet, so use `npm install`
# (`npm ci` requires a lockfile — regenerate one with `npm install` locally
# and commit it to make builds reproducible).
#
# Sources are copied path-by-path (no .dockerignore is shipped yet, so an
# unqualified `COPY frontend/ ./` could sweep in local node_modules / .env).
# If you add new top-level folders under frontend/, list them here — or add
# a .dockerignore and switch back to `COPY frontend/ ./`.
COPY frontend/package.json frontend/tsconfig.json frontend/next-env.d.ts \
     frontend/next.config.mjs frontend/postcss.config.mjs \
     frontend/tailwind.config.ts frontend/.eslintrc.json ./
RUN npm install

COPY frontend/app ./app
COPY frontend/components ./components
COPY frontend/lib ./lib
COPY frontend/public ./public
RUN npm run build

# =====================================================================
# STAGE: frontend — self-contained standalone runtime (Node 20)
# =====================================================================
FROM node:20-alpine AS frontend
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

# Standalone output bundles server.js plus a minimal node_modules.
COPY --from=frontend-build --chown=node:node /app/.next/standalone ./
# Static assets and public files must sit next to the standalone root.
COPY --from=frontend-build --chown=node:node /app/.next/static ./.next/static
COPY --from=frontend-build --chown=node:node /app/public ./public

USER node
EXPOSE 3000
CMD ["node", "server.js"]

# =====================================================================
# STAGE: backend — FastAPI + scraper + exporters (Python 3.13)
# =====================================================================
FROM python:3.13-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# `useradd` lives in the `passwd` package, which is NOT present in slim
# images. Everything else in the toolchain (lxml wheels etc.) is prebuilt,
# so no build-essential is required.
RUN apt-get update \
    && apt-get install -y --no-install-recommends passwd \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

# Install pinned dependencies first (stable layer for caching).
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install -r backend/requirements.txt

# Ship the application package (uvicorn imports `backend.main:app` from /app).
# Copied path-by-path for the same no-.dockerignore reason as the frontend
# (avoids local __pycache__ / .pyc / stray files). Add new backend subpackages
# here, or ship a .dockerignore and use `COPY backend/ ./backend/`.
COPY --chown=appuser:appuser backend/__init__.py backend/main.py ./backend/
COPY --chown=appuser:appuser backend/api backend/core backend/models \
     backend/schemas backend/services ./backend/
COPY --chown=appuser:appuser backend/scraper backend/exporters ./backend/

# Runtime data directory. `Settings.ensure_dirs()` also creates it on
# startup, but we pre-create + pre-chown it so the non-root user can write
# even when the volume is mounted as root-owned on Linux hosts.
RUN mkdir -p /app/data && chown appuser:appuser /app/data

USER appuser
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]