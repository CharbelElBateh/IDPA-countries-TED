"""k-means (Lloyd's) partitional clustering on a precomputed distance matrix.

k-means needs points in Euclidean space (it averages coordinates to form
centroids), but the project's distances are *type-aware* and
non-Euclidean (Levenshtein, EMD, log-currency, haversine, …) — we only
have a pairwise distance matrix, not coordinates. So this algorithm:

1. Embeds the N x N distance matrix into Euclidean space with classical
   (Torgerson) MDS — double-centre ``-1/2 J D^2 J``, eigen-decompose,
   keep the positive-eigenvalue axes. Negative eigenvalues (the matrix
   is not perfectly Euclidean) are clamped to zero, the standard
   truncation.
2. Runs Lloyd's k-means on those coordinates with k-means++ seeding,
   restarted ``n_init`` times, keeping the lowest-inertia assignment.

Hand-rolled with numpy (no sklearn-extra) to match ``kmeans``' siblings.
``n = 192`` with ``k <= 20`` is trivially fast.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from src.clustering.base import ClusterAlgorithm
from src.clustering.registry import register

logger = logging.getLogger(__name__)


@register
class KMeans(ClusterAlgorithm):
    """Lloyd's k-means on a classical-MDS embedding of the distance matrix."""

    name = "kmeans"
    description = (
        "k-means (Lloyd's): partitions countries into k groups around k "
        "centroids. The non-Euclidean distance matrix is first embedded "
        "into Euclidean space via classical MDS, then k-means is run with "
        "k-means++ seeding and n_init restarts."
    )

    def compute(
        self,
        distance_matrix: np.ndarray,
        names: list[str],
        *,
        params: dict[str, Any],
    ) -> tuple[dict[str, int], list[list[float]]]:
        n = distance_matrix.shape[0]
        k = int(params.get("k", 5))
        n_init = int(params.get("n_init", 10))
        max_iter = int(params.get("max_iter", 300))
        seed = int(params.get("random_seed", 0))

        if k <= 0:
            raise ValueError("k must be >= 1")
        if k > n:
            raise ValueError(f"k={k} exceeds clusterable count n={n}")
        if n == 0:
            return {}, []
        if k == 1 or n == 1:
            return {name: 0 for name in names}, []

        coords = _classical_mds(distance_matrix)

        best_labels: np.ndarray | None = None
        best_inertia = np.inf
        for r in range(max(1, n_init)):
            labels, inertia = _lloyd(
                coords, k, max_iter=max_iter, seed=seed + r,
            )
            if inertia < best_inertia:
                best_inertia = inertia
                best_labels = labels

        assert best_labels is not None
        labels = {names[i]: int(best_labels[i]) for i in range(n)}
        return labels, []


# =============================================================== MDS embedding
def _classical_mds(D: np.ndarray) -> np.ndarray:
    """Classical (Torgerson) MDS: distance matrix -> Euclidean coordinates.

    Returns an ``(n, m)`` array where ``m`` is the number of strictly
    positive eigenvalues of the double-centred Gram matrix (capped at
    ``min(n - 1, 16)``). Non-Euclidean matrices yield some negative
    eigenvalues; those axes are dropped.
    """
    n = D.shape[0]
    D2 = np.asarray(D, dtype=float) ** 2
    J = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * J @ D2 @ J
    # B is symmetric → use eigh (real eigenvalues, ascending order).
    eigvals, eigvecs = np.linalg.eigh(B)
    # Descending; keep strictly positive eigenvalues only.
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]
    pos = eigvals > 1e-9
    m = int(min(pos.sum(), n - 1, 16))
    if m <= 0:
        # Degenerate (all points coincide) — collapse to the origin.
        return np.zeros((n, 1))
    L = np.sqrt(eigvals[:m])
    return eigvecs[:, :m] * L


# =============================================================== Lloyd's loop
def _kpp_init(X: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    """k-means++ seeding: spread initial centroids by D^2 sampling."""
    n = X.shape[0]
    first = int(rng.integers(n))
    centers = [first]
    closest_sq = np.sum((X - X[first]) ** 2, axis=1)
    for _ in range(1, k):
        total = float(closest_sq.sum())
        if total <= 0.0:
            # All remaining points coincide with a chosen centre.
            nxt = int(rng.integers(n))
        else:
            probs = closest_sq / total
            nxt = int(rng.choice(n, p=probs))
        centers.append(nxt)
        d_new = np.sum((X - X[nxt]) ** 2, axis=1)
        closest_sq = np.minimum(closest_sq, d_new)
    return X[centers].copy()


def _lloyd(
    X: np.ndarray,
    k: int,
    *,
    max_iter: int,
    seed: int,
) -> tuple[np.ndarray, float]:
    """One k-means run. Returns ``(labels, inertia)``."""
    rng = np.random.default_rng(seed)
    centroids = _kpp_init(X, k, rng)
    labels = np.zeros(X.shape[0], dtype=int)

    for _ in range(max_iter):
        # Assign: nearest centroid by squared Euclidean distance.
        dists = np.linalg.norm(X[:, None, :] - centroids[None, :, :], axis=2)
        new_labels = np.argmin(dists, axis=1)
        if np.array_equal(new_labels, labels):
            labels = new_labels
            break
        labels = new_labels
        # Update: centroid = mean of its members; re-seed empty clusters
        # with the point farthest from its current centroid.
        for c in range(k):
            members = X[labels == c]
            if len(members) == 0:
                far = int(np.argmax(np.min(
                    np.linalg.norm(X[:, None, :] - centroids[None, :, :],
                                   axis=2), axis=1)))
                centroids[c] = X[far]
            else:
                centroids[c] = members.mean(axis=0)

    inertia = float(np.sum(
        np.linalg.norm(X - centroids[labels], axis=1) ** 2
    ))
    return labels, inertia
