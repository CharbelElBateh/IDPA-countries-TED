"""Classical (Torgerson) MDS embedding for the scatter visualization.

Used by the frontend scatter to plot countries while preserving pairwise
distances. The same eigendecomposition exposes the *variance explained
per axis*, which the frontend surfaces as a diagnostic so visual cluster
overlap can be interpreted: a low % on axes 1+2 means much of the
true structure has been squashed into the 2-D picture and is invisible.

This is the same family of MDS that ``kmeans._classical_mds`` runs (just
truncated to two axes here instead of up to 16), so the scatter is now a
projection of the *same* high-dimensional space k-means actually
partitions in — not a separate SMACOF embedding.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


def mds_2d(distance_matrix: np.ndarray,
           names: list[str],
           *, random_seed: int | None = 0,
           ) -> tuple[dict[str, list[float]], list[float]]:
    """Project the N x N distance matrix to 2D with classical MDS.

    Also returns the per-axis variance-explained percentages for every
    positive eigenvalue of the double-centred Gram matrix (descending).
    The frontend shows the first few as a "how much of the structure is
    actually visible in 2D?" diagnostic next to the scatter.

    Args:
        distance_matrix: Symmetric N x N float matrix in ``[0, 1]``.
        names: Row/column labels.
        random_seed: Unused — kept so callers (and existing tests) don't
            need to special-case classical vs iterative MDS.

    Returns:
        ``(coords, variance_explained)`` where ``coords`` is
        ``{country_name: [x, y]}`` and ``variance_explained`` is a list
        of floats summing to 100.0 (one entry per positive eigenvalue,
        descending). Empty when all points coincide.
    """
    _ = random_seed  # not used by classical MDS; preserved for API parity.
    n = len(names)
    if n == 0:
        return {}, []
    if n == 1:
        return {names[0]: [0.0, 0.0]}, []
    if n == 2:
        d = float(distance_matrix[0, 1])
        return {names[0]: [-d / 2, 0.0], names[1]: [d / 2, 0.0]}, [100.0]

    # Classical (Torgerson) MDS: double-centre the squared distances to
    # get a Gram matrix, then eigendecompose. eigh is fine because B is
    # symmetric by construction.
    D2 = np.asarray(distance_matrix, dtype=float) ** 2
    J = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * J @ D2 @ J
    eigvals, eigvecs = np.linalg.eigh(B)

    # Descending; drop strictly-non-positive eigenvalues. Non-Euclidean
    # inputs (Levenshtein, EMD, log-currency, haversine, …) routinely
    # yield small negative eigenvalues; those axes are not embeddable in
    # Euclidean space and are the standard truncation in classical MDS.
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]
    pos_eigvals = eigvals[eigvals > 1e-9]

    if pos_eigvals.size == 0:
        return {name: [0.0, 0.0] for name in names}, []

    total = float(pos_eigvals.sum())
    variance_explained = [float(100.0 * v / total) for v in pos_eigvals]

    # Project onto the first two positive-eigenvalue axes, scaled by
    # sqrt(eigenvalue) (the classical-MDS coordinate formula).
    L = np.sqrt(pos_eigvals[:2])
    coords_arr = eigvecs[:, :pos_eigvals.size][:, :2] * L
    if coords_arr.shape[1] == 1:
        # Only one positive eigenvalue — feature is effectively 1-D.
        # Pad axis 2 with zeros so the scatter still has [x, y] points.
        coords_arr = np.hstack([coords_arr, np.zeros((n, 1))])

    coords = {names[i]: [float(coords_arr[i, 0]), float(coords_arr[i, 1])]
              for i in range(n)}
    return coords, variance_explained


def tsne_2d(distance_matrix: np.ndarray,
            names: list[str],
            *, random_seed: int | None = 0,
            ) -> dict[str, list[float]]:
    """t-SNE 2D embedding of a precomputed distance matrix.

    An alternative to ``mds_2d`` for the scatter view. Use t-SNE when
    the classical-MDS variance-explained diagnostic shows a large chunk
    of structure is hidden in axes 4+ — t-SNE preserves *local* (i.e.
    cluster) structure dramatically better than metric MDS in that case.
    Trade-off: absolute distances on screen are NOT meaningful in t-SNE
    space; only the grouping is. The frontend must surface that caveat.

    Args:
        distance_matrix: Symmetric N x N float matrix in ``[0, 1]``.
        names: Row/column labels.
        random_seed: Forwarded to sklearn for reproducibility.

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

    # Lazy import — sklearn is heavy; not needed at module-load.
    from sklearn.manifold import TSNE

    # sklearn requires perplexity < n_samples. Default 30 is great for
    # the standard 192-country case; we shrink for smaller inputs but
    # keep a floor of 2 so very tiny tests still run.
    perplexity = min(30.0, max(2.0, (n - 1) / 3.0))

    tsne = TSNE(
        n_components=2,
        metric="precomputed",
        # init="pca" is illegal when metric is precomputed (no features).
        init="random",
        perplexity=perplexity,
        random_state=random_seed,
    )
    coords = tsne.fit_transform(np.asarray(distance_matrix, dtype=float))
    return {names[i]: [float(coords[i, 0]), float(coords[i, 1])]
            for i in range(n)}