"""Abstract base class for TED algorithms."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.core import EditScript, Tree
from src.taxonomy import TaxonomyRegistry


class TEDAlgorithm(ABC):
    """Pluggable Tree Edit Distance algorithm.

    Concrete subclasses register themselves with the registry and
    implement :meth:`compute`. Each algorithm receives the cost model
    already resolved to a flat dict (see ``src.config.resolve_cost_model``).
    """

    #: Short identifier used by the registry and the UI.
    name: str = "base"

    #: Human-readable description used by the UI.
    description: str = ""

    #: Set to True on placeholder implementations that should not be
    #: shipped to users without further work.
    placeholder: bool = False

    @abstractmethod
    def compute(self,
                t1: Tree,
                t2: Tree,
                *,
                config: dict[str, Any],
                taxonomies: TaxonomyRegistry,
                cost_model: dict[str, Any]) -> EditScript:
        """Compute an :class:`EditScript` that transforms ``t1`` into ``t2``."""
        raise NotImplementedError
