# IDPA Project — Documentation Index

This directory holds the full design + implementation notes for the IDPA
country-infobox comparison pipeline. Files are ordered for a top-down
read; later docs assume the earlier ones.

| File | Purpose |
|------|---------|
| [00-context.md](00-context.md) | What the project is, the dataset, the user, why this exists. |
| [01-architecture.md](01-architecture.md) | System overview, module layout, request flow. |
| [02-data-model.md](02-data-model.md) | `Node`, `Tree`, `Action`, `EditScript` — fields, invariants, JSON shape. |
| [03-pipeline.md](03-pipeline.md) | Mongo → cleaned dict → typed values → `Tree`. Every stage in order. |
| [04-algorithms.md](04-algorithms.md) | TED (Chawathe Z-S; Nierman & Jagadish recursive subtree similarity) + clustering (k-means with classical-MDS embedding; hierarchical agglomerative single / complete / average). |
| [05-configuration.md](05-configuration.md) | Annotated reference for `config/pipeline.json`. |
| [06-frontend.md](06-frontend.md) | Flask app, four tabs (Countries / Compare / Patch / Cluster), D3 tree viz, diff coloring. |
| [07-storage.md](07-storage.md) | MongoDB collections (`countries`, `edit_scripts`) and their schemas. |
| [08-design-decisions.md](08-design-decisions.md) | Why things are the way they are — explicit rationale for choices that aren't self-evident. |
| [09-setup.md](09-setup.md) | First-time setup, running locally, testing, debugging. |

## Quick orientation

- **Goal**: compare any two of the 192 UN member states by computing a
  Tree Edit Distance on their Wikipedia infoboxes, and visualize the
  diff.
- **Stack**: Python 3.12+, Flask, MongoDB (in Docker), D3 v7, `wptools`
  for ingestion, pymongo, pytest.
- **Status**: end-to-end working — ingestion, tree building, both TED
  algorithms (Chawathe and Nierman & Jagadish), three slide-spec
  similarity metrics (raw TED, `1/(1+TED)`, `1−TED/(|T1|+|T2|)`),
  edit-script application, four frontend tabs (Countries / Compare /
  Patch / Cluster), MongoDB caching, hand-crafted bracket-notation
  test trees, 111 passing tests.

Read [00-context.md](00-context.md) first.
