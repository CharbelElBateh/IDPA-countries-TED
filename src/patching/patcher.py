"""
Apply an EditScript to a Tree to transform it.

Operations applied in order:
  1. relabel  — change node label in-place
  2. delete   — remove node and its subtree from its parent
  3. insert   — add new node at specified parent + position

Note on iterative refinement
─────────────────────────────
For trees with large structural differences the TED matching can place
matched nodes across different structural levels (e.g. a deeply-nested
node matched to a shallower one).  When the matched node's ancestor is
then deleted, the node is removed with the ancestor's subtree — the
sequential edit script leaves a non-zero residual TED.

apply_edit_script handles this transparently: after the first pass it
checks TED(result, target).  If the residual is non-zero it applies
correction rounds (each round = fresh extract_edit_script + apply) until
TED == 0 or max_rounds is exhausted.  The target/costs parameters are
only needed when iterative refinement is desired.
"""

from classes.Node import Node
from classes.Tree import Tree
from classes.Action import Action
from classes.EditScript import EditScript


def apply_edit_script(
    tree: Tree,
    script: EditScript,
    reverse: bool = False,
    target: Tree | None = None,
    costs: dict | None = None,
    max_rounds: int = 5,
) -> Tree:
    """
    Apply *script* to a deep copy of *tree* and return the modified copy.

    When *target* and *costs* are provided the result is verified against
    *target* and correction rounds are applied until TED == 0 (up to
    *max_rounds* total, including the first pass).
    """
    result, id_map = _deep_copy_tree(tree)

    ops = list(script.operations)
    if reverse:
        ops = list(reversed(ops))

    for action in ops:
        if reverse:
            _apply_reverse(result, action, id_map)
        else:
            _apply_forward(result, action, id_map)

    # Iterative refinement — only when target is supplied
    if target is not None and costs is not None:
        from src.ted.chawathe import compute_ted, compute_ted_and_script
        for _ in range(max_rounds - 1):
            if compute_ted(result, target, costs) == 0:
                break
            _, fix_script = compute_ted_and_script(result, target, costs)
            result, id_map = _deep_copy_tree(result)
            for action in fix_script.operations:
                _apply_forward(result, action, id_map)

    return result


def _apply_forward(tree: Tree, action: Action, id_map: dict) -> None:
    """Apply a single action in the forward direction."""
    if action.op_type == 'relabel':
        # action.node is a T1 node — look it up directly via id map
        node = id_map.get(id(action.node))
        if node is not None:
            node.label = action.args['new_label']
            # Also register the matched target node so it can be found as
            # a parent by subsequent insert actions.
            t2_node = action.args.get('t2_node')
            if t2_node is not None:
                id_map[id(t2_node)] = node

    elif action.op_type == 'delete':
        node = id_map.get(id(action.node))
        if node is not None and node.parent is not None:
            node.parent.remove_child(node)
        elif node is not None and node.parent is None:
            tree.root = Node(label='', node_type='element')

    elif action.op_type == 'insert':
        # action.node   = target-tree node being inserted
        # parent        = target-tree parent node
        # source_parent = source-tree node matched to parent (always in
        #                 id_map; None if parent was itself inserted)
        parent_node: Node | None = action.args.get('parent')
        source_parent: Node | None = action.args.get('source_parent')
        position: int = action.args.get('position', 0)
        new_node = Node(label=action.node.label, node_type=action.node.node_type)
        if parent_node is None:
            new_node.add_child(tree.root)
            tree.root = new_node
        else:
            # 1. Matched source parent — always in id_map (from deep copy).
            #    Handles non-unique sibling labels correctly.
            parent_in_tree = id_map.get(id(source_parent)) if source_parent is not None else None
            # 2. Previously-inserted target parent tracked in id_map.
            if parent_in_tree is None:
                parent_in_tree = id_map.get(id(parent_node))
            # 3. Label-path fallback for uniquely-reachable nodes.
            if parent_in_tree is None:
                parent_in_tree = _find_node_by_label_path(tree, _node_path(parent_node))
            if parent_in_tree is not None:
                parent_in_tree.insert_child(position, new_node)
        # Register new node so its children can find it by id in step 2.
        id_map[id(action.node)] = new_node


def _apply_reverse(tree: Tree, action: Action, id_map: dict) -> None:
    """Apply a single action in the reverse direction (swap insert/delete, swap relabel).

    id_map maps original T2 node ids to their copies in the result tree.
    Reverse relabels use the 't2_node' stored in action.args for exact id lookup.
    """
    if action.op_type == 'relabel':
        # Use the T2 node reference stored by the TED algorithm for exact lookup
        t2_node = action.args.get('t2_node')
        node = id_map.get(id(t2_node)) if t2_node is not None else None
        if node is None:
            # Fallback: path-based (works when T2 labels are unique in context)
            new_label = action.args['new_label']
            node = _find_node_by_label_path(tree, _node_path_with_new(action.node, new_label))
        if node is not None:
            node.label = action.node.label

    elif action.op_type == 'delete':
        # Reverse of delete = insert: re-insert the deleted node
        parent_node: Node | None = action.node.parent
        new_node = Node(label=action.node.label, node_type=action.node.node_type)
        if parent_node is None:
            new_node.add_child(tree.root)
            tree.root = new_node
        else:
            parent_in_tree = _find_node_by_label_path(tree, _node_path(parent_node))
            if parent_in_tree is not None:
                position = 0
                if parent_node and action.node in parent_node.children:
                    position = parent_node.children.index(action.node)
                parent_in_tree.insert_child(position, new_node)

    elif action.op_type == 'insert':
        # Reverse of insert = delete: remove the inserted T2 node from copy
        node = _find_node_by_label_path(tree, _node_path(action.node))
        if node is not None and node.parent is not None:
            node.parent.remove_child(node)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep_copy_tree(tree: Tree) -> tuple[Tree, dict]:
    """
    Return a deep copy of the tree with parent pointers intact,
    plus a mapping {id(original_node): copied_node} for all nodes.
    """
    id_map: dict[int, Node] = {}
    new_root = _copy_node(tree.root, None, id_map)
    return Tree(new_root), id_map


def _copy_node(node: Node, parent: Node | None, id_map: dict) -> Node:
    new_node = Node(label=node.label, node_type=node.node_type)
    new_node.parent = parent
    id_map[id(node)] = new_node
    for child in node.children:
        new_child = _copy_node(child, new_node, id_map)
        new_node.children.append(new_child)
    return new_node


def _node_path(node: Node) -> str:
    """Return slash-separated label path from root to node."""
    parts = []
    cur = node
    while cur is not None:
        parts.append(cur.label)
        cur = cur.parent
    parts.reverse()
    return '/'.join(parts)


def _node_path_with_new(node: Node, new_label: str) -> str:
    """Return path where node's own label is replaced with new_label."""
    parts = []
    cur = node.parent
    while cur is not None:
        parts.append(cur.label)
        cur = cur.parent
    parts.reverse()
    parts.append(new_label)
    return '/'.join(parts)


def _find_node_by_label_path(tree: Tree, path: str) -> Node | None:
    """
    Find a node in tree matching the given slash-separated label path.
    Returns the first match in preorder, or None.
    Used only for insert parent lookups (where labels are unique element tags).
    """
    parts = path.split('/')
    if not parts:
        return None
    cur = tree.root
    if cur.label != parts[0]:
        return None
    for part in parts[1:]:
        found = None
        for child in cur.children:
            if child.label == part:
                found = child
                break
        if found is None:
            return None
        cur = found
    return cur