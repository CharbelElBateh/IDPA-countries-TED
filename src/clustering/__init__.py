"""Country-level clustering on the typed-leaf country trees.

Exposes two algorithms (k-means, hierarchical agglomerative) that operate
on a precomputed pairwise distance matrix derived from the single field
the user selects.
"""
from src.clustering.base import ClusterAlgorithm, ClusterResult
from src.clustering.fields import (
    default_weights,
    field_paths,
    fields_grouped,
    list_fields,
)
from src.clustering.registry import (
    get_algorithm,
    list_algorithms,
    register,
)
# Import for side-effect: registers the two algorithms.
from src.clustering.algorithms import (  # noqa: F401
    hierarchical_agglomerative,
    kmeans,
)
from src.clustering.run import run_clustering

__all__ = [
    "ClusterAlgorithm",
    "ClusterResult",
    "default_weights",
    "field_paths",
    "fields_grouped",
    "get_algorithm",
    "list_algorithms",
    "list_fields",
    "register",
    "run_clustering",
]
