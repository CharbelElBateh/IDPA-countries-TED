"""Semantic analysis — categorize edit script changes by domain.

Categorization (mapping fields to semantic categories) is deterministic.
Importance weighting and semantic scoring are left to the LLM — the agent
receives the categorized change list and applies its own judgment about
which changes are fundamental vs trivial.

For numeric fields (GDP, population, area, etc.) we extract the numeric
values and compute a magnitude ratio so the LLM can distinguish a small
update (1B → 1.2B, ratio 1.2) from a massive gap (1B → 50B, ratio 50).
"""

import re

from classes.EditScript import EditScript
from classes.Tree import Tree
from agent.config import SEMANTIC_CATEGORIES


def _get_field_name(action) -> str:
    """Extract the top-level field name from an action's node path."""
    node = action.node
    path_parts = []
    current = node
    while current is not None:
        path_parts.append(current.label)
        current = current.parent
    path_parts.reverse()
    # path_parts[0] is root (e.g. "country"), path_parts[1] is the field
    if len(path_parts) >= 2:
        return path_parts[1]
    return node.label


def _get_category(field_name: str) -> str:
    """Map a field name to its semantic category."""
    for category, fields in SEMANTIC_CATEGORIES.items():
        for pattern in fields:
            if pattern.endswith("*"):
                if field_name.startswith(pattern[:-1]):
                    return category
            elif field_name == pattern:
                return category
    return "other"


def _parse_number(text: str) -> float | None:
    """Try to extract a single numeric value from a string.

    Handles formats like: "1,234,567", "726.6", "$11,793", "0.59", "8,796,001".
    Returns None if the text doesn't look like a single number.
    """
    # Strip common prefixes/suffixes (currency symbols, %, etc.)
    cleaned = re.sub(r'[^\d.,\-]', '', text.strip())
    if not cleaned:
        return None
    # Remove thousands separators (commas in "1,234,567")
    cleaned = cleaned.replace(',', '')
    try:
        return float(cleaned)
    except ValueError:
        return None


def _numeric_magnitude(from_val: str, to_val: str) -> dict | None:
    """If both values are numeric, compute magnitude info for the LLM.

    Returns dict with from_num, to_num, ratio, direction, or None if
    either value isn't numeric.
    """
    from_num = _parse_number(from_val)
    to_num = _parse_number(to_val)
    if from_num is None or to_num is None:
        return None

    # Avoid division by zero
    if from_num == 0 and to_num == 0:
        return {"from_num": 0, "to_num": 0, "ratio": 1.0, "direction": "same"}

    if from_num == 0:
        ratio = float('inf')
    else:
        ratio = to_num / from_num

    if ratio > 1:
        direction = "increase"
    elif ratio < 1:
        direction = "decrease"
    else:
        direction = "same"

    return {
        "from_num": from_num,
        "to_num": to_num,
        "ratio": round(ratio, 3),
        "abs_diff": round(abs(to_num - from_num), 3),
        "direction": direction,
    }


def categorize_changes(edit_script: EditScript) -> dict[str, list[dict]]:
    """Categorize edit script actions by semantic category.

    Returns: {category: [{op_type, field, label, from_val, to_val, value, magnitude?}, ...]}
    For relabel ops on numeric values, includes a 'magnitude' dict with
    from_num, to_num, ratio, abs_diff, and direction.
    """
    categories: dict[str, list[dict]] = {}

    for action in edit_script:
        field = _get_field_name(action)
        category = _get_category(field)

        change = {
            "op_type": action.op_type,
            "field": field,
            "label": action.node.label,
            "cost": action.cost,
        }

        if action.op_type == "relabel":
            from_val = action.node.label
            to_val = action.args.get("new_label", "")
            change["from_val"] = from_val
            change["to_val"] = to_val
            # Annotate with numeric magnitude if both sides are numbers
            mag = _numeric_magnitude(from_val, to_val)
            if mag:
                change["magnitude"] = mag
        elif action.op_type in ("insert", "delete"):
            change["value"] = action.node.label

        if category not in categories:
            categories[category] = []
        categories[category].append(change)

    return categories


def build_change_summary(edit_script: EditScript, T1: Tree, T2: Tree) -> dict:
    """Build a structured summary of changes for the LLM to analyze.

    Returns a dict with:
      - t1_size, t2_size: node counts
      - total_ops: total edit operations
      - op_counts: {insert: N, delete: N, relabel: N}
      - categories: {category: {count, inserts, deletes, relabels, changes: [...]}}

    The LLM receives this and applies its own importance judgment.
    """
    categorized = categorize_changes(edit_script)

    op_counts = {"insert": 0, "delete": 0, "relabel": 0}
    for action in edit_script:
        op_counts[action.op_type] = op_counts.get(action.op_type, 0) + 1

    category_summaries = {}
    for cat, changes in categorized.items():
        # Limit to 10 changes per category to keep context manageable
        category_summaries[cat] = {
            "count": len(changes),
            "inserts": sum(1 for c in changes if c["op_type"] == "insert"),
            "deletes": sum(1 for c in changes if c["op_type"] == "delete"),
            "relabels": sum(1 for c in changes if c["op_type"] == "relabel"),
            "changes": changes[:10],
            "truncated": len(changes) > 10,
        }

    return {
        "t1_size": T1.size(),
        "t2_size": T2.size(),
        "total_ops": len(edit_script),
        "op_counts": op_counts,
        "categories": category_summaries,
    }
