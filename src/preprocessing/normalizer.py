"""
Normalize element node labels in a Tree using the field alias map.
Maps variant field names to their canonical forms.
"""

import json
from pathlib import Path

from classes.Tree import Tree

CONFIG_DIR = Path('config')


def _load_aliases() -> dict[str, str]:
    path = CONFIG_DIR / 'field_aliases.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return {}


def normalize_tree(tree: Tree, aliases: dict[str, str] | None = None) -> Tree:
    """
    Rename element node labels to canonical forms using alias map.
    Modifies the tree in-place and returns it.

    :param tree: Tree to normalize
    :param aliases: {variant: canonical}. Defaults to field_aliases.json.
    :return: the same Tree (modified in-place)
    """
    if aliases is None:
        aliases = _load_aliases()
    for node in tree.preorder():
        if node.is_element() and node.label in aliases:
            node.label = aliases[node.label]
    return tree
