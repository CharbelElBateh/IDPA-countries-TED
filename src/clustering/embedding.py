"""2D embedding of the precomputed distance matrix via classical MDS.

Used by the frontend scatter visualization to plot the same set of
countries in a way that preserves pairwise distances as faithfully as
possible in two dimensions.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


def mds_2d(distance_matrix: np.ndarray,
           names: list[str],
           *, random_seed: int | None = 0) -> dict[str, list[float]]:
    """Project the N × N distance matrix to 2D with classical MDS.

    Uses sklearn's MDS in ``dissimilarity="precomputed"`` mode. For very
    small inputs (n < 3) returns trivial coordinates rather than raising.

    Args:
        distance_matrix: Symmetric N × N float matrix in ``[0, 1]``.
        names: Row/column labels.
        random_seed: Forwarded to MDS for reproducibility.

    Returns:
        ``{country_name: [x, y]}``.
    """
    n = len(names)
    if n == 0:
        return {}
    if n == 1:
        return {names[0]: [0.0, 0.0]}
    if n == 2:
        d = float(distance_matrix[0, 1])
        return {names[0]: [-d / 2, 0.0], names[1]: [d / 2, 0.0]}

    # Lazy import — sklearn is a big dependency; not needed at module-load.
    from sklearn.manifold import MDS

    mds = MDS(
        n_components=2,
        dissimilarity="precomputed",
        random_state=random_seed,
        n_init=4,
        normalized_stress="auto",
    )
    coords = mds.fit_transform(distance_matrix)
    return {names[i]: [float(coords[i, 0]), float(coords[i, 1])]
            for i in range(n)}
