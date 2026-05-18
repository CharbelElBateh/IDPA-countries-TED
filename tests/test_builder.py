"""Tests for the country-tree builder and per-type distance functions."""

from __future__ import annotations

import pytest

from src.builder import build_country_tree
from src.config import load_config
from src.distances import (
    coordinates_distance, currency_distance, distribution_distance,
    field_weight, number_distance, percent_distance, relabel_cost,
    text_distance, year_distance,
)
from src.core import Node
from src.taxonomy import load_registry


# ----------------------------------------------------------- builder fixtures
TINY_INFOBOX = {
    "conventional_long_name": "Lebanese Republic",
    "common_name": "Lebanon",
    "demonym": "[[Lebanese people|Lebanese]]",
    "capital": "[[Beirut]]",
    "government_type": "[[Unitary parliamentary republic]]",
    "leader_title1": "[[President of Lebanon|President]]",
    "leader_name1": "[[Joseph Aoun]]",
    "leader_title2": "[[Prime Minister]]",
    "leader_name2": "[[Nawaf Salam]]",
    "established_event1": "[[Emirate of Mount Lebanon]]",
    "established_date1": "1516",
    "GDP_PPP": "{{increase}} $78.233 billion",
    "GDP_PPP_year": "2022",
    "GDP_PPP_per_capita": "{{increase}} $11,793",
    "area_km2": "10452",
    "percent_water": "1.6",
    "religion": "Islam\nChristianity\nDruze",
    "official_languages": "Arabic",
    # Layout/cite that should be dropped:
    "image_flag": "Flag of Lebanon.svg",
    "Gini_ref": "<ref>cite</ref>",
}


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def taxonomies():
    return load_registry()


@pytest.fixture
def tree(cfg, taxonomies):
    return build_country_tree("Lebanon", TINY_INFOBOX,
                              config=cfg, taxonomies=taxonomies)


class TestBuilder:
    def test_root_label(self, tree):
        assert tree.root.label == "country"
        assert tree.name == "Lebanon"

    def test_identity_subtree(self, tree):
        long_name = tree.find_by_label("identity.long_name")
        assert long_name is not None
        assert long_name.value == "Lebanese Republic"
        assert long_name.type == "text"

    def test_capital_is_resolved_wikilink(self, tree):
        cap = tree.find_by_label("geography.capital")
        assert cap is not None
        assert cap.value == "Beirut"
        assert cap.type == "wikilink"

    def test_gdp_composite(self, tree):
        value = tree.find_by_label("economy.gdp_ppp.value")
        year  = tree.find_by_label("economy.gdp_ppp.year")
        cap   = tree.find_by_label("economy.gdp_ppp.per_capita")
        assert value.value == pytest.approx(78.233e9)
        assert value.unit == "USD"
        assert value.trend == +1
        assert year.value == 2022
        assert cap.value == pytest.approx(11793.0)

    def test_area(self, tree):
        a = tree.find_by_label("geography.area.km2")
        w = tree.find_by_label("geography.area.water_pct")
        assert a.value == 10452.0
        assert w.value == 1.6 and w.type == "percent"

    def test_leaders_serial_group(self, tree):
        leaders = tree.find_by_label("government.leaders")
        assert leaders is not None
        assert len(leaders.children) == 2
        # Children are 'leader' structurals; each carries title+name+index.
        for child in leaders.children:
            assert child.label == "leader"
            labels = [c.label for c in child.children]
            assert "title" in labels
            assert "name" in labels
            assert "index" in labels

    def test_established_serial_group(self, tree):
        est = tree.find_by_label("history.established")
        assert est is not None
        assert len(est.children) == 1
        ev = est.children[0]
        assert ev.label == "event"
        date_leaf = next(c for c in ev.children if c.label == "date")
        assert date_leaf.type in {"date", "year"}

    def test_religion_distribution(self, tree):
        rel = tree.find_by_label("demographics.religion")
        assert rel is not None
        assert rel.type == "distribution"
        assert rel.taxonomy == "religion"
        # Three uniform entries — each ~1/3.
        weights = [item["weight"] for item in rel.value]
        assert sum(weights) == pytest.approx(1.0, abs=1e-6)
        assert all(abs(w - 1/3) < 0.05 for w in weights)

    def test_filtered_fields_dropped(self, tree):
        assert tree.find_by_label("identity.image_flag") is None
        # Gini_ref should be dropped by the filter too.
        labels = [n.label for n in tree.walk()]
        assert "Gini_ref" not in labels
        assert "image_flag" not in labels


# ----------------------------------------------------------- distances
class TestDistances:
    def test_number(self):
        assert number_distance(10, 10) == 0.0
        assert number_distance(10, 20) == pytest.approx(0.5)
        assert number_distance(0, 1000) == 1.0

    def test_percent(self):
        assert percent_distance(20, 80) == pytest.approx(0.6)

    def test_year(self):
        assert year_distance(2024, 2024) == 0.0
        assert year_distance(2000, 2100) == 1.0

    def test_currency_log(self):
        # 1 billion vs 100 billion = 2 orders of magnitude / 4 = 0.5
        d = currency_distance(1e9, 1e11)
        assert d == pytest.approx(0.5)

    def test_coords(self):
        # Same point.
        assert coordinates_distance((0, 0), (0, 0)) == 0.0
        # Antipodes are ~20000 km — should be near 1.
        d = coordinates_distance((0, 0), (0, 180))
        assert d >= 0.9

    def test_text(self):
        assert text_distance("abc", "abc") == 0.0
        assert 0 < text_distance("Beirut", "Berlin") < 1
        assert text_distance("abc", "xyz") == 1.0


class TestRelabelCost:
    def test_structural_same_label(self, cfg, taxonomies):
        a = Node.structural("economy")
        b = Node.structural("economy")
        assert relabel_cost(a, b, config=cfg, taxonomies=taxonomies) == 0.0

    def test_structural_diff_label(self, cfg, taxonomies):
        a = Node.structural("economy")
        b = Node.structural("government")
        assert relabel_cost(a, b, config=cfg, taxonomies=taxonomies) > 0.0

    def test_leaf_number(self, cfg, taxonomies):
        a = Node.leaf("x", 100.0, "number")
        b = Node.leaf("x", 200.0, "number")
        c = relabel_cost(a, b, config=cfg, taxonomies=taxonomies)
        assert 0 < c < 1

    def test_leaf_type_mismatch(self, cfg, taxonomies):
        a = Node.leaf("x", 100.0, "number")
        b = Node.leaf("x", "foo", "text")
        assert relabel_cost(a, b, config=cfg, taxonomies=taxonomies) > 0.5

    def test_distribution_emd(self, cfg, taxonomies):
        a = Node.leaf("religion",
                      [{"path": ["Abrahamic", "Islam", "Sunni"], "weight": 1.0}],
                      "distribution", taxonomy="religion")
        b = Node.leaf("religion",
                      [{"path": ["Abrahamic", "Islam", "Shia"], "weight": 1.0}],
                      "distribution", taxonomy="religion")
        c = Node.leaf("religion",
                      [{"path": ["Irreligious", "None"], "weight": 1.0}],
                      "distribution", taxonomy="religion")
        d_intra = relabel_cost(a, b, config=cfg, taxonomies=taxonomies)
        d_inter = relabel_cost(a, c, config=cfg, taxonomies=taxonomies)
        assert 0 < d_intra < d_inter


class TestFieldWeight:
    def test_exact_match(self):
        w = field_weight(["government", "type"],
                         {"default": 1.0, "government.type": 2.5})
        assert w == 2.5

    def test_prefix_match(self):
        w = field_weight(["economy", "gdp_ppp", "value"],
                         {"default": 1.0, "economy.gdp_ppp": 1.8})
        assert w == 1.8

    def test_default(self):
        w = field_weight(["irrelevant"], {"default": 1.5})
        assert w == 1.5

    def test_longest_prefix_wins(self):
        w = field_weight(
            ["a", "b", "c"],
            {"default": 1.0, "a": 2.0, "a.b": 3.0, "a.b.c": 4.0},
        )
        assert w == 4.0
