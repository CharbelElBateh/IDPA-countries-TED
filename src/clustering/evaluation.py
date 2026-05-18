"""Cluster-quality scoring + medoid extraction.

Silhouette is computed using sklearn's precomputed-distance variant
(safe for non-Euclidean metrics, which is the whole reason we picked
k-medoids + AGG-average over KMeans + Ward).
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


def silhouette(distance_matrix: np.ndarray,
               labels: list[int]) -> float | None:
    """Mean silhouette on a precomputed distance matrix.

    Returns ``None`` if there are fewer than 2 distinct clusters or any
    cluster has only one point (silhouette is undefined in either case).
    """
    n = len(labels)
    if n != distance_matrix.shape[0]:
        raise ValueError("labels length must match distance matrix")
    uniq = set(labels)
    if len(uniq) < 2 or len(uniq) >= n:
        return None
    sizes = {c: labels.count(c) for c in uniq}
    if any(v < 2 for v in sizes.values()):
        return None

    from sklearn.metrics import silhouette_score
    try:
        s = silhouette_score(distance_matrix, labels, metric="precomputed")
        return float(s)
    except Exception as exc:  # noqa: BLE001
        logger.warning("silhouette_score failed: %s", exc)
        return None


def medoids_per_cluster(
    distance_matrix: np.ndarray,
    names: list[str],
    labels: list[int],
) -> list[str]:
    """One representative country per cluster (minimum mean intra-cluster distance).

    For k-medoids the actual medoids are computed *during* the run; this
    function is the AGG fallback (no native medoid concept) and a sanity
    check for k-medoids.

    Returns one name per *positive* cluster id, in ascending cluster order.
    Cluster ``-1`` (outliers) is skipped.
    """
    medoids: list[str] = []
    cluster_ids = sorted(c for c in set(labels) if c >= 0)
    for c in cluster_ids:
        indices = [i for i, l in enumerate(labels) if l == c]
        if not indices:
            continue
        sub = distance_matrix[np.ix_(indices, indices)]
        means = sub.mean(axis=1)
        best_local = int(np.argmin(means))
        medoids.append(names[indices[best_local]])
    return medoids


def cluster_sizes(labels: list[int]) -> dict[str, int]:
    """Count members per cluster id (keys are str so they survive JSON)."""
    out: dict[str, int] = {}
    for l in labels:
        key = str(int(l))
        out[key] = out.get(key, 0) + 1
    return out
