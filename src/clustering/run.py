"""Orchestrator: from user request → built trees → distance matrix → ``ClusterResult``.

This is the one function ``frontend/app.py`` and ``scripts/cluster_cli.py``
both call. It handles:

1. Fetching the country docs from Mongo and building their trees.
2. Splitting into clusterable / outlier sets by the selected fields.
3. Computing (or loading from cache) the pairwise distance matrix.
4. Dispatching to the chosen algorithm.
5. Computing silhouette, medoids, cluster sizes, MDS coordinates.
6. Optionally caching everything to Mongo.

The function returns a ``ClusterResult`` whose ``to_dict()`` can be sent
directly to the browser.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from src.builder import build_country_tree
from src.clustering.base import ClusterResult
from src.clustering.distance import (
    build_distance_matrix,
    distance_matrix_key,
)
from src.clustering.embedding import mds_2d, tsne_2d
from src.clustering.evaluation import (
    cluster_sizes,
    medoids_per_cluster,
    silhouette,
)
from src.clustering.outliers import partition_trees
from src.clustering.registry import get_algorithm
from src.config import load_config, resolve_cost_model
from src.core import Tree
from src.storage.mongo_store import MongoStore
from src.taxonomy import load_registry

logger = logging.getLogger(__name__)


def run_clustering(
    algorithm: str,
    field_paths: list[str],
    *,
    weights: dict[str, float] | None = None,
    cost_model: str = "symmetric",
    params: dict[str, Any] | None = None,
    outlier_policy: str = "any_missing",
    store: MongoStore | None = None,
    cache: bool = True,
    trees: dict[str, Tree] | None = None,
) -> ClusterResult:
    """End-to-end clustering pipeline.

    Args:
        algorithm: ``"kmeans"`` or ``"hierarchical_agglomerative"``.
        field_paths: Dotted leaf paths the user selected as features.
        weights: ``{path: weight}``; missing keys default to ``1.0``.
        cost_model: Name of a cost model in ``config/pipeline.json``.
        params: Algorithm-specific knobs (k, linkage, max_iter, etc.).
        outlier_policy: Currently only ``"any_missing"`` is implemented.
        store: A ``MongoStore`` (one is constructed if not provided).
        cache: When True, save the result to ``cluster_runs`` collection.
        trees: Pre-built tree dict (skip Mongo fetch; useful in tests).

    Returns:
        Filled ``ClusterResult``.
    """
    if not field_paths:
        raise ValueError("field_paths must not be empty")

    weights = weights or {}
    params = params or {}
    store = store or MongoStore()

    cfg = load_config()
    taxonomies = load_registry()
    cost_dict = resolve_cost_model(cost_model, cfg)

    trees = trees if trees is not None else _build_all_trees(store, cfg, taxonomies)
    if not trees:
        raise ValueError("No countries available in MongoDB")

    clusterable, outliers = partition_trees(
        trees, field_paths, policy=outlier_policy,
    )
    logger.info("Clustering on %d countries (%d outliers excluded)",
                len(clusterable), len(outliers))

    # Distance matrix (with optional Mongo cache).
    matrix, names = _load_or_build_matrix(
        clusterable, field_paths, weights,
        cost_model_name=cost_model, cost_dict=cost_dict,
        cfg=cfg, taxonomies=taxonomies,
        store=store, cache=cache,
    )

    # Run the algorithm.
    algo = get_algorithm(algorithm)
    labels_dict, linkage = algo.compute(matrix, names, params=params)

    # Post-processing.
    label_list = [labels_dict[n] for n in names]
    sil = silhouette(matrix, label_list)
    medoids = medoids_per_cluster(matrix, names, label_list)
    sizes = cluster_sizes(label_list)
    # Account for outliers as cluster -1.
    if outliers:
        sizes["-1"] = len(outliers)

    coords, mds_variance = mds_2d(matrix, names)
    tsne_coords = tsne_2d(matrix, names)

    # Outliers don't get scatter coords (they have no defined distances).
    labels_with_outliers = dict(labels_dict)
    for name in outliers:
        labels_with_outliers[name] = -1

    result = ClusterResult(
        algorithm=algorithm,
        params={
            "fields": field_paths,
            "weights": weights,
            "cost_model": cost_model,
            "outlier_policy": outlier_policy,
            **params,
        },
        labels=labels_with_outliers,
        medoids=medoids,
        linkage=linkage,
        mds_2d=coords,
        mds_variance=mds_variance,
        tsne_2d=tsne_coords,
        silhouette=sil,
        cluster_sizes=sizes,
        outliers=outliers,
    )

    if cache:
        store.save_cluster_run(result)

    return result


# =============================================================== helpers
def _build_all_trees(store: MongoStore,
                     cfg: dict[str, Any],
                     taxonomies: Any) -> dict[str, Tree]:
    """Load every country doc from Mongo and build its tree.

    Synthetic / hand-crafted test trees (``source == "synthetic"``) are
    skipped: they have no real infobox and exist only for testing the
    TED pipeline interactively from the UI.
    """
    out: dict[str, Tree] = {}
    for doc in store.iter_countries():
        if doc.get("source") == "synthetic":
            continue
        name = doc.get("name") or doc.get("_id")
        if not name:
            continue
        out[name] = build_country_tree(
            name, doc.get("infobox", {}),
            config=cfg, taxonomies=taxonomies,
        )
    return out


def _load_or_build_matrix(
    clusterable: dict[str, Tree],
    field_paths: list[str],
    weights: dict[str, float],
    *,
    cost_model_name: str,
    cost_dict: dict[str, Any],
    cfg: dict[str, Any],
    taxonomies: Any,
    store: MongoStore,
    cache: bool,
) -> tuple[np.ndarray, list[str]]:
    """Return (distance_matrix, names), reading the Mongo cache when present.

    Cache key is ``distance_matrix_key(fields, weights, cost_model)``.
    Cache miss → build and (optionally) store.
    """
    key = distance_matrix_key(field_paths, weights, cost_model_name)

    if cache:
        cached = store.get_distance_matrix(key)
        if cached is not None:
            cached_names = cached["names"]
            # Cache validity depends on the same set of clusterable
            # countries — outlier set may have shifted (data ingest).
            if set(cached_names) == set(clusterable.keys()):
                logger.info("Distance matrix cache hit (%s)", key)
                matrix = np.array(cached["matrix"], dtype=float)
                return matrix, cached_names
            logger.info(
                "Distance matrix cache invalidated "
                "(%d cached names vs %d clusterable)",
                len(cached_names), len(clusterable),
            )

    matrix, names = build_distance_matrix(
        clusterable, field_paths, weights,
        config=cfg, taxonomies=taxonomies, cost_model=cost_dict,
    )

    if cache:
        store.save_distance_matrix(key, names, matrix)
    return matrix, names
