"""Outlier detection — countries missing any of the selected fields.

The user's outlier policy is ``"any_missing"``: a country is excluded
from the clustering proper if *any* selected field is missing or empty in
its tree. Outliers form a single ``cluster_-1`` bucket distinct from the
``k`` real clusters; ``k`` is computed on the rest.
"""

from __future__ import annotations

from src.clustering.distance import has_field
from src.core import Tree


def detect_outliers(
    trees: dict[str, Tree],
    field_paths: list[str],
    *,
    policy: str = "any_missing",
) -> dict[str, list[str]]:
    """Return ``{country_name: [missing_field, ...]}`` for every outlier.

    Args:
        trees: ``{country_name: Tree}``.
        field_paths: Selected clustering fields.
        policy: Only ``"any_missing"`` is implemented right now.

    Returns:
        Mapping from outlier country name to its list of missing fields.
        Empty dict if no countries are outliers.
    """
    if policy != "any_missing":
        raise ValueError(f"Unknown outlier policy {policy!r}")

    out: dict[str, list[str]] = {}
    for name, tree in trees.items():
        missing = [p for p in field_paths if not has_field(tree, p)]
        if missing:
            out[name] = missing
    return out


def partition_trees(
    trees: dict[str, Tree],
    field_paths: list[str],
    *,
    policy: str = "any_missing",
) -> tuple[dict[str, Tree], dict[str, list[str]]]:
    """Split ``trees`` into ``(clusterable, outliers)``.

    ``clusterable`` is the dict used for distance-matrix construction;
    ``outliers`` carries the per-country missing-field list for the UI.
    """
    outliers = detect_outliers(trees, field_paths, policy=policy)
    clusterable = {n: t for n, t in trees.items() if n not in outliers}
    return clusterable, outliers
