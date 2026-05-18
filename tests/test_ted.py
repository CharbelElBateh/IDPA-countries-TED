"""Tests for the TED algorithms (chawathe, nierman_jagadish).

The placeholder ``naive`` algorithm is exercised elsewhere; here we focus
on the real Zhang-Shasha-based implementations.
"""

from __future__ import annotations

import warnings

import pytest

from src.config import load_config, resolve_cost_model
from src.core import Node, Tree
from src.taxonomy import load_registry
from src.ted import get_algorithm


# --------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def taxonomies():
    return load_registry()


@pytest.fixture(scope="module")
def cost_symmetric(cfg):
    return resolve_cost_model("symmetric", cfg)


@pytest.fixture(scope="module")
def cost_asymmetric(cfg):
    return resolve_cost_model("asymmetric", cfg)




def _trivial_tree(name: str, capital: str, gdp: float) -> Tree:
    return Tree(
        Node.structural("country", [
            Node.structural("geography", [
                Node.leaf("capital", capital, "wikilink"),
            ]),
            Node.structural("economy", [
                Node.leaf("gdp", gdp, "number"),
            ]),
        ]),
        name=name,
    )


# ============================================================ Chawathe
class TestChawathe:
    def test_identical_trees_zero_cost(self, cfg, taxonomies, cost_symmetric):
        algo = get_algorithm("chawathe")
        t1 = _trivial_tree("A", "Beirut", 1.0)
        t2 = _trivial_tree("A", "Beirut", 1.0)
        script = algo.compute(t1, t2, config=cfg, taxonomies=taxonomies,
                              cost_model=cost_symmetric)
        assert script.total_cost == 0
        assert len(script.operations) == 0

    def test_single_relabel(self, cfg, taxonomies, cost_symmetric):
        algo = get_algorithm("chawathe")
        t1 = _trivial_tree("A", "Beirut", 1.0)
        t2 = _trivial_tree("B", "Bern",   1.0)
        script = algo.compute(t1, t2, config=cfg, taxonomies=taxonomies,
                              cost_model=cost_symmetric)
        ops = script.counts_by_op()
        assert ops["relabel"] == 1
        assert ops["delete"] == 0
        assert ops["insert"] == 0
        assert script.total_cost > 0

    def test_apply_recovers_target(self, cfg, taxonomies, cost_symmetric):
        algo = get_algorithm("chawathe")
        t1 = _trivial_tree("A", "Beirut", 1.0)
        t2 = _trivial_tree("B", "Bern",   2.0)
        script = algo.compute(t1, t2, config=cfg, taxonomies=taxonomies,
                              cost_model=cost_symmetric)
        patched = script.apply(t1)
        assert patched.size() == t2.size()
        # The relabeled leaves should match the target values.
        assert patched.find_by_label("geography.capital").value == "Bern"
        assert patched.find_by_label("economy.gdp").value == 2.0

    def test_inserts_when_target_has_extra_node(self, cfg, taxonomies,
                                                cost_symmetric):
        algo = get_algorithm("chawathe")
        t1 = _trivial_tree("A", "Beirut", 1.0)
        t2 = Tree(
            Node.structural("country", [
                Node.structural("geography", [
                    Node.leaf("capital", "Bern", "wikilink"),
                    Node.leaf("largest_city", "Zurich", "wikilink"),
                ]),
                Node.structural("economy", [
                    Node.leaf("gdp", 2.0, "number"),
                ]),
            ]),
            name="B",
        )
        script = algo.compute(t1, t2, config=cfg, taxonomies=taxonomies,
                              cost_model=cost_symmetric)
        ops = script.counts_by_op()
        assert ops["insert"] >= 1
        patched = script.apply(t1)
        assert patched.size() == t2.size()
        assert patched.find_by_label("geography.largest_city").value == "Zurich"

    def test_deletes_when_source_has_extra_node(self, cfg, taxonomies,
                                                cost_symmetric):
        algo = get_algorithm("chawathe")
        t1 = Tree(
            Node.structural("country", [
                Node.structural("geography", [
                    Node.leaf("capital", "Beirut", "wikilink"),
                    Node.leaf("largest_city", "Tripoli", "wikilink"),
                ]),
            ]),
            name="A",
        )
        t2 = Tree(
            Node.structural("country", [
                Node.structural("geography", [
                    Node.leaf("capital", "Beirut", "wikilink"),
                ]),
            ]),
            name="B",
        )
        script = algo.compute(t1, t2, config=cfg, taxonomies=taxonomies,
                              cost_model=cost_symmetric)
        ops = script.counts_by_op()
        assert ops["delete"] >= 1
        patched = script.apply(t1)
        assert patched.size() == t2.size()

    def test_asymmetric_costs_make_directions_differ(self, cfg, taxonomies,
                                                    cost_asymmetric):
        algo = get_algorithm("chawathe")
        t1 = Tree(
            Node.structural("country", [
                Node.structural("geography", [
                    Node.leaf("capital", "A", "wikilink"),
                    Node.leaf("largest_city", "B", "wikilink"),
                    Node.leaf("river", "C", "wikilink"),
                ]),
            ]),
            name="A",
        )
        t2 = Tree(
            Node.structural("country", [
                Node.structural("geography", [
                    Node.leaf("capital", "A", "wikilink"),
                ]),
            ]),
            name="B",
        )
        fwd = algo.compute(t1, t2, config=cfg, taxonomies=taxonomies,
                           cost_model=cost_asymmetric)
        rev = algo.compute(t2, t1, config=cfg, taxonomies=taxonomies,
                           cost_model=cost_asymmetric)
        # delete = 2, insert = 1 in asymmetric → forward (deleting 2 from t1)
        # costs more than reverse (inserting 2 into t2).
        assert fwd.total_cost > rev.total_cost


# ============================================================ Nierman & Jagadish
class TestNiermanJagadish:
    def test_identical_trees_zero_cost(self, cfg, taxonomies, cost_symmetric):
        algo = get_algorithm("nierman_jagadish")
        t1 = _trivial_tree("A", "Beirut", 1.0)
        t2 = _trivial_tree("A", "Beirut", 1.0)
        script = algo.compute(t1, t2, config=cfg, taxonomies=taxonomies,
                              cost_model=cost_symmetric)
        assert script.total_cost == 0

    def test_apply_recovers_target(self, cfg, taxonomies, cost_symmetric):
        algo = get_algorithm("nierman_jagadish")
        t1 = _trivial_tree("A", "Beirut", 1.0)
        t2 = _trivial_tree("B", "Bern",   2.0)
        patched = algo.compute(t1, t2, config=cfg, taxonomies=taxonomies,
                               cost_model=cost_symmetric).apply(t1)
        assert patched.find_by_label("geography.capital").value == "Bern"
        assert patched.find_by_label("economy.gdp").value == 2.0

    def test_subtree_containment_makes_move_cheap(self, cfg, taxonomies,
                                                  cost_symmetric):
        """Moving a subtree is a single op, not a full delete + reinsert.

        Tree A:
            country / { geography / { capital: Bern },  legacy / { city: Bern } }
        Tree B:
            country / { geography / { capital: Bern,  city: Bern } }

        The ``city: Bern`` leaf appears in both trees, just at different
        positions. The containment rule lets N&J price its insert into B
        as a single op rather than a full subtree (re)insert.
        """
        algo = get_algorithm("nierman_jagadish")
        moved_leaf = Node.leaf("city", "Bern", "wikilink")
        t1 = Tree(
            Node.structural("country", [
                Node.structural("geography", [
                    Node.leaf("capital", "Bern", "wikilink"),
                ]),
                Node.structural("legacy", [
                    Node.leaf("city", "Bern", "wikilink"),
                ]),
            ]),
            name="A",
        )
        t2 = Tree(
            Node.structural("country", [
                Node.structural("geography", [
                    Node.leaf("capital", "Bern", "wikilink"),
                    Node.leaf("city", "Bern", "wikilink"),
                ]),
            ]),
            name="B",
        )
        script = algo.compute(t1, t2, config=cfg, taxonomies=taxonomies,
                              cost_model=cost_symmetric)
        # Patched tree must still equal target.
        assert script.apply(t1).size() == t2.size()
        # Without containment the moved leaf would cost ≥2 (its insert + its
        # weighted delete); with containment both sides should be cheap.
        assert script.total_cost < 3.0

    def test_mapping_populated(self, cfg, taxonomies, cost_symmetric):
        """The script must carry the algorithm's node mapping."""
        algo = get_algorithm("nierman_jagadish")
        t1 = _trivial_tree("A", "Beirut", 1.0)
        t2 = _trivial_tree("B", "Bern",   2.0)
        script = algo.compute(t1, t2, config=cfg, taxonomies=taxonomies,
                              cost_model=cost_symmetric)
        assert len(script.mapping) > 0
        # Root maps to root.
        assert ((), ()) in [(tuple(a), tuple(b)) for a, b in script.mapping]

    def test_full_country_trees_patch_correctly(self, cfg, taxonomies,
                                                cost_symmetric):
        """End-to-end: Lebanon vs Switzerland from real Mongo data."""
        pytest.importorskip("pymongo")
        from src.storage.mongo_store import MongoStore
        from src.builder import build_country_tree

        store = MongoStore()
        if not store.ping():
            pytest.skip("MongoDB not reachable")

        t1 = build_country_tree(
            "Lebanon",
            store.get_country("Lebanon")["infobox"],
            config=cfg, taxonomies=taxonomies,
        )
        t2 = build_country_tree(
            "Switzerland",
            store.get_country("Switzerland")["infobox"],
            config=cfg, taxonomies=taxonomies,
        )
        algo = get_algorithm("nierman_jagadish")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            script = algo.compute(t1, t2, config=cfg, taxonomies=taxonomies,
                                  cost_model=cost_symmetric)
        patched = script.apply(t1)
        assert patched.size() == t2.size()
