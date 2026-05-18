"""Tests for the Taxonomy class and EMD computation."""

from __future__ import annotations

import pytest

from src.taxonomy import Taxonomy, TaxonomyRegistry, load_registry


SIMPLE_TREE = {
    "Abrahamic": {
        "Christianity": {
            "Catholic":   {"aliases": ["catholic"]},
            "Protestant": {"aliases": ["protestant", "lutheran"]},
        },
        "Islam": {
            "Sunni": {"aliases": ["sunni"]},
            "Shia":  {"aliases": ["shia", "shiite"]},
        },
    },
    "Irreligious": {
        "None": {"aliases": ["none", "irreligious"]},
    },
}


@pytest.fixture
def religion():
    return Taxonomy.from_dict("religion", SIMPLE_TREE)


class TestTaxonomyStructure:
    def test_leaves_indexed(self, religion):
        paths = list(religion.leaves())
        assert ("Abrahamic", "Christianity", "Catholic") in paths
        assert ("Abrahamic", "Islam", "Sunni") in paths
        assert ("Irreligious", "None") in paths

    def test_aliases_indexed(self, religion):
        assert religion.match("Catholic") == ("Abrahamic", "Christianity", "Catholic")
        assert religion.match("lutheran") == ("Abrahamic", "Christianity", "Protestant")
        assert religion.match("Sunni Muslim majority") == ("Abrahamic", "Islam", "Sunni")
        assert religion.match("flarbleflorp") is None


class TestGroundDistance:
    def test_same(self, religion):
        sunni = religion.match("sunni")
        assert religion.ground_distance(sunni, sunni) == 0.0

    def test_siblings_under_islam(self, religion):
        sunni = religion.match("sunni")
        shia = religion.match("shia")
        d = religion.ground_distance(sunni, shia)
        assert 0 < d < 1

    def test_islam_vs_christian(self, religion):
        sunni = religion.match("sunni")
        catholic = religion.match("catholic")
        d_inter = religion.ground_distance(sunni, catholic)
        d_intra = religion.ground_distance(sunni, religion.match("shia"))
        assert d_inter > d_intra

    def test_religious_vs_secular(self, religion):
        sunni = religion.match("sunni")
        none = religion.match("none")
        d = religion.ground_distance(sunni, none)
        catholic_vs_sunni = religion.ground_distance(
            religion.match("catholic"), sunni
        )
        assert d > catholic_vs_sunni


class TestEMD:
    def test_identical(self, religion):
        d = {("Abrahamic", "Islam", "Sunni"): 1.0}
        assert religion.emd(d, d) == 0.0

    def test_same_set_uniform_order_independent(self, religion):
        # 50/50 Sunni/Catholic two ways — should be 0 regardless of order.
        a = {("Abrahamic", "Islam", "Sunni"): 0.5,
             ("Abrahamic", "Christianity", "Catholic"): 0.5}
        b = {("Abrahamic", "Christianity", "Catholic"): 0.5,
             ("Abrahamic", "Islam", "Sunni"): 0.5}
        assert religion.emd(a, b) == 0.0

    def test_swapped_majorities(self, religion):
        # 80/20 Sunni/Catholic vs 20/80 Sunni/Catholic — non-trivial cost.
        a = {("Abrahamic", "Islam", "Sunni"): 0.8,
             ("Abrahamic", "Christianity", "Catholic"): 0.2}
        b = {("Abrahamic", "Islam", "Sunni"): 0.2,
             ("Abrahamic", "Christianity", "Catholic"): 0.8}
        d = religion.emd(a, b)
        assert d > 0.0

    def test_sunni_vs_shia_less_than_sunni_vs_catholic(self, religion):
        sunni = {("Abrahamic", "Islam", "Sunni"): 1.0}
        shia  = {("Abrahamic", "Islam", "Shia"): 1.0}
        catho = {("Abrahamic", "Christianity", "Catholic"): 1.0}
        d_intra = religion.emd(sunni, shia)
        d_inter = religion.emd(sunni, catho)
        assert d_intra < d_inter

    def test_religious_vs_secular_high(self, religion):
        rel = {("Abrahamic", "Islam", "Sunni"): 1.0}
        sec = {("Irreligious", "None"): 1.0}
        d_sec = religion.emd(rel, sec)
        d_intra = religion.emd(rel,
                               {("Abrahamic", "Islam", "Shia"): 1.0})
        assert d_sec > d_intra


class TestRegistry:
    def test_load_from_config(self):
        reg = load_registry()
        assert "religion" in reg.names()
        assert "language" in reg.names()
        assert "ethnicity" in reg.names()
        assert "government_type" in reg.names()

    def test_get_unknown_raises(self):
        reg = TaxonomyRegistry({"religion": SIMPLE_TREE})
        with pytest.raises(KeyError):
            reg.get("nope")
