"""
Format an EditScript as an IDF (IDPA Diff Format) XML document.

Namespace: urn:idpa:diff:1.0

Example output:
    <?xml version="1.0" encoding="UTF-8"?>
    <idf:diff xmlns:idf="urn:idpa:diff:1.0"
              source="Lebanon" target="Switzerland"
              algorithm="chawathe"
              ted_raw="42" sim_inverse="0.023"
              sim_normalized="0.723" sim_ratio="0.785">
      <idf:operations count="3">
        <idf:insert id="op1" parent_path="country/government" position="2">
          <idf:node label="federal_council" node_type="element"/>
        </idf:insert>
        <idf:delete id="op2">
          <idf:node label="president" node_type="element"
                    path="country/government/president"/>
        </idf:delete>
        <idf:relabel id="op3" path="country/government/leader_name1">
          <idf:from>Joseph Aoun</idf:from>
          <idf:to>Karin Keller-Sutter</idf:to>
        </idf:relabel>
      </idf:operations>
    </idf:diff>
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path

from classes.EditScript import EditScript
from classes.Node import Node

IDF_NS = 'urn:idpa:diff:1.0'
IDF_PREFIX = 'idf'


def _tag(local: str) -> str:
    return f'{{{IDF_NS}}}{local}'


def _node_path(node: Node) -> str:
    """Return slash-separated path from root to node."""
    parts = []
    cur = node
    while cur is not None:
        parts.append(cur.label)
        cur = cur.parent
    parts.reverse()
    return '/'.join(parts)


def build_idf(
    source_name: str,
    target_name: str,
    algorithm: str,
    ted_raw: float,
    sim_inverse: float,
    sim_ratio: float,
    edit_script: EditScript,
) -> ET.Element:
    """
    Build an IDF XML Element tree.

    :return: root <idf:diff> Element
    """
    ET.register_namespace(IDF_PREFIX, IDF_NS)

    root = ET.Element(_tag('diff'), {
        'source': source_name,
        'target': target_name,
        'algorithm': algorithm,
        'ted_raw': str(int(ted_raw) if ted_raw == int(ted_raw) else ted_raw),
        'sim_inverse': f'{sim_inverse:.6f}',
        'sim_ratio': f'{sim_ratio:.6f}',
    })

    ops_el = ET.SubElement(root, _tag('operations'), count=str(len(edit_script)))

    for idx, action in enumerate(edit_script, 1):
        op_id = f'op{idx}'

        if action.op_type == 'insert':
            parent_node: Node | None = action.args.get('parent')
            position: int = action.args.get('position', 0)
            parent_path = _node_path(parent_node) if parent_node else ''
            op_el = ET.SubElement(ops_el, _tag('insert'), {
                'id': op_id,
                'parent_path': parent_path,
                'position': str(position),
            })
            ET.SubElement(op_el, _tag('node'), {
                'label': action.node.label,
                'node_type': action.node.node_type,
            })

        elif action.op_type == 'delete':
            op_el = ET.SubElement(ops_el, _tag('delete'), {'id': op_id})
            ET.SubElement(op_el, _tag('node'), {
                'label': action.node.label,
                'node_type': action.node.node_type,
                'path': _node_path(action.node),
            })

        elif action.op_type == 'relabel':
            op_el = ET.SubElement(ops_el, _tag('relabel'), {
                'id': op_id,
                'path': _node_path(action.node),
            })
            from_el = ET.SubElement(op_el, _tag('from'))
            from_el.text = action.node.label
            to_el = ET.SubElement(op_el, _tag('to'))
            to_el.text = action.args.get('new_label', '')

    return root


def write_idf(element: ET.Element, path: Path) -> None:
    """Pretty-print an IDF Element tree to a file."""
    rough = ET.tostring(element, encoding='unicode')
    reparsed = minidom.parseString(rough)
    pretty = reparsed.toprettyxml(indent='  ', encoding='UTF-8')
    path.write_bytes(pretty)


def diff_to_idf(
    source_name: str,
    target_name: str,
    algorithm: str,
    ted_raw: float,
    sim_inverse: float,
    sim_ratio: float,
    edit_script: EditScript,
    output_path: Path | None = None,
) -> str:
    """
    Build an IDF diff and return it as a string.
    Optionally write to output_path.
    """
    root = build_idf(
        source_name, target_name, algorithm,
        ted_raw, sim_inverse, sim_ratio, edit_script,
    )
    rough = ET.tostring(root, encoding='unicode')
    pretty = minidom.parseString(rough).toprettyxml(indent='  ')

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(pretty, encoding='utf-8')

    return pretty
