# PostHarvest — Documentation

Deep, single-topic guides for operating, understanding and contributing to
PostHarvest. The README gives you the 2-minute orientation; these files are the
long-form reference.

| Guide | What it covers |
|---|---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Backend layout, job model, database schema, scraper internals |
| [API.md](./API.md) | Full HTTP API reference (endpoints, payloads, errors, pagination) |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Running on Docker (dev + prod), env files, Makefile, VPS/TLS plan |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | Setup, tests, CI, branch flow, review process |

Project-level decisions (product + infra, with rationale) are recorded in
[DECISIONS.md](../DECISIONS.md); the phased roadmap lives in
[ROADMAP.md](../ROADMAP.md); the compliance / permitted-use statement is in
[COMPLIANCE.md](../COMPLIANCE.md).

> Prefer clickable docs? Run the stack and open `/docs` (Swagger UI) at
> `http://localhost:8000/docs`, or the in-app help via the frontend **Docs**
> sidebar item.