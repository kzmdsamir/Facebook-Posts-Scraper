# Pagefind + Zola (Open Free Books)

Reference for static search in this repo. Pagefind runs **after** Zola builds HTML to `public/` — it does not use Zola’s `build_search_index`.

Read [Pagefind Component UI](https://pagefind.app/llms-component-ui.txt) for upstream API details. Use **Component UI** (`pagefind-component-ui.js`) only — not legacy `pagefind-ui.js` / `PagefindUI`.

## How it fits together

```text
bun run build:js     → themes/openfreebooks/static/js/bundle.js
zola build           → public/**/*.html
pagefind --site public → public/pagefind/  (index + WASM + UI assets)
```

| Environment | Index output | Served from |
|-------------|--------------|-------------|
| Production (`bun run build`) | `public/pagefind/` | Deployed with Wrangler |
| Dev (`zola serve`) | `static/pagefind/` (copy) | Zola copies `static/` to site root |

`static/pagefind/` is **gitignored**. Run `bun run index:search` after `zola build` so `zola serve` can load `/pagefind/*`.

## Commands

```bash
bun run build:js      # if frontend changed
zola build            # required before indexing
bun run index:search  # pagefind on public/ → copy to static/pagefind/
zola serve            # http://127.0.0.1:1111
```

Production (includes index + copy):

```bash
bun run build   # build:js + zola build + index:search
```

`package.json` devDependency: `pagefind` (^1.5). CLI: `pagefind --site public`.

## What gets indexed

**Live chapter pages only.** Once any page uses `data-pagefind-body`, Pagefind **skips** all pages without it.

| Source | Indexed? |
|--------|----------|
| `templates/chapter.html` → `<article data-pagefind-body>` | Yes |
| Home, about, catalog, credits, contributing, `/search/` | No |
| Catalog chapter cards (Solid + JSON) | No |
| Planned chapters (no `content/` page) | No |

New subject chapter templates must include `data-pagefind-body` on the main lesson container.

### Per-chapter markup

[`themes/openfreebooks/templates/chapter.html`](../../../themes/openfreebooks/templates/chapter.html):

```html
<article class="book-chapter" data-pagefind-body data-chapter="math/quadratic-equations">
  …
  <div id="copy-page-button" … data-pagefind-ignore></div>
  <div id="quadratic-explorer" … data-pagefind-ignore></div>
</article>
```

- **`data-pagefind-body`** — title, lead, and HTML partial prose.
- **`data-pagefind-ignore`** — chrome and interactive widgets (not lesson text).

Breadcrumb nav stays **outside** the article so it is not indexed.

## UI integration

### Global (every page)

[`themes/openfreebooks/templates/base.html`](../../../themes/openfreebooks/templates/base.html):

- `<head>`: `pagefind/pagefind-component-ui.css` + `.js` via `get_url()`
- Before `</body>`: `<pagefind-modal reset-on-close>`
- `#site-config` includes `searchUrl` from `zola.toml` `[extra] search_url`

### Header (Solid)

[`frontend/src/components/site-header.tsx`](../../../frontend/src/components/site-header.tsx):

```tsx
<pagefind-modal-trigger compact placeholder="Search" />
```

[`frontend/src/main.tsx`](../../../frontend/src/main.tsx): nav link **Search** → `config.searchUrl`.

Types: [`frontend/src/types/pagefind-components.d.ts`](../../../frontend/src/types/pagefind-components.d.ts).

### Dedicated page

| File | Role |
|------|------|
| `content/search.md` | `template = "search.html"` |
| `templates/search.html` | `pagefind-input`, `pagefind-summary`, `pagefind-results`, `pagefind-keyboard-hints` |
| `sass/_search.scss` | Layout + map `--pf-*` to site tokens (`:root`, `[data-theme="dark"]`) |

URL: `/search/`. Modal and page share the default Pagefind instance (⌘K / Ctrl+K).

## Theming

Pagefind hosts use `all: initial` — site CSS does not cascade in. Theme via **`--pf-*`** variables in `_search.scss` (see [Pagefind CSS variables](https://pagefind.app/docs/css-variables/)).

**Load order in `base.html`:** `pagefind-component-ui.css` first, then `main.css` so site `--pf-*` overrides Pagefind defaults (white button, blue focus ring).

Site theme uses `data-theme` and `data-pf-theme` on `<html>` (`theme.ts`); tokens map under `[data-theme="dark"]` and `prefers-color-scheme`. Header trigger scoped in `.site-header__search` to match `.theme-toggle`.

## Zola config

[`zola.toml`](../../../zola.toml):

```toml
build_search_index = false   # Zola search unused; Pagefind handles search
search_url = "/search/"
```

`<html lang="en">` in `base.html` — required for Pagefind language detection.

## Stale static HTML (common bug)

**Never** copy `public/` into `themes/openfreebooks/static/`. Committed `themes/openfreebooks/static/**/*.html` **overrides** Zola output and breaks:

- `data-pagefind-body` on chapters
- Pagefind assets in `base.html`
- Any template change

If search indexes 8 pages instead of 1, delete stale `themes/openfreebooks/static/**/*.html`, then `zola build` and `bun run index:search`.

Allowed under theme `static/`: built JS (`js/bundle.js`, hashed chunks), fonts, etc. — not generated HTML.

## Verify

```bash
bun run build:js && zola build && bun run index:search
```

Expect Pagefind output similar to:

```text
Indexed 1 page
Indexed … words
```

Check:

- `public/math/<slug>/index.html` contains `data-pagefind-body`
- `public/pagefind/pagefind-component-ui.js` exists
- `static/pagefind/` exists after `index:search` (for dev)
- `/search/` and header ⌘K return chapter hits only

## Adding a new live chapter

1. Publish chapter per [CONTRIBUTING.md](../../../CONTRIBUTING.md) (`content/`, partial, `chapter.html` branch).
2. Ensure content lives inside `<article data-pagefind-body>`.
3. `zola build && bun run index:search` (or full `bun run build`).
4. Confirm indexed page count increased.

## Do not

- Commit `public/pagefind/` or `static/pagefind/`.
- Use `pagefind-ui.js` / `new PagefindUI()`.
- Add `data-pagefind-body` to `base.html` or marketing pages unless you intend to index them.
- Expect catalog JSON titles in search without a static HTML index block (future enhancement).

## Related

- [SKILL.md](SKILL.md) — Zola layout and commands
- [zola-solid.md](zola-solid.md) — header mount, `searchUrl` in site config
- [ofb/SKILL.md](../ofb/SKILL.md) — product rules, chapter workflow
