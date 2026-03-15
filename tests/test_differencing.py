"""Tests for Stage 4: Edit script extraction and IDF formatting."""

import pytest
from src.preprocessing.xml_parser import parse_xml_string
from src.differencing.edit_script import extract_edit_script
from src.differencing.diff_formatter import diff_to_idf, build_idf
from src.ted.similarity import compute_similarity

COSTS = {'insert': 1, 'delete': 1, 'relabel': 1}


def make_tree(xml):
    return parse_xml_string(xml)


class TestEditScript:
    def test_no_ops_for_identical(self):
        T = make_tree('<a><b>x</b></a>')
        ted, script = extract_edit_script(T, T, COSTS, algorithm='chawathe')
        assert ted == 0.0
        assert len(script) == 0

    def test_one_relabel(self):
        T1 = make_tree('<a><b>hello</b></a>')
        T2 = make_tree('<a><b>world</b></a>')
        ted, script = extract_edit_script(T1, T2, COSTS)
        assert ted == 1.0
        relabels = [op for op in script if op.op_type == 'relabel']
        assert len(relabels) == 1

    def test_edit_script_cost_equals_ted(self):
        T1 = make_tree('<country name="A"><capital>X</capital><area_km2>100</area_km2></country>')
        T2 = make_tree('<country name="A"><capital>Y</capital><population>500</population></country>')
        ted, script = extract_edit_script(T1, T2, COSTS)
        assert abs(script.total_cost - ted) < 1e-9

    def test_nierman_jagadish_algorithm(self):
        T1 = make_tree('<a><b>x</b></a>')
        T2 = make_tree('<a><b>y</b></a>')
        ted, script = extract_edit_script(T1, T2, COSTS, algorithm='nierman_jagadish')
        assert ted == 1.0
        assert len(script) > 0

    def test_unknown_algorithm_raises(self):
        T = make_tree('<a/>')
        with pytest.raises(ValueError):
            extract_edit_script(T, T, COSTS, algorithm='unknown')


class TestDiffFormatter:
    def _make_diff(self, xml1, xml2):
        T1 = make_tree(xml1)
        T2 = make_tree(xml2)
        ted, script = extract_edit_script(T1, T2, COSTS)
        metrics = compute_similarity(ted, T1, T2)
        return ted, script, metrics

    def test_produces_string(self):
        ted, script, metrics = self._make_diff(
            '<a><b>x</b></a>', '<a><b>y</b></a>'
        )
        result = diff_to_idf(
            'A', 'B', 'chawathe',
            metrics['raw_ted'], metrics['sim_inverse'], metrics['sim_ratio'],
            script,
        )
        assert isinstance(result, str)
        assert 'idf:diff' in result

    def test_idf_contains_relabel(self):
        ted, script, metrics = self._make_diff(
            '<a><b>hello</b></a>', '<a><b>world</b></a>'
        )
        result = diff_to_idf(
            'A', 'B', 'chawathe',
            metrics['raw_ted'], metrics['sim_inverse'], metrics['sim_ratio'],
            script,
        )
        assert 'relabel' in result.lower()

    def test_idf_namespace(self):
        ted, script, metrics = self._make_diff('<a/>', '<a/>')
        result = diff_to_idf(
            'A', 'B', 'chawathe',
            metrics['raw_ted'], metrics['sim_inverse'], metrics['sim_ratio'],
            script,
        )
        assert 'urn:idpa:diff:1.0' in result

    def test_idf_attributes(self):
        ted, script, metrics = self._make_diff(
            '<a><b>x</b></a>', '<a><c>y</c></a>'
        )
        result = diff_to_idf(
            'Lebanon', 'Switzerland', 'chawathe',
            metrics['raw_ted'], metrics['sim_inverse'], metrics['sim_ratio'],
            script,
        )
        assert 'source="Lebanon"' in result
        assert 'target="Switzerland"' in result
        assert 'algorithm="chawathe"' in result
