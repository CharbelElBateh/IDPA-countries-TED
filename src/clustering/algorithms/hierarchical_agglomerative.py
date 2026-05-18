"""Hierarchical Agglomerative clustering, exactly as taught.

Reference: course slides "Ch. 10 — Data Clustering, 5.2 Hierarchical
Clustering: Agglomerative" (Clustering.pdf, slides 56-81).

================================================================
Mapping the code to the slide pseudocode
================================================================

Slide (Clustering.pdf, slide 61):

    1. Initialization:  Compute inter-cluster similarity matrix
    2. Let each data object be a cluster
    3. Repeat
    4. Grouping:        Merge the two clusters with maximum similarity
    5. Update:          Re-compute the similarity matrix considering new clusters
    6. Until verifying stopping rule
       NOTE: If no stopping rule is defined, algorithm continues until
             one single cluster remains.

How the code realizes each slide step:

* Step 1 ("Compute inter-cluster similarity matrix") -> caller-supplied
  ``distance_matrix`` is the slide's similarity matrix (we work in
  distance space, which is just the inverse of similarity — "closest"
  in distance ≡ "most similar" per slide). The caller already built
  this in ``src/clustering/distance.py`` using the type-aware leaf
  distance functions.
* Step 2 ("Each data object = one cluster")          -> implicit in
  ``scipy.cluster.hierarchy.linkage``: it starts with N singleton
  clusters indexed 0..N-1.
* Steps 3-5 ("Repeat: merge closest pair; recompute matrix")
                                                     -> ``linkage(condensed,
  method=linkage_method)``. scipy's linkage is the standard
  Lance-Williams implementation of EXACTLY this loop: at each
  iteration it finds the pair of clusters with minimum distance
  (== maximum similarity), merges them into a new cluster, and updates
  the distance from the new cluster to every other cluster using a
  formula that depends on the linkage method. The output linkage
  matrix ``Z`` has N-1 rows; each row ``[cluster_a, cluster_b,
  distance, leaf_count]`` is ONE iteration of the slide's main loop —
  what got merged, at what distance, and how big the new cluster is.
  This is exactly the merge sequence depicted across the slide's
  Iteration #1, Iteration #2, ... figures (slides 64, 66, 68, 70).
* Step 6 ("Until verifying stopping rule")           -> ``fcluster(Z,
  t=k, criterion='maxclust')`` cuts the dendrogram at the level that
  yields the user's desired number of clusters ``k``. Alternatively,
  ``fcluster(Z, t=threshold, criterion='distance')`` cuts at a fixed
  distance threshold (slides 71-73: "stopping rule based on highly
  separated, low-height sub-trees"). With no stopping rule provided,
  ``linkage`` runs to completion (N-1 merges -> one cluster) per the
  slide's note.

================================================================
Inter-cluster similarity / linkage methods (slides 78-81)
================================================================

The slide describes THREE inter-cluster similarity measures, all of
which correspond to standard scipy linkage methods:

* Single Link (slide 79):
    "Cluster similarity = similarity of the two MOST SIMILAR
     cluster objects"
    -> in distance form: ``d(C_i, C_j) = min { d(x, y) : x in C_i, y in C_j }``
    -> ``method="single"``
    -> handles non-globular shapes well; can produce long skinny chains

* Complete Link (slide 80):
    "Cluster similarity = similarity of the two LEAST SIMILAR
     cluster objects"
    -> in distance form: ``d(C_i, C_j) = max { d(x, y) : x in C_i, y in C_j }``
    -> ``method="complete"``
    -> compact clusters; tends to break large ones

* Average Link (slide 81):
    "Cluster similarity = AVERAGE similarity of all pairs of objects
     from each cluster" (also known as UPGMA / PGMA)
    -> in distance form: ``d(C_i, C_j) =
             (1 / |C_i||C_j|) * sum_{x in C_i, y in C_j} d(x, y)``
    -> ``method="average"``
    -> slide-recommended ("most robust against noise, most widely used")

Default in this code is ``"average"`` — matches the slide's
recommendation. ``"ward"`` is rejected because Ward linkage minimizes
within-cluster variance in Euclidean space, which our type-aware
non-Euclidean distance matrix does not provide.

================================================================
Dendrogram output (slides 56-59, 71-74)
================================================================

The slide explains that hierarchical clustering produces a dendrogram —
a tree whose leaves are data objects and whose internal nodes are
merged clusters, with the height of each internal node equal to the
distance at which that merge happened. scipy's linkage matrix ``Z``
encodes exactly this dendrogram:

* Row k (0-indexed) of Z is the (N + k)-th cluster, the result of
  merging clusters Z[k][0] and Z[k][1].
* Z[k][2] is the merge distance (height of the internal node).
* Z[k][3] is the count of original data objects in this new cluster.

The frontend (``frontend/static/cluster_dendrogram.js``) consumes ``Z``
directly to draw the dendrogram from these merge records.

Complexity: O(N^2 log N) for linkage with average/complete/single
linkage. For N = 192 this is trivially fast.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from src.clustering.base import ClusterAlgorithm
from src.clustering.registry import register

logger = logging.getLogger(__name__)


# Linkage methods that work on a precomputed non-Euclidean distance
# matrix — the slide's single / complete / average link methods.
# (Ward, centroid, median linkages need Euclidean coordinates.)
_VALID_LINKAGES = {"average", "complete", "single"}


@register
class HierarchicalAgglomerative(ClusterAlgorithm):
    """Bottom-up agglomerative clustering with a precomputed distance matrix.

    See the file-top docstring for a step-by-step mapping of this code
    to the course slides (Clustering.pdf, slides 56-81).
    """

    name = "hierarchical_agglomerative"
    description = (
        "Hierarchical Agglomerative: starts each country in its own "
        "cluster and iteratively merges the closest pair (slide 61). "
        "Linkage methods are single / complete / average — the three "
        "inter-cluster similarity measures described in slides 79-81. "
        "Produces a dendrogram (slide 57)."
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

        # Slide 79-81: which inter-cluster similarity formula to use.
        # Default "average" matches the slide's recommendation
        # ("most robust against noise, most widely used").
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

        # scipy wants the *condensed* upper-triangle vector of the
        # distance matrix — same matrix as the slide's similarity
        # matrix, just in compressed form.
        condensed = squareform(distance_matrix, checks=False)

        # Slide steps 1-5: linkage() runs the whole "repeat: merge
        # closest pair, recompute similarities" loop and returns the
        # full merge history as a linkage matrix Z of shape (N-1, 4).
        # Row k = the k-th merge:
        #   Z[k][0], Z[k][1] = the two cluster ids that were merged
        #   Z[k][2]          = the merge distance (dendrogram height)
        #   Z[k][3]          = number of original data objects in
        #                      the new merged cluster
        Z = linkage(condensed, method=linkage_method)

        # Slide step 6: apply the stopping rule.
        # Two options are supported, both standard ways to cut a
        # dendrogram (see slides 71-74):
        #   * distance_threshold: cut all branches taller than this
        #     (slide's "low-height sub-trees" criterion)
        #   * k:                  cut so exactly k clusters remain
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

        # scipy returns 1-indexed cluster labels; we normalize to
        # 0-indexed so they line up with k-means' 0-indexed labels and
        # the frontend's palette --c0..--c9.
        cluster_ids = cluster_ids - cluster_ids.min()
        labels = {names[i]: int(cluster_ids[i]) for i in range(n)}
        linkage_list = [list(map(float, row)) for row in Z]
        return labels, linkage_list
