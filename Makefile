# ============================================================================
# PostHarvest — developer Makefile
# ============================================================================
# One entry point for everything: Docker (dev+prod), local servers, CLI,
# tests, lint, typecheck.
#
# Docker commands run from docker/ (compose project dir — see DECISIONS.md D6).
# The root .env is for local CLI/tests; compose reads docker/.env.
# ============================================================================
SHELL := /bin/bash
.DEFAULT_GOAL := help

DOCKER := docker compose
PROD_FLAGS := -f docker-compose.yml -f docker-compose.prod.yml
PROD_DIR := docker

PY := python
PIP := python -m pip
UVICORN := python -m uvicorn

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort -k1,1 \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'


# ============================================================================
# Docker — dev stack (backend :8000, frontend :3000, postgres, hot reload)
# ============================================================================

dev: ## Start the dev stack (compose from docker/)
	cd $(PROD_DIR) && $(DOCKER) up

dev-up: ## Start dev stack in the background
	cd $(PROD_DIR) && $(DOCKER) up -d

dev-down: ## Stop dev stack (keeps images/volumes)
	cd $(PROD_DIR) && $(DOCKER) down

dev-build: ## Rebuild dev images and start
	cd $(PROD_DIR) && $(DOCKER) up -d --build

dev-logs: ## Follow dev stack logs
	cd $(PROD_DIR) && $(DOCKER) logs -f

dev-ps: ## List dev stack containers
	cd $(PROD_DIR) && $(DOCKER) ps


# ============================================================================
# Docker — production stack (nginx :80/:443 + hardened prod layer)
# ============================================================================

prod-up: ## Start the production stack (nginx, frontend, backend, postgres)
	cd $(PROD_DIR) && $(DOCKER) $(PROD_FLAGS) --profile prod up -d

prod-build: ## Rebuild prod images and start
	cd $(PROD_DIR) && $(DOCKER) $(PROD_FLAGS) --profile prod up -d --build

prod-down: ## Stop the production stack
	cd $(PROD_DIR) && $(DOCKER) $(PROD_FLAGS) --profile prod down

prod-restart: ## Restart production containers (no rebuild)
	cd $(PROD_DIR) && $(DOCKER) $(PROD_FLAGS) --profile prod restart

prod-logs: ## Follow prod stack logs
	cd $(PROD_DIR) && $(DOCKER) $(PROD_FLAGS) --profile prod logs -f

prod-ps: ## List prod stack containers
	cd $(PROD_DIR) && $(DOCKER) $(PROD_FLAGS) --profile prod ps

prod-health: ## Hit the prod health endpoint via nginx
	curl -fsS http://localhost/api/health && echo


# ============================================================================
# Python / backend (host, outside Docker)
# ============================================================================

backend-install: ## Install backend requirements into the current interpreter
	$(PIP) install -r backend/requirements.txt

backend-dev: ## Run uvicorn with reload against local code (cwd backend)
	$(UVICORN) backend.main:app --reload --reload-dir backend --host 127.0.0.1 --port 8000

backend-start: ## Run uvicorn (no reload) against local code
	$(UVICORN) backend.main:app --host 127.0.0.1 --port 8000


# ============================================================================
# CLI (host, outside Docker)
# ============================================================================

cli: ## Show CLI help
	$(PY) cli.py --help

cli-accounts: ## List saved Facebook accounts
	$(PY) cli.py accounts

cli-login: ## Open browser to log into Facebook (option: ACCOUNT=myaccount)
	$(PY) cli.py login --account $(ACCOUNT)

cli-scrape: ## Scrape posts (e.g. URL=https://facebook.com/x --browser MAXX=20 EXPORT=xlsx OUT=posts.xlsx)
	$(PY) cli.py scrape $(URL) $(if $(BROWSER),--browser ,)$(if $(MAXX),--max-posts $(MAXX) ,)$(if $(EXPORT),--export $(EXPORT) ,)$(if $(OUT),--output $(OUT) ,)


# ============================================================================
# Frontend (host, outside Docker)
# ============================================================================

frontend-install: ## Install frontend dependencies (npm ci)
	cd frontend && npm ci

frontend-dev: ## Next.js dev server (hot reload, http://localhost:3000)
	cd frontend && npm run dev

frontend-build: ## Production build
	cd frontend && npm run build

frontend-start: ## Serve a production build (port 3000)
	cd frontend && npm run start


# ============================================================================
# Tests & checks
# ============================================================================

test: ## Backend test suite (pytest, includes CLI + scraper)
	$(PY) -m pytest tests/ -v --tb=short

test-frontend: ## Frontend unit tests (vitest)
	cd frontend && npm run test

test-all: test test-frontend ## Run backend + frontend tests

lint: ## Backend lint (if configured) + frontend eslint
	cd frontend && npm run lint

lint-ff: ## Frontend fast lint (oxlint)
	cd frontend && npm run lint:ox

typecheck: ## Frontend TypeScript check
	cd frontend && npx tsc --noEmit


# ============================================================================
# Install everything (host tools)
# ============================================================================

install: backend-install frontend-install ## Install host backend + frontend deps

setup: install ## Alias for full host setup