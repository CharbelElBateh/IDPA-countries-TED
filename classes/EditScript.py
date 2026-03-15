from classes.Action import Action


class EditScript:
    """Ordered sequence of edit Actions with total cost."""

    def __init__(self):
        self.operations: list[Action] = []
        self.total_cost: int | float = 0

    def add(self, action: Action):
        self.operations.append(action)
        self.total_cost += action.cost

    def remove(self, action: Action):
        self.operations.remove(action)
        self.total_cost -= action.cost

    def __len__(self) -> int:
        return len(self.operations)

    def __iter__(self):
        return iter(self.operations)

    def __repr__(self) -> str:
        return f"EditScript(ops={len(self.operations)}, total_cost={self.total_cost})"

    def __str__(self) -> str:
        lines = [f"EditScript — {len(self.operations)} ops, cost={self.total_cost}"]
        for i, op in enumerate(self.operations, 1):
            lines.append(f"  {i}. {op}")
        return '\n'.join(lines)
