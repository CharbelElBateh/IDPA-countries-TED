"""End-to-end comparison orchestrator.

Given two country names, an algorithm name, and a cost-model name,
returns the forward + reverse :class:`EditScript`, both trees, both
patched trees, and a "marks" object describing which nodes were touched
by each operation (used by the frontend to highlight diffs).

Results are cached in MongoDB so repeated requests are instant.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.builder import build_country_tree
from src.config import load_config, resolve_cost_model
from src.core import EditScript, Tree
from src.storage.mongo_store import MongoStore
from src.taxonomy import TaxonomyRegistry, load_registry
from src.ted import get_algorithm

logger = logging.getLogger(__name__)


def similarity_metrics(ted: float, t1_size: int, t2_size: int) -> dict[str, float]:
    """Three similarity metrics from the IDPA course slides (Ch. 5).

    i.   Raw TED integer:     ``TED(T1, T2)``
    ii.  Normalized inverse:  ``1 / (1 + TED(T1, T2))``
    iii. Standard ratio:      ``1 - TED(T1, T2) / (|T1| + |T2|)``
    where ``|T|`` is the number of nodes in tree ``T``.
    """
    denom = t1_size + t2_size
    return {
        "ted_raw":        float(ted),
        "sim_inverse":    1.0 / (1.0 + ted),
        "sim_ratio":      1.0 - (ted / denom) if denom > 0 else 0.0,
        "t1_size":        t1_size,
        "t2_size":        t2_size,
    }


@dataclass
class DirectionResult:
    """One direction of a comparison: t1 → t2 (forward) or t2 → t1 (reverse)."""
    script: EditScript
    source_tree: Tree
    target_tree: Tree
    patched_tree: Tree
    source_marks: dict[str, str] = field(default_factory=dict)
    target_marks: dict[str, str] = field(default_factory=dict)

    @property
    def metrics(self) -> dict[str, float]:
        return similarity_metrics(
            self.script.total_cost,
            self.source_tree.size(),
            self.target_tree.size(),
        )

    def to_dict(self) -> dict[str, Any]:
        from frontend.formatting import tree_to_dict
        return {
            "script":      self.script.to_dict(),
            "total_cost":  self.script.total_cost,
            "op_counts":   self.script.counts_by_op(),
            "metrics":     self.metrics,
            "source":      tree_to_dict(self.source_tree.root),
            "target":      tree_to_dict(self.target_tree.root),
            "patched":     tree_to_dict(self.patched_tree.root),
            "source_marks": self.source_marks,
            "target_marks": self.target_marks,
        }


@dataclass
class ComparisonResult:
    country1: str
    country2: str
    algorithm: str
    cost_model: str
    forward: DirectionResult
    reverse: DirectionResult
    from_cache: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "country1":   self.country1,
            "country2":   self.country2,
            "algorithm":  self.algorithm,
            "cost_model": self.cost_model,
            "from_cache": self.from_cache,
            "forward":    self.forward.to_dict(),
            "reverse":    self.reverse.to_dict(),
        }


# =============================================================== entry point
def compare(country1: str, country2: str, *,
            algorithm: str = "naive",
            cost_model: str = "symmetric",
            use_cache: bool = True,
            store: MongoStore | None = None,
            config: dict[str, Any] | None = None,
            taxonomies: TaxonomyRegistry | None = None) -> ComparisonResult:
    """Compute (or fetch cached) a full comparison between two countries.

    Args:
        country1: First country name (becomes the *source* of ``forward``).
        country2: Second country name (becomes the *source* of ``reverse``).
        algorithm: Registered TED algorithm name (``"naive"`` /
            ``"chawathe"`` / ``"nierman_jagadish"``).
        cost_model: Name of a cost model in ``pipeline.json``.
        use_cache: If True, look up + persist scripts in MongoDB.
        store: Optional MongoStore (constructed if not given).
        config: Optional pre-loaded pipeline config.
        taxonomies: Optional pre-loaded taxonomy registry.
    """
    cfg = config or load_config()
    tax = taxonomies or load_registry()
    store = store or MongoStore()
    costs = resolve_cost_model(cost_model, cfg)

    # Build trees on demand.
    t1 = _load_tree(country1, store, cfg, tax)
    t2 = _load_tree(country2, store, cfg, tax)

    # Synthetic test trees change frequently while debugging — never
    # serve them from cache; always recompute.
    is_synthetic = any(
        (doc or {}).get("source") == "synthetic"
        for doc in (store.get_country(country1), store.get_country(country2))
    )
    if is_synthetic:
        use_cache = False

    # Try cache first.
    cached = None
    if use_cache:
        cached = store.get_edit_script(country1, country2, algorithm, cost_model)

    if cached is not None:
        fwd_script = EditScript.from_dict(cached["forward"])
        rev_script = EditScript.from_dict(cached["reverse"])
        from_cache = True
    else:
        algo = get_algorithm(algorithm)
        fwd_script = algo.compute(t1, t2, config=cfg, taxonomies=tax,
                                  cost_model=costs)
        rev_script = algo.compute(t2, t1, config=cfg, taxonomies=tax,
                                  cost_model=costs)
        from_cache = False
        if use_cache:
            store.save_edit_script(
                country1, country2, algorithm, cost_model,
                forward=fwd_script.to_dict(),
                reverse=rev_script.to_dict(),
            )

    forward = _make_direction(t1, t2, fwd_script)
    reverse = _make_direction(t2, t1, rev_script)

    return ComparisonResult(
        country1=country1, country2=country2,
        algorithm=algorithm, cost_model=cost_model,
        forward=forward, reverse=reverse,
        from_cache=from_cache,
    )


# =============================================================== internals
def _load_tree(name: str, store: MongoStore,
               cfg: dict[str, Any],
               tax: TaxonomyRegistry) -> Tree:
    doc = store.get_country(name)
    if doc is None:
        raise KeyError(f"No country {name!r} in MongoDB")
    # Synthetic / hand-crafted trees skip the Wikipedia-infobox pipeline
    # and are reconstructed verbatim from the stored ``tree_dict``.
    if doc.get("source") == "synthetic" and doc.get("tree_dict"):
        from src.synthetic_tree import node_from_dict
        return Tree(node_from_dict(doc["tree_dict"]), name=name)
    return build_country_tree(name, doc["infobox"], config=cfg, taxonomies=tax)


def _make_direction(source: Tree, target: Tree,
                    script: EditScript) -> DirectionResult:
    """Apply ``script`` to ``source`` and compute diff marks."""
    patched = script.apply(source)
    source_marks, target_marks = _marks_from_mapping(source, target, script)
    return DirectionResult(
        script=script,
        source_tree=source,
        target_tree=target,
        patched_tree=patched,
        source_marks=source_marks,
        target_marks=target_marks,
    )


# ----------------------------------------------------------- diff marks
def _marks_from_mapping(source: Tree, target: Tree,
                        script: EditScript
                        ) -> tuple[dict[str, str], dict[str, str]]:
    """Compute ``(source_marks, target_marks)`` from the script's mapping.

    The mapping is the algorithm's ground truth of which nodes correspond.
    From it:

    * Source nodes in the mapping → ``"relabel"`` if their counterpart
      payload differs, else *unchanged* (no mark).
    * Source nodes not in the mapping → ``"delete"``.
    * Target nodes in the mapping → ``"relabel"`` if counterpart payload
      differs, else unchanged.
    * Target nodes not in the mapping → ``"insert"``.

    Falls back to the legacy "script-driven source / dotted-path target"
    style if the script carries no mapping (older cached records).
    """
    if not script.mapping:
        return _legacy_marks_on_source(source, script), \
               _legacy_marks_on_target(target, source)

    mapped_src_paths: set[tuple[int, ...]] = set()
    mapped_tgt_paths: set[tuple[int, ...]] = set()
    src_to_tgt: dict[tuple[int, ...], tuple[int, ...]] = {}
    for s_path, t_path in script.mapping:
        s_path = tuple(s_path)
        t_path = tuple(t_path)
        mapped_src_paths.add(s_path)
        mapped_tgt_paths.add(t_path)
        src_to_tgt[s_path] = t_path

    source_marks: dict[str, str] = {}
    for n in source.walk():
        if n is source.root:
            continue
        p = source.path_of(n)
        key = _dotted(n)
        t_path = src_to_tgt.get(p)
        if t_path is not None:
            try:
                t_node = target.get(t_path)
            except IndexError:
                continue
            if _payload_differs(n, t_node):
                source_marks[key] = "relabel"
        else:
            source_marks[key] = "delete"

    target_marks: dict[str, str] = {}
    # Reverse lookup: target_path → source_path. A malformed mapping (e.g.
    # the same source path appearing with two different targets — possible
    # when LD-pair Chawathe's depth-only constraints let two sibling
    # alignments share the same parent index after the strict-parent
    # filter) loses entries during inversion. Using ``.get(p)`` instead of
    # ``[p]`` falls back to treating those targets as inserts, which is
    # correct: we couldn't recover a coherent source mapping for them.
    tgt_to_src: dict[tuple[int, ...], tuple[int, ...]] = {}
    for s_path, t_path in src_to_tgt.items():
        tgt_to_src.setdefault(t_path, s_path)
    for n in target.walk():
        if n is target.root:
            continue
        p = target.path_of(n)
        key = _dotted(n)
        s_path = tgt_to_src.get(p)
        if s_path is not None:
            try:
                s_node = source.get(s_path)
            except IndexError:
                continue
            if _payload_differs(s_node, n):
                target_marks[key] = "relabel"
        else:
            target_marks[key] = "insert"

    return source_marks, target_marks


def _payload_differs(a, b) -> bool:
    """True if two nodes' labels or leaf payloads differ."""
    if a.kind != b.kind:
        return True
    if a.is_structural:
        return a.label != b.label
    return not a.value_equals(b)


def _legacy_marks_on_source(source: Tree,
                            script: EditScript) -> dict[str, str]:
    """Fallback used when the cached script lacks a mapping."""
    marks: dict[str, str] = {}
    for act in script.operations:
        try:
            node = source.get(act.path) if act.op in {"delete", "relabel"} else None
        except IndexError:
            continue
        if node is None:
            continue
        key = _dotted(node)
        if act.op == "delete":
            marks[key] = "delete"
            for d in node.walk():
                if d is node:
                    continue
                marks[_dotted(d)] = "delete"
        elif act.op == "relabel" and key not in marks:
            marks[key] = "relabel"
    return marks


def _legacy_marks_on_target(target: Tree, source: Tree) -> dict[str, str]:
    """Fallback used when the cached script lacks a mapping."""
    marks: dict[str, str] = {}
    source_paths = {_dotted(n): n for n in source.walk()
                    if n is not source.root}
    for n in target.walk():
        if n is target.root:
            continue
        key = _dotted(n)
        if key not in source_paths:
            marks[key] = "insert"
            continue
        src = source_paths[key]
        if src.is_leaf and n.is_leaf and not src.value_equals(n):
            marks[key] = "relabel"
    return marks


def _dotted(node) -> str:
    """Stable dotted path with ``[i]`` disambiguation for repeated labels."""
    parts: list[str] = []
    cur = node
    while cur.parent is not None:
        sibs = [c for c in cur.parent.children if c.label == cur.label]
        if len(sibs) > 1:
            # Identity-based index — Node uses dataclass equality, so
            # structurally-identical siblings would collide via ``index``.
            idx = next(i for i, c in enumerate(sibs) if c is cur)
            parts.append(f"{cur.label}[{idx}]")
        else:
            parts.append(cur.label)
        cur = cur.parent
    return ".".join(reversed(parts))
