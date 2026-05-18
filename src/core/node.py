"""Node — the atomic element of a country tree.

A single class covers both ``structural`` interior nodes (e.g. ``country``,
``economy``, ``leader``) and ``leaf`` value-carrying nodes. Leaves carry a
typed Python value plus the raw wikitext for audit.

The tree is ordered (children are a list, not a set). Sibling order matters
for TED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Literal

NodeKind = Literal["structural", "leaf"]

# Type labels used on leaf nodes. Distance functions in
# ``src/distances`` are keyed on these strings.
LeafType = Literal[
    "number", "percent", "year", "date", "currency",
    "coordinates", "wikilink", "text",
    "distribution",  # parametrised by leaf.taxonomy, e.g. "religion"
    "empty",
]


@dataclass
class Node:
    """A single tree node — structural or leaf.

    Attributes:
        kind: ``"structural"`` for interior nodes; ``"leaf"`` for value nodes.
        label: The node's label. For structural nodes this is the tag-path
            segment (e.g. ``"economy"``, ``"leader"``). For leaf nodes it is
            the (canonical) field name (e.g. ``"capital"``, ``"area.km2"``).
        children: Ordered list of child nodes (structural only — always
            empty for leaves).
        value: Leaf payload — the parsed Python value (see LeafType).
        type: Leaf type label.
        raw: Original wikitext value, kept for audit / debugging.
        unit: Unit string when relevant (e.g. ``"km2"``, ``"USD"``).
        trend: ``+1`` / ``0`` / ``-1`` lifted from
            ``{{increase}}``/``{{steady}}``/``{{decrease}}`` templates.
        taxonomy: For ``type == "distribution"``, the name of the taxonomy
            (``"religion"``, ``"language"``, ``"ethnicity"``).
        parent: Back-reference to the parent node (set by ``Tree`` after
            construction; not part of equality).
    """

    kind: NodeKind
    label: str
    children: list["Node"] = field(default_factory=list)

    # Leaf-only payload.
    value: Any = None
    type: LeafType | None = None
    raw: str | None = None
    unit: str | None = None
    trend: int | None = None
    taxonomy: str | None = None

    parent: "Node | None" = field(default=None, repr=False, compare=False)

    # ----------------------------------------------------------- factories
    @classmethod
    def structural(cls, label: str, children: list["Node"] | None = None) -> "Node":
        """Create a structural (interior) node."""
        node = cls(kind="structural", label=label, children=list(children or []))
        for c in node.children:
            c.parent = node
        return node

    @classmethod
    def leaf(
        cls,
        label: str,
        value: Any,
        type: LeafType,
        *,
        raw: str | None = None,
        unit: str | None = None,
        trend: int | None = None,
        taxonomy: str | None = None,
    ) -> "Node":
        """Create a leaf node with a typed value."""
        return cls(
            kind="leaf",
            label=label,
            value=value,
            type=type,
            raw=raw,
            unit=unit,
            trend=trend,
            taxonomy=taxonomy,
        )

    # ----------------------------------------------------------- properties
    @property
    def is_leaf(self) -> bool:
        return self.kind == "leaf"

    @property
    def is_structural(self) -> bool:
        return self.kind == "structural"

    @property
    def arity(self) -> int:
        return len(self.children)

    # ----------------------------------------------------------- mutation
    def add_child(self, child: "Node") -> None:
        """Append a child to a structural node (and set its parent)."""
        if self.is_leaf:
            raise ValueError(f"Cannot add children to leaf node {self.label!r}")
        child.parent = self
        self.children.append(child)

    def remove_child(self, index: int) -> "Node":
        """Remove and return the child at ``index``."""
        if self.is_leaf:
            raise ValueError(f"Leaf node {self.label!r} has no children")
        child = self.children.pop(index)
        child.parent = None
        return child

    def insert_child(self, index: int, child: "Node") -> None:
        """Insert ``child`` at position ``index``."""
        if self.is_leaf:
            raise ValueError(f"Cannot insert into leaf node {self.label!r}")
        child.parent = self
        self.children.insert(index, child)

    # ----------------------------------------------------------- traversal
    def walk(self) -> Iterator["Node"]:
        """Pre-order traversal starting at this node."""
        yield self
        for c in self.children:
            yield from c.walk()

    def postorder(self) -> Iterator["Node"]:
        """Post-order traversal starting at this node."""
        for c in self.children:
            yield from c.postorder()
        yield self

    # ----------------------------------------------------------- equality
    def value_equals(self, other: "Node") -> bool:
        """Compare two nodes by payload (label, kind, value, type)."""
        if self.kind != other.kind or self.label != other.label:
            return False
        if self.is_leaf:
            return (
                self.type == other.type
                and self.value == other.value
                and self.taxonomy == other.taxonomy
                and self.unit == other.unit
            )
        return True

    # ----------------------------------------------------------- pretty
    def __repr__(self) -> str:  # noqa: D401
        if self.is_leaf:
            v = repr(self.value)
            if len(v) > 40:
                v = v[:37] + "..."
            return f"Leaf({self.label!r}, type={self.type}, value={v})"
        return f"Struct({self.label!r}, {len(self.children)} children)"

    def copy(self) -> "Node":
        """Deep copy of the subtree rooted at this node."""
        if self.is_leaf:
            return Node(
                kind="leaf",
                label=self.label,
                value=self.value,
                type=self.type,
                raw=self.raw,
                unit=self.unit,
                trend=self.trend,
                taxonomy=self.taxonomy,
            )
        new = Node.structural(self.label, [c.copy() for c in self.children])
        return new
