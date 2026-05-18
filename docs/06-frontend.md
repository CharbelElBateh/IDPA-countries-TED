# 06 · Frontend

A Flask single-app served at `http://127.0.0.1:5050`. Four tabs:

- **Countries** — list + per-country tree view.
- **Compare** — two countries side-by-side with diff coloring.
- **Patch** — apply an `EditScript` to a country tree.
- **Cluster** — group all 192 countries on a single chosen field.

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
| `GET /api/countries` | list of country names (includes synthetic trees) |
| `POST /api/countries` *(legacy, removed)* | replaced by `POST /api/trees` |
| `GET /api/countries/<name>` | raw country doc from Mongo |
| `GET /api/countries/<name>/tree` | `{name, size, height, root: …}` |
| `DELETE /api/countries/<name>` | `{deleted: 0|1, name}` — works for both countries and synthetic trees |
| `POST /api/trees` | body `{name, bracket}`; parses bracket notation, stores with `source="synthetic"`; returns `{name, nodes, height, updated}` |
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
  "metrics":      {
    "ted_raw":      <number>,
    "sim_inverse":  <number>,   // 1 / (1 + TED)
    "sim_ratio":    <number>,   // 1 − TED / (|T1| + |T2|)
    "t1_size":      <int>,
    "t2_size":      <int>
  },
  "source":       <tree dict>,
  "target":       <tree dict>,
  "patched":      <tree dict>,
  "source_marks": { "<dotted_path>": "delete|relabel|insert", ... },
  "target_marks": { "<dotted_path>": "delete|relabel|insert", ... }
}
```

The three similarity-metric fields mirror the slide-spec (Ch. 5) —
see [04-algorithms.md](04-algorithms.md) and
[08-design-decisions.md §25](08-design-decisions.md).

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
4. **Similarity-metrics card** directly under the page header:
   three rows (Raw TED, Normalized inverse `1/(1+TED)`, Standard
   ratio `1 − TED/(|T1|+|T2|)`) × two columns (A→B, B→A). For
   asymmetric cost models the two columns differ; for symmetric they
   match.
5. The edit-script panel below the trees enumerates the first 200
   ops with badges per op type, paths, label changes, and per-op
   costs.

## Countries page: adding test trees

The Countries list has a **"+ Add tree"** button next to the search
bar. It toggles a small card containing:

- a name input (`<input>`),
- a bracket-notation `<textarea>` (e.g. `A(B,C(D,E))`).

Submitting posts JSON `{name, bracket}` to `POST /api/trees`. The
backend parses via `src/synthetic_tree.py:parse_bracket_tree` and
upserts a `countries` document with `source="synthetic"` plus a
`tree_dict` payload (see [07-storage.md](07-storage.md) and
[08-design-decisions.md §26](08-design-decisions.md)).

After success the page reloads so the new tree appears in the
alphabetical grid alongside the 192 Wikipedia countries. Synthetic
trees are usable from the Compare page exactly like real countries.

## Patch page (`patch.js`)

Three script-source modes (radio-like toggle):

1. **Paste JSON** — `<textarea>` accepting an `EditScript.to_dict()`
   payload.
2. **Upload file** — `<input type="file">` reading a `.json` file.
3. **Cached script** — `<select>` listing all cached comparisons
   plus a "use reverse direction" checkbox.

`POST /api/patch` returns the source + patched trees plus the op
counts; `TreeView.fromData` renders the patched tree.

## Cluster page (`cluster_form.html` + `cluster_form.js`)

Two-card form, in submit order:

1. **Distance matrix** card (top). One control:
   - `cost_model` dropdown — picks which cost-model file in
     `config/pipeline.json` drives `relabel_cost`'s leaf-distance
     scales. **This is *not* an algorithm hyperparameter** — it
     controls how `D` is built; the resulting `D` is then fed to every
     algorithm below. The card sits above the algorithm picker on
     purpose, and the hint explains the same cost model yields the same
     `D` for both algorithms. See
     [08-design-decisions.md §22](08-design-decisions.md).

2. **Algorithm** card. Segmented control + per-algorithm knobs:
   - `kmeans` knobs: `k` (default 5, max 20), `n_init` (default 10),
     `max_iter` (default 300), `random_seed` (default 0).
   - `hierarchical_agglomerative` knobs: `k` (default 5),
     `linkage` (`average` / `complete` / `single`; default `average`).

3. **Feature** card. Grouped accordion of leaf paths (Government /
   Economy / Demographics / …); the user picks **exactly one** field
   via radio. Each entry is tagged with its leaf type for visibility
   (number / percent / currency / coordinates / distribution / text).

4. **Sticky run bar** at the bottom shows the live selection
   (`algorithm · k · feature · cost`) and the run button.

### Cluster result page (`cluster_result.html`)

| panel | source |
|-------|--------|
| Summary (algo, k, feature, n, silhouette) | `ClusterRun` record |
| Cluster table (countries grouped) | `labels` dict |
| 2-D scatter | `embedding.smacof_2d(D)` — see [08-design-decisions.md §16](08-design-decisions.md) about why this is **lossy** vs the higher-D space k-means actually partitions |
| Outliers list | `outliers.detect_outliers(trees, fields)` — countries missing the chosen field |
| Dendrogram (agglomerative only) | linkage matrix `Z` from `linkage(condensed, method=…)` |

### JSON routes (cluster)

| Route | Returns |
|-------|---------|
| `GET /api/cluster/algorithms` | `[{name, description}, …]` |
| `GET /api/cluster/fields` | grouped list `{group: [{path, kind}, …]}` |
| `POST /api/cluster/run` | `{id, …}` — body `{algorithm, fields, weights, cost_model, params}` |
| `GET /cluster/<run_id>` | result page |

## Notes / gotchas

- Flask runs **without** debug mode by default, so static files
  aren't auto-reloaded. After editing `tree.js`/`compare.js`/etc.,
  hard-refresh the browser (Ctrl+F5).
- The Flask process holds an `lru_cache` of built trees. Restart the
  app (or call `clear_caches()`) if you change the builder or
  taxonomies. `POST /api/trees` invalidates this cache automatically
  so newly-added synthetic trees show up on the next request.
- On the cluster form, the `distance_threshold` input was **removed**
  from the agglomerative knobs (the Python entry point still accepts
  it for CLI users); cut-by-k is now the only frontend option. See
  [08-design-decisions.md §23](08-design-decisions.md).
- The cluster form's **Run clustering** button does *not* get
  disabled while a run is in flight — only its label flips to
  `Running…`. The user can still click it (no-op on the second
  click; the in-flight request is still resolving) or change
  parameters and re-submit. Rationale: previously the disabled state
  combined with the slow request gave the impression the UI had hung.
- Synthetic trees added via `+ Add tree` bypass the comparison cache
  (always recomputed) and are excluded from clustering — see
  [08-design-decisions.md §27](08-design-decisions.md).
