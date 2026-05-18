# 06 · Frontend

A Flask single-app served at `http://127.0.0.1:5050`. Three tabs:

- **Countries** — list + per-country tree view.
- **Compare** — two countries side-by-side with diff coloring.
- **Patch** — apply an `EditScript` to a country tree.

## Files

```
frontend/
├── app.py             Flask app factory + routes
├── formatting.py      tree_to_dict + value formatters
├── templates/
│   ├── base.html               nav + Bootstrap 5 + D3 CDN
│   ├── countries_list.html     grid + search
│   ├── country_detail.html     D3 tree canvas
│   ├── compare_form.html       form + cached-comparisons table
│   ├── compare_result.html     two D3 canvases + direction toggle + edit-script panel
│   ├── patch_form.html         3-source picker + Apply
│   └── error.html
└── static/
    ├── style.css
    ├── tree.js        reusable TreeView class (D3 v7)
    ├── compare.js     compare-page wiring
    └── patch.js       patch-page wiring
```

## Routes

### HTML

| Route | Template | Notes |
|-------|----------|-------|
| `GET /` | redirects to `/countries` |  |
| `GET /countries` | `countries_list.html` | search via `?q=…` |
| `GET /countries/<name>` | `country_detail.html` | renders D3 tree from `/api/countries/<name>/tree` |
| `GET /compare` | `compare_form.html` | two pickers + algorithm + cost model |
| `GET /compare/<c1>/<c2>` | `compare_result.html` | toolbar + 2 D3 canvases + script panel; data fetched via `/api/compare/<c1>/<c2>` |
| `GET /patch` | `patch_form.html` | source picker + script source picker |

### JSON

| Route | Returns |
|-------|---------|
| `GET /api/countries` | list of country names |
| `GET /api/countries/<name>` | raw country doc from Mongo |
| `GET /api/countries/<name>/tree` | `{name, size, height, root: …}` |
| `GET /api/algorithms` | `[{name, description, placeholder}, …]` |
| `GET /api/cost-models` | `["symmetric", "asymmetric"]` |
| `GET /api/compare/<c1>/<c2>?algorithm=…&cost_model=…` | `{country1, country2, algorithm, cost_model, from_cache, forward: DirectionResult, reverse: DirectionResult}` |
| `GET /api/scripts` | summary of cached comparisons |
| `GET /api/scripts/<id>` | a single cached comparison doc |
| `POST /api/patch` | `{country, source, patched, size, ops, cost}` |

`DirectionResult` JSON shape:

```json
{
  "script":       { ...EditScript.to_dict() },
  "total_cost":   <number>,
  "op_counts":    { "insert": <n>, "delete": <n>, "relabel": <n> },
  "source":       <tree dict>,
  "target":       <tree dict>,
  "patched":      <tree dict>,
  "source_marks": { "<dotted_path>": "delete|relabel|insert", ... },
  "target_marks": { "<dotted_path>": "delete|relabel|insert", ... }
}
```

## TreeView (D3, in `tree.js`)

A reusable class that renders an arbitrary tree dict.

```js
TreeView.fromUrl(containerId, url, opts);
TreeView.fromData(containerId, treeDict, opts);
```

Options:

- `initialDepth: int` — how many levels to expand at first.
- `marks: { dottedPath: "delete"|"insert"|"relabel" }` — per-node coloring.
- `infoPanel: HTMLElement` — receives details on click (default `#node-info`).
- `onNodeClick: fn(d)` — extra callback.

### Layout

Horizontal: root on the left, children flow right. Cubic-Bézier
connectors. Structural nodes render as circles; leaves as rounded
pills containing `<label>: <value>` plus a small colored type dot
on the left. Drag-to-pan, scroll-to-zoom, click-structural-to-toggle.

### Diff coloring

When `opts.marks` is supplied, the renderer overlays it on the
default colors:

| mark | structural | leaf pill |
|------|-----------|-----------|
| `delete`  | red filled circle | red stroke + red-tinted background |
| `insert`  | green filled circle | green stroke + green-tinted background |
| `relabel` | yellow filled circle | yellow stroke + yellow-tinted background |

The dotted-path computation in JS mirrors the backend's
`_dotted(node)` exactly — same `[i]` sibling-index disambiguation —
so marks line up with the rendered nodes.

## Compare page (`compare.js`)

1. Fetches `/api/compare/<c1>/<c2>?…` once on load.
2. Renders both directions' source + target trees as `TreeView`
   instances.
3. Toolbar buttons:
   - **A → B / B → A** — toggle direction (re-renders both trees
     with the other direction's source, target, and marks).
   - **Expand all / Reset view / Fit to view** — propagated to both
     trees.
4. The edit-script panel below the trees enumerates the first 200
   ops with badges per op type, paths, label changes, and per-op
   costs.

## Patch page (`patch.js`)

Three script-source modes (radio-like toggle):

1. **Paste JSON** — `<textarea>` accepting an `EditScript.to_dict()`
   payload.
2. **Upload file** — `<input type="file">` reading a `.json` file.
3. **Cached script** — `<select>` listing all cached comparisons
   plus a "use reverse direction" checkbox.

`POST /api/patch` returns the source + patched trees plus the op
counts; `TreeView.fromData` renders the patched tree.

## Notes / gotchas

- Flask runs **without** debug mode by default, so static files
  aren't auto-reloaded. After editing `tree.js`/`compare.js`/etc.,
  hard-refresh the browser (Ctrl+F5).
- The Flask process holds an `lru_cache` of built trees. Restart the
  app (or call `clear_caches()`) if you change the builder or
  taxonomies.
