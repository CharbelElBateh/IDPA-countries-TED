"""
Parse a country infobox XML file into a Tree of Node objects.

Tree structure produced:
  - Element nodes: node_type='element', label=tag_name
  - Attribute leaf nodes: node_type='leaf', label='attr_name=attr_value'
      (sorted alphabetically by attr_name, appear before element children)
  - Text leaf nodes: node_type='leaf', label=text_content
      single_node: one leaf per element text
      token_nodes: one leaf per token
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from classes.Node import Node
from classes.Tree import Tree
from src.preprocessing.tokenizer import tokenize

CONFIG_DIR = Path('config')


def _load_tokenization_strategy() -> str:
    path = CONFIG_DIR / 'tokenization.json'
    if path.exists():
        cfg = json.loads(path.read_text(encoding='utf-8'))
        return cfg.get('strategy', 'single_node')
    return 'single_node'


def _build_node(xml_elem: ET.Element, strategy: str) -> Node:
    """Recursively build a Node from an ET.Element."""
    node = Node(label=xml_elem.tag, node_type='element')

    # 1. Attribute children — sorted alphabetically, placed first
    for attr_name in sorted(xml_elem.attrib.keys()):
        attr_val = xml_elem.attrib[attr_name]
        attr_node = Node(label=f"{attr_name}={attr_val}", node_type='leaf')
        node.add_child(attr_node)

    # 2. Sub-elements or text content
    if len(xml_elem) > 0:
        for child_elem in xml_elem:
            node.add_child(_build_node(child_elem, strategy))
    else:
        text = (xml_elem.text or '').strip()
        if text:
            if strategy == 'token_nodes':
                tokens = tokenize(text)
                for token in tokens:
                    node.add_child(Node(label=token, node_type='leaf'))
            else:
                node.add_child(Node(label=text, node_type='leaf'))

    return node


def parse_xml_file(xml_path: Path, strategy: str | None = None) -> Tree:
    """
    Parse an XML file and return a Tree object.

    :param xml_path: path to the XML file
    :param strategy: 'single_node' | 'token_nodes' (default: from config)
    :return: Tree object
    """
    if strategy is None:
        strategy = _load_tokenization_strategy()
    root_elem = ET.parse(str(xml_path)).getroot()
    return Tree(_build_node(root_elem, strategy))


def parse_xml_string(xml_str: str, strategy: str = 'single_node') -> Tree:
    """Parse an XML string into a Tree (useful for testing)."""
    root_elem = ET.fromstring(xml_str)
    return Tree(_build_node(root_elem, strategy))
