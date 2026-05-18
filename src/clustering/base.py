"""Cluster algorithm ABC and the shared ``ClusterResult`` payload.

The result intentionally carries *every* representation a frontend might
need (labels, medoids, linkage, MDS embedding, silhouette) so a single
Mongo document is enough to redraw any of the three visualizations
without recomputing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class ClusterResult:
    """A single clustering run, ready for storage / rendering.

    Attributes:
        algorithm: Algorithm name (``"kmeans"`` or ``"hierarchical_agglomerative"``).
        params: Algorithm-specific knobs as supplied to ``compute``.
        labels: ``{country_name: cluster_id}``. ``-1`` is the outlier bucket.
        medoids: One representative country per cluster — the country
            closest to all others in that cluster on average (works for
            both k-means and AGG since they don't expose a medoid).
        linkage: scipy linkage matrix (rows of ``[i, j, dist, count]``).
            Empty list for k-means.
        mds_2d: ``{country_name: [x, y]}`` — classical MDS embedding of
            the distance matrix used as the 2D scatter coordinates.
        mds_variance: Per-axis variance-explained percentages from the
            same classical-MDS eigendecomposition, descending, summing to
            100.0 over all positive eigenvalues. The frontend shows the
            first few entries to indicate how much of the data's true
            structure is visible in the 2D scatter.
        tsne_2d: ``{country_name: [x, y]}`` — alternative 2D embedding
            via t-SNE. Used when the variance-explained diagnostic shows
            structure hidden in higher MDS axes (t-SNE preserves cluster
            separation better at the cost of meaningless absolute
            distances). The frontend offers MDS / t-SNE as a toggle.
        silhouette: Mean silhouette score (precomputed-distance variant).
            ``None`` if too few clusters or the matrix is degenerate.
        cluster_sizes: ``{cluster_id (as str): n_members}``.
        outliers: Country names that were excluded from clustering, with the
            list of missing fields per country.
    """

    algorithm: str
    params: dict[str, Any]
    labels: dict[str, int] = field(default_factory=dict)
    medoids: list[str] = field(default_factory=list)
    linkage: list[list[float]] = field(default_factory=list)
    mds_2d: dict[str, list[float]] = field(default_factory=dict)
    mds_variance: list[float] = field(default_factory=list)
    tsne_2d: dict[str, list[float]] = field(default_factory=dict)
    silhouette: float | None = None
    cluster_sizes: dict[str, int] = field(default_factory=dict)
    outliers: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict (no numpy types)."""
        return {
            "algorithm": self.algorithm,
            "params": self.params,
            "labels": {str(k): int(v) for k, v in self.labels.items()},
            "medoids": list(self.medoids),
            "linkage": [list(map(float, row)) for row in self.linkage],
            "mds_2d": {str(k): [float(v[0]), float(v[1])]
                       for k, v in self.mds_2d.items()},
            "mds_variance": [float(v) for v in self.mds_variance],
            "tsne_2d": {str(k): [float(v[0]), float(v[1])]
                        for k, v in self.tsne_2d.items()},
            "silhouette": (float(self.silhouette)
                           if self.silhouette is not None else None),
            "cluster_sizes": {str(k): int(v)
                              for k, v in self.cluster_sizes.items()},
            "outliers": {str(k): list(v) for k, v in self.outliers.items()},
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ClusterResult":
        return cls(
            algorithm=d["algorithm"],
            params=d.get("params", {}),
            labels={k: int(v) for k, v in d.get("labels", {}).items()},
            medoids=list(d.get("medoids", [])),
            linkage=[list(row) for row in d.get("linkage", [])],
            mds_2d={k: [float(v[0]), float(v[1])]
                    for k, v in d.get("mds_2d", {}).items()},
            mds_variance=[float(v) for v in d.get("mds_variance", [])],
            tsne_2d={k: [float(v[0]), float(v[1])]
                     for k, v in d.get("tsne_2d", {}).items()},
            silhouette=d.get("silhouette"),
            cluster_sizes={k: int(v)
                           for k, v in d.get("cluster_sizes", {}).items()},
            outliers={k: list(v) for k, v in d.get("outliers", {}).items()},
        )


class ClusterAlgorithm(ABC):
    """Base interface for clustering algorithms.

    Implementations consume a precomputed pairwise distance matrix and the
    ordered list of country names that label its rows/columns.
    """

    name: str = ""
    description: str = ""

    @abstractmethod
    def compute(
        self,
        distance_matrix: np.ndarray,
        names: list[str],
        *,
        params: dict[str, Any],
    ) -> tuple[dict[str, int], list[list[float]]]:
        """Run clustering on the distance matrix.

        Returns:
            ``(labels, linkage)``. ``labels`` is ``{country_name: cluster_id}``;
            ``linkage`` is the scipy-format linkage matrix (empty for non-
            hierarchical algorithms).
        """
        raise NotImplementedError
