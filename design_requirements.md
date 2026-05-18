# IDPA Country Explorer — Design Brief

Hand this file to a designer (or a design-focused agent) together with the
`frontend/` folder. It captures the **what** of every screen and the
**constraints** that must be respected; the *visual look* (typography,
palette, spacing, motion) is open for redesign.

---

## 1. Product in one paragraph

**IDPA Country Explorer** is an internal research tool that lets a user
inspect, compare, and group the 192 UN member states by the structured
content of their Wikipedia infoboxes. The data behind every page is a
*rooted ordered labeled tree* per country, with typed leaves (numbers,
currencies, dates, distributions over taxonomies, etc.). The audience is
one researcher (the developer themself), so the brief is for a clean,
high-information-density, desktop-first scholarly UI — not a
consumer-facing landing page.

Reference vibes that fit: GitHub's repo-insights pages, scikit-learn's
example gallery, Observable notebook pages, Apple's developer docs.
**Avoid**: hero-image landing pages, marketing CTAs, decorative
illustrations, "fun" microcopy.

---

## 2. Technical stack — what's locked

Don't change these without asking:

| Layer | Tech | Why locked |
|---|---|---|
| Server | Flask + Jinja2 SSR | The app already exists; templates are how routes return HTML. |
| CSS framework | Bootstrap 5.3 (CDN) | All current pages use BS5 classes. A clean reskin should keep the grid + utility classes; restyling on top is welcome. |
| JS bundle | None — vanilla browser ES modules | No webpack, no node_modules. Adding a build step is out of scope. |
| Charts | D3 v7 (CDN) | Tree, scatter, dendrogram, choropleth all in D3. |
| Map topology | `world-atlas@2/countries-110m.json` from CDN | ~100KB; loaded by `cluster_map.js`. |
| Icons | None today | Adding a small icon font (Bootstrap Icons, Lucide via inline SVG) is welcome. |
| Fonts | Bootstrap defaults | Replacing with a single Google Font import is fine; don't introduce more than 2 families total. |

### What's open for redesign
- Color palette (currently raw Bootstrap defaults — flat dark navbar + white pages).
- Typography hierarchy (currently only `<h2>` / `<h5>` / `<h6>` Bootstrap defaults).
- Spacing rhythm, card backgrounds, hover states.
- Tab styling on the cluster result page.
- Diff-coloring palette in compare/patch pages (currently red/green/yellow).
- Cluster color palette in the cluster result page (currently `d3.schemeTableau10`).
- Empty / loading / error states.

---

## 3. File inventory

```
frontend/
├── app.py                       # Flask routes — don't edit shape, but
│                                # you can read it for the data model
│                                # each template receives.
├── formatting.py                # Server-side leaf-value formatters
│                                # (currency, distribution chips, trend
│                                # arrows, type badges). Edit if the
│                                # visual is improved — preserve the
│                                # function signatures.
├── templates/
│   ├── base.html                # Nav, layout shell — 4 tabs:
│   │                            # Countries, Compare, Patch, Cluster.
│   ├── countries_list.html      # Searchable country index.
│   ├── country_detail.html      # One country's tree as nested
│   │                            # <details> blocks (server-rendered).
│   ├── compare_form.html        # Pick two countries + algorithm + cost model.
│   ├── compare_result.html      # Two D3 trees side-by-side + diff legend
│   │                            # + edit-script panel.
│   ├── patch_form.html          # Apply an edit script to a tree.
│   ├── cluster_form.html        # Algorithm + single-feature picker.
│   ├── cluster_result.html      # Tabbed result: Map / Scatter /
│   │                            # Dendrogram / Members + side panel.
│   └── error.html
└── static/
    ├── style.css                # Project-specific overrides
    │                            # on top of Bootstrap. Most visual
    │                            # changes belong here.
    ├── tree.js                  # Reusable D3 TreeView (compare + country).
    ├── compare.js               # Compare-page wiring.
    ├── patch.js                 # Patch-page wiring.
    ├── cluster_form.js          # Cluster form wiring (algo knobs,
    │                            # field toggles, submit).
    ├── cluster_result.js        # Loads run JSON, fills side panel,
    │                            # dispatches to viz renderers.
    ├── cluster_map.js           # D3 choropleth world map.
    ├── cluster_scatter.js       # D3 2D MDS scatter.
    └── cluster_dendrogram.js    # D3 dendrogram from scipy linkage.
```

---

## 4. Page-by-page intent

### 4.1 `base.html` — global shell
- **Navbar**: dark, sticky, brand on the left, four tabs (Countries,
  Compare, Patch, Cluster) on the right of the brand.
- **Brand mark**: currently `<span class="brand-mark">IDPA</span>` + a
  smaller subtitle. Treat as a wordmark; don't introduce a logo file.
- **Container**: `<main class="container-fluid py-4">` wraps everything.
  Wide layouts are fine — every page wants horizontal room.

### 4.2 Countries list (`countries_list.html`)
- Searchable grid of 192 countries.
- Each card: country name (underscores → spaces), small ISO badge,
  link to detail page.
- Today this is just a `<ul>`-ish list. A 4–6 column grid with subtle
  hover lift would help density and scanning.

### 4.3 Country detail (`country_detail.html`)
- Renders the entire country tree as collapsible `<details>` blocks
  via `frontend.formatting.render_structural`.
- Each leaf has a type badge (`number`, `currency`, `wikilink`,
  `distribution`, etc.) — these badges are color-coded in
  `formatting.py`'s `TYPE_BADGE_COLORS` dict, which can be retuned.
- Distributions render as inline chips with percentages.
- Trends show ▲/▬/▼ in the trend color (green/grey/red).
- **Do not** convert to a JS-driven viewer; SSR is intentional here
  (deep-linkable, copyable, screenshottable).

### 4.4 Compare form + result
- Form is a simple horizontal row: two country selects, an algorithm
  select (`chawathe` / `nierman_jagadish`), a cost-model select
  (`symmetric` / `asymmetric`), a Compute button.
- Result page: two D3 trees side-by-side, a toolbar (A→B / B→A
  toggle, Expand / Reset / Fit), and an edit-script table beneath.
- The diff is colored on **both** trees: `delete` red, `insert`
  green, `relabel` yellow. These are the brand's "diff colors";
  shifting them to a more accessible palette (e.g. ColorBrewer's
  `Set1` or Apple's diff palette) is welcome.
- The edit-script table currently truncates at 200 ops with a hidden
  "load more" link — fine to keep.

### 4.5 Patch form
- 3-source radio: paste JSON / upload file / select cached comparison.
- Source country select. Apply button. Result is the patched tree
  rendered alongside the original.

### 4.6 Cluster form (`cluster_form.html`)
This is the **most complex form** in the app and the highest-priority
target for design polish.

Sections, in order top-to-bottom:
1. **Intro paragraph** explaining the tool.
2. **Top row**: algorithm select | cost-model select | "Run clustering" button.
3. **Algorithm-specific knobs** (one row, only the active algorithm's
   knobs are visible — JS toggles via `.algo-knobs.kmeans` /
   `.algo-knobs.hierarchical_agglomerative`):
   - k-means: `k`, `n_init`, `max_iter`, `random_seed`
   - AGG: `k`, `linkage` (`average` / `complete` / `single`),
     `distance_threshold` (optional, overrides k)
4. **Feature picker** — the meat of the form:
   - Six groups (Identity, Geography, Government, Economy,
     Demographics, Codes), each a collapsible block.
   - Per row: **radio** | label (with type hint as small text).
     Exactly **one** feature is selected; there are no per-feature
     weights (a single field needs none) and no bulk controls.
5. **Status box** (alert) appears after submit.
6. **Recent runs** table at the bottom.

**Design opportunities** (top of my wishlist):
- The feature picker is dense. A 2-column responsive grid by group
  keeps the single-select radio list from feeling cluttered.
- The algorithm knob row should look like a single coherent
  "parameters" card, not a row of disconnected inputs.
- The "Run" button is small. It's the most important action — give
  it weight (large primary button, maybe stuck to the bottom while
  scrolling the feature list).
- The recent-runs table has too many columns to be useful at a
  glance — consider a card-grid.

### 4.7 Cluster result (`cluster_result.html`)
- **Header** with algorithm name + k + outlier count + silhouette.
- **Tab bar**: World map (default) / 2D Scatter / Dendrogram (only
  for hierarchical) / Members.
- **Main viz** in a bordered card (currently white background).
- **Right column** with three stacked cards:
  - "Configuration" — algorithm + params JSON.
  - "Cluster sizes" — list with color swatches + medoid names.
  - "Outliers" — names + which fields they're missing.

The tab content needs to breathe — the current border+padding is too
tight. The right column should be slightly narrower so the viz has
more room. Cluster swatches in the side panel should be larger and
clickable (filter the viz to that cluster).

#### 4.7.1 OPEN QUESTION — scatter dimensionality (2D vs 3D vs other)

**Symptom observed:** in the 2D MDS scatter some clusters sit on top
of each other. Question raised: should it be a 3D (or higher-D)
scatter?

**Analysis / decision (to continue in a future chat — no code changed
yet):**

- Overlap in the scatter is mostly a **projection artifact**, not a
  clustering defect. Two embeddings exist:
  - the **scatter** = `src/clustering/embedding.py`, sklearn SMACOF
    MDS, `n_components=2` — picture only;
  - the space **k-means actually clusters in** =
    `src/clustering/algorithms/kmeans.py`, classical MDS,
    `min(n−1, 16)` dims.
  k-means can separate groups in ~16-D that the 2-D picture squashes
  together. **Separation should be judged by the silhouette (computed
  on the true distance matrix), never by the scatter.**
- Whether 3D helps depends on the **classical-MDS eigenvalue
  spectrum**. If eigenvalues 1–2 already explain most variance, a 3rd
  axis adds little; non-Euclidean type-aware distances are usually
  intrinsically high-D, so 2→3 often buys little. A static 3D scatter
  also needs rotation to read.
- For the **single-feature** design (current spec, §4.6): a *numeric*
  field is ~1-D (2-D MDS already invents a fake axis; 3-D invents
  two); a *categorical* field produces ties → coincident points that
  **stack** (a jitter/opacity problem, not a dimensionality one).

**Recommended direction (not yet implemented):**
1. Show **% variance explained by the first 2 (and 3) MDS
   eigenvalues** next to the scatter so overlap is interpretable.
2. Add **jitter + point transparency** for coincident points.
3. Offer a **1-D strip/histogram** view when the single feature is
   numeric (the honest representation).
4. Consider **t-SNE / UMAP** (sklearn has `TSNE`) as an optional
   projection — preserves *cluster* separation better than metric MDS.
5. Treat **3D as a later, evidence-gated, *interactive* (rotatable)
   feature only** — not a default, and only if the eigenvalues justify
   it.

See `docs/08-design-decisions.md` §16 for the rationale in full.

---

## 5. Data shapes the UI consumes

These are stable. A designer doesn't need to memorize them, but
knowing the shape helps when proposing layouts.

### 5.1 Country tree
```json
{
  "name": "Lebanon", "size": 123, "height": 4,
  "root": {
    "kind": "structural", "label": "country",
    "children": [
      { "kind": "structural", "label": "geography",
        "children": [
          { "kind": "leaf", "label": "capital",
            "type": "wikilink", "value": "Beirut",
            "raw": "[[Beirut]]", "unit": null,
            "trend": null, "taxonomy": null },
          ...
        ]
      }, ...
    ]
  }
}
```
Leaf `type` ∈ {`number`, `percent`, `year`, `date`, `currency`,
`coordinates`, `wikilink`, `text`, `distribution`}.

### 5.2 Compare result
```json
{
  "country1": "Lebanon", "country2": "Switzerland",
  "algorithm": "chawathe", "cost_model": "symmetric",
  "from_cache": true,
  "forward": {
    "script": { ...edit script... },
    "total_cost": 40.13,
    "op_counts": { "insert": 12, "delete": 8, "relabel": 23 },
    "source": <tree dict>, "target": <tree dict>,
    "source_marks": { "geography.capital": "relabel", ... },
    "target_marks": { ... }
  },
  "reverse": { ... }
}
```

### 5.3 Cluster result
```json
{
  "algorithm": "kmeans" | "hierarchical_agglomerative",
  "params": {
    "fields": ["demographics.religion"],          // exactly one
    "weights": {},                                // unused (single field)
    "cost_model": "symmetric",
    "k": 5, "n_init": 10, "max_iter": 300, "random_seed": 0
  },
  "labels":        { "Lebanon": 2, "Switzerland": 0,
                     "Syria": -1, ... },         // -1 = outlier
  "medoids":       ["France", "Brazil", "Egypt", ...],
  "linkage":       [ [i, j, dist, count], ... ], // AGG only; empty for kmeans
  "mds_2d":        { "Lebanon": [0.31, -0.18], ... },
  "silhouette":    0.42,
  "cluster_sizes": { "0": 41, "1": 27, ..., "-1": 8 },
  "outliers":      { "Tuvalu": ["economy.gdp_ppp.value"], ... }
}
```

---

## 6. Visual system — recommendations

Treat these as suggestions, not mandates. Anything that improves
density + scannability + accessibility is welcome.

### Palette (proposal)
- **Surface**: warm off-white background (`#fafaf7`), white cards.
- **Text**: near-black headings, dark grey body.
- **Accent**: a single saturated hue (deep teal or muted indigo) for
  primary buttons and the navbar's active tab.
- **Diff palette** (red/green/yellow today): keep semantic mapping
  but pick a colorblind-safer triplet.
- **Cluster palette**: an ordered qualitative palette of 10–12
  colors (Tableau 10 is OK; Vega's `category20` is too noisy).
  Outliers: `#bbbbbb`.

### Typography
- One sans for UI (Inter, IBM Plex Sans, Source Sans 3).
- One mono for code paths / labels (the dotted field paths look much
  better in monospace — `geography.area.km2` rendered as code-styled
  is a visual win across multiple pages).
- Headings: clear `h1 / h2 / h3` rhythm. Today the app uses `h2` for
  page titles and `h5–h6` for everything else — there's room for a
  more confident scale.

### Components to invent (or steal from a system)
- **Type badge** — the colored pill next to every leaf field.
  Currently a Bootstrap badge. Could become a more distinctive small
  monospace tag.
- **Cluster legend chip** — color swatch + cluster id + medoid name
  + member count. Repeated across the side panel and inside the
  Members tab.
- **Field selector row** — radio + label + type hint. Repeated in the
  cluster form (single-select; no weight input).
- **Empty state** — used by countries-list when search has no hits,
  by cluster-form recent-runs when none exist.

---

## 7. Accessibility floor

- Diff and cluster colors must be distinguishable with deuteranopia
  (use a color-blindness simulator). If a hue conflict is
  unavoidable, supplement with a glyph (✗ for delete, + for insert,
  ~ for relabel).
- Every interactive element keyboard-reachable. The cluster form's
  feature radios must accept Tab + arrow-key selection.
- Tab labels on the cluster result need `aria-controls` / `aria-selected`
  (Bootstrap handles this when using `data-bs-toggle="tab"` — keep it).
- Tooltips on D3 viz are mouseover-only today; that's a known gap
  but acceptable for v1.

---

## 8. Out of scope for this pass

- Mobile responsive layouts (desktop-only is fine for now).
- Dark mode.
- Internationalization / RTL.
- Replacing Bootstrap with a different framework.
- Build pipeline / asset bundling.
- Reworking the Python data layer or template variable names.

---

## 9. Hand-off

Drop this file plus the entire `frontend/` directory into the
design agent. Expected output:
1. Updated `frontend/static/style.css` (this is where most changes
   should land).
2. Surgical edits to the Jinja templates in `frontend/templates/`
   where structural / class changes are needed.
3. Optional: one new small CSS file for design tokens
   (`frontend/static/tokens.css`) imported from `style.css`.

The user will load the changes by hard-refreshing the browser
(Ctrl+F5) after the Flask server reloads — there's no build step
to run.
