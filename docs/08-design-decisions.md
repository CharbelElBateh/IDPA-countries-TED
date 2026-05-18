# 08 · Design Decisions

The non-obvious choices and the reasoning behind them.

## 1. Single `Node` class with a `kind` discriminator

Instead of separate `StructuralNode` and `LeafNode` types. Rationale:

- The `EditScript.apply` machinery operates on a uniform interface
  (`label`, `children`, payload fields).
- Walking and copying are simpler with one class.
- Type guards (`is_leaf`, `is_structural`) keep the intent clear at
  call sites.

The downside is that `value`, `type`, `unit`, `trend`, `taxonomy` are
all `None` on structurals. We accept this trade.

## 2. Typed leaves, not wikitext strings

The previous IDPA project (in `old/`) stored leaves as wikitext
strings and did relabel by string equality. This rebuild parses every
leaf into a Python value (number, date, distribution, …) so that the
relabel cost can be **continuous** (`|a − b| / scale`) rather than
binary. This is the single biggest leverage point for meaningful
similarity scores.

## 3. Distributions for `religion`, `ethnic_groups`, `languages`

A multi-value field like `religion = "Sunni 55%, Shia 35%, Christian 10%"`
is parsed into a normalized distribution over a taxonomy. Two
countries' distributions are compared with **tree-EMD over the
taxonomy's edge-distance metric**. Properties this gives us:

- Two countries with the same religions in different proportions get
  a *partial* distance (not 0, not max).
- A Sunni-majority country and a Shia-majority country are *closer*
  than a Muslim-majority and a Christian-majority country
  (siblings under "Islam" vs siblings under different top-level
  branches).
- A religious country vs an irreligious country is *farther* than any
  intra-religious comparison (different top-level branches).

Each taxonomy is hand-curated in `config/pipeline.json`.

## 4. Strict parent-preserving filter (Chawathe only)

Zhang-Shasha's optimal mapping only guarantees *ancestor*-preserving,
which is weaker than *parent*-preserving. Without an explicit move
operation, an "ancestor-preserving" mapping can produce a script that
double-inserts mapped descendants when their parents diverge between
trees.

To keep `EditScript.apply` correct, Chawathe iteratively drops pairs
`(m, n)` whose direct parents aren't themselves mapped to each other.
This sacrifices a small amount of Z-S optimality (≈ 5% on Lebanon ↔
Switzerland) for **guaranteed script applicability**. N&J doesn't
need this filter — its order-preserving alignment is parent-strict
by construction.

## 5. N&J as recursive subtree similarity, not Z-S with split costs

An earlier version of N&J was simply Chawathe's Z-S with the relabel
cost split into `relabel_structure` and `relabel_content` knobs. The
user corrected this: the real N&J **recursively computes subtree
similarity** with an **order-preserving sequence alignment of
children** at each level. This is fundamentally different from Z-S
because it can recognize partial subtree containment naturally; Z-S
can't.

The current N&J is a from-scratch top-down DP with `O(|T1|·|T2|·d)`
memoized calls.

## 6. Subtree-containment cost rule

`cost_insert_subtree(subtree)` returns the *base op* (× weight) — not
`sum(|subtree| × per-node-base × weight)` — when the same subtree
structure-and-content exists in the *other* tree. Same for
`cost_delete_subtree`. This makes a "move" cost ~2 ops total (one
delete + one insert) instead of ~2·|subtree|.

The rule is gated by `config.subtree_similarity.enabled`. The
signature is a recursive tuple of `(kind, label, type, value)` —
identical structure *and* identical leaf payloads.

## 7. Cross-kind safety in N&J

If N&J's recursion ever considers pairing a leaf with a structural,
the pair's cost is set to `delete_subtree + insert_subtree` (so the
alignment is neutral between pairing them and not), and the mapping
extraction *skips* the pair so the script builder emits a delete +
insert. This avoids "Cannot insert into leaf node X" errors when the
DP would otherwise produce an unapplicable mapping.

## 8. `EditScript.mapping` field

The diff-coloring on Compare needs to mark both trees from one source
of truth. The script's `operations` alone aren't enough — they're
*one* representation, not "what corresponds to what". So we added a
`mapping: list[(t1_path, t2_path)]` field to `EditScript` and have
each algorithm populate it. `comparison._marks_from_mapping` derives
both the source and target marks from the mapping.

This also means cached scripts in Mongo need to include the mapping;
older cached records without it fall back to the legacy dotted-path
target-mark logic.

## 9. Path discipline in script construction

`EditScript.apply` applies relabels in order, then deletes
**deepest+rightmost first**, then inserts **shallowest+leftmost+
smallest-position first**. The script builders match this order
exactly:

- Relabel paths = the node's path in T1 (shape is unchanged).
- Delete paths = the node's *original* T1 path. Sorted by `(len,
  path) reverse` at emission time so apply's identical sort produces
  the same order.
- Insert parent paths = `working.path_of(parent)` *after* deletes
  have been simulated. The builder maintains a working copy of T1
  and mutates it during emission to keep paths and positions in
  sync with what `apply` will see.

This invariant is what makes the script applicable.

## 10. Self-contained algorithm files

When a shared `zhang_shasha.py` was extracted, the user asked that
each algorithm file be self-contained instead. Chawathe and N&J each
inline their full algorithm (post-order traversal / recursion,
mapping extraction, script building) so a reader can take one in end-
to-end without flipping between files. The duplicate-code linter
warnings are expected.

## 11. Single `config/pipeline.json`

Every parameter lives in one file: aliases, filter patterns, layout,
serial groups, field types, weights, TED cost models, currency rates,
all four taxonomies. The file is big (~700 lines) but there's no
hunting through multiple config files to understand what a value is
or where it comes from.

## 12. `unmapped/` bucket in the tree

Fields not in `config.category_layout` go to `country/unmapped/<field>`
rather than being silently dropped. This makes it easy to discover
new Wikipedia fields that the layout doesn't yet claim, and the
algorithm can still compare them.

## 13. Currency in USD; trend lifted to a side-channel

`{{increase}} $78.233 billion` is parsed to `(78233000000.0, "USD",
trend=+1)`. The trend marker is **lifted** out of the wikitext into a
dedicated `trend` field on the leaf, so the numeric comparison isn't
contaminated by the marker and the UI can show ▲/▬/▼ separately.

## 14. Frontend caches built trees in-process

Building a country tree from a Mongo doc takes a few ms — not zero.
`frontend.app._cached_country_tree` is an `lru_cache(maxsize=256)`
so repeated visits to `/countries/<name>` and `/compare/<c1>/<c2>`
don't re-parse on every request. Restart the Flask process to
invalidate (or call `clear_caches()` from a route).

## 15. `EditScript` JSON, not custom XML

The previous project used a custom "IDF" XML diff format. This
rebuild dropped that — `EditScript.to_dict()` / `to_json()` is plain
JSON, identical in shape to what the algorithms produce in memory.
Reasons: JSON round-trips through Mongo natively, the in-memory
`EditScript` is the canonical representation, and the IDF format
wasn't doing anything XML-specific.

## 16. The 2D scatter is a lossy view; clustering happens in higher-D

**Status: analysis recorded, no code changed yet.** Trigger: clusters
visually overlap in the 2D scatter — "should it be 3D?"

There are **two distinct embeddings** of the same pairwise distance
matrix, and conflating them is the source of the confusion:

- **Scatter** (`src/clustering/embedding.py`): sklearn **SMACOF MDS**,
  `n_components=2`. Picture only — never fed to an algorithm.
- **k-means space** (`src/clustering/algorithms/kmeans.py`):
  **classical (Torgerson) MDS**, `min(n−1, 16)` positive-eigenvalue
  dimensions. This is what k-means actually partitions.

So k-means can cleanly separate groups along MDS axes 3..16 that the
2-D scatter collapses on top of each other. **The trustworthy
separation metric is the silhouette, which `evaluation.silhouette`
computes on the true distance matrix — not on the 2-D coordinates.**
A low-overlap scatter is reassuring; an overlapping one is *not*
evidence of a bad clustering.

Does 3D help? Only if the classical-MDS **eigenvalue spectrum** has a
meaningful 3rd component. Type-aware non-Euclidean distances
(Levenshtein / EMD / haversine / log-currency) are usually
intrinsically high-dimensional, so 2→3 often recovers little extra
variance, and a static 3D projection needs interactive rotation to be
legible at all.

For the **single-feature** design (one field only):

- a *numeric* field (e.g. `economy.hdi.value`) is essentially **1-D**
  — the 2-D MDS already fabricates a second axis; 3-D would fabricate
  two. A 1-D strip/histogram is the honest view.
- a *categorical* field (e.g. `government.type`) yields only a few
  distinct distance values, so many countries get **identical
  coordinates and stack**. That is a *ties* problem (fix with
  jitter/opacity), not a dimensionality problem.

Recommended order of work (deferred): (1) show % variance explained by
the first 2/3 MDS eigenvalues next to the plot; (2) jitter +
transparency for coincident points; (3) 1-D view for numeric single
features; (4) optional t-SNE/UMAP (sklearn has `TSNE`) which preserves
*cluster* separation better than metric MDS; (5) 3D only as a later,
evidence-gated, **interactive/rotatable** mode. See
`design_requirements.md` §4.7.1 for the requirement-side note.
