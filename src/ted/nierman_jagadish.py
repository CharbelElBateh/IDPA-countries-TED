"""
Tree Edit Distance — Nierman & Jagadish 2002 variant.

Same Zhang-Shasha DP as Chawathe, but distinguishes between:
  - relabel_structure: renaming an element tag (structural node)
  - relabel_content: changing a leaf text value (content node)

Cost model keys used: 'insert', 'delete', 'relabel_structure', 'relabel_content'
Falls back to 'relabel' if the split costs are absent.

Reference: Nierman A. & Jagadish H.V., "Evaluating Structural Similarity
in XML Documents", WebDB 2002, pp. 61-66.
"""

from __future__ import annotations
from classes.Node import Node
from classes.Tree import Tree
from classes.Action import Action
from classes.EditScript import EditScript

# Reuse the DP infrastructure from chawathe
from src.ted.chawathe import (
    _postorder_nodes,
    _node_to_postorder,
    _compute_lml,
    _compute_keyroots,
    _run_dp,
    _find_matching,
)


def compute_ted(T1: Tree, T2: Tree, costs: dict) -> float:
    """Compute TED between T1 and T2 using Nierman & Jagadish cost model."""
    ted, _ = compute_ted_and_script(T1, T2, costs)
    return ted


def compute_ted_and_script(
    T1: Tree, T2: Tree, costs: dict
) -> tuple[float, EditScript]:
    """
    Compute TED and extract edit script using Nierman & Jagadish costs.

    Relabel cost depends on node type:
      - element node: use 'relabel_structure' (default: 'relabel' or 1)
      - leaf node:    use 'relabel_content'   (default: 'relabel' or 1)
    """
    c_del = costs.get('delete', 1)
    c_ins = costs.get('insert', 1)
    fallback = costs.get('relabel', 1)
    c_rel_struct = costs.get('relabel_structure', fallback)
    c_rel_cont = costs.get('relabel_content', fallback)

    def c_rel_fn(n1: Node, n2: Node) -> float:
        if n1.label == n2.label:
            return 0.0
        if n1.node_type == 'leaf' and n2.node_type == 'leaf':
            return c_rel_cont
        return c_rel_struct

    nodes1 = _postorder_nodes(T1)
    nodes2 = _postorder_nodes(T2)
    n = len(nodes1)
    m = len(nodes2)

    if n == 0 and m == 0:
        return 0.0, EditScript()
    if n == 0:
        es = EditScript()
        for node in T2.preorder():
            es.add(Action('insert', c_ins, node, {'parent': node.parent, 'position': 0}))
        return es.total_cost, es
    if m == 0:
        es = EditScript()
        for node in nodes1:
            es.add(Action('delete', c_del, node, {}))
        return es.total_cost, es

    id_to_idx1 = _node_to_postorder(nodes1)
    id_to_idx2 = _node_to_postorder(nodes2)

    lml1 = _compute_lml(nodes1, id_to_idx1)
    lml2 = _compute_lml(nodes2, id_to_idx2)

    kr1 = _compute_keyroots(n, lml1)
    kr2 = _compute_keyroots(m, lml2)

    td, fd_cache = _run_dp(nodes1, nodes2, lml1, lml2, kr1, kr2, c_del, c_ins, c_rel_fn)

    lml_to_kr1 = {lml1[ki]: ki for ki in kr1}
    lml_to_kr2 = {lml2[kj]: kj for kj in kr2}

    matching = _find_matching(
        n, m, nodes1, nodes2, lml1, lml2, td, fd_cache,
        lml_to_kr1, lml_to_kr2, c_del, c_ins, c_rel_fn,
    )

    matched_t1 = {i for i, j in matching}
    matched_t2 = {j for i, j in matching}

    es = EditScript()

    for i, j in sorted(matching):
        n1 = nodes1[i - 1]
        n2 = nodes2[j - 1]
        if n1.label != n2.label:
            cost = c_rel_fn(n1, n2)
            es.add(Action('relabel', cost, n1, {'new_label': n2.label, 't2_node': n2}))

    for i in range(1, n + 1):
        if i not in matched_t1:
            n1 = nodes1[i - 1]
            es.add(Action('delete', c_del, n1, {'parent_node': n1.parent}))

    reverse_match = {j: i for i, j in matching}   # T2 idx -> T1 idx
    t2_preorder = list(T2.preorder())
    t2_id_to_postorder = {id(node): idx for idx, node in enumerate(nodes2, 1)}
    for node in t2_preorder:
        j = t2_id_to_postorder[id(node)]
        if j not in matched_t2:
            parent = node.parent
            pos = parent.children.index(node) if parent else 0
            source_parent = None
            if parent is not None:
                parent_j = t2_id_to_postorder.get(id(parent))
                if parent_j is not None:
                    parent_i = reverse_match.get(parent_j)
                    if parent_i is not None:
                        source_parent = nodes1[parent_i - 1]
            es.add(Action('insert', c_ins, node, {
                'parent': parent,
                'position': pos,
                'source_parent': source_parent,
            }))

    return td[n][m], es
