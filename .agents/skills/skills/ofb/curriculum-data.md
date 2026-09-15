# Curriculum & catalog data

## `data/catalog.json`

Site-wide catalog chrome.

```json
{
  "title": "Curriculum Catalog",
  "subtitle": "Browse chapters by subject and curriculum",
  "curriculums": ["Foundation", "DSE", "IB", "A-Level", "AP", "IGCSE", "Common Core"],
  "subjects": [
    { "id": "math", "name": "Mathematics" }
  ]
}
```

| Field | Rules |
|-------|--------|
| `id` | kebab-case, URL-safe; becomes `?subject=` and path prefix `/{id}/` |
| `name` | Display label in sidebar |
| `curriculums` | Union of all filter chips; add new labels here first |

## `data/{subject}-curriculum.json`

Example: `data/math-curriculum.json`.

```json
{
  "title": "Mathematics",
  "subtitle": "Optional; deprecated — do not use HKDSE-only framing. Catalog chrome uses data/catalog.json.",
  "intro": "Optional subject-level intro (not shown in catalog UI today)",
  "intro": "Optional; was used by old book page",
  "graph": {
    "edges": [
      { "from": "quadratic-equations", "to": "sequences-series" },
      { "from": "quadratic-equations", "to": "functions-graphs" },
      { "from": "functions-graphs", "to": "linear-programming" }
    ]
  },
  "strands": [
    {
      "id": "number-algebra",
      "title": "Number & Algebra",
      "chapters": [
        {
          "slug": "quadratic-equations",
          "title": "Quadratic equations",
          "description": "One or two sentences shown in list and map views.",
          "status": "live",
          "curriculums": ["DSE", "IB"]
        }
      ]
    }
  ]
}
```

### Chapter fields

| Field | Required | Notes |
|-------|----------|-------|
| `slug` | yes | Matches `content/{subject}/{slug}/`; kebab-case |
| `title` | yes | Catalog list + map node label |
| `description` | yes | 1–2 sentences; shown in list and map cards (clamped to 3 lines on map) |
| `status` | yes | `live` (link to chapter) or `planned` (no link) |
| `curriculumCoverage` | yes (math) | Object mapping framework label → `core` \| `extension` \| `related` (Compare matrix + filters) |
| `curriculums` | legacy | Deprecated array; use `curriculumCoverage` instead |
| `tier` | no | `foundation` (default) or `non-foundation` — shows an **Extension** badge on cards (DSE M2-style topics) |

### Graph model (map)

| Rule | Detail |
|------|--------|
| Scope | DSE compulsory topic units (~25–35 chapters); primary/junior not in JSON yet |
| Edges | **Required** prerequisites only; `graph.edges` is the sole source (no auto chain from strand array order) |
| Scope of `from`/`to` | Any chapter slug — **cross-strand** edges allowed (arrows may cross columns) |
| Levels | **Longest-path** from roots: `level = 1 + max(level(parent))`; roots at 0 |
| List order | `strands[].chapters[]` array order is for the **list** tab only (authoring / ToC) |
| Roots | Multiple level-0 chapters per strand OK; edgeless placeholders OK while drafting |

### Graph edges

- `from` / `to` are **chapter slugs** (not node ids).
- Edges must form a **DAG** (no cycles). Map builder throws on cycles.
- One prerequisite → add one edge. Multiple parents → multiple edges into the same `to`.
- Branches: one `from` → many `to` (e.g. quadratics → sequences and functions-graphs).
- Merges: many `from` → one `to` (e.g. functions + sequences → linear programming).

### Wiring into catalog

`themes/openfreebooks/templates/catalog.html` exposes strands + graph in `#catalog-data` by loading `data/{subject.id}-curriculum.json` for each catalog subject.

```tera
{% for subject in catalog.subjects %}
{% set subject_curriculum = load_data(path="data/" ~ subject.id ~ "-curriculum.json", format="json") %}
...
"strands": {{ subject_curriculum.strands | default(value=[]) | json_encode() | safe }}
{% endfor %}
```

## Status: planned vs live

| status | Catalog list | Map node | Content required |
|--------|--------------|----------|------------------|
| `planned` | Shown, “Coming soon” badge | Card shown; title not linked | Only JSON entry |
| `live` | Full card links to chapter | Title links to chapter (`→` + underline); rest of card not clickable | `content/` + HTML partial + template wiring |

Map view is Mermaid-based (`CatalogMermaidView` + `catalog-to-mermaid.ts`) and uses `graph.edges` as the source-of-truth DAG.

## Adding a curriculum label

1. Add string to `data/catalog.json` → `curriculums`.
2. Tag chapters with that string in `curriculums` arrays.
3. Add `.catalog-badge--{name}` in `_catalog.scss` (see existing `--dse`, `--ib`, …).
4. Optional: `curriculumBadgeClass()` in `frontend/src/lib/catalog-badge.ts` (defaults exist).

## Map card heights (agents)

Do not hand-place map node positions. The pipeline is:

1. `subjectToMermaid()` builds Mermaid source from strands + `graph.edges`.
2. `CatalogMermaidView` renders with Mermaid (`theme: "base"` + hex theme variables).
3. `enhanceStrandClusterHeaders()` post-processes strand header chrome in SVG.

Card markup must stay in sync between `catalog-chapter-card.tsx` (Solid + `renderCatalogChapterCardElement`) and `_catalog.scss` (especially `.catalog-chapter-card--map`).

## Validation

- `bun run validate:curriculum` (scripted checks for slugs, curricula labels, live content paths, and DAG acyclicity).
- `bun run build` succeeds.
