"""Hierarchical Agglomerative clustering, per course slide Ch.10 §5.2.

================================================================
Slide algorithm (Clustering.pdf, slide 61)
================================================================

    1. Compute inter-cluster similarity matrix
    2. Each data object is its own cluster
    3. Repeat:
    4.   Merge the two clusters with maximum similarity
         (in distance form: minimum distance)
    5.   Recompute the similarity matrix
    6. Until stopping rule
       (no rule -> continue until one cluster remains)

================================================================
File map
================================================================
    distance_matrix        ->  step 1   (the slide's similarity matrix, in
                                         distance form: closest <=> most similar)
    scipy.linkage          ->  steps 2-5 (Lance-Williams merge loop)
        returns Z : (N-1, 4) — one row per merge
            Z[k, 0], Z[k, 1] = ids of the two merged clusters
            Z[k, 2]          = merge distance (dendrogram height)
            Z[k, 3]          = leaf count in the new cluster
    scipy.fcluster         ->  step 6   (cut the dendrogram)

================================================================
Linkage methods (slides 79-81)
================================================================

All three operate directly on the precomputed non-Euclidean distance matrix:

    single    : d(C_i, C_j) = min  d(x, y)    over x in C_i, y in C_j   (slide 79)
    complete  : d(C_i, C_j) = max  d(x, y)    over x in C_i, y in C_j   (slide 80)
    average   : d(C_i, C_j) = mean d(x, y)    over x in C_i, y in C_j   (slide 81, UPGMA)
                            = (1 / |C_i||C_j|) * sum_{x in C_i, y in C_j} d(x, y)

Default is "average" — slide-recommended ("most robust against noise,
most widely used"). Ward / centroid / median linkages need Euclidean
coordinates (they average points, not pairwise distances) and are
rejected here.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from src.clustering.base import ClusterAlgorithm
from src.clustering.registry import register

logger = logging.getLogger(__name__)


# Linkages that work directly on a precomputed non-Euclidean distance matrix.
_VALID_LINKAGES = {"average", "complete", "single"}


@register
class HierarchicalAgglomerative(ClusterAlgorithm):
    """Bottom-up agglomerative clustering with a precomputed distance matrix."""

    name = "hierarchical_agglomerative"
    description = (
        "Hierarchical Agglomerative (slide 61): starts each country in "
        "its own cluster and iteratively merges the closest pair. "
        "Supports single / complete / average linkage (slides 79-81); "
        "default is average (UPGMA). Produces a dendrogram."
    )

    def compute(
        self,
        distance_matrix: np.ndarray,             # D, shape (n, n) — the slide's similarity matrix
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

        # -------- Steps 1-5: build the dendrogram --------------------------
        # condensed : upper triangle of D as a length-n(n-1)/2 vector
        #             (the form scipy.linkage expects).
        condensed = squareform(distance_matrix, checks=False)

        # Z : (n-1, 4) — full merge history. See file-top docstring for
        # column meanings. Row k corresponds to the k-th merge step and
        # equals one iteration of the slide's main loop.
        Z = linkage(condensed, method=linkage_method)

        # -------- Step 6: stopping rule (cut the dendrogram) ---------------
        # Two cuts are supported, both standard:
        #   distance_threshold: keep merges with distance < threshold
        #                       (slide 71-74: "low-height sub-trees")
        #   k                 : cut to leave exactly k clusters
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

        # fcluster returns 1-indexed labels; normalize to 0-indexed to
        # line up with k-means and the frontend palette --c0..--c9.
        cluster_ids = cluster_ids - cluster_ids.min()
        labels = {names[i]: int(cluster_ids[i]) for i in range(n)}
        linkage_list = [list(map(float, row)) for row in Z]
        return labels, linkage_list
