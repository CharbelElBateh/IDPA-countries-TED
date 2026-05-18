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

## 17. K-means requires classical MDS first; hierarchical does not

K-means' **Update step** is `m_i = mean(x ∈ C_i)` — it has to average
coordinates. Our pairwise distance matrix `D` (built in
`src/clustering/distance.py`) is the weighted mean of type-aware
leaf-distance functions (Levenshtein / log-currency / EMD over a
taxonomy / haversine / …). That mean is **not guaranteed Euclidean**:
the individual components are metric but their combination is generally
not embeddable into `R^k` without distortion.

So we run **classical (Torgerson) MDS** in
`src/clustering/algorithms/kmeans.py:_classical_mds` to turn `D` into
synthetic Euclidean coordinates `X ∈ R^m`:

```
J = I − (1/n) 1·1ᵀ          # centering matrix
B = −½ · J · D² · J         # double-centered Gram matrix
B = V · Λ · Vᵀ              # eigendecomposition
X = V[:, :m] · √Λ[:m]       # keep positive eigenvalues, cap m at 16
```

Axes with non-positive eigenvalues are dropped — that's exactly the
information loss caused by `D` not being Euclidean.

**Hierarchical agglomerative doesn't need MDS** because the
Lance-Williams update only consumes pairwise distances; it never
averages points. `scipy.cluster.hierarchy.linkage` works directly on
the condensed form of `D`.

The natural alternative for k-means would be **k-medoids (PAM)**, which
works directly on `D` (the centroid is the actual data point that
minimizes within-cluster distance). The project moved from k-medoids to
k-means in commit `2b3e3a9` — a deliberate trade of "exact distances"
for "slide-faithful Lloyd's algorithm" + the MDS pre-step.

## 18. Slide-faithful uniform random init, not k-means++

`_random_init` in `kmeans.py` picks `k` distinct rows of `X` uniformly
at random (`rng.choice(n, k, replace=False)`). k-means++ would seed
more evenly using `D²` probabilities, but the course slide spec is
"Randomly choose initial k centroids ... typically among the available
data objects" — uniform random *is* what the slide describes. The
`n_init` restart loop (default 10) is the standard mitigation for
random-init's variance.

## 19. Defensive empty-cluster reseed

Lloyd's Update step is undefined when a cluster is empty (mean of zero
points is `NaN`). The slide doesn't address this. `_lloyd` reseeds
empty clusters to **the point currently farthest from any centroid**
(`argmax of min-distance-to-any-centroid`). This is a one-line
k-means++-style nudge that prevents the NaN trap without changing the
algorithm's normal-case behavior. Documented inline at `kmeans.py:178`.

## 20. Two convergence criteria, mirroring the slide

`_lloyd` stops when **either** criterion fires:

1. `np.array_equal(new_labels, labels)` — no point changed cluster (the
   strictest form of the slide's "few or no objects changed").
2. `abs(prev_sse − sse) ≤ tol` (only if `tol > 0`) — the slide's
   "higher intra-cluster similarity at t+1 than at t", with
   `SSE = Σ_i Σ_{x ∈ C_i} ||x − m_i||²`.

Default `tol = 0.0`, i.e. rely on criterion (1) alone. Criterion (2)
is available as an early-exit knob; it doesn't affect the final result
when (1) fires first, which it usually does for n=192.

## 21. Hierarchical linkages restricted to single / complete / average

`_VALID_LINKAGES = {"single", "complete", "average"}` in
`hierarchical_agglomerative.py`. These are exactly the three
inter-cluster similarity measures taught in slides 79-81:

| linkage  | formula                                | slide |
|----------|----------------------------------------|-------|
| single   | `d(C_i, C_j) = min d(x, y)`            | 79    |
| complete | `d(C_i, C_j) = max d(x, y)`            | 80    |
| average  | `d(C_i, C_j) = mean d(x, y)` (UPGMA)   | 81    |

`ward`, `centroid`, and `median` linkages would also be in scipy's
menu, but they all require **Euclidean coordinates** (they average
*points*, not pairwise distances). Our `D` is non-Euclidean by
construction, so those linkages are rejected with a clear error message
at form-submission time.

Default is `"average"` — slide-recommended ("most robust against noise,
most widely used"). The actual Lance-Williams merge runs inside
`scipy.cluster._hierarchy.linkage_dist_update` (compiled Cython); our
code only **dispatches** at `hierarchical_agglomerative.py:113`
(`Z = linkage(condensed, method=linkage_method)`). The slide-pseudocode
loop ("repeat: merge closest pair; recompute matrix") is correct but
naive O(n³); scipy's `nn_chain` is O(n²) and battle-tested.

## 22. Cost model is a distance-matrix knob, not an algorithm knob

The `cost_model` parameter (`symmetric`, `asymmetric`) is consumed by
`src.distances.relabel_cost`, **upstream** of any clustering algorithm.
It controls:

- `type_mismatch_relabel` — penalty when comparing different leaf types
  (e.g. number vs text).
- `scales` — `currency_full_distance_usd_log10`,
  `coordinates_full_distance_km`, `year_full_distance`,
  `date_full_distance_years`, etc.

Once `relabel_cost` produces a per-pair leaf distance in `[0, 1]`,
`pairwise_distance` takes a weighted mean across selected fields, and
`build_distance_matrix` assembles the N×N matrix `D`. The cost model
**never enters `KMeans.compute` or `HierarchicalAgglomerative.compute`** —
they only see `D`.

UX consequence: the cost-model dropdown was lifted out of the
"Algorithm" card on the cluster form and into its own **"Distance
matrix"** card above the algorithm picker, with a hint stating that the
same cost model yields the same `D` for every algorithm. See
`frontend/templates/cluster_form.html`.

Asymmetric insert/delete costs in `cost_model_asymmetric.json` are
**dead weight for clustering** — clustering never inserts or deletes
tree nodes; it only invokes `relabel_cost` to score leaf pairs. The
asymmetric model only meaningfully differs from symmetric for TED.

## 23. Removed the distance-threshold cut for agglomerative

The cluster form previously offered two ways to cut the dendrogram:
(a) "give me exactly k clusters" (`fcluster(Z, t=k, criterion='maxclust')`)
or (b) "cut at distance threshold h" (`criterion='distance'`). The
distance-threshold input was removed because:

- All other algorithms in the project are parameterized by `k`; mixing
  cut modes complicates the comparison view.
- A reasonable threshold isn't predictable without first inspecting the
  dendrogram — which the user can already do in the result view.
- Keeping a single canonical "k" knob makes the side-by-side
  evaluation honest.

The Python entry point in `hierarchical_agglomerative.py:compute` still
accepts `distance_threshold` as a parameter — only the frontend input
was removed. CLI users can pass it through if they want.

## 24. Identity, not equality, when finding a node in its parent

`Node` is a `@dataclass` — Python generates `__eq__` from every field
except `parent` (excluded via `compare=False`). Two structurally
identical sibling subtrees therefore compare equal under `==`, so
`parent.children.index(node)` — which uses `==` semantically —
returns the index of the **first** equal sibling rather than the
actual one.

For Wikipedia country trees this never bit anyone: every infobox
field has a unique label under its parent, so equality and identity
coincide. Hand-crafted test trees (see §27) like `A(B, B)` or
`root(a, b(c, d), a)` trip it instantly. The collapse propagates: the
script's `mapping` ends up with duplicate source paths, the inverse
`tgt_to_src` dict in `_marks_from_mapping` drops entries, and the
compare-result page raises `KeyError: (0,)` from the path lookup.

Fix: every place that resolves a node's position in `parent.children`
now does it by `is`-identity:

```python
idx = next(i for i, c in enumerate(parent.children) if c is cur)
```

Touched call sites:
- `src/core/tree.py:Tree.path_of` — the root cause; bad paths
  propagated everywhere downstream.
- `src/ted/chawathe.py:_build_script` delete step.
- `src/ted/nierman_jagadish.py:_build_script` delete step.
- `src/comparison.py:_dotted` — the `[i]` sibling-index for
  repeated-label disambiguation.

`src/comparison.py:_marks_from_mapping` also switched its
`tgt_to_src[p]` / `src_to_tgt[p]` lookups to `.get(p)` as
defense-in-depth, so any *future* malformed mapping degrades to
"treat as insert/delete" rather than crashing the comparison page.

## 25. Three similarity metrics on the compare-result page

Course slide Ch. 5 specifies three numbers from a TED computation,
not just the raw cost:

| metric | formula |
|---|---|
| Raw TED integer | `TED(T1, T2)` |
| Normalized inverse | `1 / (1 + TED(T1, T2))` |
| Standard ratio | `1 − TED(T1, T2) / (|T1| + |T2|)` |

`|T|` is the number of nodes in the tree. All three are computed by
`src/comparison.py:similarity_metrics(ted, t1_size, t2_size)` and
exposed on `DirectionResult.metrics`, both for the forward
(`compare.forward.metrics`) and reverse (`compare.reverse.metrics`)
directions. The `to_dict()` payload includes a `metrics` field next
to `total_cost` and `op_counts` so the JSON API at
`/api/compare/<c1>/<c2>` carries them as well.

The compare-result template renders the metrics in a dedicated
"Similarity metrics" card directly under the page header. Asymmetric
cost models (`{insert:1, delete:2, relabel:1}`) produce different
values for A→B vs B→A; the table shows both columns so the asymmetry
is visible at a glance.

## 26. Synthetic / hand-crafted test trees

Trees can be added from the UI for testing the TED pipeline without
relying on Wikipedia infoboxes. Input is **bracket notation** — the
standard format from the course textbook:

```
root(a, b(c, d), e)
```

Whitespace is ignored. Labels match `[A-Za-z0-9_.-]+`. Parsing lives
in `src/synthetic_tree.py`:

- `parse_bracket_tree(text, name=None) → Tree` — produces a `Tree`
  whose nodes are all `structural` (childless nodes are *not*
  marked `leaf` — TED treats both identically and the relabel-cost
  logic stays trivial: cost is `0` when labels match, else the
  `type_mismatch_relabel` constant).
- `node_from_dict(d) → Node` — round-trip from
  `frontend.formatting.tree_to_dict` for documents persisted in Mongo.

Storage is **the same `countries` collection**, with `source =
"synthetic"` and an additional `tree_dict` field carrying the
serialized tree. We considered a separate collection but reusing
`countries` means no changes are needed to the compare-form
dropdowns, the country-detail page, or the patch flow — synthetic
trees just show up alongside the 192 UN member states.

Loading logic in `src/comparison.py:_load_tree` and
`frontend.app._cached_country_tree` short-circuits to
`Tree(node_from_dict(doc["tree_dict"]), name=name)` when the doc has
`source == "synthetic"`, bypassing the full Wikipedia-infobox pipeline.

UI: a "+ Add tree" button on `/countries` toggles a card with a name
input + a bracket-notation `<textarea>`, posting to `/api/trees`.

## 27. Synthetic trees: cache-bypass and clustering-exclusion

Two safety rules apply to synthetic trees so they don't pollute the
rest of the pipeline:

- **Comparison cache is bypassed.** `src/comparison.py:compare`
  detects when either side is synthetic and forces `use_cache = False`
  for that call. Hand-crafted trees are routinely edited (delete +
  re-add with the same name) during testing; serving stale scripts
  out of `edit_scripts` would silently use the previous tree's
  mapping, which is exactly the kind of confusing bug §24 fixed.
  Always recomputing for synthetic trees is cheap (they're tiny)
  and lets the user iterate freely.
- **Excluded from clustering.** `src/clustering/run.py:_build_all_trees`
  skips any document with `source == "synthetic"` before building
  trees. Synthetic trees have no real fields, no `economy.hdi.value`,
  no `geography.coordinates` — they'd either contribute a row of NaNs
  to the distance matrix or be silently dropped as outliers. Either
  way the cluster result would be misleading, so we filter at the
  source.

There's a single chokepoint per concern (`compare` for cache,
`_build_all_trees` for clustering), so the rule lives in exactly one
place each and doesn't need to be threaded through the storage layer.

## 28. Per-leaf-type distance dispatch in `src/distances.py`

`relabel_cost(a, b)` dispatches on `(a.kind, b.kind)` first and then on
`(a.type, b.type)` to a dedicated distance function per leaf type:

| type | distance | normalizer |
|---|---|---|
| `number` | relative diff `abs(a − b) / max(abs(a), abs(b), ε)` | `ε` = `number_min_denom` |
| `percent` | `abs(a − b) / 100` | points are already `[0, 100]` |
| `year` | `abs(a − b) / Y` | `Y` = `year_full_distance` (100) |
| `date` | calendar days / `(Y · 365.25)` | `Y` = `date_full_distance_years` (100) |
| `currency` | `abs(log₁₀ a − log₁₀ b) / S` (falls back to `number` for `≤ 0`) | `S` = `currency_full_distance_usd_log10` (4) |
| `coordinates` | haversine km with `R = 6371 km` | `D` = `coordinates_full_distance_km` (20000) |
| `text`, `wikilink` | iterative Levenshtein on `.lower().strip()` strings, normalized by max length | — |
| `distribution` | `Taxonomy.emd(da, db)` over a hand-curated taxonomy | taxonomy edges |

Every function `min`-clamps at `1.0`. Cross-kind or cross-type pairs
(including `distribution` with different taxonomies) collapse to
`type_mismatch_relabel` — no coercion is attempted. The full table
with the exact formulas lives in
[04-algorithms.md → Cost contract](04-algorithms.md).

This is the single most important property of the clustering input:
**every component of `D[i,j]` is bounded in `[0,1]` and normalized by
a scale that's meaningful for that field's units**, so currency
(spanning 6 orders of magnitude) doesn't dominate text (Levenshtein
≤ 1).
