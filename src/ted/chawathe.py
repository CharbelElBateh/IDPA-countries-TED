"""Chawathe (VLDB 1999) Tree Edit Distance.

Reference: S. Chawathe, "Comparing Hierarchical Data in External Memory",
VLDB 1999, pp. 90-101.

The core dynamic program is Zhang-Shasha (1989) operating on a post-order
linearization of both trees and using *keyroots* to bound the set of
forest-distance matrices to compute. Chawathe's contribution is the
edit-script reconstruction by backtracking through the forest-distance
records.

Cost dispatch for Chawathe (in this module):

* delete(v)   = ``costs.delete``   × weight(field_path(v_in_t1))
* insert(v)   = ``costs.insert``   × weight(field_path(v_in_t2))
* relabel(a,b) = ``distances.relabel_cost(a,b)`` × weight(field_path(a))

Where ``distances.relabel_cost`` returns a value in ``[0, 1]`` driven by
the typed leaf comparison (numeric, percent, date, currency, EMD over
distributions, …) — see ``src.distances``.

This file is intentionally self-contained: the entire Zhang-Shasha core
(post-order traversal, keyroots, forest-distance DP, backtracking, and
script construction by simulation) lives here so the algorithm can be
read end-to-end in one place.
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
    description = ("Chawathe (VLDB 1999) — Zhang-Shasha dynamic programming "
                   "with edit-script backtracking. Optimal-cost mapping.")
    placeholder = False

    def compute(self, t1: Tree, t2: Tree, *, config: dict[str, Any],
                taxonomies: TaxonomyRegistry,
                cost_model: dict[str, Any]) -> EditScript:
        info1 = _PostOrderInfo.of(t1)
        info2 = _PostOrderInfo.of(t2)

        weights = config.get("field_weights", {})
        delete_base = float(cost_model.get("delete", 1.0))
        insert_base = float(cost_model.get("insert", 1.0))
        type_mismatch = float(cost_model.get("type_mismatch_relabel", 1.0))

        def cost_delete(i: int) -> float:
            n = info1.nodes[i]
            return delete_base * field_weight(_label_path(n), weights)

        def cost_insert(j: int) -> float:
            n = info2.nodes[j]
            return insert_base * field_weight(_label_path(n), weights)

        def cost_relabel(i: int, j: int) -> float:
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

        td, backtrack = _zhang_shasha(info1, info2,
                                      cost_delete, cost_insert, cost_relabel)
        mapping = _extract_mapping(info1, info2, td, backtrack)
        # Filter Z-S's optimal mapping to a strict parent-preserving subset
        # so the script can be reproduced with only insert/delete/relabel
        # (no "move" operations). Without this, a Z-S pair whose parents
        # don't align in the two trees would cause mapped subtrees to be
        # double-inserted on patch.
        mapping = _strict_parent_preserving(mapping, t1, t2, info1, info2)
        return _build_script(t1, t2, info1, info2, mapping,
                             cost_delete, cost_insert, cost_relabel)


# ============================================================ post-order info
@dataclass
class _PostOrderInfo:
    """Post-order linearization + Zhang-Shasha auxiliary arrays."""

    tree: Tree
    nodes: list[Node] = field(default_factory=list)
    index_of: dict[int, int] = field(default_factory=dict)
    lld: list[int] = field(default_factory=list)
    keyroots: list[int] = field(default_factory=list)

    @classmethod
    def of(cls, tree: Tree) -> "_PostOrderInfo":
        info = cls(tree=tree)
        info._walk(tree.root)
        info._compute_keyroots()
        return info

    def _walk(self, node: Node) -> None:
        if not node.children:
            idx = len(self.nodes)
            self.nodes.append(node)
            self.index_of[id(node)] = idx
            self.lld.append(idx)
            return
        for c in node.children:
            self._walk(c)
        idx = len(self.nodes)
        self.nodes.append(node)
        self.index_of[id(node)] = idx
        leftmost = node.children[0]
        self.lld.append(self.lld[self.index_of[id(leftmost)]])

    def _compute_keyroots(self) -> None:
        seen: dict[int, int] = {}
        for v in range(len(self.nodes)):
            l = self.lld[v]
            if l not in seen or v > seen[l]:
                seen[l] = v
        self.keyroots = sorted(seen.values())


# ============================================================ Zhang-Shasha DP
def _zhang_shasha(
    info1: _PostOrderInfo, info2: _PostOrderInfo,
    cost_delete: Callable[[int], float],
    cost_insert: Callable[[int], float],
    cost_relabel: Callable[[int, int], float],
) -> tuple[list[list[float]], dict]:
    n1, n2 = len(info1.nodes), len(info2.nodes)
    td: list[list[float]] = [[0.0] * n2 for _ in range(n1)]
    backtrack: dict[tuple[int, int], dict] = {}

    for i in info1.keyroots:
        for j in info2.keyroots:
            _forestdist(i, j, info1, info2, td, backtrack,
                        cost_delete, cost_insert, cost_relabel)
    return td, backtrack


def _forestdist(
    i: int, j: int,
    info1: _PostOrderInfo, info2: _PostOrderInfo,
    td: list[list[float]], backtrack: dict,
    cost_delete, cost_insert, cost_relabel,
) -> None:
    l1, l2 = info1.lld, info2.lld
    rows = i - l1[i] + 2
    cols = j - l2[j] + 2
    fd: list[list[float]] = [[0.0] * cols for _ in range(rows)]
    bt: list[list[tuple | None]] = [[None] * cols for _ in range(rows)]

    for r in range(1, rows):
        m = l1[i] + r - 1
        fd[r][0] = fd[r - 1][0] + cost_delete(m)
        bt[r][0] = ("D", m)
    for c in range(1, cols):
        n = l2[j] + c - 1
        fd[0][c] = fd[0][c - 1] + cost_insert(n)
        bt[0][c] = ("I", n)

    for r in range(1, rows):
        m = l1[i] + r - 1
        for c in range(1, cols):
            n = l2[j] + c - 1
            d_cost = fd[r - 1][c] + cost_delete(m)
            i_cost = fd[r][c - 1] + cost_insert(n)
            if l1[m] == l1[i] and l2[n] == l2[j]:
                r_cost = fd[r - 1][c - 1] + cost_relabel(m, n)
                best = min(d_cost, i_cost, r_cost)
                fd[r][c] = best
                if best == r_cost:
                    bt[r][c] = ("M", m, n)
                elif best == d_cost:
                    bt[r][c] = ("D", m)
                else:
                    bt[r][c] = ("I", n)
                td[m][n] = best
            else:
                r_off = l1[m] - l1[i]
                c_off = l2[n] - l2[j]
                t_cost = fd[r_off][c_off] + td[m][n]
                best = min(d_cost, i_cost, t_cost)
                fd[r][c] = best
                if best == t_cost:
                    bt[r][c] = ("T", m, n)
                elif best == d_cost:
                    bt[r][c] = ("D", m)
                else:
                    bt[r][c] = ("I", n)

    backtrack[(i, j)] = {"fd": fd, "bt": bt,
                         "l1_i": l1[i], "l2_j": l2[j]}


# ============================================================ mapping extraction
def _extract_mapping(info1: _PostOrderInfo, info2: _PostOrderInfo,
                     td: list[list[float]], backtrack: dict
                     ) -> list[tuple[int, int]]:
    if not info1.nodes or not info2.nodes:
        return []
    mapping: list[tuple[int, int]] = []
    stack: list[tuple[int, int]] = [(len(info1.nodes) - 1,
                                     len(info2.nodes) - 1)]
    while stack:
        i, j = stack.pop()
        rec = backtrack.get((i, j))
        if rec is None:
            continue
        bt = rec["bt"]
        l_i, l_j = rec["l1_i"], rec["l2_j"]
        r = i - l_i + 1
        c = j - l_j + 1
        while r > 0 or c > 0:
            decision = bt[r][c]
            if decision is None:
                break
            op = decision[0]
            if op == "D":
                r -= 1
            elif op == "I":
                c -= 1
            elif op == "M":
                mapping.append((decision[1], decision[2]))
                r -= 1
                c -= 1
            elif op == "T":
                m, n = decision[1], decision[2]
                stack.append((m, n))
                r = info1.lld[m] - l_i
                c = info2.lld[n] - l_j
            else:
                break
    return mapping


# ============================================================ script construction
def _record_mapping(t1: Tree, t2: Tree,
                    info1: _PostOrderInfo, info2: _PostOrderInfo,
                    pairs: list[tuple[int, int]]
                    ) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
    """Convert ``(post_order_idx1, post_order_idx2)`` pairs to
    ``(t1_path, t2_path)`` pairs for use in :attr:`EditScript.mapping`."""
    out: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
    for m, n in pairs:
        out.append((t1.path_of(info1.nodes[m]),
                    t2.path_of(info2.nodes[n])))
    return out


def _build_script(
    t1: Tree, t2: Tree,
    info1: _PostOrderInfo, info2: _PostOrderInfo,
    mapping: list[tuple[int, int]],
    cost_delete, cost_insert, cost_relabel,
) -> EditScript:
    """Turn a Zhang-Shasha mapping into an applicable :class:`EditScript`.

    We build a *working* copy of ``t1`` plus a correspondence map and apply
    each operation as we emit it, so action paths are always valid in the
    current working state. ``EditScript.apply`` will replay them in the
    same order (relabels → deletes deepest-first → inserts shallowest-first).
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

    # ---- relabels
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

    # ---- deletes (deepest first; suppress descendants of an outer delete)
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
    # Sort by (depth desc, path desc) to match EditScript.apply's order.
    to_delete.sort(key=lambda n: (len(t1.path_of(n)), t1.path_of(n)),
                   reverse=True)

    for node in to_delete:
        w = t1_to_w.get(id(node))
        if w is None or w.parent is None:
            continue
        # Emit the *original* t1 path, not the mutated working path —
        # EditScript.apply replays deletes against a fresh copy of t1 in
        # this same sorted order, so the t1 path is what it expects.
        path = t1.path_of(node)
        cost = cost_delete(info1.index_of[id(node)])
        script.add(Action(op="delete", path=path, cost=cost,
                          old_label=node.label, new_node=node.copy()))
        w.parent.remove_child(w.parent.children.index(w))
        for desc in node.walk():
            t1_to_w.pop(id(desc), None)

    # ---- inserts (shallowest first)
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
    info1: _PostOrderInfo, info2: _PostOrderInfo,
) -> list[tuple[int, int]]:
    """Iteratively remove pairs ``(m, n)`` whose parents are not themselves
    mapped to each other.

    Z-S's optimal mapping only guarantees the weaker "ancestor preserving"
    property. For our script representation (no move operations) we need
    *direct-parent* preservation, otherwise inserting an unmapped T2
    subtree would also re-insert mapped descendants that already live
    elsewhere in the working tree. This filter converges in a few passes.
    """
    surviving: set[tuple[int, int]] = set(mapping)
    while True:
        t1_to_t2 = {m: n for m, n in surviving}
        next_surviving: set[tuple[int, int]] = set()
        for m, n in surviving:
            nm = info1.nodes[m]
            nn = info2.nodes[n]
            # Root pair: always keep.
            if nm.parent is None and nn.parent is None:
                next_surviving.add((m, n))
                continue
            if nm.parent is None or nn.parent is None:
                # Root mapped to non-root — drop.
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
