"""Tests for Stage 6: Post-processing (Tree → XML / infobox)."""

import pytest
from src.preprocessing.xml_parser import parse_xml_string
from src.postprocessing.serializer import tree_to_xml_string, tree_to_infobox


def make_tree(xml):
    return parse_xml_string(xml)


class TestSerializer:
    def test_xml_roundtrip_structure(self):
        xml = '<country name="TestLand"><capital>Testville</capital></country>'
        tree = make_tree(xml)
        out = tree_to_xml_string(tree)
        assert 'capital' in out
        assert 'Testville' in out

    def test_xml_is_string(self):
        tree = make_tree('<a><b>x</b></a>')
        result = tree_to_xml_string(tree)
        assert isinstance(result, str)

    def test_infobox_format(self):
        xml = '<country name="TestLand"><capital>Testville</capital><area_km2>100</area_km2></country>'
        tree = make_tree(xml)
        infobox = tree_to_infobox(tree)
        assert '{{Infobox country' in infobox
        assert '}}' in infobox
        assert 'capital' in infobox
        assert 'Testville' in infobox

    def test_infobox_established_group(self):
        xml = """<country name="X">
          <established>
            <event><label>Independence</label><date>1900</date></event>
          </established>
        </country>"""
        tree = make_tree(xml)
        infobox = tree_to_infobox(tree)
        assert 'established_event1' in infobox
        assert 'Independence' in infobox
        assert 'established_date1' in infobox
        assert '1900' in infobox

    def test_infobox_leaders_group(self):
        xml = """<country name="X">
          <leaders>
            <leader><title>President</title><name>John Doe</name></leader>
          </leaders>
        </country>"""
        tree = make_tree(xml)
        infobox = tree_to_infobox(tree)
        assert 'leader_title1' in infobox
        assert 'President' in infobox
        assert 'leader_name1' in infobox
        assert 'John Doe' in infobox
