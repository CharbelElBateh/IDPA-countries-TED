"""Algorithm registry: ``@register("name")`` decorator + lookup helpers."""

from __future__ import annotations

from typing import Callable, Type

from src.ted.base import TEDAlgorithm

_REGISTRY: dict[str, Type[TEDAlgorithm]] = {}


def register(name: str) -> Callable[[Type[TEDAlgorithm]], Type[TEDAlgorithm]]:
    """Register a TED algorithm class under ``name``."""
    def decorator(cls: Type[TEDAlgorithm]) -> Type[TEDAlgorithm]:
        if name in _REGISTRY:
            raise ValueError(f"TED algorithm {name!r} already registered")
        cls.name = name
        _REGISTRY[name] = cls
        return cls
    return decorator


def get_algorithm(name: str) -> TEDAlgorithm:
    """Return a fresh instance of the algorithm registered under ``name``."""
    if name not in _REGISTRY:
        raise KeyError(f"No TED algorithm named {name!r}. "
                       f"Available: {list(_REGISTRY)}")
    return _REGISTRY[name]()


def list_algorithms(*, include_placeholders: bool = True
                    ) -> list[dict[str, object]]:
    """Return metadata for every registered algorithm."""
    out: list[dict[str, object]] = []
    for name, cls in _REGISTRY.items():
        if cls.placeholder and not include_placeholders:
            continue
        out.append({
            "name": name,
            "description": cls.description,
            "placeholder": cls.placeholder,
        })
    return out
