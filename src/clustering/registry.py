"""Decorator-based registry for clustering algorithms.

Mirrors the pattern used in ``src.ted.registry`` so all pluggable
algorithm catalogs in the project look the same.
"""

from __future__ import annotations

from typing import Callable, Type

from src.clustering.base import ClusterAlgorithm

_REGISTRY: dict[str, Type[ClusterAlgorithm]] = {}


def register(cls: Type[ClusterAlgorithm]) -> Type[ClusterAlgorithm]:
    """Register a clustering algorithm under its ``name`` attribute."""
    if not cls.name:
        raise ValueError(f"{cls.__name__} must define a non-empty ``name``")
    if cls.name in _REGISTRY:
        raise ValueError(f"Algorithm {cls.name!r} already registered")
    _REGISTRY[cls.name] = cls
    return cls


def get_algorithm(name: str) -> ClusterAlgorithm:
    """Instantiate a registered algorithm by name."""
    if name not in _REGISTRY:
        raise KeyError(f"Unknown clustering algorithm {name!r}. "
                       f"Available: {list(_REGISTRY)}")
    return _REGISTRY[name]()


def list_algorithms() -> list[dict[str, str]]:
    """Return ``[{name, description}, ...]`` for the UI dropdown."""
    return [{"name": cls.name, "description": cls.description}
            for cls in _REGISTRY.values()]
