"""
Compute the three similarity metrics between two trees given their TED.

Metrics:
  1. raw_ted:        TED(T1, T2)
  2. sim_inverse:    1 / (1 + TED)
  3. sim_ratio:      1 - TED / (|T1| + |T2|)   where |T| = number of nodes
"""

from classes.Tree import Tree


def compute_similarity(ted: float, T1: Tree, T2: Tree) -> dict[str, float]:
    """
    Return all three similarity metrics.

    :param ted:  pre-computed TED value
    :param T1:   source tree
    :param T2:   target tree
    :return: dict with keys 'raw_ted', 'sim_inverse', 'sim_ratio'
    """
    size1 = T1.size()
    size2 = T2.size()
    total = size1 + size2

    sim_inverse = 1.0 / (1.0 + ted)
    sim_ratio = 1.0 - (ted / total) if total > 0 else 1.0

    return {
        'raw_ted': ted,
        'sim_inverse': sim_inverse,
        'sim_ratio': sim_ratio,
    }
