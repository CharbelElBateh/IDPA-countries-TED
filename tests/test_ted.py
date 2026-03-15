"""Tests for Stage 3: TED algorithms and similarity metrics."""

import pytest
from classes.Node import Node
from classes.Tree import Tree
from src.preprocessing.xml_parser import parse_xml_string
from src.ted.chawathe import compute_ted, compute_ted_and_script
from src.ted.nierman_jagadish import compute_ted as nj_compute_ted
from src.ted.similarity import compute_similarity

COSTS = {'insert': 1, 'delete': 1, 'relabel': 1}


def make_tree(xml: str) -> Tree:
    return parse_xml_string(xml)


class TestChawathe:
    def test_identical_trees(self):
        xml = '<a><b>x</b></a>'
        T = make_tree(xml)
        assert compute_ted(T, T, COSTS) == 0.0

    def test_empty_vs_single(self):
        xml1 = '<a/>'
        xml2 = '<a><b>x</b></a>'
        T1 = make_tree(xml1)
        T2 = make_tree(xml2)
        # T2 has <b> (element) and leaf 'x' extra: 2 inserts
        ted = compute_ted(T1, T2, COSTS)
        assert ted == 2.0

    def test_single_relabel(self):
        T1 = make_tree('<a><b>hello</b></a>')
        T2 = make_tree('<a><b>world</b></a>')
        ted = compute_ted(T1, T2, COSTS)
        assert ted == 1.0

    def test_delete_one_child(self):
        T1 = make_tree('<a><b>x</b><c>y</c></a>')
        T2 = make_tree('<a><b>x</b></a>')
        ted = compute_ted(T1, T2, COSTS)
        # Delete <c> (element) + delete leaf 'y' = 2
        assert ted == 2.0

    def test_symmetry(self):
        T1 = make_tree('<a><b>x</b></a>')
        T2 = make_tree('<a><c>y</c></a>')
        assert compute_ted(T1, T2, COSTS) == compute_ted(T2, T1, COSTS)

    def test_triangle_inequality(self):
        T1 = make_tree('<a><b>x</b></a>')
        T2 = make_tree('<a><b>y</b></a>')
        T3 = make_tree('<a><c>y</c></a>')
        d12 = compute_ted(T1, T2, COSTS)
        d23 = compute_ted(T2, T3, COSTS)
        d13 = compute_ted(T1, T3, COSTS)
        assert d13 <= d12 + d23

    def test_edit_script_cost_matches_ted(self):
        T1 = make_tree('<a><b>x</b><c>y</c></a>')
        T2 = make_tree('<a><b>x</b><d>z</d></a>')
        ted, script = compute_ted_and_script(T1, T2, COSTS)
        assert script.total_cost == ted

    def test_custom_costs(self):
        costs = {'insert': 2, 'delete': 3, 'relabel': 5}
        T1 = make_tree('<a><b>x</b></a>')
        T2 = make_tree('<a><b>y</b></a>')
        ted = compute_ted(T1, T2, costs)
        assert ted == 5.0  # one relabel

    def test_asymmetric_costs_directional(self):
        """With delete > insert, TED(T1→T2) > TED(T2→T1) when T1 has extra nodes."""
        costs = {'insert': 1, 'delete': 2, 'relabel': 1}
        # Forward: delete <c>+leaf 'y' (2 deletes × 2 = 4)
        # Reverse: insert <c>+leaf 'y' (2 inserts × 1 = 2)
        T1 = make_tree('<a><b>x</b><c>y</c></a>')
        T2 = make_tree('<a><b>x</b></a>')
        ted_fwd = compute_ted(T1, T2, costs)
        ted_rv  = compute_ted(T2, T1, costs)
        assert ted_fwd == 4.0   # 2 deletes × cost 2
        assert ted_rv  == 2.0   # 2 inserts × cost 1
        assert ted_fwd != ted_rv

    def test_equal_trees_zero_script(self):
        T = make_tree('<country name="X"><capital>City</capital></country>')
        ted, script = compute_ted_and_script(T, T, COSTS)
        assert ted == 0.0
        assert script.total_cost == 0.0


class TestNiermanJagadish:
    def test_identical_trees(self):
        xml = '<a><b>x</b></a>'
        T = make_tree(xml)
        assert nj_compute_ted(T, T, COSTS) == 0.0

    def test_structure_vs_content_costs(self):
        costs = {
            'insert': 10, 'delete': 10,
            'relabel_structure': 3, 'relabel_content': 1,
        }
        # relabel_structure(3) < delete+insert(20), so algorithm relabels b→c
        T1 = make_tree('<a><b>x</b></a>')
        T2 = make_tree('<a><c>x</c></a>')
        ted = nj_compute_ted(T1, T2, costs)
        assert ted == 3.0  # relabel_structure for <b>→<c>

    def test_content_relabel(self):
        costs = {
            'insert': 1, 'delete': 1,
            'relabel_structure': 3, 'relabel_content': 1,
        }
        T1 = make_tree('<a><b>hello</b></a>')
        T2 = make_tree('<a><b>world</b></a>')
        ted = nj_compute_ted(T1, T2, costs)
        assert ted == 1.0  # relabel_content for leaf

    def test_same_as_chawathe_with_uniform_costs(self):
        T1 = make_tree('<a><b>x</b><c>y</c></a>')
        T2 = make_tree('<a><b>x</b><d>z</d></a>')
        ted_c = compute_ted(T1, T2, COSTS)
        ted_nj = nj_compute_ted(T1, T2, COSTS)
        assert ted_c == ted_nj

    def test_nj_diverges_from_chawathe_with_split_costs(self):
        """N&J gives a lower TED than Chawathe when structural relabels are cheap
        and the uniform Chawathe cost would prefer delete+insert instead."""
        costs_nj = {
            'insert': 10, 'delete': 10,
            'relabel_structure': 1, 'relabel_content': 1,
        }
        costs_cw = {'insert': 10, 'delete': 10, 'relabel': 1}
        T1 = make_tree('<root><a><b>x</b></a></root>')
        T2 = make_tree('<root><a><c>x</c></a></root>')
        # Both should prefer relabeling b→c (cost 1) over delete+insert (cost 20)
        ted_nj = nj_compute_ted(T1, T2, costs_nj)
        ted_cw = compute_ted(T1, T2, costs_cw)
        assert ted_nj == ted_cw  # same optimal cost here; both relabel
        # Now make structural relabels free — N&J tree-distance drops further
        costs_nj2 = {'insert': 10, 'delete': 10, 'relabel_structure': 0, 'relabel_content': 1}
        costs_cw2 = {'insert': 10, 'delete': 10, 'relabel': 1}
        ted_nj2 = nj_compute_ted(T1, T2, costs_nj2)
        ted_cw2 = compute_ted(T1, T2, costs_cw2)
        assert ted_nj2 < ted_cw2  # N&J is strictly cheaper when struct relabel = 0


class TestSimilarity:
    def test_identical_zero_ted(self):
        T = make_tree('<a><b>x</b></a>')
        metrics = compute_similarity(0.0, T, T)
        assert metrics['raw_ted'] == 0.0
        assert metrics['sim_inverse'] == 1.0
        assert metrics['sim_ratio'] == 1.0

    def test_high_ted_low_similarity(self):
        T1 = make_tree('<a><b>x</b></a>')
        T2 = make_tree('<a><b>y</b></a>')
        ted = compute_ted(T1, T2, COSTS)
        metrics = compute_similarity(ted, T1, T2)
        assert 0 < metrics['sim_inverse'] < 1
        assert 0 < metrics['sim_ratio'] <= 1

    def test_sim_inverse_formula(self):
        T = make_tree('<a/>')
        metrics = compute_similarity(4.0, T, T)
        assert abs(metrics['sim_inverse'] - 1.0 / 5.0) < 1e-9

    def test_sim_ratio_formula(self):
        T1 = make_tree('<a><b>x</b></a>')  # 3 nodes
        T2 = make_tree('<a><b>y</b></a>')  # 3 nodes
        ted = 1.0
        metrics = compute_similarity(ted, T1, T2)
        # sim_ratio = 1 - 1/6
        assert abs(metrics['sim_ratio'] - (1.0 - 1.0 / 6.0)) < 1e-9
