# 07 · Storage (MongoDB)

A single MongoDB instance runs in Docker (see `docker-compose.yml`).
Two collections back the application: `countries` and `edit_scripts`.

## Docker stack

`docker-compose.yml` brings up:

- `mongo:7` on `127.0.0.1:27017`, named volume `idpa_mongo_data`.
- `mongo-express:1.0.2` on `127.0.0.1:8081` (admin UI, basic-auth).

Credentials, URI, DB name, and collection names come from `.env`
(template in `.env.example`):

```
MONGO_INITDB_ROOT_USERNAME=root
MONGO_INITDB_ROOT_PASSWORD=changeme
MONGO_DB_NAME=idpa
MONGO_URI=mongodb://root:changeme@localhost:27017/?authSource=admin
MONGO_COUNTRIES_COLLECTION=countries
MONGO_SCRIPTS_COLLECTION=edit_scripts
```

## `MongoStore` (`src/storage/mongo_store.py`)

Thin wrapper around `pymongo.MongoClient` exposing the two
collections.

### Methods

- `ping()` → bool. Used by `frontend.app` and the smoke tests.
- `ensure_indexes()` — creates unique indexes; idempotent.
- **Countries**:
  - `upsert_country(name, infobox, template, wikitext, source, extra)`
  - `get_country(name) → doc | None`
  - `list_country_names() → list[str]`
  - `iter_countries(projection) → cursor`
  - `count() → int`
- **Scripts**:
  - `script_key(c1, c2, algo, cost_model) → str` (deterministic `_id`)
  - `get_edit_script(c1, c2, algo, cost_model) → doc | None`
  - `save_edit_script(c1, c2, algo, cost_model, forward, reverse) → str`
  - `list_edit_scripts() → list[summary]`
  - `delete_edit_script(c1, c2, algo, cost_model) → int`
  - `drop_collection()` — destructive, used in dev/tests.

## Collection: `countries`

One document per UN member state, keyed by the canonical English name
(e.g. `Lebanon`, `Switzerland`, `United_States`).

```json
{
  "_id":         "Lebanon",
  "name":        "Lebanon",
  "infobox":     { "<field>": "<wikitext>", ... },
  "template":    "Infobox country",
  "wikitext":    "<full page wikitext>",
  "source":      "wikipedia",
  "ingested_at": <UTC datetime>
}
```

### Synthetic test trees (same collection)

Hand-crafted trees added from the `/countries` "+ Add tree" UI share
this collection, distinguished by `source = "synthetic"`. The
`infobox` field is empty and a `tree_dict` field carries the
serialized tree (round-trip of `frontend.formatting.tree_to_dict`).

```json
{
  "_id":         "T1",
  "name":        "T1",
  "infobox":     {},
  "template":    null,
  "wikitext":    "A(B,C(D,E))",      // original bracket-notation input
  "source":      "synthetic",
  "tree_dict":   {
    "kind":     "structural",
    "label":    "A",
    "children": [ ... ]
  },
  "ingested_at": <UTC datetime>
}
```

Loaders short-circuit on `source == "synthetic"`:

- `src/comparison.py:_load_tree` — `Tree(node_from_dict(doc["tree_dict"]), name=name)`,
  skipping `build_country_tree`.
- `frontend.app._cached_country_tree` — same shortcut.
- `src/clustering/run.py:_build_all_trees` — **skips** synthetic
  documents so they don't enter the distance matrix or any cluster
  run.
- `src/comparison.py:compare` — forces `use_cache = False` when
  either side is synthetic (the `edit_scripts` collection is not
  trusted for hand-crafted trees because they're frequently edited).

See [08-design-decisions.md §26-§27](08-design-decisions.md).

### Indexes

- Unique on `name`.
- Ascending on `ingested_at`.

### Volume

- 192 documents (192/192 UN member states).
- ~80 fields per document on average.
- `wikitext` is the full page (megabytes per country). The infobox
  dict itself is small (~10 KB).

### Ingestion

`scripts/ingest_countries.py` reads
`src/un_member_states.txt`, fetches via `wptools.page(name).get_parse()`,
extracts `data["infobox"]`, and upserts. The country list was bootstrapped
from a prior project's filenames and has BOM stripping in the loader.
Re-running the script with `--skip-existing` is a no-op for already-
ingested countries.

## Collection: `edit_scripts`

One document per (country pair, algorithm, cost_model) combination.

```json
{
  "_id":          "Lebanon__Switzerland__chawathe__symmetric",
  "country1":     "Lebanon",
  "country2":     "Switzerland",
  "algorithm":    "chawathe",
  "cost_model":   "symmetric",
  "forward":      { ...EditScript.to_dict() },
  "reverse":      { ...EditScript.to_dict() },
  "computed_at":  <UTC datetime>
}
```

The `_id` makes lookups deterministic — `MongoStore.script_key`
constructs it. Both directions are stored together so the UI's A↔B
toggle is a single fetch.

### `EditScript.to_dict()` shape (recap)

```json
{
  "source": "Lebanon",
  "target": "Switzerland",
  "total_cost": 40.13,
  "mapping": [ [[…], […]], … ],
  "operations": [
    {
      "op": "relabel",
      "path": [1, 0],
      "cost": 0.4,
      "position": null,
      "old_label": "capital",
      "old_value": "Beirut",
      "old_type": "wikilink",
      "old_taxonomy": null,
      "new_node": { "kind": "leaf", "label": "capital", "value": "Bern", "type": "wikilink", ... }
    },
    ...
  ]
}
```

### Indexes

- Unique compound on `(country1, country2, algorithm, cost_model)`.
- Ascending on `computed_at`.

### Cache invalidation

Hand-managed. Run

```python
from src.storage.mongo_store import MongoStore
MongoStore().scripts.delete_many({})
```

after changing any algorithm or cost model. The UI's
"cached comparisons" table reflects this collection live.

## Future tables (placeholders)

- `vectors` — country feature vectors for clustering (planned but
  not implemented in this rebuild).
- `clusters` — clustering results.
