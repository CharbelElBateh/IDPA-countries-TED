# 01 · System Architecture

## High-level data flow

```
   Wikipedia (wptools)
         │
         ▼
   ┌──────────────────┐
   │ scripts/         │   one-shot ingestion
   │  ingest_         │
   │  countries.py    │
   └────────┬─────────┘
            │  upsert
            ▼
   ┌──────────────────┐
   │ MongoDB          │   collection: countries
   │  (Docker)        │   _id = country name
   └────────┬─────────┘
            │  read on demand
            ▼
   ┌──────────────────┐
   │ src.builder      │   build_country_tree(name, infobox)
   │  + parsing       │
   │  + preprocessing │
   │  + taxonomy      │
   │  + typed values  │
   └────────┬─────────┘
            │  Tree
            ▼
   ┌──────────────────┐
   │ src.ted          │   chawathe / nierman_jagadish
   │  algorithms      │
   └────────┬─────────┘
            │  EditScript (with mapping)
            ▼
   ┌──────────────────┐
   │ MongoDB          │   collection: edit_scripts
   │  cache           │   _id = c1__c2__algo__cost_model
   └────────┬─────────┘
            │  served via /api
            ▼
   ┌──────────────────┐
   │ frontend (Flask) │   3 tabs: Countries / Compare / Patch
   │  + D3 tree viz   │
   └──────────────────┘
```

## Module layout

```
IDPA-Project/
├── config/
│   └── pipeline.json           # single source of truth for everything
├── data/
│   ├── analysis/               # one-off analysis artifacts
│   └── (runs/, etc.)
├── scripts/
│   ├── ingest_countries.py     # wptools → Mongo
│   └── analyze_infoboxes.py    # post-ingestion analysis
├── src/
│   ├── config.py               # loader + cost-model resolver
│   ├── storage/
│   │   └── mongo_store.py      # MongoStore (countries + edit_scripts)
│   ├── parsing/
│   │   ├── wikitext.py         # strip refs, resolve [[…]], lift trends
│   │   ├── typed.py            # number / date / currency / coords parsing
│   │   └── distribution.py     # religion / ethnicity / language → distribution
│   ├── taxonomy.py             # Taxonomy + TaxonomyRegistry + EMD
│   ├── preprocessing/
│   │   ├── normalize.py        # alias map + filter patterns
│   │   └── grouping.py         # fold serial fields (leader_title* + leader_name*)
│   ├── builder.py              # build_country_tree(name, infobox)
│   ├── distances.py            # typed relabel costs + field weights
│   ├── core/                   # Node, Tree, Action, EditScript
│   ├── ted/
│   │   ├── base.py             # TEDAlgorithm ABC
│   │   ├── registry.py         # @register + get_algorithm
│   │   ├── chawathe.py         # Zhang-Shasha, self-contained
│   │   └── nierman_jagadish.py # recursive subtree similarity, self-contained
│   └── comparison.py           # orchestrator: trees + algorithm → ComparisonResult
├── frontend/
│   ├── app.py                  # Flask routes
│   ├── formatting.py           # tree_to_dict + value formatters
│   ├── templates/              # base, countries_list, country_detail, compare_*, patch_*
│   └── static/
│       ├── style.css
│       ├── tree.js             # reusable D3 TreeView class
│       ├── compare.js          # Compare-page logic
│       └── patch.js            # Patch-page logic
└── tests/
    ├── test_core.py
    ├── test_parsing.py
    ├── test_taxonomy.py
    ├── test_builder.py
    └── test_ted.py
```

## Request flow (Compare tab)

1. User picks two countries, an algorithm, and a cost model.
2. Browser hits `/compare/<c1>/<c2>?algorithm=…&cost_model=…`.
3. Server calls `src.comparison.compare`:
   - Loads `Tree` for each country (`build_country_tree`).
   - Checks `edit_scripts` collection by `_id` —
     `c1__c2__algo__cost_model`.
   - If cached: deserialize `EditScript.from_dict`.
   - Else: instantiate the algorithm via `get_algorithm(name)`,
     run `compute()`, store the result in Mongo.
   - Builds `ComparisonResult` containing both directions + diff marks.
4. Server returns an HTML shell; the browser fetches
   `/api/compare/<c1>/<c2>?…` to populate the two D3 trees with the
   per-node mark dict.
5. Toggle A→B / B→A in the UI swaps the marks and labels client-side
   without a re-fetch.

## Frontend layers

- **`TreeView`** (in `tree.js`) is a reusable class with two
  factories: `fromUrl(containerId, url, opts)` and
  `fromData(containerId, data, opts)`. `opts.marks` is the
  dotted-path → mark-name dict.
- **`compare.js`** owns the side-by-side wiring and the direction
  toggle.
- **`patch.js`** owns the three script sources (paste / upload /
  cached comparison) and posts to `/api/patch`.

## Storage layers

- **`countries`** (`_id = country_name`): raw infobox dict from
  `wptools`, plus `wikitext` and metadata. Driven by
  `scripts/ingest_countries.py`.
- **`edit_scripts`** (`_id = c1__c2__algorithm__cost_model`): the
  computed `EditScript` for the *forward* direction plus its
  *reverse*. Includes the algorithm's node mapping.
