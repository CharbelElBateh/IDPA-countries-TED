"""Hierarchical Agglomerative clustering via scipy on a precomputed matrix.

scipy's ``linkage`` accepts the **condensed** form of a symmetric
distance matrix (upper-triangle in row-major order). It produces a
linkage matrix of shape ``(n - 1, 4)``: rows of
``[cluster_a, cluster_b, distance, leaf_count]``. The frontend renders
that linkage directly as a D3 dendrogram.

Supported linkage methods on precomputed *non-Euclidean* matrices:
``average``, ``complete``, ``single``. (Ward, centroid, median require
Euclidean coordinates and are intentionally rejected.)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from src.clustering.base import ClusterAlgorithm
from src.clustering.registry import register

logger = logging.getLogger(__name__)


_VALID_LINKAGES = {"average", "complete", "single"}


@register
class HierarchicalAgglomerative(ClusterAlgorithm):
    """Bottom-up agglomerative clustering with a precomputed distance matrix."""

    name = "hierarchical_agglomerative"
    description = (
        "Hierarchical Agglomerative: starts each country in its own "
        "cluster and iteratively merges the closest pair. Produces a "
        "dendrogram. Linkage: average, complete, or single."
    )

    def compute(
        self,
        distance_matrix: np.ndarray,
        names: list[str],
        *,
        params: dict[str, Any],
    ) -> tuple[dict[str, int], list[list[float]]]:
        from scipy.cluster.hierarchy import fcluster, linkage
        from scipy.spatial.distance import squareform

        linkage_method = params.get("linkage", "average")
        if linkage_method not in _VALID_LINKAGES:
            raise ValueError(
                f"linkage={linkage_method!r} not supported with a "
                f"precomputed non-Euclidean distance matrix. "
                f"Use one of {_VALID_LINKAGES}."
            )

        n = distance_matrix.shape[0]
        if n == 0:
            return {}, []
        if n == 1:
            return {names[0]: 0}, []

        # scipy wants the *condensed* upper-triangle vector.
        condensed = squareform(distance_matrix, checks=False)
        Z = linkage(condensed, method=linkage_method)

        # Cut the tree by k or by distance_threshold (mutually exclusive).
        k = params.get("k")
        threshold = params.get("distance_threshold")
        if threshold is not None:
            cluster_ids = fcluster(Z, t=float(threshold), criterion="distance")
        else:
            if k is None:
                k = 5
            k = int(k)
            if k <= 0:
                raise ValueError("k must be >= 1")
            if k > n:
                raise ValueError(f"k={k} exceeds clusterable count n={n}")
            cluster_ids = fcluster(Z, t=k, criterion="maxclust")

        # scipy returns 1-indexed labels; normalize to 0-indexed for
        # consistency with k-medoids.
        cluster_ids = cluster_ids - cluster_ids.min()
        labels = {names[i]: int(cluster_ids[i]) for i in range(n)}
        linkage_list = [list(map(float, row)) for row in Z]
        return labels, linkage_list
