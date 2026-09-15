---
name: ofb
description: >-
  Develop Open Free Books (OFB): Zola static site, catalog/curriculum JSON,
  HTML chapters, Solid.js, Mermaid catalog maps, Sass. Use when editing openfreebooks,
  adding subjects/chapters/curriculum, catalog, math content, or deploying to
  Cloudflare.
---

# Open Free Books (OFB)

Free, static, open-source textbooks. **Zola** + theme `openfreebooks` + **Solid.js** + **Bun/Vite**. Deploy: `public/` via Wrangler.

Read [spec.md](../../../spec.md) for product rules. Pair with [zola](../zola/SKILL.md) for template/Sass details.

## Architecture (mental model)

```text
data/catalog.json          → subject list + global curriculum filter chips
data/{subject}-curriculum.json → strands, chapters, curriculums[], graph.edges
content/{subject}/…        → Zola sections (chapter pages at /{subject}/{slug}/)
themes/…/partials/{subject}/ → chapter HTML bodies (not Markdown today)
frontend/                  → catalog-app, Mermaid map view, site chrome
/catalog/                  → browse UI (list + Mermaid map)
```

**Catalog is the subject index.** `/math/` redirects to `/catalog/?subject=math`. Do not revive a separate book index unless asked.

**Curriculum labels** appear only in catalog data (badges + filters), **never** in chapter page prose ([spec.md](../../../spec.md)).

## Commands

```bash
bun install
bun run dev                      # instant local serve (zola only)
bun run build:chapter math/measures-dispersion math/loci
bun run build:chapter math/*
bun run build:chapter   # auto-detect changed chapters (interactive confirm)
bun run build:site      # full rebuild (sync external data + all chapters + site)
bun run build           # alias of build:site
bun test
```

## Non-negotiables

| Rule | Detail |
|------|--------|
| Styling | Sass + `class=""` in templates/JSX — **no Tailwind** |
| React | Functional **Solid** only; mount via `main.tsx` |
| Theme static | **Only** commit `themes/openfreebooks/static/js/bundle.js` (+ fonts if any). **Never** commit `public/` or stale HTML under theme `static/` |
| Tera | Never name a loaded JSON variable `math` (reserved). Use `math_catalog`, etc. |
| Chapter URLs | `/{subjectId}/{chapter-slug}/` (e.g. `/math/quadratic-equations/`) |
| Map | Mermaid DAG view (`?view=tree`) driven by `graph.edges` |
| Graph | `graph.edges` must be **acyclic**; builder throws on cycles |
| Chart axes (all widgets) | Every coordinate chart must render **x/y axis labels, positive-direction arrowheads, and visible graduations (ticks + scale labels)**. Apply this consistently across all subjects/widgets. |
| Accessibility | Avoid decorative characters that may render as emoji on mobile. Prefer broadly supported symbols/text so desktop and mobile stay visually consistent. |
| Demo responsiveness (all widgets) | Mobile-first: keep demo viewport short, reserve stage/canvas height up front to avoid CLS, and never let status/controls overlap or block the interactive area. Use collapsible/toggle controls on small screens when needed. |

## Common tasks → where to edit

| Task | Files |
|------|--------|
| New global curriculum chip (e.g. GCSE) | `data/catalog.json` → `curriculums[]`; `_catalog.scss` badge; `frontend/src/lib/catalog-badge.ts`; rebuild |
| New subject (sidebar) | `data/catalog.json` → `subjects[]`; `data/{id}-curriculum.json` (catalog template auto-loads by `id`) |
| New chapter (planned) | `{subject}-curriculum.json` strand entry; optional `graph.edges` |
| New chapter (live) | Above + `content/{subject}/{slug}/_index.md` + HTML partial + `chapter.html` wiring + `main.tsx` widget mount if interactive |
| Sitemap/feed coverage | `scripts/generate-site-metadata.ts`, `static/sitemap.xml`, `static/feed.xml`, `package.json` build script |
| Homepage subject card | `themes/.../templates/index.html` (not yet data-driven) |
| Browse / nav URL | `zola.toml` `[extra] browse_url` + `base.html` site-config + `main.tsx` fallback |
| Search UI / index | `base.html` (Pagefind assets + modal), `content/search.md`, `_search.scss`; chapter/site builds refresh Pagefind |

## Sitemap / feed auto-generation

- `bun run generate:site-metadata` generates:
  - `static/sitemap.xml` (all user-facing built pages + live chapters)
  - `static/feed.xml` (RSS 2.0 for pages + live chapters)
- URL timestamps come from `git log -1` on content-source paths. If a page/chapter has no commit yet, generator falls back to filesystem mtime.
- Build pipeline runs this automatically before `zola build`.
- Include only resolvable pages; planned chapters without live content are excluded.

## Search (Pagefind)

| Piece | Path |
|-------|------|
| Global modal + assets | `themes/.../templates/base.html` |
| Dedicated page | `/search/` — `content/search.md`, `templates/search.html` |
| Header trigger | `frontend/src/components/site-header.tsx` (`pagefind-modal-trigger`) |
| Nav link | `main.tsx` + `zola.toml` `search_url` |
| Theming | `themes/.../sass/_search.scss` (`--pf-*` → site tokens) |

- **Component UI** only (`pagefind-component-ui.js`), not legacy `pagefind-ui.js`.
- Index runs **after** `zola build` in build commands (`build:chapter`/`build:site`).
- v1 indexes **live chapter pages only** (`data-pagefind-body` on `templates/chapter.html`); home, about, catalog, credits, and other site pages are excluded.

Detailed checklists: [curriculum-data.md](curriculum-data.md). Human-facing guide: [CONTRIBUTING.md](../../../CONTRIBUTING.md).

## Catalog / map

| Piece | Path |
|-------|------|
| Shell UI (subject, filters, list/map toggle) | `frontend/src/components/catalog-app.tsx` |
| Shared chapter card (list + map markup) | `frontend/src/components/catalog-chapter-card.tsx` |
| Map viewer (Mermaid) | `frontend/src/components/catalog-mermaid-view.tsx` (lazy chunk) |
| Mermaid source builder | `frontend/src/lib/catalog-to-mermaid.ts` |
| Mermaid theme (light/dark hex colors) | `frontend/src/lib/catalog-mermaid-theme.ts` |
| Theme-mode helpers used by map | `frontend/src/lib/catalog-canvas-theme.ts` |
| Curriculum badge CSS class map | `frontend/src/lib/catalog-badge.ts` |
| Types | `data/catalog.types.ts` |
| Styles | `themes/openfreebooks/sass/_catalog.scss` |

- Embedded data: `#catalog-data` in `templates/catalog.html` (merged at build time)
- URL: `/catalog/?subject=math` (list), `&view=tree` (map), `&view=compare` (math curricula doc — HTML partial `partials/math-curricula-compare.html`)

**List view:** full-card link for live chapters; number + title row on wide screens.

**Map view:** `CatalogMermaidView` renders a Mermaid DAG from `graph.edges`. Only live chapter titles become links; planned chapters are non-clickable.

**Map layout:** generated in `catalog-to-mermaid.ts` with strand subgraphs + edges from curriculum DAG data.

**Mermaid quirks:** use `theme: "base"` + hex `themeVariables`; Mermaid applies inline fills, so cluster fills are controlled in Mermaid config, not plain Sass overrides.

Prerequisites: **only** `graph.edges` (required, global DAG, cross-strand OK). Longest-path levels. No implicit strand-list chains. List order ≠ map order.

## Chapter content (colocated folder)

Live chapters live under `content/{subject}/{slug}/`:

1. `data/{subject}-curriculum.json` — catalog metadata (`status`, `curriculums`, `graph.edges`)
2. **Subject shared** (when a subject has multiple chapters): `content/{subject}/subject.scss` → `/css/subjects/{subject}.css`; `content/{subject}/subject.ts` → `initSubject()` via `frontend/src/generated/subject-modules.ts`. Math HTML conventions: [math-chapter-patterns.md](math-chapter-patterns.md).
3. `_index.md` — front matter only (`template = "chapter.html"`, `[extra] subject`, `chapter_id`, `strand`)
4. `core.html` (required), optional `supplement.html`, `assets/`, `widgets/*.tsx`, optional `chapter.scss` (chapter-only styles — do not duplicate subject.scss)
5. `bun run sync:chapters` merges HTML into `_index.md`, copies assets to `static/chapters/…`, compiles subject + chapter CSS, generates `chapter-widgets.ts` and `subject-modules.ts`, writes `data/_generated/subjects-meta.json`
6. `templates/chapter.html` loads subject CSS then chapter CSS; `main.tsx` runs subject init then mounts widgets

**Checkpoints (all subjects):** use `book-question`, `book-question__prompt`, `book-question__solution` (styled in theme `_book.scss`). Never use `book-question__answer`.

**Charts (all subjects):** coordinate charts in chapter widgets must include axis labels, arrowheads, and graduation/tick scale by default. Do not ship unlabeled axes.

**Math checkpoints / dots:** follow [math-chapter-patterns.md](math-chapter-patterns.md); shared dot classes in `content/math/subject.scss`.

**Math equation layout (all subjects):** for chained calculations, **always prefer multi-line KaTeX** and **always align at the equal sign** using `aligned` (e.g. `\begin{aligned} ... &= ... \\ ... \end{aligned}`). Do not write long one-line chains; aligned multi-line steps are the default for readability and mobile layout.

**Dialog/modals in widgets:** when adding a `<dialog>` in chapter widgets, use the shared modal pattern and classes from `themes/openfreebooks/sass/_contributors.scss` (`contributor-dialog`, `contributor-dialog-panel`, `contributor-dialog-close`) as the base style, keep the dialog centered in modal mode, and only layer minimal widget-specific overrides on top.

**Widget layout standards (all subjects):**
- Keep the primary demo stage visible without long pre-scroll on mobile.
- Reserve stage space from first render (`min-height`/fixed aspect) so hydration or assets do not shift nearby content.
- Keep feedback UI (step badges, status, toolbars) outside the canvas interaction area, or anchored so they never occlude controls/content.

### Interactive demo technology choices

Interactive demos can use different technologies based on the learning goal and interaction type:

- **Vanilla JavaScript / Solid widget**: default for lightweight chapter interactions and custom canvas/SVG behavior.
- **JSXGraph**: geometric constructions (points, lines, labeled angles, right-angle markers, draggable Euclidean figures).
- **Plotly.js**: data-heavy charts, coordinate plots, and quick interactive graphing.
- **D3**: custom data visualizations where fine-grained control over rendering/animation is needed.
- **three.js**: 3D scenes, spatial intuition demos, and rotation/perspective interactions.

Choose the simplest tool that satisfies the pedagogy, performance, and accessibility needs of the chapter.

Reference: `content/math/quadratic-equations/`.

## Verify before PR

```bash
bun run build
```

- `public/catalog/index.html` includes your JSON changes in `#catalog-data`
- No stale `themes/openfreebooks/static/**/*.html` (delete if present — they override Zola)
- `public/main.css` contains new Sass selectors
- Catalog: subject appears, filters work, map loads without cycle error; map cards not clipped (check long titles e.g. permutations); live map titles link and show underline on hover
- Live chapter: breadcrumb → catalog, no curriculum mentions in body

## Planned / not implemented (do not assume)

- Defuddle “copy as Markdown” on non-chapter pages
- Data-driven homepage cards
- Single source for subject metadata (`catalog.json` + `*-curriculum.json`)
- Subject scaffold command (`scaffold:subject`)

See README **Contributor experience** task list for tracked fixes.

## Additional resources

- [curriculum-data.md](curriculum-data.md) — JSON schemas, examples, graph rules
- [zola/SKILL.md](../zola/SKILL.md) — Tera, Sass, Solid mount points
- [zola/zola-solid.md](../zola/zola-solid.md) — `main.tsx`, bundle, dialogs
