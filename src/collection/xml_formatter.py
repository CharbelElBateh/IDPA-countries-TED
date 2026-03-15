"""
Convert a cleaned infobox dictionary to a well-formed XML file.

Tree structure produced:
  <country name="Lebanon">
    <field_name>value</field_name>          ← single-value leaf
    <field_name>                             ← multi-value element (token_nodes mode)
      <item>value 1</item>
      <item>value 2</item>
    </field_name>
    <established>                            ← grouped numbered pairs
      <event>
        <label>Emirate of Mount Lebanon</label>
        <date>1516</date>
      </event>
    </established>
    <leaders>
      <leader>
        <title>President</title>
        <name>Joseph Aoun</name>
      </leader>
    </leaders>
  </country>
"""

import re
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path


# ---------------------------------------------------------------------------
# Field filtering
# ---------------------------------------------------------------------------

# Patterns for fields to drop (rendering / citation spillover / layout)
_FILTER_PATTERNS: list[re.Pattern] = [
    re.compile(r'^rowclass\d*$'),
    re.compile(r'^label\d*$'),
    re.compile(r'^data\d*$'),
    re.compile(r'^titlestyle$'),
    re.compile(r'^bodystyle$'),
    re.compile(r'^subbox$'),
    re.compile(r'^liststyle$'),
    re.compile(r'^item_style$'),
    re.compile(r'^map_width$'),
    re.compile(r'^alt_'),
    re.compile(r'^image_'),
    re.compile(r'^coa_size$'),
    re.compile(r'^area_label\d*$'),
    re.compile(r'^area_footnote$'),
    re.compile(r'^area_link$'),
    re.compile(r'^area_data\d*$'),
    re.compile(r'^today$'),
    re.compile(r'_ref$'),          # Gini_ref, HDI_ref, etc.
    # Citation spillover (when wptools pulls in embedded ref fields)
    re.compile(r'^last$'),
    re.compile(r'^date$'),
    re.compile(r'^title$'),
    re.compile(r'^journal$'),
    re.compile(r'^script-journal$'),
    re.compile(r'^volume$'),
    re.compile(r'^pages$'),
    re.compile(r'^url$'),
    re.compile(r'^url-status$'),
    re.compile(r'^archiveurl$'),
    re.compile(r'^archivedate$'),
    re.compile(r'^publisher$'),
]


def _should_filter(field: str) -> bool:
    return any(p.match(field) for p in _FILTER_PATTERNS)


# ---------------------------------------------------------------------------
# Grouped numbered-pair fields
# ---------------------------------------------------------------------------

def _extract_numbered_pairs(
    data: dict,
    key_prefix: str,
    label_prefix: str,
    value_prefix: str,
) -> tuple[list[tuple[str, str]], set[str]]:
    """
    Scan data for fields like `label_prefix1`, `value_prefix1`, etc.
    Returns (list of (label, value) tuples, set of consumed field names).
    """
    pairs: list[tuple[str, str]] = []
    consumed: set[str] = set()
    for i in range(1, 30):
        lk = f"{label_prefix}{i}"
        vk = f"{value_prefix}{i}"
        label_val = data.get(lk, '').strip()
        value_val = data.get(vk, '').strip()
        if not label_val and not value_val:
            continue
        pairs.append((label_val, value_val))
        consumed.add(lk)
        consumed.add(vk)
    return pairs, consumed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_xml(
    country_name: str,
    infobox: dict,
    tokenization_strategy: str = 'single_node',
) -> ET.Element:
    """
    Build an ElementTree Element tree from a cleaned infobox dict.

    :param country_name: used as the 'name' attribute on <country>
    :param infobox: dict of field_name → cleaned value string(s)
    :param tokenization_strategy: 'single_node' | 'token_nodes'
    :return: <country> Element
    """
    from src.collection.wikitext_cleaner import clean_value, extract_list_items

    root = ET.Element('country', name=country_name)

    consumed: set[str] = set()

    # --- Group established_event*/established_date* pairs ---
    est_pairs, est_consumed = _extract_numbered_pairs(
        infobox,
        key_prefix='established',
        label_prefix='established_event',
        value_prefix='established_date',
    )
    consumed |= est_consumed

    # --- Group leader_title*/leader_name* pairs ---
    leader_pairs, leader_consumed = _extract_numbered_pairs(
        infobox,
        key_prefix='leader',
        label_prefix='leader_title',
        value_prefix='leader_name',
    )
    consumed |= leader_consumed

    # --- Emit regular fields ---
    for field, raw_value in infobox.items():
        if field in consumed:
            continue
        if _should_filter(field):
            continue

        tag = _safe_tag(field)
        raw = str(raw_value) if raw_value is not None else ''

        if tokenization_strategy == 'token_nodes':
            items = extract_list_items(raw)
            if len(items) > 1:
                el = ET.SubElement(root, tag)
                for item in items:
                    item_el = ET.SubElement(el, 'item')
                    item_el.text = item
            elif items:
                el = ET.SubElement(root, tag)
                el.text = items[0]
        else:
            value = clean_value(raw)
            if value:
                el = ET.SubElement(root, tag)
                el.text = value

    # --- Emit <established> group ---
    if est_pairs:
        est_el = ET.SubElement(root, 'established')
        for (event_label, event_date) in est_pairs:
            ev_el = ET.SubElement(est_el, 'event')
            if event_label:
                lbl_el = ET.SubElement(ev_el, 'label')
                lbl_el.text = clean_value(event_label)
            if event_date:
                dt_el = ET.SubElement(ev_el, 'date')
                dt_el.text = clean_value(event_date)

    # --- Emit <leaders> group ---
    if leader_pairs:
        leaders_el = ET.SubElement(root, 'leaders')
        for (title, name) in leader_pairs:
            leader_el = ET.SubElement(leaders_el, 'leader')
            if title:
                title_el = ET.SubElement(leader_el, 'title')
                title_el.text = clean_value(title)
            if name:
                name_el = ET.SubElement(leader_el, 'name')
                name_el.text = clean_value(name)

    return root


def write_xml(element: ET.Element, path: Path):
    """Pretty-print an Element tree to a file."""
    rough = ET.tostring(element, encoding='unicode')
    reparsed = minidom.parseString(rough)
    pretty = reparsed.toprettyxml(indent='  ', encoding='UTF-8')
    path.write_bytes(pretty)


def _safe_tag(name: str) -> str:
    """Convert an infobox field name to a valid XML tag."""
    tag = re.sub(r'[^a-zA-Z0-9_\-.]', '_', name)
    if tag and tag[0].isdigit():
        tag = '_' + tag
    return tag or '_field'
