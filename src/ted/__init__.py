"""Tree Edit Distance algorithms.

Each algorithm subclasses :class:`TEDAlgorithm` and registers itself via
:func:`register`. The orchestrator in :mod:`src.comparison` looks
algorithms up by name through :func:`get_algorithm`.
"""

from src.ted.base import TEDAlgorithm
from src.ted.registry import get_algorithm, list_algorithms, register

# Import side-effect-registered algorithms.
from src.ted import chawathe, nierman_jagadish  # noqa: F401

__all__ = ["TEDAlgorithm", "get_algorithm", "list_algorithms", "register"]
