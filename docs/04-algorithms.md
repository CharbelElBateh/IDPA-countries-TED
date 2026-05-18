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
`src.distances.relabel_cost(a, b, taxonomies, cost_model)`,
which dispatches by leaf type:

| type | distance function |
|------|-------------------|
| `number` | normalized relative diff |
| `percent` | `|a-b|/100` |
| `year` | `|a-b|/100` (capped at 1) |
| `date` | `|a-b|.days / (100 · 365)` (capped at 1) |
| `currency` | log10-scale, `|log a − log b| / 4` (capped at 1) |
| `coordinates` | haversine km / 20000 |
| `wikilink`, `text` | normalized Levenshtein |
| `distribution` | tree-EMD over the taxonomy's ground-distance metric |

All distances are in `[0, 1]`. Multiply by `type_mismatch_relabel`
when kinds differ.

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
