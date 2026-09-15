# Zola reference (Open Free Books)

## `zola.toml` extras

```toml
[extra]
site_title = "Open Free Books"
github_url = "https://github.com/hananoshikayomaru/openfreebooks"
browse_url = "/browse/"
about_url = "/about/"
faq_url = "/faq/"
credits_url = "/credits/"
```

Injected into templates and `#site-config` JSON for Solid (see zola-solid subskill).

## Homepage vs sections

- Homepage: `content/_index.md` with `template = "index.html"`.
- Other pages: e.g. `content/credits.md` with `template = "credits.html"`.
- Shared why blocks: `partials/why-sections.html`; community block: `partials/community-section.html`.

## Common Tera errors

| Error | Fix |
|-------|-----|
| `unexpected tag` on `{% import %}` in partial | Move `{% import %}` to parent template (e.g. `index.html`) before `{% include %}` |
| `expected a keyword argument` in macro | Use `{{ macro::name(param=value) }}` |
| `load_data` file not found | Path must be `data/file.json` on Zola 0.22+ |

## Theme `static/` hazard

Zola merges `themes/openfreebooks/static/` **over** generated assets. If `main.css` or `index.html` appear there, they **override** compiled Sass and the real homepage.

**Allowed in theme static:** `js/bundle.js` only (see `.gitignore`).

If styles “don’t apply”, delete stray `themes/openfreebooks/static/main.css` and rebuild.

## Sass pipeline

`themes/openfreebooks/sass/main.scss` imports partials; Zola writes `public/main.css`. Never commit compiled CSS into theme `static/`.

## Credits / contributors pattern

- `data/contributors.json` + `data/credits.json` — source of truth.
- `static/contributors.json` — optional mirror for `/contributors.json` if needed.
- Contributors UI: `partials/contributors-block.html`; credits page: `credits.html` + `partials/credits-content.html`.

## Catalog URLs

| URL | View |
|-----|------|
| `/catalog/?subject=math` | List |
| `/catalog/?subject=math&view=tree` | Mermaid map |
| `/catalog/?subject=math&view=compare` | Math curricula compare (HTML partial) |

Catalog build/data/Mermaid details: [zola-catalog.md](zola-catalog.md).

## Social icons

1. Source SVGs: `static/icons/social/{kind}.svg` (from [Tabler Icons](https://tabler.io/icons) outline set).
2. Template partials: `templates/partials/icons/social/{kind}.html` (normalized `currentColor`, 20×20).
3. Macro router: `templates/macros/social-icons.html`.

Regenerate partials after updating raw SVGs if stroke/size should stay consistent.
