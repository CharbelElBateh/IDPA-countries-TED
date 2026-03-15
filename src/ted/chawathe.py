"""
Tree Edit Distance — Chawathe 1999 variant.

Implements the Zhang-Shasha (1989) ordered tree edit distance algorithm,
extended with edit-script extraction via DP backtracking, as described in
the Chawathe 1999 (VLDB) approach.

Cost model keys used: 'insert', 'delete', 'relabel'
"""

from __future__ import annotations
from classes.Node import Node
from classes.Tree import Tree
from classes.Action import Action
from classes.EditScript import EditScript


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _postorder_nodes(tree: Tree) -> list[Node]:
    return list(tree.postorder())


def _node_to_postorder(nodes: list[Node]) -> dict[int, int]:
    """Map id(node) -> 1-based postorder index."""
    return {id(n): i for i, n in enumerate(nodes, 1)}


def _compute_lml(nodes: list[Node], id_to_idx: dict[int, int]) -> list[int]:
    """
    Returns lml[i] for i = 1..n (1-based).
    lml[i] = 1-based postorder index of leftmost leaf descendant of nodes[i-1].
    """
    lml = [0] * (len(nodes) + 1)
    for i, node in enumerate(nodes, 1):
        cur = node
        while cur.children:
            cur = cur.children[0]
        lml[i] = id_to_idx[id(cur)]
    return lml


def _compute_keyroots(n: int, lml: list[int]) -> list[int]:
    """
    Returns sorted list of 1-based key root indices.
    Key root: for each distinct lml value, the node with the highest postorder index.
    """
    seen: dict[int, int] = {}
    for i in range(1, n + 1):
        seen[lml[i]] = i
    return sorted(seen.values())


# ---------------------------------------------------------------------------
# Zhang-Shasha DP
# ---------------------------------------------------------------------------

def _run_dp(
    nodes1: list[Node],
    nodes2: list[Node],
    lml1: list[int],
    lml2: list[int],
    kr1: list[int],
    kr2: list[int],
    c_del: float,
    c_ins: float,
    c_rel_fn,
) -> tuple[list[list[float]], dict]:
    """
    Run the Zhang-Shasha DP.
    Returns (td, fd_cache) where:
      td[i][j] = TED between subtree i (1-based) in T1 and subtree j in T2
      fd_cache[(ki, kj)] = (li, lj, fd_matrix)
    """
    n = len(nodes1)
    m = len(nodes2)

    td: list[list[float]] = [[0.0] * (m + 1) for _ in range(n + 1)]
    fd_cache: dict = {}

    for ki in kr1:
        for kj in kr2:
            li = lml1[ki]
            lj = lml2[kj]

            rows = ki - li + 2  # offsets 0..ki-li+1
            cols = kj - lj + 2

            fd: list[list[float]] = [[0.0] * cols for _ in range(rows)]

            for r in range(1, rows):
                fd[r][0] = fd[r - 1][0] + c_del
            for c_idx in range(1, cols):
                fd[0][c_idx] = fd[0][c_idx - 1] + c_ins

            for r in range(1, rows):
                for c_idx in range(1, cols):
                    i = li + r - 1      # 1-based node in T1
                    j = lj + c_idx - 1  # 1-based node in T2
                    li2 = lml1[i]
                    lj2 = lml2[j]

                    opt_del = fd[r - 1][c_idx] + c_del
                    opt_ins = fd[r][c_idx - 1] + c_ins

                    if li2 == li and lj2 == lj:
                        ren = c_rel_fn(nodes1[i - 1], nodes2[j - 1])
                        best = min(opt_del, opt_ins, fd[r - 1][c_idx - 1] + ren)
                        fd[r][c_idx] = best
                        td[i][j] = best
                    else:
                        r2 = li2 - li
                        c2 = lj2 - lj
                        best = min(opt_del, opt_ins, fd[r2][c2] + td[i][j])
                        fd[r][c_idx] = best

            fd_cache[(ki, kj)] = (li, lj, fd)

    return td, fd_cache


# ---------------------------------------------------------------------------
# Backtracking — find matching
# ---------------------------------------------------------------------------

def _find_matching(
    n: int,
    m: int,
    nodes1: list[Node],
    nodes2: list[Node],
    lml1: list[int],
    lml2: list[int],
    td: list[list[float]],
    fd_cache: dict,
    lml_to_kr1: dict[int, int],
    lml_to_kr2: dict[int, int],
    c_del: float,
    c_ins: float,
    c_rel_fn,
) -> list[tuple[int, int]]:
    """
    Backtrack td/fd tables to find the set of matched (i, j) pairs (1-based).
    """
    EPS = 1e-9
    matched: set[tuple[int, int]] = set()

    def backtrack_subtree(i: int, j: int) -> None:
        if i == 0 or j == 0:
            return
        ki = lml_to_kr1[lml1[i]]
        kj = lml_to_kr2[lml2[j]]
        li, lj, fd = fd_cache[(ki, kj)]
        r = i - li + 1
        c = j - lj + 1
        backtrack_fd(ki, kj, li, lj, fd, r, c)

    def backtrack_fd(ki, kj, li, lj, fd, r: int, c: int) -> None:
        while r > 0 and c > 0:
            i = li + r - 1
            j = lj + c - 1
            li2 = lml1[i]
            lj2 = lml2[j]

            val = fd[r][c]

            if li2 == li and lj2 == lj:
                ren = c_rel_fn(nodes1[i - 1], nodes2[j - 1])
                if abs(val - (fd[r - 1][c] + c_del)) < EPS and val <= fd[r][c - 1] + c_ins:
                    r -= 1
                elif abs(val - (fd[r][c - 1] + c_ins)) < EPS:
                    c -= 1
                else:
                    matched.add((i, j))
                    r -= 1
                    c -= 1
            else:
                r2 = li2 - li
                c2 = lj2 - lj
                opt_tree = fd[r2][c2] + td[i][j]
                if abs(val - (fd[r - 1][c] + c_del)) < EPS and val <= fd[r][c - 1] + c_ins and val <= opt_tree:
                    r -= 1
                elif abs(val - (fd[r][c - 1] + c_ins)) < EPS and val <= opt_tree:
                    c -= 1
                else:
                    matched.add((i, j))
                    backtrack_subtree(i, j)
                    r = r2
                    c = c2

    backtrack_subtree(n, m)
    return list(matched)


# ---------------------------------------------------------------------------
# Path computation for IDF format
# ---------------------------------------------------------------------------

def _get_path(node: Node) -> str:
    """Return slash-separated path from root to node (using node labels)."""
    parts = []
    cur = node
    while cur is not None:
        parts.append(cur.label)
        cur = cur.parent
    parts.reverse()
    return '/'.join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_ted(T1: Tree, T2: Tree, costs: dict) -> float:
    """Compute TED between T1 and T2 using Chawathe/Zhang-Shasha."""
    ted, _ = compute_ted_and_script(T1, T2, costs)
    return ted


def compute_ted_and_script(
    T1: Tree, T2: Tree, costs: dict
) -> tuple[float, EditScript]:
    """
    Compute TED and extract edit script.

    :param T1: source tree
    :param T2: target tree
    :param costs: dict with keys 'insert', 'delete', 'relabel'
    :return: (TED value, EditScript)
    """
    c_del = costs.get('delete', 1)
    c_ins = costs.get('insert', 1)
    c_rel = costs.get('relabel', 1)

    def c_rel_fn(n1: Node, n2: Node) -> float:
        return 0.0 if n1.label == n2.label else c_rel

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

    # Build edit script from matching
    matched_t1 = {i for i, j in matching}
    matched_t2 = {j for i, j in matching}
    match_map = {i: j for i, j in matching}  # T1 idx -> T2 idx

    es = EditScript()

    # Relabels (matched pairs with different labels)
    for i, j in sorted(matching):
        n1 = nodes1[i - 1]
        n2 = nodes2[j - 1]
        if n1.label != n2.label:
            es.add(Action('relabel', c_rel, n1, {'new_label': n2.label, 't2_node': n2}))

    # Deletes (unmatched T1 nodes, bottom-up = postorder)
    for i in range(1, n + 1):
        if i not in matched_t1:
            n1 = nodes1[i - 1]
            es.add(Action('delete', c_del, n1, {'parent_node': n1.parent}))

    # Inserts (unmatched T2 nodes, top-down = preorder)
    reverse_match = {j: i for i, j in matching}   # T2 idx -> T1 idx
    t2_preorder = list(T2.preorder())
    t2_id_to_postorder = {id(n): i for i, n in enumerate(nodes2, 1)}
    for node in t2_preorder:
        j = t2_id_to_postorder[id(node)]
        if j not in matched_t2:
            parent = node.parent
            pos = parent.children.index(node) if parent else 0
            # Find the T1 source node matched to this T2 parent so the
            # patcher can look it up directly in id_map (handles cases
            # where parent label is not unique among siblings).
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
