"""
Serialize a Tree back to XML, Wikipedia infobox wikitext, or ASCII art.
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path

from classes.Node import Node
from classes.Tree import Tree


# ---------------------------------------------------------------------------
# Tree → ASCII art
# ---------------------------------------------------------------------------

def tree_to_text(tree: Tree, max_label: int = 80) -> str:
    """
    Render a tree as indented ASCII art, e.g.:

        country  (173 nodes)
        ├── name=Lebanon  [leaf]
        ├── conventional_long_name  [element]
        │   └── Lebanese Republic  [leaf]
        └── capital  [element]
            └── Beirut  [leaf]
    """
    root = tree.root
    lines = [f'{root.label}  ({tree.size()} nodes)']
    for i, child in enumerate(root.children):
        _render_node(child, lines, '', i == len(root.children) - 1, max_label)
    return '\n'.join(lines)


def _render_node(node: Node, lines: list, prefix: str, is_last: bool, max_label: int) -> None:
    connector = '└── ' if is_last else '├── '
    label = node.label if len(node.label) <= max_label else node.label[:max_label - 3] + '...'
    type_tag = '  [leaf]' if node.node_type == 'leaf' else ''
    lines.append(f'{prefix}{connector}{label}{type_tag}')
    if node.children:
        child_prefix = prefix + ('    ' if is_last else '│   ')
        for i, child in enumerate(node.children):
            _render_node(child, lines, child_prefix, i == len(node.children) - 1, max_label)


# ---------------------------------------------------------------------------
# Tree → XML
# ---------------------------------------------------------------------------

def tree_to_xml_element(node: Node) -> ET.Element:
    """
    Recursively convert a Node tree to an ET.Element tree.

    Attribute leaf nodes (label contains '=') become XML attributes on parent.
    Other leaf nodes become text content.
    Element nodes become sub-elements.
    """
    el = ET.Element(node.label)

    text_parts = []
    for child in node.children:
        if child.node_type == 'leaf':
            # Check if it's an attribute node (format: "name=value")
            if '=' in child.label and child.parent == node:
                # Only treat as attribute if it looks like attr=value
                k, _, v = child.label.partition('=')
                if k and not any(c in k for c in ' /\\'):
                    el.set(k, v)
                    continue
            # Plain text leaf
            text_parts.append(child.label)
        else:
            sub = tree_to_xml_element(child)
            el.append(sub)

    if text_parts:
        el.text = ' '.join(text_parts)

    return el


def tree_to_xml_string(tree: Tree, pretty: bool = True) -> str:
    """Convert a Tree to an XML string."""
    el = tree_to_xml_element(tree.root)
    rough = ET.tostring(el, encoding='unicode')
    if pretty:
        return minidom.parseString(rough).toprettyxml(indent='  ')
    return rough


def write_tree_xml(tree: Tree, path: Path) -> None:
    """Write a Tree as pretty-printed XML to a file."""
    el = tree_to_xml_element(tree.root)
    rough = ET.tostring(el, encoding='unicode')
    pretty = minidom.parseString(rough).toprettyxml(indent='  ', encoding='UTF-8')
    path.write_bytes(pretty)


# ---------------------------------------------------------------------------
# Tree → Wikipedia infobox wikitext
# ---------------------------------------------------------------------------

def tree_to_infobox(tree: Tree) -> str:
    """
    Best-effort conversion of a Tree back to Wikipedia infobox wikitext.

    Produces:
        {{Infobox country
        | field_name = value
        | field_name2 = value2
        ...
        }}
    """
    root = tree.root
    lines = ['{{Infobox country']

    for child in root.children:
        if child.node_type == 'leaf':
            # Attribute node — skip (metadata)
            continue
        if child.node_type == 'element':
            _emit_field(child, lines)

    lines.append('}}')
    return '\n'.join(lines)


def _emit_field(node: Node, lines: list[str], indent: int = 0) -> None:
    """Emit a single field node as a wikitext line."""
    prefix = '  ' * indent

    if node.label == 'established':
        lines.append(f'{prefix}| established_events =')
        for i, event in enumerate(node.children, 1):
            label_node = next((c for c in event.children if c.label == 'label'), None)
            date_node = next((c for c in event.children if c.label == 'date'), None)
            label_text = _leaf_text(label_node)
            date_text = _leaf_text(date_node)
            if label_text:
                lines.append(f'{prefix}| established_event{i} = {label_text}')
            if date_text:
                lines.append(f'{prefix}| established_date{i} = {date_text}')
        return

    if node.label == 'leaders':
        for i, leader in enumerate(node.children, 1):
            title_node = next((c for c in leader.children if c.label == 'title'), None)
            name_node = next((c for c in leader.children if c.label == 'name'), None)
            if title_node:
                lines.append(f'{prefix}| leader_title{i} = {_leaf_text(title_node)}')
            if name_node:
                lines.append(f'{prefix}| leader_name{i} = {_leaf_text(name_node)}')
        return

    # Multi-value field: children are <item> nodes
    item_children = [c for c in node.children if c.label == 'item']
    if item_children:
        items = [_leaf_text(ic) for ic in item_children]
        value = '{{unbulleted list|' + '|'.join(items) + '}}'
        lines.append(f'{prefix}| {node.label} = {value}')
        return

    # Single-value field
    value = _leaf_text(node)
    lines.append(f'{prefix}| {node.label} = {value}')


def _leaf_text(node: Node | None) -> str:
    """Extract text from a node: join all leaf descendants."""
    if node is None:
        return ''
    if node.node_type == 'leaf':
        return node.label
    parts = []
    for child in node.children:
        if child.node_type == 'leaf':
            parts.append(child.label)
        else:
            parts.append(_leaf_text(child))
    return ' '.join(p for p in parts if p)
