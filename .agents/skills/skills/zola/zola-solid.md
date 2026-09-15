# Solid.js + Vite (Open Free Books)

Reference for client-side work in this Zola repo. Read this when editing `frontend/`, `bundle.js`, or adding interactivity.

## Stack

| Piece | Location |
|-------|----------|
| Source | `frontend/src/` (functional Solid components) |
| Entry | `frontend/src/main.tsx` |
| Build | Vite + `vite-plugin-solid` |
| Output | `themes/openfreebooks/static/js/bundle.js` |
| Loaded in | `themes/openfreebooks/templates/base.html` (`defer`) |

Package manager: **Bun** (`bun install`, `bun run build:js`).

## Config bridge (Zola → Solid)

`base.html` embeds JSON:

```html
<script id="site-config" type="application/json">…</script>
```

`main.tsx` reads it via `readConfig()` for brand, `homeUrl`, `browseUrl`, `aboutUrl`, `githubUrl`. Add new global URLs in **`zola.toml` `[extra]`** and mirror in `base.html` + `readConfig()` types.

## Mount points

| ID / target | Component | Role |
|-------------|-----------|------|
| `#site-header` | `SiteHeader` | Nav + theme toggle |
| `#marquee` | `Marquee` | Homepage quote strip |
| `document.body` | `ScrollRevealBootstrap` | `[data-scroll-reveal-card]` |
| `document.body` | `ContributorsDialogBootstrap` | `<dialog>` for contributors |
| `#footer-year` | `mountFooterYear()` | Copyright year |

Prefer **bootstrap** components that `querySelector` existing markup over re-rendering large HTML regions in Solid.

## Conventions

- **Functional** components only; no class components.
- **No mocks** in Vitest unless the user asks for tests.
- Keep bundles small: mount only what’s needed.
- Styles stay in **Sass** (`themes/openfreebooks/sass/`); use `className` with existing classes, not inline Tailwind.
- Scroll reveal: stagger **per section** (`[data-scroll-reveal]` group), not global index; reveal in-viewport items immediately on load (`scroll-reveal.tsx`).

## Vite config

- `outDir`: `themes/openfreebooks/static`
- `emptyOutDir: false` — do not wipe theme static (only add `js/bundle.js`)
- Entry: `frontend/src/main.tsx` → `js/bundle.js`
- Lazy chunks: e.g. `import("./catalog-mermaid-view")` → `js/catalog-mermaid-view-[hash].js`

## Workflow

1. Edit `frontend/src/…`.
2. Run `bun run build:js` (or `bun run dev:js` while `zola serve` runs).
3. Hard-refresh browser.
4. For production: `bun run build` then `wrangler deploy`.

## Catalog (Solid + Mermaid)

Mounted from `catalog.html` via `catalog-app.tsx` (in main bundle). Map view lazy-loads `catalog-mermaid-view.tsx`.

| Concern | Module |
|---------|--------|
| Diagram source | `lib/catalog-to-mermaid.ts` |
| Mermaid init / hex theme | `lib/catalog-mermaid-theme.ts` → `mermaidInitializeOptions(mode)` |
| Strand title band overlay | `lib/catalog-mermaid-strand-headers.ts` |
| Light/dark for map | `lib/catalog-canvas-theme.ts` |
| Compare tab HTML | `catalog-compare-doc.tsx` reads `#catalog-compare-template` |

**Mermaid theming:** use `theme: "base"` and hex `themeVariables` only; CSS cannot override Mermaid’s inline cluster fills. See [zola-catalog.md](zola-catalog.md).

## Subject shared assets (chapters)

For subjects with multiple chapters (e.g. mathematics), colocate shared code under `content/{subject}/`:

| File | Build output | Loaded by |
|------|----------------|-----------|
| `subject.scss` | `static/css/subjects/{subject}.css` | `chapter.html` when `subjects-meta.json` has `hasCss` |
| `subject.ts` | chunk via Vite | `main.tsx` → `generated/subject-modules.ts` → `initSubject(article)` |

Run `bun run sync:chapters` to compile CSS and regenerate `subject-modules.ts` + `data/_generated/subjects-meta.json`. Chapter-only styles stay in `content/{subject}/{slug}/chapter.scss`.

Math conventions: `.agents/skills/ofb/math-chapter-patterns.md`.

## KaTeX (math)

| Use case | API | Where |
|----------|-----|--------|
| Chapter HTML with `\( … \)` / `\[ … \]` | `renderBookMath()` | `frontend/src/lib/katex.ts` — runs on load via `initBookMath()` in `main.tsx` |
| Widget labels / dynamic formulas | `renderLatex()` + `innerHTML` | `import { renderLatex } from "@ofb/katex"` in `content/**/widgets/*.tsx` |
| Captions with delimiter math | `renderMathInContainer(el)` | Same module; do not duplicate per chapter |

- **CSS:** `js/katex.css` is linked from `base.html` on every page.
- **Do not** add local `function renderLatex` or `import katex from "katex"` in widgets — use `@ofb/katex` only.

## Adding a feature

1. Add mount root in Tera template (empty `<div id="…">` or use existing).
2. Create `frontend/src/components/your-feature.tsx`.
3. Import and `render()` in `main.tsx` (or extend a bootstrap).
4. Add Sass if new UI.

## Dialogs

Contributor modals use native `<dialog>` + `showModal()` in `contributors-dialog.tsx`. Markup lives in `partials/contributors-block.html`.

## Do not

- Commit generated `main.css` or `index.html` under `themes/openfreebooks/static/`.
- Use `emptyOutDir: true` in Vite without restoring allowed theme static files.

## Verify

```bash
bun run build:js
zola build
```

Check `themes/openfreebooks/static/js/bundle.js` updated; hard-refresh if behavior looks stale.
