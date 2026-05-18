"""Tests for the clustering tool.

These tests stay deliberately Mongo-free: they build small synthetic
distance matrices and trees in memory, and exercise the pure-Python
parts of the pipeline (algorithms, evaluation, outlier policy,
embedding shape, ClusterResult round-trip).

The Mongo-backed orchestrator ``run.run_clustering`` is tested via a
``trees=`` kwarg that lets us skip the database entirely.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.clustering import (
    fields_grouped,
    get_algorithm,
    list_algorithms,
    list_fields,
    run_clustering,
)
from src.clustering.base import ClusterResult
from src.clustering.distance import build_distance_matrix, has_field
from src.clustering.embedding import mds_2d
from src.clustering.evaluation import (
    cluster_sizes,
    medoids_per_cluster,
    silhouette,
)
from src.clustering.outliers import detect_outliers, partition_trees
from src.core import Node, Tree


# =============================================================== fixtures
def _make_tree(name: str, fields: dict[str, object]) -> Tree:
    """Build a flat tree with the given dotted-path leaves.

    Distance code only cares about ``find_by_label``; we don't need a
    realistic shape here.
    """
    root = Node.structural("country")
    for path, value in fields.items():
        parts = path.split(".")
        parent = root
        for label in parts[:-1]:
            existing = next((c for c in parent.children
                             if c.is_structural and c.label == label), None)
            if existing is None:
                existing = Node.structural(label)
                parent.add_child(existing)
            parent = existing
        if isinstance(value, str):
            parent.add_child(Node.leaf(parts[-1], value, "text"))
        elif isinstance(value, float) or isinstance(value, int):
            parent.add_child(Node.leaf(parts[-1], float(value), "number"))
    return Tree(root=root, name=name)


def _two_blob_matrix() -> tuple[np.ndarray, list[str]]:
    """6 points in two well-separated 'blobs' on a 1-D line."""
    coords = np.array([0.0, 0.05, 0.1, 0.9, 0.95, 1.0])
    n = len(coords)
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            D[i, j] = abs(coords[i] - coords[j])
    names = [f"c{i}" for i in range(n)]
    return D, names


# =============================================================== registry
def test_registry_has_both_algorithms():
    names = {a["name"] for a in list_algorithms()}
    assert "kmeans" in names
    assert "hierarchical_agglomerative" in names


def test_get_algorithm_unknown_raises():
    with pytest.raises(KeyError):
        get_algorithm("nope")


# =============================================================== fields
def test_list_fields_nonempty():
    fields = list_fields()
    assert len(fields) > 10
    assert all("path" in f and "label" in f and "group" in f for f in fields)


def test_fields_grouped_has_expected_groups():
    g = fields_grouped()
    for group in ("Identity", "Geography", "Government", "Economy",
                  "Demographics", "Codes"):
        assert group in g
        assert len(g[group]) >= 1


# =============================================================== has_field / outliers
def test_has_field_simple():
    t = _make_tree("A", {"geography.capital": "Bern"})
    assert has_field(t, "geography.capital") is True
    assert has_field(t, "economy.gdp_ppp.value") is False


def test_detect_outliers_finds_missing_fields():
    trees = {
        "A": _make_tree("A", {"x.y": "v", "z": 1.0}),
        "B": _make_tree("B", {"x.y": "u"}),               # missing z
        "C": _make_tree("C", {}),                          # missing both
    }
    out = detect_outliers(trees, ["x.y", "z"])
    assert set(out["B"]) == {"z"}
    assert set(out["C"]) == {"x.y", "z"}
    assert "A" not in out


def test_partition_trees_splits_correctly():
    trees = {
        "A": _make_tree("A", {"x.y": "v"}),
        "B": _make_tree("B", {}),
    }
    clusterable, outliers = partition_trees(trees, ["x.y"])
    assert list(clusterable) == ["A"]
    assert list(outliers) == ["B"]


# =============================================================== distance matrix
def test_build_distance_matrix_is_symmetric_zero_diagonal():
    trees = {
        "A": _make_tree("A", {"geography.capital": "Bern"}),
        "B": _make_tree("B", {"geography.capital": "Beirut"}),
        "C": _make_tree("C", {"geography.capital": "Bern"}),
    }
    from src.config import load_config, resolve_cost_model
    from src.taxonomy import load_registry
    cfg = load_config()
    tax = load_registry()
    cost = resolve_cost_model("symmetric", cfg)
    D, names = build_distance_matrix(trees, ["geography.capital"], {},
                                     config=cfg, taxonomies=tax,
                                     cost_model=cost)
    assert names == ["A", "B", "C"]
    assert np.allclose(D, D.T)
    assert np.allclose(np.diag(D), 0)
    # A and C have the same capital → distance 0.
    a, c = names.index("A"), names.index("C")
    assert D[a, c] == pytest.approx(0.0)
    # A and B have different capitals → distance > 0.
    b = names.index("B")
    assert D[a, b] > 0


# =============================================================== embedding
def test_mds_2d_shape_matches_input():
    D, names = _two_blob_matrix()
    coords = mds_2d(D, names, random_seed=0)
    assert set(coords) == set(names)
    for v in coords.values():
        assert len(v) == 2
        assert all(isinstance(x, float) for x in v)


# =============================================================== evaluation
def test_silhouette_separates_two_blobs():
    D, _ = _two_blob_matrix()
    labels = [0, 0, 0, 1, 1, 1]
    s = silhouette(D, labels)
    assert s is not None
    assert s > 0.7   # well-separated blobs


def test_silhouette_returns_none_for_singleton_cluster():
    D = np.array([[0, 0.1, 0.9],
                  [0.1, 0, 0.8],
                  [0.9, 0.8, 0]])
    assert silhouette(D, [0, 0, 1]) is None


def test_cluster_sizes():
    sizes = cluster_sizes([0, 0, 1, 1, 1, 2])
    assert sizes == {"0": 2, "1": 3, "2": 1}


def test_medoids_per_cluster_skips_outliers():
    D, names = _two_blob_matrix()
    labels = [0, 0, 0, 1, 1, -1]
    medoids = medoids_per_cluster(D, names, labels)
    # Two real clusters → two medoids; outlier ignored.
    assert len(medoids) == 2
    assert medoids[0] in ("c0", "c1", "c2")
    assert medoids[1] in ("c3", "c4")


# =============================================================== algorithms
def test_kmeans_two_blobs():
    D, names = _two_blob_matrix()
    algo = get_algorithm("kmeans")
    labels, linkage = algo.compute(D, names, params={"k": 2, "random_seed": 0})
    assert linkage == []
    # Each blob's 3 points should share the same label.
    blob_a = {labels["c0"], labels["c1"], labels["c2"]}
    blob_b = {labels["c3"], labels["c4"], labels["c5"]}
    assert len(blob_a) == 1
    assert len(blob_b) == 1
    assert blob_a != blob_b


def test_kmeans_k_too_large():
    D, names = _two_blob_matrix()
    algo = get_algorithm("kmeans")
    with pytest.raises(ValueError):
        algo.compute(D, names, params={"k": 99})


def test_agg_two_blobs_average_linkage():
    D, names = _two_blob_matrix()
    algo = get_algorithm("hierarchical_agglomerative")
    labels, Z = algo.compute(D, names, params={"k": 2, "linkage": "average"})
    # scipy's Z has n-1 rows.
    assert len(Z) == len(names) - 1
    assert {labels["c0"], labels["c1"], labels["c2"]} == {labels["c0"]}
    assert {labels["c3"], labels["c4"], labels["c5"]} == {labels["c3"]}


def test_agg_rejects_ward_linkage():
    D, names = _two_blob_matrix()
    algo = get_algorithm("hierarchical_agglomerative")
    with pytest.raises(ValueError):
        algo.compute(D, names, params={"k": 2, "linkage": "ward"})


def test_agg_distance_threshold():
    D, names = _two_blob_matrix()
    algo = get_algorithm("hierarchical_agglomerative")
    labels, Z = algo.compute(
        D, names,
        params={"distance_threshold": 0.5, "linkage": "average"},
    )
    # Threshold below blob gap → exactly two clusters.
    assert len(set(labels.values())) == 2


# =============================================================== ClusterResult round-trip
def test_cluster_result_roundtrip():
    r = ClusterResult(
        algorithm="kmeans",
        params={"k": 3},
        labels={"A": 0, "B": 1, "C": -1},
        medoids=["A", "B"],
        linkage=[],
        mds_2d={"A": [0.1, 0.2], "B": [0.3, 0.4]},
        silhouette=0.42,
        cluster_sizes={"0": 1, "1": 1, "-1": 1},
        outliers={"C": ["x.y"]},
    )
    d = r.to_dict()
    r2 = ClusterResult.from_dict(d)
    assert r2.algorithm == r.algorithm
    assert r2.labels == r.labels
    assert r2.medoids == r.medoids
    assert r2.silhouette == pytest.approx(0.42)
    assert r2.outliers == r.outliers


# =============================================================== orchestrator (Mongo-free)
def test_run_clustering_end_to_end_no_mongo():
    # 4 simple "countries" — two with same field values, two outliers.
    trees = {
        "A": _make_tree("A", {"government.type": "republic",
                              "economy.gdp_ppp.value": 1000.0}),
        "B": _make_tree("B", {"government.type": "republic",
                              "economy.gdp_ppp.value": 1100.0}),
        "C": _make_tree("C", {"government.type": "monarchy",
                              "economy.gdp_ppp.value": 50000.0}),
        "D": _make_tree("D", {"government.type": "monarchy"}),  # missing gdp → outlier
    }

    class _NullStore:
        def save_cluster_run(self, *_a, **_kw): return "noop"
        def get_distance_matrix(self, *_a, **_kw): return None
        def save_distance_matrix(self, *_a, **_kw): return "noop"
        def iter_countries(self): return iter([])

    result = run_clustering(
        algorithm="kmeans",
        field_paths=["government.type", "economy.gdp_ppp.value"],
        params={"k": 2, "random_seed": 0},
        store=_NullStore(),
        cache=False,
        trees=trees,
    )

    assert result.labels["D"] == -1
    # A & B should land in the same cluster (close in both fields);
    # C should be on its own.
    assert result.labels["A"] == result.labels["B"]
    assert result.labels["A"] != result.labels["C"]
    assert len(result.outliers) == 1
