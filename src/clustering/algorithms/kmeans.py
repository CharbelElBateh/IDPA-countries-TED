"""K-means (Lloyd's) partitional clustering, per course slide Ch.10 §5.1.

================================================================
Algorithm (img_2.png)
================================================================

    Init:    Pick k initial centroids m_1, ..., m_k uniformly at random
             from the data objects.
    Assign:  C_i = { x_p : Sim(x_p, m_i) >= Sim(x_p, m_j) for all j }
             In distance form: assign x_p to argmin_i ||x_p - m_i||.
    Update:  m_i^(t+1) = (1 / |C_i^(t)|) * sum_{x_p in C_i^(t)} x_p
    Stop:    (1) no objects changed cluster between t and t+1, OR
             (2) SSE drop below tol, where
                 SSE^(t) = sum_{i=1..k} sum_{x_p in C_i^(t)} ||x_p - m_i^(t)||^2

================================================================
File map
================================================================
    _classical_mds  -> project glue (non-Euclidean D -> Euclidean X)
    _random_init    -> Init
    _lloyd          -> Assign / Update / Stop loop  (+ empty-cluster reseed)
    KMeans.compute  -> n_init restarts, keep lowest-SSE result

================================================================
Why MDS first
================================================================

The slide assumes the data already lives in Euclidean space because
Update averages coordinates. Our distance matrix is type-aware
(Levenshtein, EMD, log-currency, haversine, ...) and not generally
Euclidean. Classical (Torgerson) MDS embeds the N x N distance matrix
into Euclidean R^m (m capped at 16 for stability). The Lloyd loop is
unchanged after the embedding.
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
    """Lloyd's k-means with random init, on a classical-MDS embedding."""

    name = "kmeans"
    description = (
        "K-means (Lloyd's): partitions countries into k groups around k "
        "centroids. Random init from data objects (slide-spec). The "
        "non-Euclidean distance matrix is first embedded with classical "
        "MDS, then Lloyd iterations (Assign / Update / Stop) run with "
        "n_init restarts; the run with the lowest final SSE wins."
    )

    def compute(
        self,
        distance_matrix: np.ndarray,             # D, shape (n, n)
        names: list[str],
        *,
        params: dict[str, Any],
    ) -> tuple[dict[str, int], list[list[float]]]:
        n = distance_matrix.shape[0]
        k = int(params.get("k", 5))
        n_init = int(params.get("n_init", 10))
        max_iter = int(params.get("max_iter", 300))
        seed = int(params.get("random_seed", 0))
        tol = float(params.get("tol", 0.0))      # 0 -> label-stability only

        if k <= 0:
            raise ValueError("k must be >= 1")
        if k > n:
            raise ValueError(f"k={k} exceeds clusterable count n={n}")
        if n == 0:
            return {}, []
        if k == 1 or n == 1:
            return {name: 0 for name in names}, []

        # Project glue: D (n x n, non-Euclidean) -> X (n x m, Euclidean).
        X = _classical_mds(distance_matrix)

        # n_init restarts; keep the run with the lowest final SSE.
        best_labels: np.ndarray | None = None
        best_sse = np.inf
        for r in range(max(1, n_init)):
            labels, sse = _lloyd(X, k, max_iter=max_iter, seed=seed + r, tol=tol)
            if sse < best_sse:
                best_sse = sse
                best_labels = labels

        assert best_labels is not None
        return {names[i]: int(best_labels[i]) for i in range(n)}, []


# =============================================================== MDS embedding
def _classical_mds(D: np.ndarray) -> np.ndarray:
    """Classical (Torgerson) MDS: distance matrix -> Euclidean coords.

    Formula
    -------
        J = I - (1/n) * 1 1^T                        (centering matrix)
        B = -1/2 * J . D**2 . J                      (Gram matrix)
        B = V . Lambda . V^T                         (eigendecomposition)
        X = V[:, :m] * sqrt(Lambda[:m])              (m = # positive eigenvalues, capped 16)

    Returns
    -------
    X : (n, m) Euclidean coordinates, m <= min(n-1, 16).
    """
    n = D.shape[0]
    D2 = np.asarray(D, dtype=float) ** 2             # squared distances, (n, n)
    J = np.eye(n) - np.ones((n, n)) / n              # centering matrix, (n, n)
    B = -0.5 * J @ D2 @ J                            # double-centered Gram, (n, n)

    eigvals, eigvecs = np.linalg.eigh(B)             # ascending order
    order = np.argsort(eigvals)[::-1]                # -> descending
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]

    # Drop axes with non-positive eigenvalues (D is not perfectly Euclidean).
    m = int(min((eigvals > 1e-9).sum(), n - 1, 16))
    if m <= 0:
        return np.zeros((n, 1))
    return eigvecs[:, :m] * np.sqrt(eigvals[:m])     # X = V sqrt(Lambda)


# =============================================================== Init
def _random_init(X: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    """Slide-spec init: pick k DISTINCT data rows as initial centroids."""
    indices = rng.choice(X.shape[0], size=k, replace=False)
    return X[indices].copy()                         # (k, dim)


# =============================================================== Lloyd's loop
def _lloyd(
    X: np.ndarray,                                   # (n, dim) Euclidean coords
    k: int,
    *,
    max_iter: int,
    seed: int,
    tol: float = 0.0,
) -> tuple[np.ndarray, float]:
    """One k-means run: Assign / Update / Stop.

    Returns
    -------
    labels : (n,) int — cluster id per point.
    sse    : final Sum of Squared Error (lower = tighter clusters).
    """
    rng = np.random.default_rng(seed)
    n = X.shape[0]
    centroids = _random_init(X, k, rng)              # M, shape (k, dim)
    labels = np.zeros(n, dtype=int)
    prev_sse = np.inf

    for _ in range(max_iter):
        # -------- ASSIGN ---------------------------------------------------
        # dists[p, i] = || X[p] - centroids[i] ||_2,        shape (n, k)
        # new_labels[p] = argmin_i dists[p, i],             shape (n,)
        dists = np.linalg.norm(X[:, None, :] - centroids[None, :, :], axis=2)
        new_labels = np.argmin(dists, axis=1)

        # -------- STOP (1): no point changed cluster -----------------------
        if np.array_equal(new_labels, labels):
            labels = new_labels
            break
        labels = new_labels

        # -------- UPDATE: m_i = (1 / |C_i|) * sum_{x in C_i} x -------------
        for c in range(k):
            members = X[labels == c]
            if len(members) == 0:
                # Defensive: empty cluster -> reseed to the point farthest
                # from any current centroid (slide doesn't specify; without
                # this, mean of zero points is NaN and breaks next iter).
                d_min = np.min(
                    np.linalg.norm(X[:, None, :] - centroids[None, :, :], axis=2),
                    axis=1,
                )
                centroids[c] = X[int(np.argmax(d_min))]
            else:
                centroids[c] = members.mean(axis=0)

        # -------- STOP (2): SSE drop below tol -----------------------------
        # SSE = sum_i sum_{x in C_i} || x - m_i ||^2
        if tol > 0.0:
            sse = float(np.sum(np.linalg.norm(X - centroids[labels], axis=1) ** 2))
            if abs(prev_sse - sse) <= tol:
                break
            prev_sse = sse

    # Final SSE — used by the outer restart loop to pick the best run.
    sse = float(np.sum(np.linalg.norm(X - centroids[labels], axis=1) ** 2))
    return labels, sse
