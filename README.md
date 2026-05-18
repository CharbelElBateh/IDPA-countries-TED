# IDPA Country Explorer

A Python + MongoDB + Flask tool that turns the Wikipedia infobox of every
UN member state into a typed, hierarchical tree, computes pairwise
Tree-Edit Distance (TED) between any two of them, and groups them into
clusters by feature similarity.

Four tabs in the web UI: **Countries · Compare · Patch · Cluster**.

---

## What it does

| Stage | Module | Output |
|---|---|---|
| 1. Ingest | `scripts/ingest_countries.py` | Raw `Infobox country` dict per UN member state, stored in MongoDB |
| 2. Build | `src/builder.py` | Rooted ordered labeled `Tree` with typed leaves |
| 3. Diff | `src/ted/{chawathe,nierman_jagadish}.py` | `EditScript` with mapping, costs, op list |
| 4. Patch | `src/core/edit_script.py` | Apply / invert any edit script |
| 5. Cluster | `src/clustering/` | k-means or hierarchical AGG on a single selected field |

Distances are **type-aware** and every per-type function returns a
value in `[0, 1]` (min-clamped) so a weighted mean across heterogeneous
fields is commensurable:

- `number` / `percent` — relative diff `abs(a − b) / max(abs(a), abs(b), ε)` / `abs(a − b) / 100`.
- `year` / `date` — `abs(a − b) / Y` and `days / (Y·365.25)`; `Y` defaults to 100.
- `currency` — log-scale, `abs(log₁₀ a − log₁₀ b) / S` with `S = 4` (10 000× ratio = 1.0); falls back to `number` for non-positive values.
- `coordinates` — haversine km (Earth radius 6371) over `D = 20 000` km.
- `text`, `wikilink` — Levenshtein on `.lower().strip()` strings, normalized by the longer length.
- `distribution` — tree-EMD over a hand-curated taxonomy (`religion` / `language` / `ethnicity` / `government`).

Cross-kind or cross-type pairs (and distributions on different
taxonomies) collapse to `type_mismatch_relabel`. See `src/distances.py`
and the full table in `docs/04-algorithms.md`.

---

## Requirements

- **Python 3.10+** (project uses 3.12+; tested on 3.14).
- **Docker Desktop** (for MongoDB + mongo-express).
- **Windows / PowerShell** is the primary dev environment; WSL2 and
  macOS/Linux work too.

Python deps (`requirements.txt`):

```
pymongo>=4.7
python-dotenv>=1.0
wptools>=0.4
tqdm>=4.66
flask>=3.0
```

Optional dev/runtime deps used by the clustering tool:

```
numpy, scipy, scikit-learn      # already pulled in by wptools' deps
pytest                          # for the test suite
```

---

## First-time setup

> Run these in **a real PowerShell terminal**, not the agent's bash tool —
> `pip install` is known to hang under the agent shell.

### 1. Clone & create the virtualenv

```powershell
git clone <repo> C:\dev\IDPA-Project
cd C:\dev\IDPA-Project
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pytest scipy scikit-learn       # if not already pulled in
```

### 2. Configure secrets

```powershell
Copy-Item .env.example .env
notepad .env
```

Replace the default values (especially `MONGO_INITDB_ROOT_PASSWORD`).
The file is gitignored.

```
MONGO_INITDB_ROOT_USERNAME=root
MONGO_INITDB_ROOT_PASSWORD=<your-password>
MONGO_DB_NAME=idpa
MONGO_URI=mongodb://root:<your-password>@localhost:27017/?authSource=admin
MONGO_COUNTRIES_COLLECTION=countries

# admin UI
ME_CONFIG_BASICAUTH_USERNAME=admin
ME_CONFIG_BASICAUTH_PASSWORD=<your-admin-password>
```

### 3. Start MongoDB

```powershell
docker compose up -d
```

This brings up two services:

| Service | Port | Purpose |
|---|---|---|
| `idpa-mongo` (mongo:7) | `127.0.0.1:27017` | The database (data volume `idpa_mongo_data`) |
| `idpa-mongo-express` (mongo-express:1.0.2) | `127.0.0.1:8081` | Web admin UI (basic-auth) |

Verify:

```powershell
docker compose ps
.venv\Scripts\python.exe -c "from src.storage.mongo_store import MongoStore; print('ping:', MongoStore().ping())"
```

Both should report healthy / `True`.

### 4. Ingest the 192 UN member states

```powershell
.venv\Scripts\python.exe scripts\ingest_countries.py --skip-existing --sleep 0.2
```

What this does:
- Reads `src/un_member_states.txt` (192 country names).
- Calls `wptools.page(<name>).get_parse()` for each — pulls the
  raw `Infobox country` template from Wikipedia.
- Upserts one document per country into `countries` collection,
  keyed by `_id = <country_name>`.

Takes ~10–15 minutes the first time (Wikipedia API is the bottleneck).
`--skip-existing` makes re-runs cheap. `--sleep 0.2` keeps you under
Wikipedia's polite-rate limits.

Inspect via mongo-express at <http://localhost:8081>.

### 5. (Optional) Run the data-shape analysis

```powershell
.venv\Scripts\python.exe scripts\analyze_infoboxes.py
```

Writes `data/analysis/infobox_keys.csv`, `infobox_values.jsonl`, and
`infobox_summary.md` — useful when adding new fields to
`config/pipeline.json`.

---

## Running the app

```powershell
.venv\Scripts\python.exe -m frontend.app --port 5050
```

Open <http://127.0.0.1:5050>. Four tabs:

### Countries
A–Z index of all 192 UN member states, with ISO-3 chips, alpha-rail
quick-jump, and per-country detail pages showing the full structural
tree (TOC + nested `<details>` blocks + type-composition side panel).

A **"+ Add tree"** button lets you create hand-crafted test trees in
bracket notation (e.g. `A(B,C(D,E))`) directly from the UI. These
synthetic trees show up alongside real countries in the Compare and
Patch dropdowns, but are **excluded from clustering** (no real
infobox fields) and **bypass the comparison cache** (always
recomputed, since you'll be editing them as you test). Parsing lives
in `src/synthetic_tree.py`; storage is the same `countries`
collection with `source = "synthetic"`.

### Compare
Pick any two countries, an algorithm (`chawathe` or `nierman_jagadish`),
and a cost model (`symmetric` or `asymmetric`). Get a side-by-side
diff with red/green/yellow ✗/+/~ marks, the edit-script table, and
A→B / B→A direction toggle.

A **Similarity metrics** card directly under the header shows the
three slide-spec numbers (Ch. 5) for both directions:

| metric | formula |
|---|---|
| Raw TED | `TED(T1, T2)` |
| Normalized inverse | `1 / (1 + TED(T1, T2))` |
| Standard ratio | `1 − TED(T1, T2) / (|T1| + |T2|)` |

For asymmetric cost models the A→B and B→A columns differ.

### Patch
Apply any `EditScript` (paste JSON / upload `.json` file / pick a
cached comparison) to a source country tree. Reverse-direction
checkbox inverts every op.

### Cluster
Group the 192 countries by similarity on a **single** chosen typed
field (no per-feature weights — only one field is used). Two algorithms:

- **k-means (Lloyd's)** — partition into `k` groups around `k`
  centroids. The non-Euclidean distance matrix is first embedded into
  Euclidean space via classical MDS; initialization is uniform-random
  sampling of `k` data objects (per the course slides), `n_init`
  restarts.
- **hierarchical_agglomerative** — bottom-up merges. Linkage: `average`
  / `complete` / `single` (Ward is rejected — needs Euclidean
  coordinates). Optional `distance_threshold` overrides `k`.

Results render in four tabs:

1. **World map** — TopoJSON choropleth, colored by cluster id.
2. **2D scatter** — classical MDS embedding by default, with an in-viz
   `[MDS] [t-SNE]` toggle to switch projections. MDS shows a
   variance-% diagnostic ("Axes 1+2 explain X%") so visual cluster
   overlap is interpretable; t-SNE preserves cluster separation better
   when MDS shows lots of structure hidden in higher axes (at the cost
   of making absolute distances on screen meaningless). Convex hulls
   per cluster, medoids highlighted.
3. **Dendrogram** — D3 right-angle tree built from scipy's linkage
   matrix (AGG only).
4. **Members** — color-grouped country grid with links to each
   country's detail page.

Click any chip in the *Cluster sizes* side panel to filter the active
viz to that cluster. Countries missing the selected field are
excluded into a separate **outlier** bucket.

---

## CLI

The clustering tool also has a CLI driver:

```powershell
.venv\Scripts\python.exe scripts\cluster_cli.py `
    --algorithm kmeans --k 5 `
    --fields demographics.religion

.venv\Scripts\python.exe scripts\cluster_cli.py `
    --algorithm hierarchical_agglomerative --k 6 --linkage average `
    --fields economy.hdi.value
```

Pick a single field with `--fields`. Results are persisted to the
`cluster_runs` collection and visible in the **Cluster** tab's
"Recent runs" panel.

`--list-fields` prints all clusterable fields. `--no-cache` skips
persistence.

---

## Running tests

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```

131 tests across six files: `test_core`, `test_parsing`,
`test_taxonomy`, `test_builder`, `test_ted`, `test_clustering`.
None of them touch Mongo — they use synthetic trees / matrices.

---

## Project layout

```
IDPA-Project/
├── config/
│   └── pipeline.json              # single source of truth: aliases, layout,
│                                  # types, weights, cost models, taxonomies
├── data/
│   ├── country_iso_codes.json     # name → ISO-3 alpha mapping (192)
│   ├── country_numeric_codes.json # name → ISO-3 numeric (for the world map)
│   └── analysis/                  # output of analyze_infoboxes.py
├── docker-compose.yml             # mongo + mongo-express
├── .env.example                   # env-var template
├── scripts/
│   ├── ingest_countries.py        # Wikipedia → MongoDB
│   ├── analyze_infoboxes.py       # field/coverage stats
│   └── cluster_cli.py             # clustering driver
├── src/
│   ├── core/                      # Node, Tree, Action, EditScript
│   ├── parsing/                   # wikitext, typed values, distributions
│   ├── preprocessing/             # alias map, filter regex, serial groups
│   ├── builder.py                 # raw infobox dict → Tree
│   ├── distances.py               # per-type leaf distance functions
│   ├── taxonomy.py                # Taxonomy + tree-EMD
│   ├── comparison.py              # orchestrator for the Compare tab
│   ├── config.py                  # pipeline.json loader
│   ├── ted/                       # chawathe / nierman_jagadish
│   ├── clustering/                # k-means, AGG, MDS, evaluation
│   ├── synthetic_tree.py          # bracket-notation parser + dict round-trip
│   └── storage/
│       └── mongo_store.py         # countries / edit_scripts /
│                                  # cluster_runs / distance_matrices
├── frontend/
│   ├── app.py                     # Flask routes
│   ├── formatting.py              # server-rendered tree (HTML)
│   ├── templates/                 # base + 8 page templates
│   └── static/                    # tokens.css + style.css (IBM Plex theme),
│                                  # cluster_*.js, tree.js, compare.js, patch.js
└── tests/                         # 131 tests
```

---

## MongoDB collections

| Collection | Key | Contents |
|---|---|---|
| `countries` | `_id = <name>` | Raw infobox dict from `wptools`, plus the full page wikitext (audit). |
| `edit_scripts` | `_id = c1__c2__algorithm__cost_model` | Cached `EditScript` (both directions). |
| `cluster_runs` | `_id = <algo>__<params-hash>` | Persisted `ClusterResult` — labels, medoids, linkage, MDS, silhouette. |
| `distance_matrices` | `_id = dm__<costmodel>__<fields>__<weights>` | Cached pairwise distance matrix for clustering. |

Reset the cluster cache after changing algorithm code or weights:

```powershell
.venv\Scripts\python.exe -c "from src.storage.mongo_store import MongoStore; s = MongoStore(); print(s.clusters.delete_many({}).deleted_count, 'runs deleted'); print(s.matrices.delete_many({}).deleted_count, 'matrices deleted')"
```

---

## Frontend (design system)

The UI is **server-side rendered** Jinja2 with vanilla browser JS + D3.
No Bootstrap, no build step — open a template, edit it, hard-refresh
the browser (Ctrl+F5).

Visual design lives in two files:

- `frontend/static/tokens.css` — design tokens (colors, type, spacing,
  radius). Warm paper background, single deep-teal accent, IBM Plex
  Sans + IBM Plex Mono.
- `frontend/static/style.css` — component styles consuming those
  tokens (nav, buttons, forms, cards, country grid, leaf rows,
  feature picker, cluster chips, viz tabs, etc.).

Fonts are pulled from Google Fonts CDN; D3 v7 and topojson are pulled
from `cdn.jsdelivr.net` / `d3js.org`. The world topology
(`countries-110m.json`) is loaded lazily by the map viz.

If you want to redesign the look, edit `tokens.css` first (the
accent hue, the cluster palette `--c0..--c9`, the radii) — most
of the UI re-themes automatically.

---

## Common operations

### Clear cached comparisons

After changing a TED algorithm or cost model:

```powershell
.venv\Scripts\python.exe -c "from src.storage.mongo_store import MongoStore; print(MongoStore().scripts.delete_many({}).deleted_count, 'cleared')"
```

### Add a new clusterable field

Edit `src/clustering/fields.py` — append to the `_FIELDS` list:

```python
("geography.coastline_km", "Coastline (km)", "Geography", "number", 0.8),
```

Make sure the same path also exists in `config/pipeline.json`'s
`category_layout`, otherwise it won't be populated by the builder.

### Kill a stuck Flask server on port 5050

```powershell
Get-NetTCPConnection -LocalPort 5050 -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `MongoStore().ping()` returns False | `docker compose ps`; restart with `docker compose up -d` |
| `pymongo.errors.OperationFailure: Authentication failed` | `.env` doesn't match `docker-compose.yml`'s env vars |
| Frontend shows old visuals after edit | Hard-refresh (Ctrl+F5); Flask serves static files cached |
| `pip install` hangs in Claude/agent terminal | Run it in a real PowerShell window instead |
| Clustering finishes with N outliers and tiny `n` | A selected field is rare; check `data/analysis/infobox_summary.md` for coverage |
| World map missing tiles for some countries | Check `data/country_numeric_codes.json` — the world-atlas topo keys by ISO numeric |
| `KeyError: (0,)` on Compare with identical sibling subtrees | Fixed in `Tree.path_of` (identity not equality). If it returns, look for any new `.children.index(...)` call — see `docs/08-design-decisions.md` §24 |
| Synthetic tree appears in a cluster run | `_build_all_trees` filter must skip `source == "synthetic"`; confirm the doc has that field set |
| Stale TED result after editing a synthetic tree | `compare()` should set `use_cache = False` when either side is synthetic — restart Flask if you just edited `src/comparison.py` |

---

## References

- Chawathe S., *Comparing Hierarchical Data in External Memory*, VLDB 1999.
- Nierman A. & Jagadish H.V., *Evaluating Structural Similarity in XML Documents*, WebDB 2002.
- Lloyd S.P., *Least Squares Quantization in PCM*, IEEE Trans. IT 1982 (k-means).
- Torgerson W.S., *Multidimensional Scaling: I. Theory and Method*, Psychometrika 1952 (classical MDS).
- wptools: <https://github.com/siznax/wptools>

Course: **IDPA — Intelligent Data Processing and Applications**.
