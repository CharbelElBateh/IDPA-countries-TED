"""Action — a single edit operation on a tree.

Three operation types:

- ``"insert"``: insert ``new_node`` (a fresh subtree) as a child of the node
  at ``parent_path``, at child index ``position``.
- ``"delete"``: remove the subtree rooted at ``path``.
- ``"relabel"``: replace the node at ``path`` with one whose payload comes
  from ``new_node`` (label / value / type / ...). For structural nodes only
  ``label`` is touched; children are preserved.

Paths are tuples of child indices from the root (see ``src/core/tree.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from src.core.node import Node

OpType = Literal["insert", "delete", "relabel"]


@dataclass
class Action:
    """One TED edit operation.

    Attributes:
        op: ``"insert"`` | ``"delete"`` | ``"relabel"``.
        path: Path to the target (or to the parent, for ``insert``).
        cost: Real-valued cost of this operation.
        new_node: Replacement subtree for ``insert`` / ``relabel``.
        position: Child index where the new node is inserted (``insert`` only).
        old_label: Original label captured at script time (``relabel`` / ``delete``)
            — used to make the script self-describing and reversible.
        old_value: Original value (``relabel`` of a leaf) — captured for reversal.
    """

    op: OpType
    path: tuple[int, ...]
    cost: float = 1.0
    new_node: Node | None = None
    position: int | None = None
    old_label: str | None = None
    old_value: object = field(default=None, repr=False)
    old_type: str | None = None
    old_taxonomy: str | None = None

    # ----------------------------------------------------------- helpers
    def __repr__(self) -> str:  # noqa: D401
        path_str = "()" if not self.path else "→".join(str(i) for i in self.path)
        if self.op == "insert":
            child = self.new_node.label if self.new_node else "?"
            return (f"Insert({path_str} @ {self.position}, "
                    f"{child!r}, cost={self.cost:.3f})")
        if self.op == "delete":
            return f"Delete({path_str}, {self.old_label!r}, cost={self.cost:.3f})"
        # relabel
        new_label = self.new_node.label if self.new_node else "?"
        return (f"Relabel({path_str}, {self.old_label!r}→{new_label!r}, "
                f"cost={self.cost:.3f})")
