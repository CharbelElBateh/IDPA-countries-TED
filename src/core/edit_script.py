"""EditScript — an ordered list of Actions that transforms one tree into another.

Apply order matters. To keep paths valid as the tree mutates, the script is
applied in an order that processes deeper / later siblings first so that
earlier-path indices remain stable:

- ``delete`` operations are sorted by path **descending** (deepest, rightmost first).
- ``insert`` operations are sorted by path **ascending** within each parent.
- ``relabel`` does not change tree shape and can be applied in any order.

Applying an EditScript:

>>> new_tree = script.apply(old_tree)

Reversing:

>>> reverse = script.inverse()    # transforms target back to source

EditScripts are JSON-serializable for persistence and inspection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from src.core.action import Action, OpType
from src.core.node import Node
from src.core.tree import Tree


@dataclass
class EditScript:
    """An ordered, applicable list of edit operations.

    Attributes:
        operations: Actions in the order they were emitted by TED.
        total_cost: Sum of action costs.
        source_name: Optional name of the source tree (for audit).
        target_name: Optional name of the target tree (for audit).
        mapping: List of ``(t1_path, t2_path)`` pairs — the node-pair
            mapping the TED algorithm settled on, kept here so the
            frontend can colour both trees consistently without
            re-deriving the mapping from the script. Each path is a
            tuple of child indices from the root.
    """

    operations: list[Action] = field(default_factory=list)
    total_cost: float = 0.0
    source_name: str | None = None
    target_name: str | None = None
    mapping: list[tuple[tuple[int, ...], tuple[int, ...]]] = \
        field(default_factory=list)

    # ----------------------------------------------------------- building
    def add(self, action: Action) -> None:
        """Append one action and accumulate its cost."""
        self.operations.append(action)
        self.total_cost += action.cost

    def extend(self, actions: Iterable[Action]) -> None:
        """Append several actions."""
        for a in actions:
            self.add(a)

    # ----------------------------------------------------------- query
    def __len__(self) -> int:
        return len(self.operations)

    def __iter__(self):
        return iter(self.operations)

    def __repr__(self) -> str:  # noqa: D401
        return (f"EditScript({len(self.operations)} ops, "
                f"cost={self.total_cost:.3f}, "
                f"{self.source_name!r} → {self.target_name!r})")

    def counts_by_op(self) -> dict[str, int]:
        """Return ``{op_type: count}`` for diagnostics."""
        out: dict[str, int] = {"insert": 0, "delete": 0, "relabel": 0}
        for a in self.operations:
            out[a.op] += 1
        return out

    # ----------------------------------------------------------- apply
    def apply(self, tree: Tree) -> Tree:
        """Return a new tree resulting from applying this script to ``tree``.

        The input tree is **not** mutated.
        """
        result = tree.copy()

        # 1) Relabels first — they don't change shape.
        for act in (a for a in self.operations if a.op == "relabel"):
            self._apply_relabel(result, act)

        # 2) Deletes in deepest-rightmost order so earlier paths stay valid.
        for act in sorted(
            (a for a in self.operations if a.op == "delete"),
            key=lambda a: (len(a.path), a.path),
            reverse=True,
        ):
            self._apply_delete(result, act)

        # 3) Inserts in (parent-path, position) order — shallow-first, left-to-right.
        for act in sorted(
            (a for a in self.operations if a.op == "insert"),
            key=lambda a: (len(a.path), a.path, a.position or 0),
        ):
            self._apply_insert(result, act)

        return result

    @staticmethod
    def _apply_relabel(tree: Tree, act: Action) -> None:
        if act.new_node is None:
            raise ValueError(f"Relabel action missing new_node: {act}")
        target = tree.get(act.path)
        new = act.new_node
        # Keep children of structural target intact — replace payload only.
        target.label = new.label
        if target.is_leaf:
            target.value = new.value
            target.type = new.type
            target.raw = new.raw
            target.unit = new.unit
            target.trend = new.trend
            target.taxonomy = new.taxonomy

    @staticmethod
    def _apply_delete(tree: Tree, act: Action) -> None:
        if not act.path:
            raise ValueError("Cannot delete the root node")
        parent = tree.get(act.path[:-1])
        parent.remove_child(act.path[-1])

    @staticmethod
    def _apply_insert(tree: Tree, act: Action) -> None:
        if act.new_node is None or act.position is None:
            raise ValueError(f"Insert action missing new_node/position: {act}")
        parent = tree.get(act.path)
        parent.insert_child(act.position, act.new_node.copy())

    # ----------------------------------------------------------- inverse
    def inverse(self) -> "EditScript":
        """Return the script that undoes this one (target → source).

        - ``insert`` at (parent_path, position) → ``delete`` at
          (parent_path + (position,))
        - ``delete`` at path → ``insert`` of the old subtree at
          (path[:-1], path[-1]); this requires the deleted subtree to have
          been captured in ``new_node`` at script-build time.
        - ``relabel`` → relabel back to old payload.
        """
        ops: list[Action] = []
        for act in self.operations:
            if act.op == "relabel":
                if act.old_label is None:
                    raise ValueError(f"Cannot invert relabel without old_label: {act}")
                restored = Node(
                    kind="leaf" if act.old_type else "structural",
                    label=act.old_label,
                    value=act.old_value,
                    type=act.old_type,  # type: ignore[arg-type]
                    taxonomy=act.old_taxonomy,
                )
                ops.append(Action(
                    op="relabel",
                    path=act.path,
                    cost=act.cost,
                    new_node=restored,
                    old_label=act.new_node.label if act.new_node else None,
                    old_value=act.new_node.value if act.new_node else None,
                    old_type=act.new_node.type if act.new_node else None,
                ))
            elif act.op == "insert":
                # Inverse of an insert is a delete at the inserted position.
                if act.position is None:
                    raise ValueError(f"Insert action missing position: {act}")
                ops.append(Action(
                    op="delete",
                    path=act.path + (act.position,),
                    cost=act.cost,
                    old_label=act.new_node.label if act.new_node else None,
                    new_node=act.new_node.copy() if act.new_node else None,
                ))
            else:  # delete
                if not act.path:
                    raise ValueError("Cannot invert root-delete")
                if act.new_node is None:
                    raise ValueError(
                        f"Cannot invert delete without captured subtree: {act}"
                    )
                ops.append(Action(
                    op="insert",
                    path=act.path[:-1],
                    position=act.path[-1],
                    cost=act.cost,
                    new_node=act.new_node.copy(),
                ))

        return EditScript(
            operations=ops,
            total_cost=self.total_cost,
            source_name=self.target_name,
            target_name=self.source_name,
        )

    # ----------------------------------------------------------- I/O
    def to_dict(self) -> dict[str, Any]:
        """Plain-dict representation suitable for ``json.dump`` and Mongo storage."""
        return {
            "source": self.source_name,
            "target": self.target_name,
            "total_cost": self.total_cost,
            "mapping": [
                [list(t1p), list(t2p)] for t1p, t2p in self.mapping
            ],
            "operations": [
                {
                    "op": a.op,
                    "path": list(a.path),
                    "cost": a.cost,
                    "position": a.position,
                    "old_label": a.old_label,
                    "old_value": _serialize_value(a.old_value),
                    "old_type": a.old_type,
                    "old_taxonomy": a.old_taxonomy,
                    "new_node": _node_to_dict(a.new_node) if a.new_node else None,
                }
                for a in self.operations
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EditScript":
        """Inverse of :meth:`to_dict`."""
        ops = [
            Action(
                op=o["op"],
                path=tuple(o["path"]),
                cost=o["cost"],
                position=o.get("position"),
                old_label=o.get("old_label"),
                old_value=_deserialize_value(o.get("old_value"), o.get("old_type")),
                old_type=o.get("old_type"),
                old_taxonomy=o.get("old_taxonomy"),
                new_node=_node_from_dict(o["new_node"]) if o.get("new_node") else None,
            )
            for o in payload["operations"]
        ]
        mapping = [
            (tuple(pair[0]), tuple(pair[1]))
            for pair in payload.get("mapping", [])
        ]
        return cls(
            operations=ops,
            total_cost=payload.get("total_cost", sum(a.cost for a in ops)),
            source_name=payload.get("source"),
            target_name=payload.get("target"),
            mapping=mapping,
        )

    def to_json(self, path: str | Path) -> None:
        """Write the script as pretty-printed JSON."""
        Path(path).write_text(
            json.dumps(self.to_dict(), indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def from_json(cls, path: str | Path) -> "EditScript":
        """Load a script from JSON."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)


# --------------------------------------------------------------- helpers
def _serialize_value(v: Any) -> Any:
    """Convert ``v`` to a JSON/BSON-friendly form (dates → ISO strings, tuples → lists)."""
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, tuple):
        return [_serialize_value(x) for x in v]
    if isinstance(v, list):
        return [_serialize_value(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _serialize_value(x) for k, x in v.items()}
    return v


def _deserialize_value(v: Any, type_hint: str | None) -> Any:
    """Inverse of :func:`_serialize_value` for typed leaves."""
    if v is None:
        return None
    if type_hint == "date" and isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except ValueError:
            return v
    if type_hint == "coordinates" and isinstance(v, list) and len(v) == 2:
        return tuple(v)
    return v


def _node_to_dict(node: Node) -> dict[str, Any]:
    """Recursively serialize a Node subtree to plain dicts."""
    d: dict[str, Any] = {
        "kind": node.kind,
        "label": node.label,
    }
    if node.is_leaf:
        d.update({
            "value": _serialize_value(node.value),
            "type": node.type,
            "raw": node.raw,
            "unit": node.unit,
            "trend": node.trend,
            "taxonomy": node.taxonomy,
        })
    else:
        d["children"] = [_node_to_dict(c) for c in node.children]
    return d


def _node_from_dict(d: dict[str, Any]) -> Node:
    """Inverse of :func:`_node_to_dict`."""
    if d["kind"] == "leaf":
        return Node.leaf(
            label=d["label"],
            value=_deserialize_value(d.get("value"), d.get("type")),
            type=d.get("type"),
            raw=d.get("raw"),
            unit=d.get("unit"),
            trend=d.get("trend"),
            taxonomy=d.get("taxonomy"),
        )
    return Node.structural(
        label=d["label"],
        children=[_node_from_dict(c) for c in d.get("children", [])],
    )
