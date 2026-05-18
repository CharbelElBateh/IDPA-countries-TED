"""Render a country :class:`Tree` as HTML using nested ``<details>`` blocks.

The output is a single self-contained HTML fragment intended to be dropped
into a Bootstrap-styled page. Each structural node is rendered as a
collapsible ``<details>``; each leaf is rendered as a list item with a
type badge and a formatted value.
"""

from __future__ import annotations

from datetime import date, datetime
from html import escape
from typing import Any

from src.core import Node, Tree
from src.taxonomy import TaxonomyRegistry


# ----------------------------------------------------------- value formatters
def format_currency(amount: float) -> str:
    """``78233000000`` → ``"$78.23B"``."""
    sign = "-" if amount < 0 else ""
    n = abs(amount)
    if n >= 1e12:
        return f"{sign}${n / 1e12:.2f}T"
    if n >= 1e9:
        return f"{sign}${n / 1e9:.2f}B"
    if n >= 1e6:
        return f"{sign}${n / 1e6:.2f}M"
    if n >= 1e3:
        return f"{sign}${n / 1e3:.1f}K"
    return f"{sign}${n:,.2f}"


def format_number(n: float) -> str:
    if isinstance(n, float) and n.is_integer():
        n = int(n)
    if isinstance(n, int):
        return f"{n:,}"
    if abs(n) >= 1e6:
        return f"{n:,.2f}"
    return f"{n:g}"


def format_date(d: Any) -> str:
    if isinstance(d, (date, datetime)):
        return d.isoformat()
    return str(d)


def format_distribution(items: list[dict[str, Any]],
                        max_shown: int = 6) -> str:
    """Render a distribution payload as a chip list."""
    if not items:
        return '<span class="text-muted">∅</span>'
    chips: list[str] = []
    for it in items[:max_shown]:
        path = " › ".join(escape(p) for p in it.get("path", []))
        w = float(it.get("weight", 0)) * 100
        chips.append(
            f'<span class="badge bg-secondary me-1">{path} '
            f'<small>{w:.0f}%</small></span>'
        )
    if len(items) > max_shown:
        chips.append(
            f'<span class="text-muted small">+{len(items) - max_shown} more</span>'
        )
    return " ".join(chips)


def format_coordinates(coords: Any) -> str:
    if isinstance(coords, (list, tuple)) and len(coords) == 2:
        lat, lon = coords
        return f"{lat:.4f}, {lon:.4f}"
    return str(coords)


def format_trend(trend: int | None) -> str:
    if trend is None:
        return ""
    icon = {1: "▲", 0: "▬", -1: "▼"}[trend]
    color = {1: "success", 0: "secondary", -1: "danger"}[trend]
    return f'<span class="text-{color} ms-2">{icon}</span>'


# ----------------------------------------------------------- node renderer
TYPE_BADGE_COLORS = {
    "number":       "info",
    "percent":      "info",
    "year":         "info",
    "date":         "info",
    "currency":     "success",
    "coordinates":  "warning",
    "wikilink":     "primary",
    "text":         "secondary",
    "distribution": "danger",
}


def render_leaf(node: Node) -> str:
    """Render one leaf node as an HTML ``<li>``."""
    type_color = TYPE_BADGE_COLORS.get(node.type or "", "dark")
    type_badge = (f'<span class="badge bg-{type_color} type-badge">'
                  f'{escape(node.type or "?")}</span>')

    value_html = _format_value(node)
    trend_html = format_trend(node.trend)
    unit_html = (f'<span class="text-muted ms-2">{escape(node.unit)}</span>'
                 if node.unit else "")

    raw_html = ""
    if node.raw and node.raw.strip() != str(node.value):
        raw_html = (f'<span class="raw-value" title="{escape(node.raw)}">'
                    f' <i class="text-muted small">(raw)</i></span>')

    return (
        f'<li class="leaf-row">'
        f'<span class="leaf-label">{escape(node.label)}</span>'
        f' {type_badge}'
        f' <span class="leaf-value">{value_html}</span>'
        f'{unit_html}{trend_html}{raw_html}'
        f'</li>'
    )


def _format_value(node: Node) -> str:
    t = node.type
    v = node.value
    if v is None:
        return '<span class="text-muted">∅</span>'
    if t == "currency":
        return f'<strong>{format_currency(float(v))}</strong>'
    if t == "number":
        return f'<strong>{format_number(v)}</strong>'
    if t == "percent":
        return f'<strong>{format_number(v)}%</strong>'
    if t == "year":
        return f'<strong>{v}</strong>'
    if t == "date":
        return f'<strong>{format_date(v)}</strong>'
    if t == "coordinates":
        return f'<strong>{format_coordinates(v)}</strong>'
    if t == "distribution":
        return format_distribution(v)
    return escape(str(v))


def render_structural(node: Node, open_by_default: bool = False) -> str:
    """Render a structural subtree as a collapsible block."""
    open_attr = " open" if open_by_default else ""
    body_parts: list[str] = []

    # Render structural children first, then leaves.
    structurals = [c for c in node.children if c.is_structural]
    leaves = [c for c in node.children if c.is_leaf]

    if leaves:
        body_parts.append("<ul class='leaf-list'>")
        for child in leaves:
            body_parts.append(render_leaf(child))
        body_parts.append("</ul>")

    for child in structurals:
        body_parts.append(render_structural(child, open_by_default=False))

    counts = {
        "leaves": sum(1 for c in node.walk() if c.is_leaf),
    }
    summary = (
        f'<summary>'
        f'<span class="struct-label">{escape(node.label)}</span>'
        f'<span class="struct-count">{counts["leaves"]} fields</span>'
        f'</summary>'
    )
    return (f'<details class="struct-block"{open_attr}>{summary}'
            f'<div class="struct-body">'
            + "".join(body_parts) +
            f'</div></details>')


def render_tree(tree: Tree) -> str:
    """Render a country tree as a full HTML fragment."""
    return render_structural(tree.root, open_by_default=True)


# ----------------------------------------------------------- tree to dict
def tree_to_dict(node: Node) -> dict[str, Any]:
    """JSON-friendly recursive representation of a node."""
    if node.is_leaf:
        return {
            "kind": "leaf",
            "label": node.label,
            "type": node.type,
            "value": _jsonable(node.value),
            "raw": node.raw,
            "unit": node.unit,
            "trend": node.trend,
            "taxonomy": node.taxonomy,
        }
    return {
        "kind": "structural",
        "label": node.label,
        "children": [tree_to_dict(c) for c in node.children],
    }


def _jsonable(v: Any) -> Any:
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, (tuple, list)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    return v
