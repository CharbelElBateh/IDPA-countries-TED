"""Smoke tests for src.core: Node, Tree, Action, EditScript."""

from __future__ import annotations

import json

import pytest

from src.core import Action, EditScript, Node, Tree


# ----------------------------------------------------------------- helpers
def make_country_tree(name: str, capital: str, gdp: float) -> Tree:
    """Build a tiny country tree: country/{geography/capital, economy/gdp}."""
    return Tree(
        Node.structural("country", [
            Node.structural("geography", [
                Node.leaf("capital", capital, "wikilink"),
            ]),
            Node.structural("economy", [
                Node.leaf("gdp", gdp, "number", unit="USD"),
            ]),
        ]),
        name=name,
    )


# ----------------------------------------------------------------- Node
class TestNode:
    def test_structural_factory(self):
        n = Node.structural("economy", [Node.leaf("gdp", 1.0, "number")])
        assert n.is_structural
        assert n.arity == 1
        assert n.children[0].parent is n

    def test_leaf_factory(self):
        n = Node.leaf("hdi", 0.752, "number", raw="0.752")
        assert n.is_leaf
        assert n.value == 0.752
        assert n.type == "number"
        assert n.raw == "0.752"
        assert n.arity == 0

    def test_add_child_sets_parent(self):
        root = Node.structural("country")
        leaf = Node.leaf("capital", "Beirut", "wikilink")
        root.add_child(leaf)
        assert leaf.parent is root
        assert root.children == [leaf]

    def test_leaf_cannot_have_children(self):
        leaf = Node.leaf("x", 1, "number")
        with pytest.raises(ValueError):
            leaf.add_child(Node.leaf("y", 2, "number"))

    def test_copy_is_deep(self):
        root = Node.structural("a", [Node.leaf("b", 1, "number")])
        clone = root.copy()
        clone.children[0].value = 99
        assert root.children[0].value == 1

    def test_value_equals(self):
        a = Node.leaf("x", 1, "number")
        b = Node.leaf("x", 1, "number")
        c = Node.leaf("x", 2, "number")
        assert a.value_equals(b)
        assert not a.value_equals(c)


# ----------------------------------------------------------------- Tree
class TestTree:
    def test_size(self):
        t = make_country_tree("X", "Capital", 1.0)
        assert t.size() == 5  # country + geo + capital + econ + gdp

    def test_height(self):
        t = make_country_tree("X", "Capital", 1.0)
        assert t.height() == 2

    def test_parent_wiring(self):
        t = make_country_tree("X", "Capital", 1.0)
        for n in t.walk():
            if n is t.root:
                assert n.parent is None
            else:
                assert n.parent is not None

    def test_get_by_path(self):
        t = make_country_tree("X", "Capital", 1.0)
        assert t.get(()) is t.root
        assert t.get((0,)).label == "geography"
        assert t.get((1, 0)).label == "gdp"

    def test_path_of_roundtrip(self):
        t = make_country_tree("X", "Capital", 1.0)
        for n in t.walk():
            assert t.get(t.path_of(n)) is n

    def test_find_by_label(self):
        t = make_country_tree("X", "Capital", 1.0)
        node = t.find_by_label("economy.gdp")
        assert node is not None and node.value == 1.0
        assert t.find_by_label("does.not.exist") is None

    def test_copy_is_deep(self):
        t = make_country_tree("X", "Capital", 1.0)
        t2 = t.copy()
        t2.root.children[0].children[0].value = "Other"
        assert t.root.children[0].children[0].value == "Capital"

    def test_ascii_render(self):
        t = make_country_tree("X", "Capital", 1.0)
        text = t.to_ascii()
        assert "country/" in text
        assert "geography/" in text
        assert "capital" in text


# ----------------------------------------------------------------- EditScript
class TestEditScript:
    def test_relabel(self):
        t1 = make_country_tree("A", "Beirut", 1.0)
        capital_path = t1.path_of(t1.find_by_label("geography.capital"))
        script = EditScript(source_name="A", target_name="B")
        script.add(Action(
            op="relabel",
            path=capital_path,
            cost=0.3,
            new_node=Node.leaf("capital", "Bern", "wikilink"),
            old_label="capital",
            old_value="Beirut",
            old_type="wikilink",
        ))
        t2 = script.apply(t1)
        assert t1.find_by_label("geography.capital").value == "Beirut"
        assert t2.find_by_label("geography.capital").value == "Bern"

    def test_delete(self):
        t1 = make_country_tree("A", "Beirut", 1.0)
        gdp_path = t1.path_of(t1.find_by_label("economy.gdp"))
        script = EditScript()
        script.add(Action(
            op="delete",
            path=gdp_path,
            cost=1.0,
            old_label="gdp",
            new_node=t1.find_by_label("economy.gdp").copy(),
        ))
        t2 = script.apply(t1)
        assert t2.find_by_label("economy.gdp") is None
        assert t1.find_by_label("economy.gdp") is not None  # unmutated

    def test_insert(self):
        t1 = make_country_tree("A", "Beirut", 1.0)
        econ_path = t1.path_of(t1.find_by_label("economy"))
        script = EditScript()
        script.add(Action(
            op="insert",
            path=econ_path,
            position=1,
            cost=1.0,
            new_node=Node.leaf("hdi", 0.752, "number"),
        ))
        t2 = script.apply(t1)
        assert t2.find_by_label("economy.hdi").value == 0.752

    def test_inverse_relabel(self):
        t1 = make_country_tree("A", "Beirut", 1.0)
        cap_path = t1.path_of(t1.find_by_label("geography.capital"))
        script = EditScript(source_name="A", target_name="B")
        script.add(Action(
            op="relabel", path=cap_path, cost=0.3,
            new_node=Node.leaf("capital", "Bern", "wikilink"),
            old_label="capital", old_value="Beirut", old_type="wikilink",
        ))
        t2 = script.apply(t1)
        t1_back = script.inverse().apply(t2)
        assert t1_back.find_by_label("geography.capital").value == "Beirut"

    def test_inverse_delete_insert(self):
        t1 = make_country_tree("A", "Beirut", 1.0)
        gdp_node = t1.find_by_label("economy.gdp")
        gdp_path = t1.path_of(gdp_node)
        script = EditScript()
        script.add(Action(
            op="delete", path=gdp_path, cost=1.0,
            old_label="gdp", new_node=gdp_node.copy(),
        ))
        t2 = script.apply(t1)
        assert t2.find_by_label("economy.gdp") is None
        t1_back = script.inverse().apply(t2)
        assert t1_back.find_by_label("economy.gdp").value == 1.0

    def test_json_roundtrip(self, tmp_path):
        t1 = make_country_tree("A", "Beirut", 1.0)
        cap_path = t1.path_of(t1.find_by_label("geography.capital"))
        script = EditScript(source_name="A", target_name="B")
        script.add(Action(
            op="relabel", path=cap_path, cost=0.3,
            new_node=Node.leaf("capital", "Bern", "wikilink"),
            old_label="capital", old_value="Beirut", old_type="wikilink",
        ))
        p = tmp_path / "script.json"
        script.to_json(p)
        loaded = EditScript.from_json(p)
        assert loaded.source_name == "A"
        assert loaded.target_name == "B"
        assert len(loaded) == 1
        assert loaded.operations[0].op == "relabel"
        # Apply the loaded script to the original tree — same result.
        assert loaded.apply(t1).find_by_label("geography.capital").value == "Bern"

    def test_counts_and_repr(self):
        s = EditScript()
        s.add(Action(op="relabel", path=(), cost=0.1,
                     new_node=Node.structural("x"), old_label="y"))
        s.add(Action(op="delete", path=(0,), cost=1.0, old_label="z",
                     new_node=Node.leaf("z", 1, "number")))
        s.add(Action(op="insert", path=(), position=0, cost=1.0,
                     new_node=Node.leaf("w", 2, "number")))
        assert s.counts_by_op() == {"insert": 1, "delete": 1, "relabel": 1}
        assert "3 ops" in repr(s)
        assert abs(s.total_cost - 2.1) < 1e-9
