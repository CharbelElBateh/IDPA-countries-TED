"""Nierman & Jagadish (WebDB 2002) — recursive top-down subtree similarity.

Reference: A. Nierman & H. V. Jagadish, "Evaluating Structural Similarity in
XML Documents", WebDB 2002, pp. 61-66.

Unlike Chawathe (which is Zhang-Shasha bottom-up DP over post-order indices),
N&J **recursively computes a similarity score per subtree pair** and aligns
children at each level with an order-preserving sequence alignment. This
makes the algorithm naturally aware of *subtree containment* — when a
fragment of one tree appears inside another, the recursion gives that
fragment a low partial-match cost rather than paying the full
delete+insert it would in flat Z-S.

The recurrence for two nodes ``a`` (in T1) and ``b`` (in T2)::

    D(a, b) =
        relabel(a, b)                                 if both leaves
        relabel(a, b) + Σ insert(c)  for c in b.children    if a leaf, b internal
        relabel(a, b) + Σ delete(c)  for c in a.children    if a internal, b leaf
        relabel(a, b) + align(a.children, b.children)        otherwise

where ``align`` is a sequence-alignment DP over the two child sequences
(deletes pay ``|subtree|``, inserts pay ``|subtree|``, matches recurse).

A memoization dict keyed on ``(id(a), id(b))`` keeps the total work
``O(|T1|·|T2|·d)`` where ``d`` is the maximum out-degree. Each subtree
pair is computed once.

This file is fully self-contained — no shared TED core module.
"""

from __future__ import annotations

from typing import Any

from src.core import Action, EditScript, Node, Tree
from src.distances import field_weight, relabel_cost
from src.taxonomy import TaxonomyRegistry
from src.ted.base import TEDAlgorithm
from src.ted.registry import register


# ============================================================ algorithm
@register("nierman_jagadish")
class NiermanJagadishTED(TEDAlgorithm):
    description = ("Nierman & Jagadish (WebDB 2002) — top-down recursive "
                   "subtree similarity with order-preserving child alignment. "
                   "Captures subtree containment.")
    placeholder = False

    def compute(self, t1: Tree, t2: Tree, *, config: dict[str, Any],
                taxonomies: TaxonomyRegistry,
                cost_model: dict[str, Any]) -> EditScript:
        weights = config.get("field_weights", {})
        delete_base = float(cost_model.get("delete", 1.0))
        insert_base = float(cost_model.get("insert", 1.0))
        type_mismatch = float(cost_model.get("type_mismatch_relabel", 1.0))

        # Subtree-containment switch (see ``config/pipeline.json``).
        sub_cfg = config.get("subtree_similarity", {})
        containment_enabled = bool(sub_cfg.get("enabled", True))
        move_factor = float(sub_cfg.get("move_cost_factor", 1.0))

        # When enabled, precompute structure+content signatures for every
        # subtree of both trees so we can recognize that an "inserted"
        # subtree is just a moved copy of one already present in the
        # source. Moves cost a single base op (× field weight × factor)
        # rather than the per-node sum.
        if containment_enabled:
            t1_subtree_sigs: set = {_subtree_signature(n) for n in t1.walk()}
            t2_subtree_sigs: set = {_subtree_signature(n) for n in t2.walk()}
        else:
            t1_subtree_sigs = set()
            t2_subtree_sigs = set()

        # ----- per-node weighted op costs -----
        def cost_delete_node(node: Node) -> float:
            return delete_base * field_weight(_label_path(node), weights)

        def cost_insert_node(node: Node) -> float:
            return insert_base * field_weight(_label_path(node), weights)

        def cost_relabel_pair(a: Node, b: Node) -> float:
            w = field_weight(_label_path(a), weights)
            if a.kind != b.kind:
                return type_mismatch * w
            if a.is_structural:
                return 0.0 if a.label == b.label else type_mismatch * w
            if a.value_equals(b):
                return 0.0
            d = relabel_cost(a, b, config=config,
                             taxonomies=taxonomies,
                             cost_model=cost_model)
            return d * w

        # Whole-subtree delete/insert costs.
        # If the subtree's structure+content also lives in the other tree,
        # treat it as a *move* and charge a single weighted op; otherwise
        # charge the sum of per-node costs.
        def cost_delete_subtree(node: Node) -> float:
            if containment_enabled and _subtree_signature(node) in t2_subtree_sigs:
                return (move_factor * delete_base
                        * field_weight(_label_path(node), weights))
            return sum(cost_delete_node(n) for n in node.walk())

        def cost_insert_subtree(node: Node) -> float:
            if containment_enabled and _subtree_signature(node) in t1_subtree_sigs:
                return (move_factor * insert_base
                        * field_weight(_label_path(node), weights))
            return sum(cost_insert_node(n) for n in node.walk())

        # ----- memoized recursive D(a, b) -----
        memo: dict[tuple[int, int], tuple[float, dict | None]] = {}

        def similarity(a: Node, b: Node) -> float:
            key = (id(a), id(b))
            if key in memo:
                return memo[key][0]

            if a.is_leaf and b.is_leaf:
                memo[key] = (cost_relabel_pair(a, b), None)
                return memo[key][0]

            if a.kind != b.kind:
                # Cross-kind pair: not a real match — price it as a full
                # delete of one side + full insert of the other so the
                # surrounding alignment picks the delete-then-insert path.
                # The script-construction step won't add this to the
                # mapping (see ``_extract_mapping``).
                cost = cost_delete_subtree(a) + cost_insert_subtree(b)
                memo[key] = (cost, None)
                return cost

            root_cost = cost_relabel_pair(a, b)

            # Both internal — align children.
            c1, c2 = a.children, b.children
            n, m = len(c1), len(c2)
            F: list[list[float]] = [[0.0] * (m + 1) for _ in range(n + 1)]
            BT: list[list[tuple | None]] = [[None] * (m + 1)
                                            for _ in range(n + 1)]

            for i in range(1, n + 1):
                F[i][0] = F[i - 1][0] + cost_delete_subtree(c1[i - 1])
                BT[i][0] = ("D", i - 1)
            for j in range(1, m + 1):
                F[0][j] = F[0][j - 1] + cost_insert_subtree(c2[j - 1])
                BT[0][j] = ("I", j - 1)

            for i in range(1, n + 1):
                for j in range(1, m + 1):
                    d_cost = F[i - 1][j] + cost_delete_subtree(c1[i - 1])
                    i_cost = F[i][j - 1] + cost_insert_subtree(c2[j - 1])
                    m_cost = F[i - 1][j - 1] + similarity(c1[i - 1], c2[j - 1])
                    best = min(d_cost, i_cost, m_cost)
                    F[i][j] = best
                    if best == m_cost:
                        BT[i][j] = ("M", i - 1, j - 1)
                    elif best == d_cost:
                        BT[i][j] = ("D", i - 1)
                    else:
                        BT[i][j] = ("I", j - 1)

            memo[key] = (root_cost + F[n][m],
                         {"F": F, "BT": BT, "c1": c1, "c2": c2})
            return memo[key][0]

        # ----- main entry: compute distance + extract mapping -----
        similarity(t1.root, t2.root)
        pairs = _extract_mapping(t1.root, t2.root, memo)
        return _build_script(t1, t2, pairs, memo,
                             cost_delete_node, cost_insert_node,
                             cost_relabel_pair)


# ============================================================ mapping extraction
def _extract_mapping(root1: Node, root2: Node,
                     memo: dict) -> list[tuple[Node, Node]]:
    """Walk the per-subtree backtrack records to recover the node mapping."""
    pairs: list[tuple[Node, Node]] = []

    def walk(a: Node, b: Node) -> None:
        # Cross-kind "pairings" produced by the DP aren't real matches —
        # they were priced as delete + insert. Skip them so the script
        # builder emits separate delete and insert actions.
        if a.kind == b.kind:
            pairs.append((a, b))
        bt_data = memo.get((id(a), id(b)), (None, None))[1]
        if bt_data is None:
            return
        bt = bt_data["BT"]
        c1 = bt_data["c1"]
        c2 = bt_data["c2"]
        i, j = len(c1), len(c2)
        # Backtrack through the child-alignment matrix.
        while i > 0 or j > 0:
            decision = bt[i][j]
            if decision is None:
                break
            op = decision[0]
            if op == "M":
                ci, cj = decision[1], decision[2]
                walk(c1[ci], c2[cj])
                i -= 1
                j -= 1
            elif op == "D":
                i -= 1
            elif op == "I":
                j -= 1
            else:
                break

    walk(root1, root2)
    return pairs


# ============================================================ script construction
def _build_script(
    t1: Tree, t2: Tree,
    pairs: list[tuple[Node, Node]],
    memo: dict,
    cost_delete_node, cost_insert_node, cost_relabel_pair,
) -> EditScript:
    """Convert the mapping into an applicable :class:`EditScript`.

    Because N&J's child alignment is order-preserving and strictly
    parent-respecting, the mapping is already in the form the script
    needs — no extra filtering is required (unlike Z-S).
    """
    mapped_t1: set[int] = {id(a) for a, _ in pairs}
    mapped_t2: set[int] = {id(b) for _, b in pairs}

    # Record (t1_path, t2_path) on the script for the frontend.
    path_mapping = [(t1.path_of(a), t2.path_of(b)) for a, b in pairs]

    script = EditScript(
        source_name=t1.name,
        target_name=t2.name,
        mapping=path_mapping,
    )

    # Working copy + correspondence so action paths track the current state.
    working = t1.copy()
    t1_to_w: dict[int, Node] = {}

    def _link(a: Node, b: Node) -> None:
        t1_to_w[id(a)] = b
        for ca, cb in zip(a.children, b.children):
            _link(ca, cb)
    _link(t1.root, working.root)

    # ---- relabels
    for a, b in pairs:
        if a is t1.root and b is t2.root:
            continue
        if a.kind != b.kind:
            continue
        if a.is_structural and a.label == b.label:
            continue
        if a.is_leaf and a.value_equals(b):
            continue
        w = t1_to_w.get(id(a))
        if w is None:
            continue
        path = t1.path_of(a)
        cost = cost_relabel_pair(a, b)
        if a.is_structural:
            script.add(Action(op="relabel", path=path, cost=cost,
                              new_node=Node.structural(b.label),
                              old_label=a.label))
            w.label = b.label
        else:
            script.add(Action(op="relabel", path=path, cost=cost,
                              new_node=b.copy(),
                              old_label=a.label,
                              old_value=a.value,
                              old_type=a.type,
                              old_taxonomy=a.taxonomy))
            w.label = b.label
            w.value = b.value
            w.type = b.type
            w.unit = b.unit
            w.trend = b.trend
            w.taxonomy = b.taxonomy
            w.raw = b.raw

    # ---- deletes — unmapped T1 nodes whose parents are NOT also unmapped
    delete_nodes = [n for n in t1.walk()
                    if id(n) not in mapped_t1 and n is not t1.root]
    delete_ids = {id(n) for n in delete_nodes}

    def _has_deleted_ancestor(node: Node) -> bool:
        cur = node.parent
        while cur is not None:
            if id(cur) in delete_ids:
                return True
            cur = cur.parent
        return False

    to_delete = [n for n in delete_nodes if not _has_deleted_ancestor(n)]
    # Sort to match EditScript.apply's order (deepest+rightmost first via t1 paths).
    to_delete.sort(key=lambda n: (len(t1.path_of(n)), t1.path_of(n)),
                   reverse=True)

    for node in to_delete:
        w = t1_to_w.get(id(node))
        if w is None or w.parent is None:
            continue
        path = t1.path_of(node)
        cost = cost_delete_node(node)
        script.add(Action(op="delete", path=path, cost=cost,
                          old_label=node.label, new_node=node.copy()))
        w.parent.remove_child(w.parent.children.index(w))
        for desc in node.walk():
            t1_to_w.pop(id(desc), None)

    # ---- inserts — unmapped T2 nodes (shallowest first, suppress descendants
    # of an outer insert so we don't double-insert).
    t2_to_w: dict[int, Node] = {}
    for a, b in pairs:
        if id(a) in t1_to_w:
            t2_to_w[id(b)] = t1_to_w[id(a)]

    insert_nodes = [n for n in t2.walk()
                    if id(n) not in mapped_t2 and n is not t2.root]
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
        cost = cost_insert_node(node2)
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


# ============================================================ subtree signatures
def _subtree_signature(node: Node) -> tuple:
    """Return a hashable structural+content signature for ``node``'s subtree.

    Two subtrees have the same signature iff they have the same labels,
    same leaf values, and same child ordering. Used by N&J's subtree-
    containment cost rule.
    """
    if node.is_leaf:
        return ("L", node.label, node.type, _hashable(node.value))
    return ("S", node.label,
            tuple(_subtree_signature(c) for c in node.children))


def _hashable(v) -> tuple | str | int | float | bool | None:
    """Coerce a leaf value into a hashable, JSON-style representation."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (list, tuple)):
        return tuple(_hashable(x) for x in v)
    if isinstance(v, dict):
        return tuple(sorted((k, _hashable(v[k])) for k in v))
    return str(v)


# ============================================================ helpers
def _depth(n: Node) -> int:
    d = 0
    cur = n
    while cur.parent is not None:
        d += 1
        cur = cur.parent
    return d


def _label_path(n: Node) -> list[str]:
    parts: list[str] = []
    cur = n
    while cur.parent is not None:
        parts.append(cur.label)
        cur = cur.parent
    return list(reversed(parts))
