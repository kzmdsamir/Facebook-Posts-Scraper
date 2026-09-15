---
name: zola
description: >-
  Build and maintain the Open Free Books static site with Zola (Tera templates,
  Sass, content/, data/, theme) and Solid.js frontend. Use when editing zola.toml,
  content/, themes/openfreebooks/templates/, Sass, static assets, frontend/src/,
  bundle.js, or running zola build/serve.
---

# Zola (Open Free Books)

Static site: **Zola** + custom theme `openfreebooks`. Output goes to `public/` (gitignored). Deploy via Wrangler from `public/`.

## Layout

| Path | Role |
|------|------|
| `zola.toml` | Site config, `[extra]` URLs for templates |
| `content/` | Pages (`*.md` + front matter, `template = "…"`) |
| `data/` | JSON for `load_data()` (contributors, credits) |
| `static/` | Copied to site root (`favicons`, `icons/`, etc.) |
| `themes/openfreebooks/templates/` | Tera HTML, partials, macros |
| `themes/openfreebooks/sass/` | Source styles → compiled `public/main.css` |
| `themes/openfreebooks/static/js/` | Vite output: `bundle.js` (site chrome) + lazy chunks (e.g. `catalog-mermaid-view-*.js`) |

See [reference.md](reference.md) for Tera pitfalls and build checks.

## Commands

```bash
bun run dev            # instant serve (zola only)
bun run build:chapter math/loci math/measures-dispersion
bun run build:chapter math/*      # wildcard chapter builds
bun run build:chapter             # auto-detect changed chapters (interactive confirm)
bun run build:site                # full site rebuild (includes sponsor sync when token exists)
bun run build                     # alias of build:site
bun test
```

After Sass or template changes, run `zola build` (or `zola serve`). Do **not** copy `public/` into `themes/openfreebooks/static/`.

### Build mode behavior

- **Chapter workflow:** prefer `build:chapter` for normal content work; it rebuilds chapter assets and only runs Vite when frontend/site-shell code changes.
- **Site workflow:** use `build:site`/`build` for full rebuilds and release verification.
- **CI:** use `bun run build:site` and `bun test`.

**Search (Pagefind):** read [zola-pagefind.md](zola-pagefind.md) before changing search UI, indexing, or `data-pagefind-*` attributes.

## Templates (Tera)

- Extend `base.html`; use `{% block content %}` for page bodies.
- **`{% import "macros/….html" as ns %}`** only in templates that **extend** a layout (e.g. `index.html`), **not** inside `{% include %}` partials.
- Macro calls use **keyword arguments**: `{{ ns::macro_name(arg=value) }}`.
- Prefer **partials** under `templates/partials/`; kebab-case filenames.
- Icons: Tabler SVGs in `static/icons/social/`; inline copies in `templates/partials/icons/social/*.html` included from `macros/social-icons.html`.

## Data files

```tera
{% set data = load_data(path="data/contributors.json", format="json") %}
```

On Zola 0.22+, use the `data/…` path (not bare `contributors.json` at repo root).

## New page checklist

1. Add `content/your-page.md` with `title`, `template = "your-template.html"`.
2. Add `themes/openfreebooks/templates/your-template.html` extending `base.html`.
3. Add Sass in `themes/openfreebooks/sass/` and `@import` in `main.scss`.
4. Wire footer/nav URLs in `zola.toml` `[extra]` if needed.

## Styling

- No inline Tailwind; use Sass partials and `class=""` on elements.
- Design tokens in `_tokens.scss`; section patterns in `_components.scss`, `_why-sections.scss`, etc.
- Grain overlay and dark mode via `data-theme` + CSS variables.

## Solid.js

Client behavior lives in `frontend/` and mounts from `base.html`:

| Entry | Mount | Notes |
|-------|--------|--------|
| `js/bundle.js` | `main.tsx` | Header, theme, homepage, chapter widgets |
| `#catalog-app` on `/catalog/` | `catalog-app.tsx` in bundle | List / Map / Compare; Map lazy-loads `catalog-mermaid-view` |

**When changing `frontend/` or adding interactivity**, read [zola-solid.md](zola-solid.md) before editing JS.

**When changing the catalog page, map, or compare doc**, read [zola-catalog.md](zola-catalog.md).

### Search (Pagefind)

- Runs after `zola build`; indexes **live chapter pages** only (`data-pagefind-body` on chapter template).
- UI: global modal (⌘K) + `/search/` page. See [zola-pagefind.md](zola-pagefind.md).

### Catalog page

- `content/catalog.md` → `template = "catalog.html"`
- `templates/catalog.html` — `#catalog-app`, `#catalog-data` JSON, `<template id="catalog-compare-template">` (math compare partial)
- Views: list (default), `?view=tree` (Mermaid DAG map), `?view=compare` (math curricula doc)
- Map colors: Mermaid `theme: "base"` + hex `themeVariables` in `frontend/src/lib/catalog-mermaid-theme.ts` — **not** Sass `fill` on cluster rects (inline SVG wins)
- Full file map, strand header post-render, and verify steps: [zola-catalog.md](zola-catalog.md)
- Run `bun run build:js` after any `frontend/src/components/catalog-*` or `frontend/src/lib/catalog-*` change

## Verify

```bash
bun run build
```

Confirm `public/main.css` contains new selectors (no stale `themes/openfreebooks/static/main.css` overriding compile). Confirm HTML under `public/` matches templates, not an old `themes/openfreebooks/static/index.html`.
