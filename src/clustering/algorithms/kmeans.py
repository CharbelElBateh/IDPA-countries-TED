"""K-means (Lloyd's) partitional clustering, exactly as taught.

Reference: course slides "Ch. 10 — Data Clustering, 5.1 Partitional
Clustering: K-means" (img_2.png + Kmeans.txt). The slide's spec is the
classical Lloyd algorithm with **random initialization**.

================================================================
Mapping the code to the slide pseudocode
================================================================

Slide (img_2.png, simplified):

    Initialization:  Given k chosen by user
                     Randomly choose initial k centroids m_1^(t0), ..., m_k^(t0)
                     (typically among the available data objects)

    Assignment:      Given the k centroids at iteration t
                     For every data object x_p, compute Sim(x_p, m_i^(t)) for all i
                     Assign x_p to cluster C_i corresponding to the most similar m_i:
                         C_i^(t) = { x_p / Sim(x_p, m_i^(t)) >= Sim(x_p, m_j^(t))
                                     for all j, 1 <= j <= k }

    Update:          Re-compute centroids as means of data objects in each cluster:
                         m_i^(t+1) = (1 / |C_i^(t)|) * sum_{x_p in C_i^(t)} x_p

    Convergence:     Either (1) no (or few) objects changed clusters between
                     iterations  t  and  t+1   (threshold = max changes allowed), OR
                     (2) higher intra-cluster similarity at t+1 than at t —
                     measured by Sum of Squared Error (SSE):
                         SSE^(t) = sum_{i=1..k} sum_{x_p in C_i^(t)} Dist(x_p, m_i^(t))^2
                     Higher intra-cluster similarity  =  lower SSE.

How the code realizes each slide step:

* Initialization        -> ``_random_init`` — slide says "Randomly choose
                           initial k centroids ... typically among the
                           available data objects". We sample k DISTINCT
                           data points uniformly at random, exactly as
                           described. (We deliberately do *not* use
                           k-means++ D^2-weighted sampling; that's a
                           known improvement but it's not what the
                           slide teaches.) Multiple restarts (`n_init`)
                           are kept because the slide doesn't forbid
                           them and they make a random-init Lloyd run
                           more reliable.
* Assignment            -> ``_lloyd`` inner loop, the ``np.argmin`` line:
                           for each point we compute Euclidean distance
                           to every centroid (cheapest similarity
                           measure when the coordinates are real numbers)
                           and assign to the closest one. "Closest" is
                           the inverse of "most similar".
* Update                -> ``_lloyd`` centroid recomputation: for each
                           cluster c, ``centroids[c] = members.mean(axis=0)``
                           — the slide's m_i^(t+1) = mean of points in
                           C_i^(t).
* Convergence           -> two complementary checks:
                           - ``np.array_equal(new_labels, labels)``
                             implements criterion (1) with threshold = 0
                             ("no objects changed" — the strictest form
                             of "few or no objects changed").
                           - When ``params['tol']`` is provided, we also
                             check criterion (2): SSE drop between
                             iterations < tol. SSE is computed exactly
                             as the slide formula above.

Non-Euclidean inputs:

Our distance matrix is *type-aware* and non-Euclidean (Levenshtein for
text, EMD over taxonomies for distributions, log-currency, haversine,
...). K-means needs points in Euclidean space (it averages coordinates
to form centroids), so before the Lloyd loop we embed the N x N
distance matrix into Euclidean space via classical (Torgerson) MDS,
keeping all axes with strictly positive eigenvalues (capped at 16
dimensions for stability). The "data objects" in the slide become
points in this MDS space; the algorithm itself is unchanged. This step
is project glue, NOT part of the slide algorithm.

Complexity: O(n * k * dim * iters * n_init) where ``dim`` is the number
of MDS axes (<= 16) and ``iters`` is bounded by ``max_iter`` (default
300). For n = 192 and k <= 20 this is trivially fast.
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
    """Lloyd's k-means with random initialization, on a classical-MDS embedding."""

    name = "kmeans"
    description = (
        "K-means (Lloyd's): partitions countries into k groups around k "
        "centroids (means). Initialization is uniform random sampling of "
        "k data objects, per the course slide. The non-Euclidean distance "
        "matrix is first embedded into Euclidean space via classical MDS, "
        "then standard Lloyd iterations (Assignment / Update / Convergence) "
        "run with n_init restarts."
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
        # tol: optional SSE-delta convergence threshold (slide criterion 2).
        # 0.0 means rely on assignment-stability only (criterion 1).
        tol = float(params.get("tol", 0.0))

        if k <= 0:
            raise ValueError("k must be >= 1")
        if k > n:
            raise ValueError(f"k={k} exceeds clusterable count n={n}")
        if n == 0:
            return {}, []
        if k == 1 or n == 1:
            return {name: 0 for name in names}, []

        # Project glue: embed the non-Euclidean distance matrix into
        # Euclidean coords (classical MDS). Slide assumes data already
        # lives in Euclidean space.
        coords = _classical_mds(distance_matrix)

        # n_init restarts — each one is an independent Lloyd run with a
        # fresh random initialization. We keep the result with the
        # lowest SSE (best intra-cluster similarity, per slide).
        best_labels: np.ndarray | None = None
        best_sse = np.inf
        for r in range(max(1, n_init)):
            labels, sse = _lloyd(coords, k, max_iter=max_iter,
                                 seed=seed + r, tol=tol)
            if sse < best_sse:
                best_sse = sse
                best_labels = labels

        assert best_labels is not None
        labels = {names[i]: int(best_labels[i]) for i in range(n)}
        return labels, []


# =============================================================== MDS embedding
def _classical_mds(D: np.ndarray) -> np.ndarray:
    """Classical (Torgerson) MDS: distance matrix -> Euclidean coordinates.

    Project-specific glue (not part of the slide algorithm). Allows
    k-means — which fundamentally needs Euclidean coordinates to compute
    centroid means — to operate on our type-aware non-Euclidean distance
    matrices. Drops axes with non-positive eigenvalues (the standard
    truncation for non-Euclidean inputs); caps dimensionality at
    ``min(n - 1, 16)`` for numerical stability.
    """
    n = D.shape[0]
    D2 = np.asarray(D, dtype=float) ** 2
    J = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * J @ D2 @ J
    eigvals, eigvecs = np.linalg.eigh(B)
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]
    pos = eigvals > 1e-9
    m = int(min(pos.sum(), n - 1, 16))
    if m <= 0:
        return np.zeros((n, 1))
    L = np.sqrt(eigvals[:m])
    return eigvecs[:, :m] * L


# =============================================================== Initialization
def _random_init(X: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    """Slide-spec initialization: pick k centroids uniformly at random
    from the available data objects.

    The slide says: "Randomly choose initial k centroids (means) at
    iteration t_0: m_1^(t_0), ..., m_k^(t_0) ... typically among the
    available data objects". We sample k DISTINCT row indices (no
    replacement) from the N rows of X and return those rows as the
    initial centroids.

    This is the simplest valid initialization. k-means++ D^2 sampling
    would spread the seeds more evenly, but it's an extension not
    covered by the slide, so we deliberately don't use it.
    """
    n = X.shape[0]
    # rng.choice with replace=False guarantees k DISTINCT data objects,
    # matching the slide's "Randomly choose initial k centroids".
    indices = rng.choice(n, size=k, replace=False)
    return X[indices].copy()


# =============================================================== Lloyd's loop
def _lloyd(
    X: np.ndarray,
    k: int,
    *,
    max_iter: int,
    seed: int,
    tol: float = 0.0,
) -> tuple[np.ndarray, float]:
    """One k-means run: Assignment -> Update -> Convergence (slide steps).

    Parameters
    ----------
    X : (n, dim) Euclidean coords (output of classical MDS).
    k : number of clusters.
    max_iter : safety cap on iterations.
    seed : RNG seed for reproducible random init.
    tol : optional SSE-delta convergence threshold. If positive, also
        stop when ``|SSE^(t-1) - SSE^(t)| <= tol``. Slide's second
        convergence criterion. ``0.0`` -> rely on assignment stability
        only (the first criterion).

    Returns
    -------
    labels : (n,) int array — cluster id per point.
    sse :    final Sum of Squared Error, used to pick the best of the
             ``n_init`` restarts (lower = higher intra-cluster similarity).
    """
    rng = np.random.default_rng(seed)
    # ---- Initialization (slide step 1) ----------------------------------
    centroids = _random_init(X, k, rng)
    labels = np.zeros(X.shape[0], dtype=int)
    prev_sse = np.inf

    for _ in range(max_iter):
        # ---- Assignment (slide step 2) -----------------------------------
        # For every x_p compute Euclidean distance to every centroid; assign
        # to the closest (highest similarity = lowest distance).
        # C_i^(t) = { x_p : x_p closer to m_i than any other m_j }
        dists = np.linalg.norm(X[:, None, :] - centroids[None, :, :], axis=2)
        new_labels = np.argmin(dists, axis=1)

        # ---- Convergence criterion 1 (slide): no objects changed ---------
        if np.array_equal(new_labels, labels):
            labels = new_labels
            break
        labels = new_labels

        # ---- Update (slide step 3) ---------------------------------------
        # m_i^(t+1) = (1 / |C_i^(t)|) * sum_{x_p in C_i^(t)} x_p
        # The empty-cluster reseed is a defensive fix that the slide
        # doesn't discuss — without it, an empty cluster c would yield
        # mean of zero points (NaN) and crash the next iteration.
        for c in range(k):
            members = X[labels == c]
            if len(members) == 0:
                far = int(np.argmax(np.min(
                    np.linalg.norm(X[:, None, :] - centroids[None, :, :],
                                   axis=2), axis=1)))
                centroids[c] = X[far]
            else:
                centroids[c] = members.mean(axis=0)

        # ---- Convergence criterion 2 (slide): SSE-delta below threshold --
        # SSE^(t) = sum_{i=1..k} sum_{x_p in C_i^(t)} Dist(x_p, m_i^(t))^2
        if tol > 0.0:
            sse = float(np.sum(
                np.linalg.norm(X - centroids[labels], axis=1) ** 2
            ))
            if abs(prev_sse - sse) <= tol:
                break
            prev_sse = sse

    # Final SSE — used by the orchestrator to choose the best of the
    # n_init restarts (lowest SSE = highest intra-cluster similarity).
    sse = float(np.sum(
        np.linalg.norm(X - centroids[labels], axis=1) ** 2
    ))
    return labels, sse
