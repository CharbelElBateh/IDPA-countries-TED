"""
Render a Tree as a self-contained HTML file that mimics the Wikipedia
country-infobox sidebar style.
"""

from __future__ import annotations
from html import escape
from pathlib import Path

from classes.Node import Node
from classes.Tree import Tree


# ---------------------------------------------------------------------------
# CSS — Wikipedia-inspired infobox look
# ---------------------------------------------------------------------------

_CSS = """\
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Linux Libertine', 'Georgia', 'Times New Roman', serif;
  background: #f6f6f6; padding: 24px;
  display: flex; justify-content: center;
}
.infobox {
  width: 340px; border: 1px solid #a2a9b1; border-collapse: collapse;
  background: #f8f9fa; font-size: 13.5px; line-height: 1.5;
}
.infobox caption,
.infobox .ib-header {
  background: #ccd2d9; padding: 8px 10px;
  font-size: 1.2em; font-weight: 700; text-align: center;
  border-bottom: 1px solid #a2a9b1;
}
.infobox .ib-subheader {
  background: #dde; padding: 4px 10px;
  font-size: 0.95em; text-align: center; font-style: italic;
  border-bottom: 1px solid #a2a9b1;
}
.infobox .ib-section {
  background: #e0e0e0; padding: 5px 10px;
  font-weight: 700; text-align: center; font-size: 0.92em;
  border-top: 1px solid #a2a9b1; border-bottom: 1px solid #a2a9b1;
}
.infobox tr { border-bottom: 1px solid #e0e0e0; }
.infobox th {
  padding: 4px 10px; text-align: left; vertical-align: top;
  font-weight: 600; width: 38%; color: #333; font-size: 0.9em;
  background: #f0f2f4;
}
.infobox td {
  padding: 4px 10px; vertical-align: top; font-size: 0.92em;
}
.infobox ul {
  margin: 0; padding-left: 16px;
}
.infobox ul li { margin-bottom: 1px; }
.ib-footer {
  padding: 6px 10px; font-size: 0.82em; color: #666;
  text-align: center; border-top: 1px solid #a2a9b1;
  background: #eef;
}
"""

# Map internal field names to human-friendly Wikipedia labels.
_FIELD_LABELS: dict[str, str] = {
    'conventional_long_name': 'Official name',
    'common_name': 'Common name',
    'native_name': 'Native name',
    'national_motto': 'Motto',
    'national_anthem': 'Anthem',
    'capital': 'Capital',
    'largest_city': 'Largest city',
    'official_languages': 'Official languages',
    'languages': 'Languages',
    'languages_type': 'Languages type',
    'languages2': 'Recognised languages',
    'languages2_type': 'Languages (other) type',
    'demonym': 'Demonym',
    'ethnic_groups': 'Ethnic groups',
    'ethnic_groups_year': 'Ethnic groups (year)',
    'religion': 'Religion',
    'religion_year': 'Religion (year)',
    'government_type': 'Government',
    'legislature': 'Legislature',
    'upper_house': 'Upper house',
    'lower_house': 'Lower house',
    'area_km2': 'Area (km²)',
    'area_rank': 'Area rank',
    'area_sq_mi': 'Area (sq mi)',
    'percent_water': 'Water (%)',
    'population_estimate': 'Population estimate',
    'population_estimate_year': 'Population est. year',
    'population_estimate_rank': 'Population rank',
    'population_census': 'Population census',
    'population_census_year': 'Census year',
    'population_density_km2': 'Density (/km²)',
    'population_density_sq_mi': 'Density (/sq mi)',
    'GDP_PPP': 'GDP (PPP)',
    'GDP_PPP_year': 'GDP (PPP) year',
    'GDP_PPP_rank': 'GDP (PPP) rank',
    'GDP_PPP_per_capita': 'GDP (PPP) per capita',
    'GDP_PPP_per_capita_rank': 'Per capita rank',
    'GDP_nominal': 'GDP (nominal)',
    'GDP_nominal_year': 'GDP (nominal) year',
    'GDP_nominal_rank': 'GDP (nominal) rank',
    'GDP_nominal_per_capita': 'GDP (nominal) per capita',
    'GDP_nominal_per_capita_rank': 'Per capita rank',
    'Gini': 'Gini coefficient',
    'Gini_year': 'Gini year',
    'Gini_change': 'Gini change',
    'HDI': 'HDI',
    'HDI_year': 'HDI year',
    'HDI_change': 'HDI change',
    'HDI_rank': 'HDI rank',
    'currency': 'Currency',
    'currency_code': 'Currency code',
    'time_zone': 'Time zone',
    'utc_offset': 'UTC offset',
    'utc_offset_DST': 'UTC offset (DST)',
    'time_zone_DST': 'Time zone (DST)',
    'drives_on': 'Driving side',
    'calling_code': 'Calling code',
    'cctld': 'Internet TLD',
    'iso3166code': 'ISO 3166 code',
    'coordinates': 'Coordinates',
    'map_caption': 'Map caption',
}

# Sections: group consecutive fields under a section heading.
_SECTIONS: list[tuple[str, list[str]]] = [
    ('', [
        'conventional_long_name', 'common_name', 'native_name',
        'national_motto', 'national_anthem', 'map_caption',
    ]),
    ('', [
        'capital', 'largest_city', 'official_languages', 'languages',
        'languages_type', 'languages2', 'languages2_type',
        'demonym', 'ethnic_groups', 'ethnic_groups_year',
        'religion', 'religion_year', 'coordinates',
    ]),
    ('Government', [
        'government_type', 'legislature', 'upper_house', 'lower_house',
    ]),
    ('Area', [
        'area_km2', 'area_rank', 'area_sq_mi', 'percent_water',
    ]),
    ('Population', [
        'population_estimate', 'population_estimate_year',
        'population_estimate_rank', 'population_census',
        'population_census_year', 'population_density_km2',
        'population_density_sq_mi',
    ]),
    ('GDP (PPP)', [
        'GDP_PPP', 'GDP_PPP_year', 'GDP_PPP_rank',
        'GDP_PPP_per_capita', 'GDP_PPP_per_capita_rank',
    ]),
    ('GDP (nominal)', [
        'GDP_nominal', 'GDP_nominal_year', 'GDP_nominal_rank',
        'GDP_nominal_per_capita', 'GDP_nominal_per_capita_rank',
    ]),
    ('Development', [
        'Gini', 'Gini_year', 'Gini_change',
        'HDI', 'HDI_year', 'HDI_change', 'HDI_rank',
    ]),
    ('Miscellaneous', [
        'currency', 'currency_code', 'time_zone', 'utc_offset',
        'time_zone_DST', 'utc_offset_DST', 'drives_on',
        'calling_code', 'cctld', 'iso3166code',
    ]),
]

# Collect all explicitly-listed fields for quick lookup.
_LISTED_FIELDS: set[str] = set()
for _sec_name, _fields in _SECTIONS:
    _LISTED_FIELDS.update(_fields)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _render_value_html(node: Node) -> str:
    """Render a field node's value as HTML (handles <item> lists)."""
    item_children = [c for c in node.children if c.label == 'item']
    if item_children:
        items = ''.join(f'<li>{escape(_leaf_text(ic))}</li>' for ic in item_children)
        return f'<ul>{items}</ul>'
    return escape(_leaf_text(node))


def _render_established(node: Node) -> str:
    """Render the <established> grouped node as multiple table rows."""
    rows = []
    for event in node.children:
        label_node = next((c for c in event.children if c.label == 'label'), None)
        date_node = next((c for c in event.children if c.label == 'date'), None)
        label_text = _leaf_text(label_node) if label_node else ''
        date_text = _leaf_text(date_node) if date_node else ''
        if label_text or date_text:
            rows.append(
                f'<tr><th>{escape(label_text)}</th>'
                f'<td>{escape(date_text)}</td></tr>'
            )
    return '\n'.join(rows)


def _render_leaders(node: Node) -> str:
    """Render the <leaders> grouped node as multiple table rows."""
    rows = []
    for leader in node.children:
        title_node = next((c for c in leader.children if c.label == 'title'), None)
        name_node = next((c for c in leader.children if c.label == 'name'), None)
        title_text = _leaf_text(title_node) if title_node else ''
        name_text = _leaf_text(name_node) if name_node else ''
        if title_text or name_text:
            rows.append(
                f'<tr><th>{escape(title_text)}</th>'
                f'<td>{escape(name_text)}</td></tr>'
            )
    return '\n'.join(rows)


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

def generate_infobox_html(tree: Tree, country_name: str, subtitle: str = '') -> str:
    """
    Render *tree* as a self-contained Wikipedia-style infobox HTML page.

    Parameters
    ----------
    tree : Tree
        The country tree (original or patched).
    country_name : str
        Display name shown in the infobox header.
    subtitle : str, optional
        Extra line below the header (e.g. "patched from Lebanon").
    """
    root = tree.root

    # Build a dict of field_label -> node for quick lookup
    field_map: dict[str, Node] = {}
    for child in root.children:
        if child.node_type == 'element':
            field_map[child.label] = child

    rows_html: list[str] = []

    # Render sections in order
    for sec_name, fields in _SECTIONS:
        sec_rows = []
        for field in fields:
            if field not in field_map:
                continue
            node = field_map[field]
            label = _FIELD_LABELS.get(field, field.replace('_', ' ').title())
            value = _render_value_html(node)
            if value:
                sec_rows.append(
                    f'<tr><th>{escape(label)}</th><td>{value}</td></tr>'
                )
        if sec_rows:
            if sec_name:
                rows_html.append(
                    f'<tr><td colspan="2" class="ib-section">{escape(sec_name)}</td></tr>'
                )
            rows_html.extend(sec_rows)

    # Special grouped fields: leaders
    if 'leaders' in field_map:
        rows_html.append(
            '<tr><td colspan="2" class="ib-section">Leadership</td></tr>'
        )
        rows_html.append(_render_leaders(field_map['leaders']))

    # Special grouped fields: established
    if 'established' in field_map:
        rows_html.append(
            '<tr><td colspan="2" class="ib-section">Established</td></tr>'
        )
        rows_html.append(_render_established(field_map['established']))

    # Any remaining fields not in the explicit list
    remaining = []
    for child in root.children:
        if child.node_type != 'element':
            continue
        if child.label in _LISTED_FIELDS or child.label in ('established', 'leaders'):
            continue
        label = _FIELD_LABELS.get(child.label, child.label.replace('_', ' ').title())
        value = _render_value_html(child)
        if value:
            remaining.append(
                f'<tr><th>{escape(label)}</th><td>{value}</td></tr>'
            )
    if remaining:
        rows_html.append(
            '<tr><td colspan="2" class="ib-section">Other</td></tr>'
        )
        rows_html.extend(remaining)

    subtitle_html = ''
    if subtitle:
        subtitle_html = f'<tr><td colspan="2" class="ib-subheader">{escape(subtitle)}</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Infobox: {escape(country_name)}</title>
  <style>{_CSS}</style>
</head>
<body>
  <table class="infobox">
    <tr><td colspan="2" class="ib-header">{escape(country_name)}</td></tr>
    {subtitle_html}
    {''.join(rows_html)}
    <tr><td colspan="2" class="ib-footer">
      Generated by IDPA TED Pipeline &middot; {tree.size()} nodes
    </td></tr>
  </table>
</body>
</html>
"""


def write_infobox_html(
    path: Path,
    tree: Tree,
    country_name: str,
    subtitle: str = '',
) -> str:
    """Write the infobox HTML to *path* and return the HTML string."""
    html = generate_infobox_html(tree, country_name, subtitle)
    path.write_text(html, encoding='utf-8')
    return html