"""Build a country :class:`Tree` from a raw infobox dict.

Steps performed:

1. Apply field aliases and drop filtered fields (preprocessing).
2. Fold serial groups (``leader_title*`` / ``leader_name*`` → ``@leaders``).
3. For each remaining field, look up its target tree path in
   ``category_layout`` and parse the value with the type given by
   ``field_types`` (falling back to detection).
4. For composite paths like ``economy.gdp_ppp.value`` create the
   intermediate structural Nodes on demand so the tree shape is exactly
   what ``category_layout`` describes.
5. Place serial-group entries (``@leaders``, ``@established``) under their
   declared path, producing structural children with ``label = child_label``.

The resulting Tree's root has ``label = "country"`` and ``name = <country name>``.
"""

from __future__ import annotations

import logging
from typing import Any

from src.config import load_config
from src.core import Node, Tree
from src.parsing.distribution import parse_distribution
from src.parsing.typed import parse_value
from src.preprocessing.grouping import apply_serial_groups
from src.preprocessing.normalize import normalize_infobox
from src.taxonomy import LeafPath, TaxonomyRegistry, load_registry

logger = logging.getLogger(__name__)


# =============================================================== entry point
def build_country_tree(
    name: str,
    infobox: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
    taxonomies: TaxonomyRegistry | None = None,
) -> Tree:
    """Build a country tree from a raw infobox dict.

    Args:
        name: Country name; used for the tree's ``name`` attribute.
        infobox: Raw infobox dict as returned by ``wptools``.
        config: Pipeline config (loaded from ``config/pipeline.json`` if None).
        taxonomies: Pre-loaded taxonomy registry (loaded if None).

    Returns:
        A populated :class:`Tree`.
    """
    cfg = config or load_config()
    tax = taxonomies or load_registry()

    aliases       = cfg.get("field_aliases", {})
    filter_pats   = cfg.get("field_filter_patterns", [])
    serial_rules  = cfg.get("serial_groups", {})
    layout        = cfg.get("category_layout", {})
    field_types   = cfg.get("field_types", {})
    rates         = cfg.get("currency_to_usd", {})

    # --- preprocessing
    normalized = normalize_infobox(infobox, aliases, filter_pats)
    grouped    = apply_serial_groups(normalized, serial_rules)

    # --- build the structural skeleton + populate leaves
    root = Node.structural("country")

    for field, value in grouped.items():
        if field not in layout:
            # Unknown fields go into a flat "unmapped" bucket so we don't
            # silently drop data; useful for debugging.
            target_path = f"unmapped.{field}"
        else:
            target_path = layout[field]

        if field in serial_rules:
            _attach_serial(root, target_path, value, serial_rules[field],
                           field_types, rates, tax)
        else:
            _attach_scalar(root, target_path, field, value,
                           field_types, rates, tax)

    return Tree(root=root, name=name)


# =============================================================== helpers
def _attach_scalar(
    root: Node,
    target_path: str,
    field_name: str,
    raw_value: Any,
    field_types: dict[str, str],
    rates: dict[str, float],
    tax: TaxonomyRegistry,
) -> None:
    """Parse one infobox field and attach it as a leaf at ``target_path``."""
    parts = target_path.split(".")
    leaf_label = parts[-1]
    parent_path = parts[:-1]

    parent = _ensure_structural(root, parent_path)
    type_hint = field_types.get(field_name)

    if type_hint and type_hint.startswith("distribution:"):
        tax_name = type_hint.split(":", 1)[1]
        try:
            taxonomy = tax.get(tax_name)
        except KeyError:
            logger.warning("Unknown taxonomy %r for field %r", tax_name, field_name)
            return
        dist = parse_distribution(raw_value, taxonomy)
        leaf = Node.leaf(
            label=leaf_label,
            value=_distribution_to_jsonable(dist),
            type="distribution",
            raw=str(raw_value) if raw_value is not None else None,
            taxonomy=tax_name,
        )
        parent.add_child(leaf)
        return

    parsed_value, t, trend, unit = parse_value(raw_value, type_hint=type_hint,
                                               rates=rates)
    if t == "empty":
        return
    leaf = Node.leaf(
        label=leaf_label,
        value=parsed_value,
        type=t,
        raw=str(raw_value) if raw_value is not None else None,
        unit=unit,
        trend=trend,
    )
    parent.add_child(leaf)


def _attach_serial(
    root: Node,
    target_path: str,
    items: list[dict[str, Any]],
    rule: dict[str, Any],
    field_types: dict[str, str],
    rates: dict[str, float],
    tax: TaxonomyRegistry,
) -> None:
    """Attach an ordered list of composite items (leaders, established events)."""
    parts = target_path.split(".")
    parent = _ensure_structural(root, parts)
    child_label = rule.get("child_label", "item")
    index_key = rule.get("index_key", "index")

    for entry in items:
        index = entry.get(index_key, 0)
        child = Node.structural(child_label)
        # Stable child ordering by slot name (alphabetical) to keep
        # equality / TED deterministic.
        for slot in sorted(entry.keys()):
            if slot == index_key:
                continue
            raw = entry[slot]
            parsed_value, t, trend, unit = parse_value(raw, rates=rates)
            if t == "empty":
                continue
            child.add_child(Node.leaf(
                label=slot, value=parsed_value, type=t,
                raw=str(raw) if raw is not None else None,
                unit=unit, trend=trend,
            ))
        # Attach an order-index leaf so TED differentiates positions.
        child.add_child(Node.leaf(
            label=index_key, value=index, type="number",
        ))
        parent.add_child(child)


def _ensure_structural(root: Node, parts: list[str]) -> Node:
    """Walk/create structural nodes along the dotted path.

    Empty ``parts`` returns the root itself.
    """
    cur = root
    for label in parts:
        existing = next((c for c in cur.children
                         if c.is_structural and c.label == label), None)
        if existing is None:
            existing = Node.structural(label)
            cur.add_child(existing)
        cur = existing
    return cur


def _distribution_to_jsonable(dist: dict[LeafPath, float]
                              ) -> list[dict[str, Any]]:
    """Make a distribution JSON-friendly: list of ``{path, weight}`` records."""
    return [
        {"path": list(path), "weight": float(weight)}
        for path, weight in sorted(dist.items(),
                                   key=lambda kv: kv[1], reverse=True)
    ]
