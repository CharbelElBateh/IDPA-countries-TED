class Node:
    def __init__(self, label: str, node_type: str):
        """
        :param label: tag name for element nodes, text content for leaf nodes
        :param node_type: 'element' | 'leaf'
        """
        self.label = label
        self.node_type = node_type
        self.children: list['Node'] = []
        self.parent: 'Node | None' = None

    def add_child(self, child: 'Node'):
        child.parent = self
        self.children.append(child)

    def insert_child(self, index: int, child: 'Node'):
        child.parent = self
        self.children.insert(index, child)

    def remove_child(self, child: 'Node'):
        self.children.remove(child)
        child.parent = None

    def is_leaf(self) -> bool:
        return self.node_type == 'leaf'

    def is_element(self) -> bool:
        return self.node_type == 'element'

    def __repr__(self) -> str:
        return f"Node({self.node_type}, {self.label!r})"
