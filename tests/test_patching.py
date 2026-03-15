"""Tests for Stage 5: Patching (apply edit script to tree)."""

import pytest
from src.preprocessing.xml_parser import parse_xml_string
from src.differencing.edit_script import extract_edit_script
from src.patching.patcher import apply_edit_script
from src.ted.chawathe import compute_ted

COSTS = {'insert': 1, 'delete': 1, 'relabel': 1}


def make_tree(xml):
    return parse_xml_string(xml)


class TestPatcher:
    def test_identical_trees_no_change(self):
        T = make_tree('<a><b>x</b></a>')
        _, script = extract_edit_script(T, T, COSTS)
        result = apply_edit_script(T, script)
        # No operations — should be structurally identical
        assert result.size() == T.size()

    def test_relabel_applied(self):
        T1 = make_tree('<a><b>hello</b></a>')
        T2 = make_tree('<a><b>world</b></a>')
        _, script = extract_edit_script(T1, T2, COSTS)
        patched = apply_edit_script(T1, script)
        leaves = [n for n in patched.postorder() if n.node_type == 'leaf' and n.label not in ('a', 'b')]
        # The leaf 'hello' should have been relabeled to 'world'
        leaf_labels = [n.label for n in patched.postorder() if n.is_leaf()]
        assert 'world' in leaf_labels

    def test_original_tree_unchanged(self):
        T1 = make_tree('<a><b>hello</b></a>')
        T2 = make_tree('<a><b>world</b></a>')
        _, script = extract_edit_script(T1, T2, COSTS)
        original_size = T1.size()
        apply_edit_script(T1, script)
        assert T1.size() == original_size  # original not mutated

    def test_patch_produces_tree_object(self):
        T1 = make_tree('<a><b>x</b></a>')
        T2 = make_tree('<a><b>y</b></a>')
        _, script = extract_edit_script(T1, T2, COSTS)
        result = apply_edit_script(T1, script)
        from classes.Tree import Tree
        assert isinstance(result, Tree)

    def test_empty_script_clones_tree(self):
        T = make_tree('<a><b>x</b><c>y</c></a>')
        from classes.EditScript import EditScript
        result = apply_edit_script(T, EditScript())
        assert result.size() == T.size()
        assert result.root is not T.root  # deep copy

    def test_asymmetric_costs_forward_converges(self):
        """Patching with delete > insert cost still produces a perfect result."""
        costs = {'insert': 1, 'delete': 2, 'relabel': 1}
        T1 = make_tree('<a><b>hello</b><c>extra</c></a>')
        T2 = make_tree('<a><b>world</b></a>')
        _, script = extract_edit_script(T1, T2, costs)
        patched = apply_edit_script(T1, script, target=T2, costs=costs)
        assert compute_ted(patched, T2, costs) == 0.0

    def test_asymmetric_costs_reverse_converges(self):
        """Reverse patching (T2→T1) with asymmetric costs is also perfect."""
        costs = {'insert': 1, 'delete': 2, 'relabel': 1}
        T1 = make_tree('<a><b>hello</b><c>extra</c></a>')
        T2 = make_tree('<a><b>world</b></a>')
        _, script_rv = extract_edit_script(T2, T1, costs)
        patched = apply_edit_script(T2, script_rv, target=T1, costs=costs)
        assert compute_ted(patched, T1, costs) == 0.0

    def test_iterative_refinement_cross_level_match(self):
        """Iterative refinement (target= param) converges when subtree deletion
        removes a node that was matched at a different structural level."""
        costs = {'insert': 1, 'delete': 1, 'relabel': 1}
        # T1: root/a/b/c  — c is deeply nested under b
        # T2: root/a/c    — c sits directly under a
        # Zhang-Shasha may match T1's c to T2's c; when b is deleted (with its
        # subtree including c), the first pass may leave a residual.
        # With target= supplied, iterative refinement must recover to TED=0.
        T1 = make_tree('<root><a><b><c>val</c></b></a></root>')
        T2 = make_tree('<root><a><c>val</c></a></root>')
        _, script = extract_edit_script(T1, T2, costs)
        patched = apply_edit_script(T1, script, target=T2, costs=costs)
        assert compute_ted(patched, T2, costs) == 0.0

    def test_iterative_refinement_without_target_may_differ(self):
        """Without target= the patcher applies exactly one pass; with target= it
        guarantees convergence. Both are valid calls; only the latter asserts 0."""
        costs = {'insert': 1, 'delete': 1, 'relabel': 1}
        T1 = make_tree('<root><a><b><c>x</c><d>y</d></b></a></root>')
        T2 = make_tree('<root><a><c>x</c><d>z</d></a></root>')
        _, script = extract_edit_script(T1, T2, costs)
        # Single pass — result is a valid tree but may have residual
        patched_single = apply_edit_script(T1, script)
        assert patched_single.size() > 0  # tree is non-empty
        # With refinement — guaranteed perfect
        patched_refined = apply_edit_script(T1, script, target=T2, costs=costs)
        assert compute_ted(patched_refined, T2, costs) == 0.0
