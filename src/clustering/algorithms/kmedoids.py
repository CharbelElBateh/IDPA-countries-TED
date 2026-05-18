"""k-medoids (PAM) on a precomputed pairwise distance matrix.

Written from scratch so we don't pull in ``sklearn-extra``. The PAM
recipe is: pick ``k`` initial medoids; iteratively (a) assign each
point to its nearest medoid; (b) replace each medoid with the point in
its cluster that minimizes total intra-cluster distance; (c) stop when
no medoid changes.

Two init strategies:

- ``"build"``: greedy — pick the point with the smallest total distance
  to all others as the first medoid; then iteratively add the point
  that, made into a medoid, would reduce total distance the most.
- ``"random"``: simple random sample with a fixed seed.

PAM's complexity is O(k · (n − k)²) per iteration; n = 192 and k ≤ 20
is comfortable.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from src.clustering.base import ClusterAlgorithm
from src.clustering.registry import register

logger = logging.getLogger(__name__)


@register
class KMedoids(ClusterAlgorithm):
    """Partitioning Around Medoids on any precomputed distance matrix."""

    name = "kmedoids"
    description = (
        "k-medoids (PAM): partitions countries into k groups around k "
        "representative medoid countries. Works on any pairwise distance "
        "metric — no Euclidean assumption."
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
        init = params.get("init", "build")
        max_iter = int(params.get("max_iter", 100))
        seed = params.get("random_seed", 0)

        if k <= 0:
            raise ValueError("k must be >= 1")
        if k > n:
            raise ValueError(f"k={k} exceeds clusterable count n={n}")
        if k == 1:
            labels = {name: 0 for name in names}
            return labels, []

        medoid_idx = (_init_random(distance_matrix, k, seed=seed)
                      if init == "random"
                      else _init_build(distance_matrix, k))

        assignments = _assign(distance_matrix, medoid_idx)
        for it in range(max_iter):
            new_medoids = _update_medoids(distance_matrix, assignments, k)
            if np.array_equal(new_medoids, medoid_idx):
                logger.debug("k-medoids converged after %d iterations", it)
                break
            medoid_idx = new_medoids
            assignments = _assign(distance_matrix, medoid_idx)

        labels = {names[i]: int(assignments[i]) for i in range(n)}
        return labels, []


# =============================================================== init
def _init_build(D: np.ndarray, k: int) -> np.ndarray:
    """Greedy BUILD init from the original PAM paper (Kaufman & Rousseeuw)."""
    n = D.shape[0]
    # First medoid: the point with the smallest total distance.
    row_sums = D.sum(axis=1)
    medoids = [int(np.argmin(row_sums))]

    while len(medoids) < k:
        # Current min-distance to nearest medoid, per point.
        d_nearest = D[:, medoids].min(axis=1)
        best_gain = -np.inf
        best_point = -1
        for cand in range(n):
            if cand in medoids:
                continue
            # Adding `cand` reduces each point's nearest distance to
            # min(d_nearest[i], D[i, cand]); gain is summed reductions.
            gains = d_nearest - np.minimum(d_nearest, D[:, cand])
            total = float(gains.sum())
            if total > best_gain:
                best_gain = total
                best_point = cand
        medoids.append(best_point)
    return np.array(medoids, dtype=int)


def _init_random(D: np.ndarray, k: int, *, seed: int | None = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.choice(D.shape[0], size=k, replace=False)


# =============================================================== inner loops
def _assign(D: np.ndarray, medoids: np.ndarray) -> np.ndarray:
    """Assign each point to its nearest medoid; returns ``[medoid_position]``."""
    sub = D[:, medoids]
    return np.argmin(sub, axis=1)


def _update_medoids(D: np.ndarray, assignments: np.ndarray, k: int) -> np.ndarray:
    """Replace each medoid with the cluster's intra-distance minimizer."""
    new_medoids: list[int] = []
    for c in range(k):
        members = np.where(assignments == c)[0]
        if len(members) == 0:
            # Pick the point furthest from any current medoid — re-seed.
            # (Rare on infobox-derived matrices, but keeps the loop robust.)
            new_medoids.append(int(np.argmax(D.min(axis=1))))
            continue
        sub = D[np.ix_(members, members)]
        sums = sub.sum(axis=1)
        new_medoids.append(int(members[int(np.argmin(sums))]))
    return np.array(new_medoids, dtype=int)
