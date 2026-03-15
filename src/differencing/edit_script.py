"""
Edit script extraction.

Thin wrapper that calls the chosen TED algorithm and returns both the
TED value and the EditScript.

Usage:
    from src.differencing.edit_script import extract_edit_script

    ted, script = extract_edit_script(T1, T2, costs, algorithm='chawathe')
"""

from classes.Tree import Tree
from classes.EditScript import EditScript


def extract_edit_script(
    T1: Tree,
    T2: Tree,
    costs: dict,
    algorithm: str = 'chawathe',
) -> tuple[float, EditScript]:
    """
    Compute TED and produce an edit script for T1 → T2.

    :param T1: source tree
    :param T2: target tree
    :param costs: cost model dict
    :param algorithm: 'chawathe' | 'nierman_jagadish'
    :return: (TED value, EditScript)
    """
    if algorithm == 'chawathe':
        from src.ted.chawathe import compute_ted_and_script
        return compute_ted_and_script(T1, T2, costs)
    elif algorithm == 'nierman_jagadish':
        from src.ted.nierman_jagadish import compute_ted_and_script
        return compute_ted_and_script(T1, T2, costs)
    else:
        raise ValueError(f"Unknown algorithm {algorithm!r}. Choose 'chawathe' or 'nierman_jagadish'.")
