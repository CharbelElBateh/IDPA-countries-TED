"""Build a pairwise country distance matrix from a subset of fields.

Given:
- a list of country trees,
- a list of dotted leaf paths (e.g. ``["demographics.religion", "economy.gdp_ppp.value"]``),
- a per-field weight dict (defaults to 1.0 each),
- a resolved cost-model dict,

produces an N × N symmetric float matrix ``D`` in ``[0, 1]`` where
``D[i, j]`` is the weighted-mean per-field distance between countries
``i`` and ``j``. Distances are powered by ``src.distances.relabel_cost``
so each leaf type uses its dedicated metric (Levenshtein for text,
log-scale for currency, EMD for distributions, haversine for
coordinates, etc.).

Outliers — countries missing one or more selected fields — are removed
*before* matrix construction. The caller (``run.py``) detects them via
``outliers.detect_outliers``.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from src.core import Node, Tree
from src.distances import relabel_cost
from src.taxonomy import TaxonomyRegistry

logger = logging.getLogger(__name__)


def get_field_node(tree: Tree, field_path: str) -> Node | None:
    """Resolve ``field_path`` to a leaf or structural node, or ``None``."""
    return tree.find_by_label(field_path)


def has_field(tree: Tree, field_path: str) -> bool:
    """Whether ``field_path`` resolves to a non-empty node in ``tree``."""
    node = tree.find_by_label(field_path)
    if node is None:
        return False
    if node.is_leaf:
        # Distributions: non-empty list.
        if node.type == "distribution":
            return bool(node.value)
        # Strings: non-empty after strip.
        if isinstance(node.value, str):
            return bool(node.value.strip())
        return node.value is not None
    # Structural node: counts as present if it has any children.
    return bool(node.children)


def pairwise_distance(
    tree_a: Tree,
    tree_b: Tree,
    field_paths: list[str],
    weights: dict[str, float],
    *,
    config: dict[str, Any],
    taxonomies: TaxonomyRegistry,
    cost_model: dict[str, Any],
) -> float:
    """Weighted-mean per-field distance between two country trees.

    Missing fields shouldn't reach this function — callers must filter
    outliers first. If they do, the field contributes a full ``1.0``.
    """
    total_weight = 0.0
    total_distance = 0.0

    for path in field_paths:
        w = float(weights.get(path, weights.get("default", 1.0)))
        if w <= 0:
            continue
        a = tree_a.find_by_label(path)
        b = tree_b.find_by_label(path)
        if a is None or b is None:
            d = 1.0  # Fail-safe: caller should have removed these.
        else:
            d = relabel_cost(a, b, config=config,
                             taxonomies=taxonomies, cost_model=cost_model)
        total_weight += w
        total_distance += w * d

    if total_weight == 0:
        return 0.0
    return total_distance / total_weight


def build_distance_matrix(
    trees: dict[str, Tree],
    field_paths: list[str],
    weights: dict[str, float] | None = None,
    *,
    config: dict[str, Any],
    taxonomies: TaxonomyRegistry,
    cost_model: dict[str, Any],
) -> tuple[np.ndarray, list[str]]:
    """Compute the N × N symmetric distance matrix for ``trees``.

    Args:
        trees: ``{country_name: Tree}``. Must contain only countries that
            have *all* of ``field_paths`` populated (i.e. outliers
            already removed).
        field_paths: Dotted leaf paths to use as clustering features.
        weights: Per-path multiplier; missing keys fall back to ``1.0``.

    Returns:
        ``(matrix, names)`` where ``names`` is the row/column order
        (alphabetical for determinism).
    """
    weights = weights or {}
    names = sorted(trees.keys())
    n = len(names)
    if n == 0:
        return np.zeros((0, 0)), []

    matrix = np.zeros((n, n), dtype=float)
    for i in range(n):
        ti = trees[names[i]]
        for j in range(i + 1, n):
            d = pairwise_distance(
                ti, trees[names[j]], field_paths, weights,
                config=config, taxonomies=taxonomies, cost_model=cost_model,
            )
            matrix[i, j] = d
            matrix[j, i] = d
    logger.debug("Built %dx%d distance matrix (fields=%s)",
                 n, n, field_paths)
    return matrix, names


# =============================================================== caching key
def distance_matrix_key(
    field_paths: list[str],
    weights: dict[str, float],
    cost_model_name: str,
) -> str:
    """Deterministic Mongo ``_id`` for a cached distance matrix.

    Sorting the field list keeps the key stable regardless of the order
    in which the user picks fields.
    """
    fields_part = "|".join(sorted(field_paths))
    weights_part = "|".join(
        f"{k}={weights[k]}" for k in sorted(weights.keys())
    )
    return f"dm__{cost_model_name}__{fields_part}__{weights_part}"
