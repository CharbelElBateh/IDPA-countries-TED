"""Parse / serialize hand-crafted trees for testing the TED pipeline.

Input format is the bracket notation standard in TED textbooks:

    root(a, b(c, d), e)

Whitespace is ignored. Labels are matched against ``[A-Za-z0-9_.\\-]+``.
Every node parsed this way is created as ``structural`` — childless
nodes are still ``structural`` (TED treats them identically to leaves,
and downstream relabel-cost logic stays simple).

The companion ``node_from_dict`` round-trips a tree previously produced
by ``frontend.formatting.tree_to_dict`` (used to persist synthetic
trees in MongoDB).
"""

from __future__ import annotations

import re
from typing import Any

from src.core import Node, Tree

_TOKEN_RE = re.compile(r"[A-Za-z0-9_.\-]+|[(),]")


def parse_bracket_tree(text: str, *, name: str | None = None) -> Tree:
    """Parse bracket-notation ``text`` into a :class:`Tree`.

    Raises:
        ValueError: on any syntactic problem (with the offending position).
    """
    tokens = _TOKEN_RE.findall(text or "")
    if not tokens:
        raise ValueError("empty input")

    pos = [0]

    def _node() -> Node:
        if pos[0] >= len(tokens):
            raise ValueError("expected label, reached end of input")
        tok = tokens[pos[0]]
        if tok in "(),":
            raise ValueError(f"expected label at token #{pos[0]}, got {tok!r}")
        pos[0] += 1
        children: list[Node] = []
        if pos[0] < len(tokens) and tokens[pos[0]] == "(":
            pos[0] += 1                     # consume '('
            children.append(_node())
            while pos[0] < len(tokens) and tokens[pos[0]] == ",":
                pos[0] += 1                 # consume ','
                children.append(_node())
            if pos[0] >= len(tokens) or tokens[pos[0]] != ")":
                raise ValueError(f"expected ')' at token #{pos[0]}")
            pos[0] += 1                     # consume ')'
        return Node.structural(tok, children)

    root = _node()
    if pos[0] != len(tokens):
        raise ValueError(f"unexpected trailing token {tokens[pos[0]]!r} "
                         f"at position #{pos[0]}")
    return Tree(root, name=name)


def node_from_dict(d: dict[str, Any]) -> Node:
    """Reconstruct a :class:`Node` from the dict produced by ``tree_to_dict``."""
    if d.get("kind") == "leaf":
        return Node.leaf(
            label=d["label"],
            value=d.get("value"),
            type=d.get("type") or "text",
            raw=d.get("raw"),
            unit=d.get("unit"),
            trend=d.get("trend"),
            taxonomy=d.get("taxonomy"),
        )
    return Node.structural(
        label=d["label"],
        children=[node_from_dict(c) for c in d.get("children", [])],
    )
