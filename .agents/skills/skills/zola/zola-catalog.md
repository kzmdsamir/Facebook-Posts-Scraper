# Catalog page (Zola + Solid + Mermaid)

Read this when editing `/catalog/`, `templates/catalog.html`, `sass/_catalog.scss`, or `frontend/src/**/catalog-*`.

## Zola side

| Piece | Path |
|-------|------|
| Page | `content/catalog.md` → `template = "catalog.html"` |
| Shell | `themes/openfreebooks/templates/catalog.html` |
| Compare doc (math only) | `templates/partials/math-curricula-compare.html` — embedded in `<template id="catalog-compare-template">` |
| Build-time JSON | `#catalog-data` — merged subject curricula from `data/{subject}-curriculum.json` + `data/catalog.json` |
| Styles | `themes/openfreebooks/sass/_catalog.scss` |

**Tera:** never bind curriculum JSON to a variable named `math` (reserved). Use `math_catalog`, etc.

## URL and views

| View | `view` param | UI |
|------|----------------|-----|
| List (default) | (omit) | Strand sections + `CatalogChapterCard` |
| Map | `tree` | Lazy `CatalogMermaidView` — DAG from `graph.edges` |
| Compare | `compare` | Math only — `CatalogCompareDoc` clones compare partial HTML |

Example: `/catalog/?subject=math&view=tree`

Curriculum filter chips come from `data/catalog.json` → `curriculums[]`. Math chapters use `curriculumCoverage` in `math-curriculum.json` (`core` / `extension` / `related` per framework). Compare matrix uses all roles; list/map badges show framework labels only.

## Solid / Vite

| Piece | Path |
|-------|------|
| App shell | `frontend/src/components/catalog-app.tsx` |
| List card | `frontend/src/components/catalog-chapter-card.tsx` |
| Compare mount | `frontend/src/components/catalog-compare-doc.tsx` |
| Map viewer | `frontend/src/components/catalog-mermaid-view.tsx` (lazy chunk `catalog-mermaid-view-*.js`) |
| Mermaid source | `frontend/src/lib/catalog-to-mermaid.ts` |
| Theme (hex) | `frontend/src/lib/catalog-mermaid-theme.ts` |
| Strand header chrome | `frontend/src/lib/catalog-mermaid-strand-headers.ts` |
| Light/dark mode | `frontend/src/lib/catalog-canvas-theme.ts` (`siteCanvasTheme`, `watchSiteTheme`) |
| Badge classes | `frontend/src/lib/catalog-badge.ts` |
| Types | `data/catalog.types.ts` (`CatalogViewMode`: `"linear" \| "tree" \| "compare"`) |

After any catalog frontend change: `bun run build:js` then hard-refresh.

## Mermaid map — theming (important)

Mermaid writes **inline `fill` on SVG nodes**. CSS `fill` on `.cluster rect` does **not** override themed colors.

| Rule | Detail |
|------|--------|
| Custom colors | Only with `theme: "base"` + `themeVariables` (hex). Other themes (`default`, `dark`, …) are not customizable via variables. |
| Color format | Hex only (`#121110`). Named colors (`red`) are ignored by the theming engine. |
| Site-wide init | `mermaid.initialize({ …mermaidInitializeOptions(mode) })` in `catalog-mermaid-view.tsx` |
| Strand subgraph body | `clusterBkg` in `mermaidThemeVariables()` |
| Strand title band | `secondaryColor` — also applied to overlay header rect in `enhanceStrandClusterHeaders()` |
| Borders / edges | `clusterBorder`, `lineColor`, `nodeBorder`, etc. |

Do **not** try to drive strand cluster fills from Sass variables on `.cluster rect`; keep SCSS for typography, label chrome, and map chrome (pan/zoom, card links).

### Strand subgraph titles

Mermaid puts subgraph titles on the cluster border. Post-render:

1. `enhanceStrandClusterHeaders(svg, mode)` finds `g.cluster` ids containing `strand_`
2. Inserts header `rect` + rule `line` at `STRAND_HEADER_HEIGHT` (44px)
3. Repositions `foreignObject` label into the header band
4. Sets `rx="0"` on cluster frame (square corners)

Diagram source uses HTML in subgraph titles, e.g. `<header class='catalog-mermaid-strand__header'>…</header>` — see `catalog-to-mermaid.ts`.

### Map chapter cards

List and map share card markup via `CatalogChapterCard`. In the map, only the **title** is a link for live chapters; planned chapters are non-clickable.

## Sass notes (`_catalog.scss`)

- Curriculum badge tokens and dark-mode contrast live here.
- Map card title underline: under `.catalog-mermaid-view` / `.catalog-canvas` legacy class names if present.
- Strand label styling: `.catalog-mermaid-strand__header`, `.catalog-mermaid-strand-label-fo` — not cluster `fill`.

## Tests

```bash
bun test frontend/src/lib/catalog-to-mermaid.test.ts
bun test frontend/src/lib/catalog-mermaid-theme.test.ts
bun test frontend/src/lib/catalog-mermaid-strand-headers.test.ts
```

## Verify locally

```bash
bun run build:js && zola serve
```

Open `/catalog/?subject=math`, toggle List / Map / Compare (math), and switch site light/dark — strand header band should differ from subgraph body in both modes.
