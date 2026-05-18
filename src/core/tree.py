"""Tree — wraps a root Node and provides path-based access + traversal utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from src.core.node import Node

# A NodePath is a tuple of child-indices from the root.
# () is the root itself; (0,) is root.children[0]; (1, 2) is root.children[1].children[2].
NodePath = tuple[int, ...]


@dataclass
class Tree:
    """A rooted ordered labeled tree of ``Node`` instances.

    Attributes:
        root: The root node (always structural).
        name: Optional identifier (e.g. the country name).
    """

    root: Node
    name: str | None = None

    # ----------------------------------------------------------- factory
    def __post_init__(self) -> None:
        # Re-wire parent pointers — defensive against caller-built node lists
        # that may have stale parents from another tree.
        self._rewire_parents(self.root, None)

    @staticmethod
    def _rewire_parents(node: Node, parent: Node | None) -> None:
        node.parent = parent
        for c in node.children:
            Tree._rewire_parents(c, node)

    # ----------------------------------------------------------- structure
    def size(self) -> int:
        """Total number of nodes in the tree."""
        return sum(1 for _ in self.root.walk())

    def height(self) -> int:
        """Maximum depth of any node (root has depth 0)."""
        def h(n: Node) -> int:
            if not n.children:
                return 0
            return 1 + max(h(c) for c in n.children)
        return h(self.root)

    # ----------------------------------------------------------- traversal
    def walk(self) -> Iterator[Node]:
        """Pre-order traversal."""
        return self.root.walk()

    def postorder(self) -> Iterator[Node]:
        """Post-order traversal."""
        return self.root.postorder()

    def leaves(self) -> Iterator[Node]:
        """Yield every leaf node in pre-order."""
        for n in self.walk():
            if n.is_leaf:
                yield n

    # ----------------------------------------------------------- paths
    def get(self, path: NodePath) -> Node:
        """Return the node at ``path``.

        Raises:
            IndexError: if any index in the path is out of range.
        """
        node = self.root
        for i in path:
            node = node.children[i]
        return node

    def path_of(self, node: Node) -> NodePath:
        """Return the path of ``node`` by walking up parent pointers.

        Uses *identity* (``is``) when finding ``cur`` in
        ``parent.children``: ``Node`` is a dataclass with default
        equality, so two structurally-identical sibling subtrees
        compare equal and ``list.index`` would return the first match
        (collapsing distinct nodes to the same path). Common in
        hand-crafted test trees like ``A(B, B)``.
        """
        indices: list[int] = []
        cur = node
        while cur.parent is not None:
            parent = cur.parent
            idx = next(
                (i for i, c in enumerate(parent.children) if c is cur),
                None,
            )
            if idx is None:
                raise ValueError(
                    f"node {cur.label!r} not found in its parent's children "
                    f"(stale parent pointer?)"
                )
            indices.append(idx)
            cur = parent
        return tuple(reversed(indices))

    def find_by_label(self, dotted: str) -> Node | None:
        """Resolve a dotted structural label path (e.g. ``"economy.gdp_ppp.value"``).

        Returns the first matching node, or ``None`` if not found.
        """
        parts = dotted.split(".")
        cur = self.root
        for p in parts:
            match = next((c for c in cur.children if c.label == p), None)
            if match is None:
                return None
            cur = match
        return cur

    # ----------------------------------------------------------- mutations
    def copy(self) -> "Tree":
        """Deep copy of the entire tree."""
        return Tree(self.root.copy(), name=self.name)

    # ----------------------------------------------------------- pretty
    def to_ascii(self, *, max_value_chars: int = 60) -> str:
        """Render the tree as indented ASCII art."""
        lines: list[str] = []

        def render(node: Node, prefix: str, is_last: bool) -> None:
            connector = "└── " if is_last else "├── "
            if node.is_leaf:
                v = repr(node.value)
                if len(v) > max_value_chars:
                    v = v[:max_value_chars - 3] + "..."
                lines.append(
                    f"{prefix}{connector}{node.label} [{node.type}] = {v}"
                )
            else:
                lines.append(f"{prefix}{connector}{node.label}/")
            child_prefix = prefix + ("    " if is_last else "│   ")
            for i, c in enumerate(node.children):
                render(c, child_prefix, i == len(node.children) - 1)

        # Root line.
        lines.append(self.root.label + "/")
        for i, c in enumerate(self.root.children):
            render(c, "", i == len(self.root.children) - 1)
        return "\n".join(lines)

    def __repr__(self) -> str:  # noqa: D401
        return f"Tree(name={self.name!r}, size={self.size()})"
