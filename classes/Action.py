from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from classes.Node import Node


class Action:
    """Represents a single edit operation in an edit script."""

    VALID_OPS = {'insert', 'delete', 'relabel'}

    def __init__(self, op_type: str, cost: int | float, node: 'Node', args: dict):
        """
        :param op_type: 'insert' | 'delete' | 'relabel'
        :param cost: numeric cost of this operation
        :param node: the Node this operation targets
        :param args: op-specific parameters
            insert: {'parent': Node, 'position': int}
            delete: {}
            relabel: {'new_label': str}
        """
        if op_type not in self.VALID_OPS:
            raise ValueError(f"Invalid op_type {op_type!r}. Must be one of {self.VALID_OPS}")
        self.op_type = op_type
        self.cost = cost
        self.node = node
        self.args = args

    def __repr__(self) -> str:
        return f"Action({self.op_type}, cost={self.cost}, node={self.node!r}, args={self.args})"

    def __str__(self) -> str:
        if self.op_type == 'insert':
            return f"insert({self.node.label!r}, parent={self.args.get('parent')}, pos={self.args.get('position')})"
        if self.op_type == 'delete':
            return f"delete({self.node.label!r})"
        if self.op_type == 'relabel':
            return f"relabel({self.node.label!r} -> {self.args.get('new_label')!r})"
        return repr(self)
