"""Tests for Stage 2: Pre-Processing (XML → Tree)."""

import pytest
from src.preprocessing.xml_parser import parse_xml_string
from src.preprocessing.tokenizer import tokenize
from src.preprocessing.normalizer import normalize_tree


class TestTokenizer:
    def test_basic(self):
        assert tokenize("I like data processing") == ['I', 'like', 'data', 'processing']

    def test_punctuation_stripped(self):
        tokens = tokenize("$11,793")
        assert tokens == ['11', '793']

    def test_empty(self):
        assert tokenize("") == []

    def test_numbers(self):
        assert tokenize("0.752") == ['0', '752']


class TestXmlParser:
    XML = """<country name="TestLand">
      <capital>Testville</capital>
      <area_km2>1234</area_km2>
      <established>
        <event>
          <label>Independence</label>
          <date>1900</date>
        </event>
      </established>
    </country>"""

    def test_root_is_element(self):
        tree = parse_xml_string(self.XML)
        assert tree.root.node_type == 'element'
        assert tree.root.label == 'country'

    def test_attribute_leaf(self):
        tree = parse_xml_string(self.XML)
        # First child should be attribute leaf 'name=TestLand'
        attr_child = tree.root.children[0]
        assert attr_child.node_type == 'leaf'
        assert attr_child.label == 'name=TestLand'

    def test_simple_field_leaf(self):
        tree = parse_xml_string(self.XML)
        # Find <capital> child
        capital = next(c for c in tree.root.children if c.label == 'capital')
        assert capital.node_type == 'element'
        assert len(capital.children) == 1
        assert capital.children[0].node_type == 'leaf'
        assert capital.children[0].label == 'Testville'

    def test_nested_elements(self):
        tree = parse_xml_string(self.XML)
        established = next(c for c in tree.root.children if c.label == 'established')
        assert established.node_type == 'element'
        assert len(established.children) == 1
        event = established.children[0]
        assert event.label == 'event'

    def test_tree_size(self):
        tree = parse_xml_string(self.XML)
        # country(attr) + capital(leaf) + area_km2(leaf) + established > event > label(leaf) + date(leaf)
        assert tree.size() > 5

    def test_postorder_yields_all(self):
        tree = parse_xml_string(self.XML)
        nodes = list(tree.postorder())
        assert len(nodes) == tree.size()

    def test_parent_pointers(self):
        tree = parse_xml_string(self.XML)
        for node in tree.preorder():
            for child in node.children:
                assert child.parent is node

    def test_token_nodes_strategy(self):
        xml = '<country name="X"><ethnic_groups>95% Arab, 4% other</ethnic_groups></country>'
        tree = parse_xml_string(xml, strategy='token_nodes')
        eg = next(c for c in tree.root.children if c.label == 'ethnic_groups')
        # Should have multiple token leaves
        assert len(eg.children) > 1
        assert all(c.node_type == 'leaf' for c in eg.children)

    def test_single_node_strategy(self):
        xml = '<country name="X"><ethnic_groups>95% Arab, 4% other</ethnic_groups></country>'
        tree = parse_xml_string(xml, strategy='single_node')
        eg = next(c for c in tree.root.children if c.label == 'ethnic_groups')
        assert len(eg.children) == 1
        assert eg.children[0].node_type == 'leaf'


class TestNormalizer:
    def test_alias_applied(self):
        xml = '<country name="X"><englishmotto>Peace</englishmotto></country>'
        tree = parse_xml_string(xml)
        aliases = {'englishmotto': 'national_motto'}
        normalize_tree(tree, aliases)
        labels = [c.label for c in tree.root.children if c.node_type == 'element']
        assert 'national_motto' in labels
        assert 'englishmotto' not in labels

    def test_no_alias_unchanged(self):
        xml = '<country name="X"><capital>City</capital></country>'
        tree = parse_xml_string(xml)
        normalize_tree(tree, {'image_map_caption': 'map_caption'})
        labels = [c.label for c in tree.root.children if c.node_type == 'element']
        assert 'capital' in labels
