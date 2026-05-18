# 04 · Algorithms

Two TED algorithms ship with the project. Both implementations are
**self-contained** — each file inlines its full algorithm (post-order
traversal / recursive DP, mapping extraction, script construction) so
a reader can take it in end-to-end. This is a deliberate user
preference; the duplicate-code linter warnings on these files are
expected.

## Cost contract (shared)

Both algorithms receive the same shape of arguments:

```python
compute(t1, t2, *, config, taxonomies, cost_model) -> EditScript
```

Where `cost_model` is the resolved dict from
`src.config.resolve_cost_model(name, cfg)`. Available models:
`symmetric`, `asymmetric` (see `05-configuration.md`).

The per-operation base costs are scaled by **field weights** taken
from `config.field_weights` — see `src.distances.field_weight(path,
weights)`. Longest-prefix match wins; default 1.0.

The leaf-content comparison uses
`src.distances.relabel_cost(a, b, *, taxonomies, cost_model)`. It
**dispatches by the two nodes' kinds and types** before computing
anything:

| pair | result |
|---|---|
| structural ↔ structural, labels equal | `0.0` |
| structural ↔ structural, labels differ | `type_mismatch_relabel` |
| structural ↔ leaf (kinds differ) | `type_mismatch_relabel` |
| leaf ↔ leaf, types differ | `type_mismatch_relabel` |
| leaf ↔ leaf, distribution but different taxonomies | `type_mismatch_relabel` |
| leaf ↔ leaf, same type | per-type distance below |

All per-type distance functions return a value in `[0, 1]`. Every
non-trivial result is **min-clamped at 1.0** so a wildly large gap
can't dominate the weighted mean. The scale knobs come from the
resolved `cost_model["scales"]` block (see
[05-configuration.md](05-configuration.md)); defaults are shown in
parentheses.

| type | distance function | scale knob (default) |
|------|-------------------|----------------------|
| `number` | `min(1, abs(a − b) / max(abs(a), abs(b), ε))` — relative diff with a floor `ε` on the denominator so `0 vs 0` doesn't divide by zero. | `number_min_denom` (`1e-9`) |
| `percent` | `min(1, abs(a − b) / 100)` — points are already in `[0, 100]`. | — |
| `year` | `min(1, abs(a − b) / Y)` — integer years (BCE negative). | `year_full_distance` (`100`) |
| `date` | `min(1, days(a, b) / (Y · 365.25))` — calendar-day delta normalized over `Y` years. Returns `type_mismatch_relabel` if either value isn't a `datetime.date`. | `date_full_distance_years` (`100`) |
| `currency` | `min(1, abs(log₁₀ a − log₁₀ b) / S)` — log-scale handles 6 orders of magnitude between micro-states and superpowers. **Falls back to** `number_distance` if either side is `≤ 0` (logs are undefined). | `currency_full_distance_usd_log10` (`4`, i.e. a `10000×` ratio = `1.0`) |
| `coordinates` | `min(1, haversine(a, b) / D)` — great-circle distance in km using Earth radius `6371 km`. | `coordinates_full_distance_km` (`20000` ≈ antipodal) |
| `wikilink`, `text` | `lev(a', b') / max(len(a'), len(b'))` where `x' = x.lower().strip()` — iterative Levenshtein on case- and whitespace-folded strings, normalized by the longer length. Returns `0.0` if both empty or both equal after folding. | — |
| `distribution` | `Taxonomy.emd(da, db)` — tree-EMD over the taxonomy's ground-distance metric (`religion` / `language` / `ethnicity` / `government`). Distribution payloads come in as `list[{path, weight}]` and are coerced to `dict[tuple[str, ...], float]` before the EMD call. | — taxonomy structure is the scale |

Notes that aren't in the table:
- The function **does not multiply the per-type result by `type_mismatch_relabel`** — that constant is only the substitute when no per-type function applies (kind/type mismatch).
- The final TED cell cost is `relabel_cost(a, b) × field_weight(path, weights)` — see `src.distances.field_weight`. Field weights use longest-prefix match against `config.field_weights` and fall back to `1.0`.
- A leaf with type `empty` is never emitted by the builder (`_attach_scalar` returns early), so it doesn't appear in `relabel_cost`. An unknown type collapses to `type_mismatch_relabel`.

## Algorithm 1: Chawathe (Zhang-Shasha)

File: `src/ted/chawathe.py`.

Reference: S. Chawathe, *Comparing Hierarchical Data in External
Memory*, VLDB 1999.

Bottom-up dynamic programming on post-order numberings, using
**keyroots** to bound the set of forest-distance matrices that need to
be computed.

### Steps

1. **Linearize both trees** into post-order via `_PostOrderInfo.of`:
   - `nodes[i]` — the `i`-th node in post-order.
   - `lld[i]` — post-order index of the leftmost leaf descendant of
     `nodes[i]`.
   - `keyroots` — for each distinct `lld` value, the largest `i` with
     that value. These are the only nodes for which we need
     forest-distance matrices.

2. **For each keyroot pair** `(i, j)` (iterated in increasing order),
   compute a forest-distance matrix `fd` with `(i − lld[i] + 2)` rows
   and `(j − lld[j] + 2)` columns:
   - Row 0 / column 0: cumulative delete / insert costs.
   - Cell `(r, c)` for `m = lld[i] + r − 1`, `n = lld[j] + c − 1`:
     - If `lld[m] == lld[i]` *and* `lld[n] == lld[j]`: stay in this
       forest. Take min of delete / insert / relabel.
     - Else: defer to `td[m][n]` (the treedist of the subtree pair),
       which a smaller keyroot pair has already computed.
   - For "M" choices, set `td[m][n] = fd[r][c]`.

3. **Extract mapping** by backtracking. Push the root pair `(|T1|−1,
   |T2|−1)` onto a stack, walk back through each forest's BT records,
   recording every "M" pair. "T" decisions push the subtree pair onto
   the stack to continue.

4. **Filter to strict parent-preserving** mapping (`_strict_parent_
   preserving`). Z-S's optimal mapping only guarantees the weaker
   "ancestor preserving" property, but our `EditScript` model lacks
   move operations — so any pair `(M, N)` whose parents aren't
   themselves mapped to each other has to be dropped. Iterates until
   fixed-point (usually 1–2 passes).

5. **Build the script** by simulation (`_build_script`):
   - Start with a working copy of T1 and a node-correspondence dict.
   - Emit **relabels** (paths in T1) for every mapped pair whose
     payload changed; apply them to the working copy.
   - Emit **deletes** for every unmapped T1 node, suppressing
     descendants of already-deleted ancestors. Paths are the
     **original T1 paths**, sorted in `EditScript.apply`'s order
     (`(len(path), path) reverse`) so the script replays correctly.
   - Emit **inserts** for every unmapped T2 node, shallowest-first.
     Parent path is the working tree's `path_of` after deletes have
     been applied; a `inserted_via_cascade` set prevents
     double-inserting T2 descendants of an already-inserted subtree.

### Caveats

- Doesn't model "moves". A subtree that exists in both trees at
  different positions costs |X| delete + |X| insert.
- The strict-parent-preserving filter sacrifices a small amount of
  Z-S optimality for guaranteed script applicability. In practice the
  loss is small (~5% in Lebanon ↔ Switzerland).

## Algorithm 2: Nierman & Jagadish (recursive subtree similarity)

File: `src/ted/nierman_jagadish.py`.

Reference: A. Nierman & H. V. Jagadish, *Evaluating Structural
Similarity in XML Documents*, WebDB 2002.

A **top-down** recursive DP that computes a similarity score per
subtree pair, with **order-preserving sequence alignment of children**
at each level (Selkow-style). Naturally captures *subtree
containment*: a subtree present in both trees is recognized as a unit
rather than as a sum of node operations.

### The recurrence

```
D(a, b) =
    relabel(a, b)                                  if both leaves
    delete_subtree(a) + insert_subtree(b)          if kinds differ
    relabel(a, b) + align(a.children, b.children)  otherwise
```

`align(c1, c2)` is a sequence-alignment DP:

```
F[i][j] = min(
    F[i-1][j] + delete_subtree(c1[i-1]),
    F[i][j-1] + insert_subtree(c2[j-1]),
    F[i-1][j-1] + D(c1[i-1], c2[j-1])
)
```

with row/column 0 being cumulative delete-from-left / insert-from-left.

Each `D(a, b)` call is memoized on `(id(a), id(b))`, so the total work
is `O(|T1|·|T2|·max_outdegree)`.

### Subtree-containment rule

`cost_delete_subtree(node)` returns:

- `delete_base × move_cost_factor × weight(path)` if `_subtree_
  signature(node)` is found in T2's subtree-signature set
  (it's a *move*, not a destroy).
- Otherwise, `sum(cost_delete_node(n) for n in node.walk())`.

Mirror for `cost_insert_subtree`. The signature is a recursive
hashable tuple of `(kind, label, type, value)` so it captures
both structure and content.

Controlled by `config.subtree_similarity`:

```json
{ "enabled": true, "move_cost_factor": 1.0 }
```

Set `enabled: false` to recover the classic Selkow-style per-node
sum.

### Cross-kind safety

If the recursion considers pairing a leaf with a structural, the cost
of that "pair" is set to `delete_subtree(a) + insert_subtree(b)` — the
same as not pairing at all. The mapping extraction (`_extract_mapping`)
**skips** kind-mismatched pairs so the script builder emits a delete +
insert rather than an impossible relabel. (Relabel can't change a
node's `kind`; trying to insert into a leaf parent would raise.)

### Script construction

Same shape as Chawathe's — same `_build_script` style, same
parent-correspondence simulation, same insert-cascade dedup, same
ordering choices to match `EditScript.apply`. N&J's mapping is
already strictly parent-preserving by construction (the alignment is
order-respecting), so no `_strict_parent_preserving` filter is needed.

## Three similarity metrics (slide Ch. 5)

For *any* TED computation, three numbers are reported by
`src/comparison.py:similarity_metrics(ted, |T1|, |T2|)` —

| metric | formula | range |
|---|---|---|
| Raw TED | `TED(T1, T2)` | `[0, ∞)` |
| Normalized inverse | `1 / (1 + TED)` | `(0, 1]` |
| Standard ratio | `1 − TED / (|T1| + |T2|)` | typically `[0, 1]` |

`|T|` is the node count returned by `Tree.size()`. The metrics are
attached to `DirectionResult.metrics` so both the forward and reverse
direction expose all three independently (asymmetric cost models give
distinct A→B / B→A values). The `/api/compare/<c1>/<c2>` JSON payload
includes them under each direction's `metrics` key, and the
compare-result page renders them as a 3-row table directly below the
page header. See [08-design-decisions.md §25](08-design-decisions.md).

## EditScript: the `mapping` field

Both algorithms populate `EditScript.mapping` with `(t1_path,
t2_path)` tuples for every matched pair. The frontend uses this to
mark **both** trees from a single source of truth — a node in the
source whose `path` isn't in the mapping is colored `delete`; a node
in the target whose `path` isn't in the mapping is colored `insert`;
any mapped pair whose payloads differ is colored `relabel` *on both
sides*. See `src.comparison._marks_from_mapping`.

## Quick numbers (Lebanon ↔ Switzerland)

| Algorithm | Cost model | Forward | Reverse | Mapping size |
|---|---|---:|---:|---:|
| chawathe | symmetric | 40.1 | 40.1 | 71 |
| chawathe | asymmetric | 45.5 | 43.1 | 62 |
| nierman_jagadish | symmetric | 51.4 | 56.3 | 78 |
| nierman_jagadish | asymmetric | 71.6 | 61.6 | 84 |

Both produce a patched tree whose size matches the target tree exactly
(99 forward, 123 reverse). N&J finds more pairs (78 vs 71) thanks to
its order-preserving alignment and subtree containment.

## Performance

- Chawathe on Lebanon ↔ Switzerland (123 vs 99 nodes): ~1.3 s per
  direction. The hot loop is the nested keyroot iteration in Python.
- N&J on the same pair: ~600 ms per direction (the recursion fans out
  less than the full keyroot grid for trees of our shape).
- Both are cached in Mongo, so the second run is instant.

# Clustering algorithms

The clustering pipeline (`src/clustering/`) groups the 192 countries on
a single chosen field. Two algorithms ship today, both slide-faithful
(course slides Ch. 10 §5.1 and §5.2).

## Distance matrix `D`

Both algorithms consume the same N×N symmetric matrix in `[0, 1]`,
built by `src/clustering/distance.py:build_distance_matrix`.

`src/clustering/run.py:_build_all_trees` is the single chokepoint
that decides *which* documents enter the pipeline. It skips any
document with `source == "synthetic"` so hand-crafted test trees
(see [08-design-decisions.md §26-§27](08-design-decisions.md)) don't
contribute rows of NaN to `D` — only real Wikipedia countries are
clustered.

The matrix itself:

```
relabel_cost(a, b)              -> per-leaf typed distance in [0, 1]
                                   (Levenshtein / log-currency / EMD /
                                    haversine / |a-b|/scale / …)
pairwise_distance(c1, c2)       -> Σ w_f · d_f  /  Σ w_f   over chosen fields
build_distance_matrix(trees)    -> D : (N, N), symmetric, zero diagonal
```

The `cost_model` parameter only affects `relabel_cost`'s **scales**
(currency log range, coordinate full-distance km, year window, etc.) —
it does **not** enter the clustering algorithms themselves. See
[08-design-decisions.md §22](08-design-decisions.md).

## Algorithm 3: K-means (Lloyd's)

File: `src/clustering/algorithms/kmeans.py`.

Reference: course slide Ch.10 §5.1 ("img_2.png" / `Kmeans.txt`).
Classical Lloyd's algorithm with **uniform random initialization from
data points** (slide-spec; not k-means++).

### Steps

```
Init:    Pick k distinct data rows uniformly at random as centroids.
Assign:  C_i = { x_p : argmin_i ||x_p − m_i||_2 }
Update:  m_i^(t+1) = (1 / |C_i^(t)|) · Σ_{x ∈ C_i^(t)} x
Stop:    (1) no point changed cluster between t and t+1, OR
         (2) SSE drop below tol, where
             SSE = Σ_i Σ_{x ∈ C_i} ||x − m_i||²
```

`n_init` restarts (default 10), final pick = lowest-SSE run.

### Classical MDS pre-step (project glue, not slide)

K-means needs Euclidean coordinates to compute the Update mean. Our
`D` is non-Euclidean. `_classical_mds` embeds `D` into `R^m`:

```
J = I − (1/n) 1·1ᵀ           # centering matrix, (n, n)
B = −½ · J · D² · J          # double-centered Gram, (n, n)
B = V · Λ · Vᵀ               # eigendecomposition
X = V[:, :m] · √Λ[:m]        # keep positive eigenvalues; cap m ≤ 16
```

Axes with non-positive eigenvalues are dropped — the standard
truncation for non-Euclidean inputs. This is the **only** information
loss in the clustering pipeline.

### Empty-cluster reseed

When a cluster ends up empty after assignment, `_lloyd` reseeds its
centroid to the point currently farthest from any other centroid
(defensive; slide doesn't specify). Without this, the next Update step
would yield `mean([])` = NaN.

### Quick numbers (single-feature on `economy.hdi.value`, k=5, default cost model)

| metric | value |
|---|---:|
| N (after outlier removal) | ~190 |
| MDS dims kept (`m`) | 16 (cap) |
| Iterations per restart | typically 5-15 |
| n_init restarts | 10 (default) |
| Wall-clock | < 100 ms |

## Algorithm 4: Hierarchical Agglomerative

File: `src/clustering/algorithms/hierarchical_agglomerative.py`.

Reference: course slide Ch.10 §5.2 (slides 56-81). Bottom-up merge
loop, slide pseudocode (slide 61):

```
1. Compute inter-cluster similarity matrix
2. Each data object is its own cluster
3. Repeat:
4.   Merge the two clusters with maximum similarity (= minimum distance)
5.   Recompute the similarity matrix
6. Until stopping rule (none -> continue to one cluster)
```

### Dispatch to scipy

Our code at `hierarchical_agglomerative.py:113`:

```python
condensed = squareform(D, checks=False)              # upper triangle of D
Z         = linkage(condensed, method=linkage_method) # the merge loop
```

`Z` has shape `(N-1, 4)`; row `k` is the k-th merge step:

| column | meaning |
|--------|---------|
| `Z[k, 0]` | id of first merged cluster |
| `Z[k, 1]` | id of second merged cluster |
| `Z[k, 2]` | merge distance (dendrogram height) |
| `Z[k, 3]` | leaf count in the new cluster |

The actual Lance-Williams update — *where the `min`/`max`/`mean`
formula is applied* — runs inside scipy's compiled
`_hierarchy.pyx:nn_chain` (O(n²) for these three linkages). The
slide-pseudocode loop is correct but naive O(n³); we delegate to scipy
because the merge bookkeeping is mechanical and the formula is the
same.

### Linkage methods (slides 79-81)

| method     | formula                                              | slide |
|------------|------------------------------------------------------|-------|
| `single`   | `d(C_i, C_j) = min  d(x, y)`,  x ∈ C_i, y ∈ C_j      | 79    |
| `complete` | `d(C_i, C_j) = max  d(x, y)`,  x ∈ C_i, y ∈ C_j      | 80    |
| `average`  | `d(C_i, C_j) = mean d(x, y)` (UPGMA)                 | 81    |

`ward`, `centroid`, and `median` linkages are **rejected** — they need
Euclidean coordinates (they average points, not pairwise distances)
and our `D` is non-Euclidean.

Default is `"average"` — slide-recommended ("most robust against noise,
most widely used").

### Stopping rule

`fcluster(Z, t=k, criterion="maxclust")` cuts the dendrogram to leave
exactly `k` clusters. (The `criterion="distance"` variant for cutting
at a fixed height is implemented in the Python entry point but **not
exposed in the frontend** — see [08-design-decisions.md §23](08-design-decisions.md).)

scipy returns 1-indexed cluster labels; we shift to 0-indexed to align
with k-means and the frontend palette `--c0..--c9`.

## Choosing between them

| | k-means | agglomerative |
|---|---|---|
| Output | flat partition | full merge tree (dendrogram) |
| Requires k upfront | yes | no (cut anywhere) |
| Direct on `D` | no (needs MDS) | yes |
| Sensitivity to init | high (mitigated by `n_init`) | none (deterministic given linkage) |
| Complexity | O(n·k·m·iters·n_init) | O(n² log n) |
| Best for | "how do these 192 split into 5 groups?" | "show me the merge structure" |
