from classes.Node import Node


class Tree:
    def __init__(self, root: Node):
        self.root = root

    def size(self) -> int:
        """Return total number of nodes in the tree."""
        return sum(1 for _ in self.postorder())

    def postorder(self):
        """Yield all nodes in postorder (left-to-right, children before parent)."""
        yield from self._postorder(self.root)

    def _postorder(self, node: Node):
        for child in node.children:
            yield from self._postorder(child)
        yield node

    def preorder(self):
        """Yield all nodes in preorder (parent before children)."""
        yield from self._preorder(self.root)

    def _preorder(self, node: Node):
        yield node
        for child in node.children:
            yield from self._preorder(child)

    def get_nodes(self) -> list[Node]:
        """Return all nodes as a list in postorder."""
        return list(self.postorder())

    def __repr__(self) -> str:
        return f"Tree(root={self.root!r}, size={self.size()})"
