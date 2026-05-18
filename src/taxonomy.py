"""Taxonomy: load a category tree from config, match wikitext to leaves,
compute ground-distance between leaves, and compute Earth-Mover's Distance
between two distributions over the leaves.

A taxonomy is a nested dict like::

    {
        "Abrahamic": {
            "Christianity": {
                "Catholic":  {"aliases": ["catholic", "roman catholic"]},
                ...
            },
            ...
        },
        ...
    }

Internal nodes can themselves carry an ``aliases`` list (treated as a leaf
fallback if their children don't match).

A *leaf path* is a tuple of category labels from root to leaf, e.g.
``("Abrahamic", "Islam", "Sunni")``. Distance between two leaves is
``(depth1 + depth2 − 2·depth(LCA)) / diameter`` ∈ ``[0, 1]``.

EMD is computed efficiently using the tree formula: for unit-mass tree
metrics, ``EMD = Σ_e w(e) · |F1(e) − F2(e)|`` where ``F_i(e)`` is the
total mass below edge ``e`` in distribution ``i``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

LeafPath = tuple[str, ...]


# =============================================================== Taxonomy
@dataclass
class Taxonomy:
    """A hierarchical category tree with alias-based matching.

    Use :meth:`from_dict` to build one from the JSON config.
    """

    name: str
    tree: dict[str, Any]
    leaf_paths: list[LeafPath] = field(default_factory=list)
    alias_index: dict[str, LeafPath] = field(default_factory=dict)
    diameter: int = 0

    # ----------------------------------------------------------- factory
    @classmethod
    def from_dict(cls, name: str, raw: dict[str, Any]) -> "Taxonomy":
        """Build a Taxonomy from a config-style dict.

        Accepts either ``{"tree": {...}}`` (nested form) or directly the
        nested dict.
        """
        tree = raw.get("tree", raw) if isinstance(raw, dict) else {}
        t = cls(name=name, tree=tree)
        t._build_index()
        t.diameter = t._compute_diameter()
        return t

    # ----------------------------------------------------------- build
    def _build_index(self) -> None:
        self.leaf_paths = []
        self.alias_index = {}
        self._walk(self.tree, ())

    def _walk(self, node: Any, path: LeafPath) -> None:
        if not isinstance(node, dict):
            return
        # If this node has "aliases", it's a leaf (or a leaf-like internal).
        if "aliases" in node:
            self.leaf_paths.append(path)
            for alias in node["aliases"]:
                self.alias_index[alias.lower()] = path
            # Children may still exist alongside aliases — recurse.
            for k, v in node.items():
                if k == "aliases":
                    continue
                self._walk(v, path + (k,))
            return
        # Pure internal node: recurse into children.
        for k, v in node.items():
            self._walk(v, path + (k,))
        # If the internal node had no leaves at all, treat the label as a leaf.
        if not any(p[:len(path)] == path and len(p) > len(path) for p in self.leaf_paths):
            # Only register as a leaf if there were truly no children dicts.
            if not any(isinstance(v, dict) for v in node.values()):
                self.leaf_paths.append(path)
                self.alias_index[path[-1].lower()] = path

    # ----------------------------------------------------------- depth/distance
    @staticmethod
    def depth(path: LeafPath) -> int:
        return len(path)

    @staticmethod
    def lca(a: LeafPath, b: LeafPath) -> LeafPath:
        out: list[str] = []
        for x, y in zip(a, b):
            if x == y:
                out.append(x)
            else:
                break
        return tuple(out)

    def _path_distance(self, a: LeafPath, b: LeafPath) -> int:
        """Number of edges on the path between two nodes (unit weights)."""
        common = self.lca(a, b)
        return (len(a) - len(common)) + (len(b) - len(common))

    def _compute_diameter(self) -> int:
        if not self.leaf_paths:
            return 1
        d = 0
        for i in range(len(self.leaf_paths)):
            for j in range(i + 1, len(self.leaf_paths)):
                d = max(d, self._path_distance(self.leaf_paths[i], self.leaf_paths[j]))
        return max(d, 1)

    def ground_distance(self, a: LeafPath, b: LeafPath) -> float:
        """Normalized tree distance between two leaves in ``[0, 1]``."""
        if a == b:
            return 0.0
        return self._path_distance(a, b) / self.diameter

    # ----------------------------------------------------------- matching
    def match(self, text: str) -> LeafPath | None:
        """Return the leaf path whose aliases best match ``text``.

        Matching is case-insensitive whole-word/substring. Returns the
        longest-alias match to avoid e.g. "Sunni" being shadowed by "ni".
        """
        if not text:
            return None
        lower = text.lower()
        best: tuple[int, LeafPath] | None = None
        for alias, path in self.alias_index.items():
            if alias in lower:
                if best is None or len(alias) > best[0]:
                    best = (len(alias), path)
        return best[1] if best else None

    def leaves(self) -> Iterable[LeafPath]:
        return iter(self.leaf_paths)

    # ----------------------------------------------------------- EMD
    def emd(self, dist1: dict[LeafPath, float],
            dist2: dict[LeafPath, float]) -> float:
        """Earth-Mover's Distance between two distributions over leaves.

        Both distributions are normalized to total mass 1 before comparison.
        Returns a value in ``[0, 1]``.

        Tree formula: ``EMD = Σ_e |F1(e) − F2(e)|`` over edges. With unit
        edge weights this equals the cost of optimal transport. Divide by
        the diameter to bound to ``[0, 1]``.
        """
        d1 = _normalize(dist1)
        d2 = _normalize(dist2)
        if not d1 and not d2:
            return 0.0
        if not d1 or not d2:
            return 1.0
        # Collect all edges (parent_path → child_path) by enumerating
        # every prefix of every leaf path with non-zero subtree mass.
        # For each edge ending at node ``v``, work = |F1(v) − F2(v)|,
        # where F_i(v) is the cumulative mass of leaves equal to v or
        # under v in distribution i. The root edge has F = 1 for both
        # (after normalization) so we skip it.
        subtree1 = _subtree_masses(d1)
        subtree2 = _subtree_masses(d2)
        total = 0.0
        for node in subtree1.keys() | subtree2.keys():
            if not node:  # root contributes nothing meaningful
                continue
            total += abs(subtree1.get(node, 0.0) - subtree2.get(node, 0.0))
        return min(1.0, total / self.diameter)


# =============================================================== helpers
def _normalize(dist: dict[LeafPath, float]) -> dict[LeafPath, float]:
    """Normalize a distribution to total mass 1.0 (drop non-positive entries)."""
    if not dist:
        return {}
    items = [(k, v) for k, v in dist.items() if v and v > 0]
    if not items:
        return {}
    total = sum(v for _, v in items)
    return {k: v / total for k, v in items}


def _subtree_masses(dist: dict[LeafPath, float]) -> dict[LeafPath, float]:
    """For each prefix of each leaf path, sum the mass of leaves under it."""
    out: dict[LeafPath, float] = {}
    for leaf, mass in dist.items():
        for k in range(1, len(leaf) + 1):
            prefix = leaf[:k]
            out[prefix] = out.get(prefix, 0.0) + mass
    return out


# =============================================================== registry
class TaxonomyRegistry:
    """All taxonomies loaded from the pipeline config keyed by name."""

    def __init__(self, taxonomies_config: dict[str, Any]) -> None:
        self._by_name: dict[str, Taxonomy] = {
            name: Taxonomy.from_dict(name, raw)
            for name, raw in taxonomies_config.items()
        }

    def get(self, name: str) -> Taxonomy:
        if name not in self._by_name:
            raise KeyError(f"No taxonomy named {name!r}. "
                           f"Available: {list(self._by_name)}")
        return self._by_name[name]

    def names(self) -> list[str]:
        return list(self._by_name)


def load_registry() -> TaxonomyRegistry:
    """Convenience: load all taxonomies from ``config/pipeline.json``."""
    from src.config import load_config
    cfg = load_config()
    return TaxonomyRegistry(cfg.get("taxonomies", {}))
