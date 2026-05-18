"""Chawathe (VLDB 1999) — LD-pair tree edit distance, exactly as taught.

Reference: S. Chawathe, "Comparing Hierarchical Data in External Memory",
VLDB 1999. The version implemented here is the **LD-pair dynamic
program** from the course slides (img.png). It is a constrained
string-edit-distance computed on the (Label, Depth) linearization of
each tree, where the depth comparisons enforce tree structure.

================================================================
Mapping the code to the slide pseudocode
================================================================

Slide:

    Input:  Tree LD-pair representations  A* and B*
    Output: Edit distance between A* and B*,  TED(A*, B*)

    Begin
        Dist[][] = new |A*||B*|
        Dist[0][0] = 0
        For (i = 1; i <= |A*|; i++) {                              // line 4
            Dist[i][0] = Dist[i-1][0] + Cost_del(A_i*)
        }
        For (j = 1; j <= |B*|; j++) {                              // line 5
            Dist[0][j] = Dist[0][j-1] + Cost_ins(B_j*)
        }
        For (i = 1; i <= |A*|; i++)
        {
            For (j = 1; j <= |B*|; j++)
            {
                Dist[i][j] = min{
                    If Condition_1 true:  Dist[i-1][j-1] + Cost_upd(A_i*, B_j*)
                    If Condition_2 true:  Dist[i-1][j]   + Cost_del(A_i*)
                    If Condition_3 true:  Dist[i][j-1]   + Cost_ins(B_j*)
                }
            }
        }
        Return Dist[|A*|][|B*|]
    End

    Chawathe conditions:
        Condition_1:  A[i].d == B[j].d
        Condition_2:  (A[i].d >= B[j].d)  or  (j == |B|)
        Condition_3:  (A[i].d <= B[j].d)  or  (i == |A|)

Step-by-step:

* "LD-pair representation A*" = ``_ld_pairs(tree)``: walk the tree in
  PRE-ORDER and emit one (node, depth) entry per node. Both children
  appear after their parent, in left-to-right order, so the resulting
  list mirrors how a reader would scan the tree top-down.
* ``Dist[i][j]`` = ``_dist[i][j]`` in ``_chawathe_ld_pair_dp`` — cost
  of editing the prefix ``A[0..i-1]`` into ``B[0..j-1]``.
* Slide line 1 (``Dist[0][0] = 0``)            -> ``_dist[0][0] = 0.0``
* Slide line 4 (init delete row)               -> ``for i in range(1, n+1): ... cost_delete``
* Slide line 5 (init insert column)            -> ``for j in range(1, m+1): ... cost_insert``
* Inner min{...}                                -> the three ``if`` branches
  inside the double loop; each guarded by exactly the slide's
  Condition_1 / Condition_2 / Condition_3.
* Slide ``Cost_upd(A_i*, B_j*)``                -> ``cost_relabel(...)``
  (typed leaf comparison via ``src.distances.relabel_cost`` + structural
  label equality; weighted by ``field_weight`` on the dotted path).
* Slide ``Cost_del`` / ``Cost_ins``             -> ``cost_delete`` / ``cost_insert``
  (base cost from the cost model x field weight).
* ``Return Dist[|A*|][|B*|]``                   -> ``_dist[n][m]``.

The backtrace through the chosen branch at each cell recovers a
**mapping** of (T1 pre-order index <-> T2 pre-order index) pairs — these
are the (A_i*, B_j*) for which the algorithm chose the relabel branch
(Condition_1). The mapping is then handed to ``_build_script`` which
turns it into an applicable ``EditScript`` of relabel / delete / insert
actions.

================================================================
Why a depth-constrained string DP is a tree edit distance
================================================================

A plain string edit distance on the pre-order linearization would let
the algorithm match nodes at incompatible depths (e.g. align a leaf
with a root), producing structurally meaningless mappings. The slide's
three conditions block this:

* Condition_1 (equal depth required for relabel) keeps every
  relabel between nodes at the same depth in their respective trees.
* Condition_2 only allows a delete from A when we are at-or-below
  B's current depth (or have consumed all of B) — this forces deletions
  to happen at the deeper side, so subtrees are removed from the
  bottom up.
* Condition_3 is the mirror image for inserts.

Together the three conditions make every cell choice a tree-aware
operation, while the DP itself stays a linear-time-per-cell two-loop
program (``O(|T1| * |T2|)`` time, same big-O as Chawathe's original
paper but much simpler to read).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from src.core import Action, EditScript, Node, Tree
from src.distances import field_weight, relabel_cost
from src.taxonomy import TaxonomyRegistry
from src.ted.base import TEDAlgorithm
from src.ted.registry import register


# ============================================================ algorithm
@register("chawathe")
class ChawatheTED(TEDAlgorithm):
    description = ("Chawathe (VLDB 1999) — LD-pair dynamic program: "
                   "constrained string edit distance on the (label, depth) "
                   "pre-order linearization of each tree.")
    placeholder = False

    def compute(self, t1: Tree, t2: Tree, *, config: dict[str, Any],
                taxonomies: TaxonomyRegistry,
                cost_model: dict[str, Any]) -> EditScript:
        info1 = _LDPairInfo.of(t1)
        info2 = _LDPairInfo.of(t2)

        weights = config.get("field_weights", {})
        delete_base = float(cost_model.get("delete", 1.0))
        insert_base = float(cost_model.get("insert", 1.0))
        type_mismatch = float(cost_model.get("type_mismatch_relabel", 1.0))

        def cost_delete(i: int) -> float:
            """Cost_del(A_i*) — slide line 4."""
            n = info1.nodes[i]
            return delete_base * field_weight(_label_path(n), weights)

        def cost_insert(j: int) -> float:
            """Cost_ins(B_j*) — slide line 5."""
            n = info2.nodes[j]
            return insert_base * field_weight(_label_path(n), weights)

        def cost_relabel(i: int, j: int) -> float:
            """Cost_upd(A_i*, B_j*) — slide's Condition_1 branch."""
            a, b = info1.nodes[i], info2.nodes[j]
            if a.kind != b.kind:
                return type_mismatch * field_weight(_label_path(a), weights)
            if a.is_structural:
                base = 0.0 if a.label == b.label else type_mismatch
            else:
                if a.value_equals(b):
                    base = 0.0
                else:
                    base = relabel_cost(a, b, config=config,
                                        taxonomies=taxonomies,
                                        cost_model=cost_model)
            return base * field_weight(_label_path(a), weights)

        dist, backtrack = _chawathe_ld_pair_dp(
            info1, info2, cost_delete, cost_insert, cost_relabel,
        )
        mapping = _extract_mapping(info1, info2, backtrack)
        # Safety net: LD-pair Chawathe is naturally order- and
        # ancestor-preserving but pathological cell choices can still
        # produce pairs whose parents aren't themselves mapped. The
        # script representation assumes direct-parent preservation, so
        # filter the mapping iteratively.
        mapping = _strict_parent_preserving(mapping, t1, t2, info1, info2)
        return _build_script(t1, t2, info1, info2, mapping,
                             cost_delete, cost_insert, cost_relabel)


# ============================================================ LD-pair linearization
@dataclass
class _LDPairInfo:
    """Pre-order linearization of a tree as the slide's ``A*`` / ``B*``.

    For every node we record:
      * ``nodes[i]``        — the Node itself
      * ``depths[i]``       — its depth (root = 0)
      * ``index_of[id(n)]`` — reverse lookup (Node id -> pre-order index)
    """

    tree: Tree
    nodes: list[Node] = field(default_factory=list)
    depths: list[int] = field(default_factory=list)
    index_of: dict[int, int] = field(default_factory=dict)

    @classmethod
    def of(cls, tree: Tree) -> "_LDPairInfo":
        info = cls(tree=tree)
        info._walk(tree.root, 0)
        return info

    def _walk(self, node: Node, depth: int) -> None:
        idx = len(self.nodes)
        self.nodes.append(node)
        self.depths.append(depth)
        self.index_of[id(node)] = idx
        for child in node.children:
            self._walk(child, depth + 1)


# ============================================================ LD-pair DP
# Backtrack opcodes used to remember which branch the min{} chose:
#   "M" = match/relabel (Condition_1 — diagonal step, slide's Cost_upd)
#   "D" = delete from A (Condition_2 — vertical step, slide's Cost_del)
#   "I" = insert from B (Condition_3 — horizontal step, slide's Cost_ins)
_M, _D, _I = "M", "D", "I"


def _chawathe_ld_pair_dp(
    info1: _LDPairInfo, info2: _LDPairInfo,
    cost_delete: Callable[[int], float],
    cost_insert: Callable[[int], float],
    cost_relabel: Callable[[int, int], float],
) -> tuple[list[list[float]], list[list[str]]]:
    """Slide pseudocode, transcribed.

    Returns
    -------
    dist : Dist[][] from the slide. dist[i][j] = TED(A[0..i-1], B[0..j-1]).
    backtrack : same shape, recording which branch the min{} chose at
                each cell ("M"/"D"/"I"/""). Used by ``_extract_mapping``.
    """
    depths1, depths2 = info1.depths, info2.depths
    n, m = len(info1.nodes), len(info2.nodes)
    INF = float("inf")

    dist: list[list[float]] = [[INF] * (m + 1) for _ in range(n + 1)]
    backtrack: list[list[str]] = [[""] * (m + 1) for _ in range(n + 1)]

    # --- slide: Dist[0][0] = 0
    dist[0][0] = 0.0

    # --- slide line 4: For (i = 1; i <= |A*|; i++) Dist[i][0] = Dist[i-1][0] + Cost_del(A_i*)
    for i in range(1, n + 1):
        dist[i][0] = dist[i - 1][0] + cost_delete(i - 1)
        backtrack[i][0] = _D

    # --- slide line 5: For (j = 1; j <= |B*|; j++) Dist[0][j] = Dist[0][j-1] + Cost_ins(B_j*)
    for j in range(1, m + 1):
        dist[0][j] = dist[0][j - 1] + cost_insert(j - 1)
        backtrack[0][j] = _I

    # --- slide main double loop with three conditional branches
    for i in range(1, n + 1):
        da = depths1[i - 1]                # A[i].d
        for j in range(1, m + 1):
            db = depths2[j - 1]            # B[j].d
            best_cost = INF
            best_op = ""

            # Condition_1: A[i].d == B[j].d
            if da == db:
                c = dist[i - 1][j - 1] + cost_relabel(i - 1, j - 1)
                if c < best_cost:
                    best_cost, best_op = c, _M

            # Condition_2: (A[i].d >= B[j].d) or (j == |B|)
            if da >= db or j == m:
                c = dist[i - 1][j] + cost_delete(i - 1)
                if c < best_cost:
                    best_cost, best_op = c, _D

            # Condition_3: (A[i].d <= B[j].d) or (i == |A|)
            if da <= db or i == n:
                c = dist[i][j - 1] + cost_insert(j - 1)
                if c < best_cost:
                    best_cost, best_op = c, _I

            dist[i][j] = best_cost
            backtrack[i][j] = best_op

    return dist, backtrack


# ============================================================ mapping extraction
def _extract_mapping(info1: _LDPairInfo, info2: _LDPairInfo,
                     backtrack: list[list[str]]
                     ) -> list[tuple[int, int]]:
    """Backtrace from ``(|A*|, |B*|)`` to ``(0, 0)`` to recover the pairs.

    Every cell whose chosen branch was ``M`` (Condition_1) contributes a
    (pre-order index in T1, pre-order index in T2) pair to the mapping.

    Cross-kind pairs (a structural matched to a leaf, or vice versa) are
    dropped here — the DP can pick them when the type_mismatch relabel
    cost is cheaper than the alternative delete+insert, but our patcher
    cannot relabel a leaf into a subtree-bearing structural node. By
    omitting them, the downstream script builder naturally emits a
    delete + insert for those positions instead of a no-op relabel.
    """
    n = len(info1.nodes)
    m = len(info2.nodes)
    pairs: list[tuple[int, int]] = []
    i, j = n, m
    while i > 0 or j > 0:
        op = backtrack[i][j]
        if op == _M:
            a = info1.nodes[i - 1]
            b = info2.nodes[j - 1]
            if a.kind == b.kind:
                pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif op == _D:
            i -= 1
        elif op == _I:
            j -= 1
        else:
            # Defensive: should not happen on a well-formed DP table.
            break
    return pairs


# ============================================================ script construction
def _record_mapping(t1: Tree, t2: Tree,
                    info1: _LDPairInfo, info2: _LDPairInfo,
                    pairs: list[tuple[int, int]]
                    ) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
    """Convert (pre-order_idx_t1, pre-order_idx_t2) pairs to (t1_path,
    t2_path) pairs for the resulting :attr:`EditScript.mapping`."""
    out: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
    for m, n in pairs:
        out.append((t1.path_of(info1.nodes[m]),
                    t2.path_of(info2.nodes[n])))
    return out


def _build_script(
    t1: Tree, t2: Tree,
    info1: _LDPairInfo, info2: _LDPairInfo,
    mapping: list[tuple[int, int]],
    cost_delete, cost_insert, cost_relabel,
) -> EditScript:
    """Turn the LD-pair mapping into an applicable :class:`EditScript`.

    The slide pseudocode produces the cost number; this function turns
    its backtrace into the actual sequence of relabel/delete/insert
    actions a downstream patcher can apply. We maintain a working copy
    of t1 alongside a correspondence map so each action's path is valid
    in the current intermediate state.
    """
    script = EditScript(
        source_name=t1.name,
        target_name=t2.name,
        mapping=_record_mapping(t1, t2, info1, info2, mapping),
    )
    mapped_t1 = {m for m, _ in mapping}
    mapped_t2 = {n for _, n in mapping}

    working = t1.copy()
    t1_to_w: dict[int, Node] = {}

    def _link(a: Node, b: Node) -> None:
        t1_to_w[id(a)] = b
        for ca, cb in zip(a.children, b.children):
            _link(ca, cb)
    _link(t1.root, working.root)

    # ---- relabels (Condition_1 cells whose Cost_upd > 0)
    for m, n in mapping:
        nm, nn = info1.nodes[m], info2.nodes[n]
        if nm is t1.root and nn is t2.root:
            continue
        if nm.kind != nn.kind:
            continue
        if nm.is_structural and nm.label == nn.label:
            continue
        if nm.is_leaf and nm.value_equals(nn):
            continue
        w = t1_to_w.get(id(nm))
        if w is None:
            continue
        path = working.path_of(w)
        cost = cost_relabel(m, n)
        if nm.is_structural:
            script.add(Action(op="relabel", path=path, cost=cost,
                              new_node=Node.structural(nn.label),
                              old_label=nm.label))
            w.label = nn.label
        else:
            script.add(Action(op="relabel", path=path, cost=cost,
                              new_node=nn.copy(),
                              old_label=nm.label,
                              old_value=nm.value,
                              old_type=nm.type,
                              old_taxonomy=nm.taxonomy))
            w.label = nn.label
            w.value = nn.value
            w.type = nn.type
            w.unit = nn.unit
            w.trend = nn.trend
            w.taxonomy = nn.taxonomy
            w.raw = nn.raw

    # ---- deletes (Condition_2 cells — deepest first, suppress descendants
    # of an outer delete so we don't emit redundant child deletes)
    delete_nodes = [info1.nodes[i] for i in range(len(info1.nodes))
                    if i not in mapped_t1 and info1.nodes[i] is not t1.root]
    delete_ids = {id(n) for n in delete_nodes}

    def _has_deleted_ancestor(node: Node) -> bool:
        cur = node.parent
        while cur is not None:
            if id(cur) in delete_ids:
                return True
            cur = cur.parent
        return False

    to_delete = [n for n in delete_nodes if not _has_deleted_ancestor(n)]
    to_delete.sort(key=lambda n: (len(t1.path_of(n)), t1.path_of(n)),
                   reverse=True)

    for node in to_delete:
        w = t1_to_w.get(id(node))
        if w is None or w.parent is None:
            continue
        path = t1.path_of(node)
        cost = cost_delete(info1.index_of[id(node)])
        script.add(Action(op="delete", path=path, cost=cost,
                          old_label=node.label, new_node=node.copy()))
        # Identity, not equality: two structurally-identical siblings
        # would compare equal under Node.__eq__ (dataclass default),
        # and list.index would return the first match.
        w.parent.remove_child(
            next(i for i, c in enumerate(w.parent.children) if c is w)
        )
        for desc in node.walk():
            t1_to_w.pop(id(desc), None)

    # ---- inserts (Condition_3 cells — shallowest first, cascading children)
    t2_to_w: dict[int, Node] = {}
    for m, n in mapping:
        nm = info1.nodes[m]
        nn = info2.nodes[n]
        if id(nm) in t1_to_w:
            t2_to_w[id(nn)] = t1_to_w[id(nm)]

    insert_nodes = [info2.nodes[i] for i in range(len(info2.nodes))
                    if i not in mapped_t2 and info2.nodes[i] is not t2.root]
    insert_nodes.sort(key=lambda n: _depth(n))

    inserted_via_cascade: set[int] = set()
    for node2 in insert_nodes:
        if id(node2) in inserted_via_cascade:
            continue
        parent2 = node2.parent
        if parent2 is None or id(parent2) not in t2_to_w:
            continue
        w_parent = t2_to_w[id(parent2)]
        position = len(w_parent.children)
        parent_path = working.path_of(w_parent)
        cost = cost_insert(info2.index_of[id(node2)])
        new_subtree = node2.copy()
        script.add(Action(op="insert", path=parent_path, position=position,
                          cost=cost, new_node=new_subtree.copy(),
                          old_label=node2.label))
        w_parent.insert_child(position, new_subtree)

        def _register(t2_n: Node, w_n: Node) -> None:
            t2_to_w[id(t2_n)] = w_n
            inserted_via_cascade.add(id(t2_n))
            for c2, cw in zip(t2_n.children, w_n.children):
                _register(c2, cw)
        _register(node2, new_subtree)

    return script


# ============================================================ mapping filter
def _strict_parent_preserving(
    mapping: list[tuple[int, int]],
    t1: Tree, t2: Tree,
    info1: _LDPairInfo, info2: _LDPairInfo,
) -> list[tuple[int, int]]:
    """Iteratively drop pairs (m, n) whose parents aren't themselves mapped.

    LD-pair Chawathe is naturally ancestor-preserving (a child cell can
    only be reached after its ancestors), but two siblings at the same
    depth in T1 could theoretically be matched against two siblings in
    T2 whose parent didn't get matched in the same cell — leaving an
    orphan pair. Our patcher needs direct-parent preservation to emit
    an applicable script; this filter converges in a few passes.
    """
    surviving: set[tuple[int, int]] = set(mapping)
    while True:
        t1_to_t2 = {m: n for m, n in surviving}
        next_surviving: set[tuple[int, int]] = set()
        for m, n in surviving:
            nm = info1.nodes[m]
            nn = info2.nodes[n]
            if nm.parent is None and nn.parent is None:
                next_surviving.add((m, n))
                continue
            if nm.parent is None or nn.parent is None:
                continue
            p1 = info1.index_of[id(nm.parent)]
            p2 = info2.index_of[id(nn.parent)]
            if t1_to_t2.get(p1) == p2:
                next_surviving.add((m, n))
        if next_surviving == surviving:
            return list(surviving)
        surviving = next_surviving


# ============================================================ helpers
def _depth(n: Node) -> int:
    d = 0
    cur = n
    while cur.parent is not None:
        d += 1
        cur = cur.parent
    return d


def _label_path(n: Node) -> list[str]:
    """Dotted label-path (without ``[i]`` disambiguation) for field-weight lookup."""
    parts: list[str] = []
    cur = n
    while cur.parent is not None:
        parts.append(cur.label)
        cur = cur.parent
    return list(reversed(parts))
