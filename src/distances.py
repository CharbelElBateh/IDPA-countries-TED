"""Per-type relabel distance functions returning values in ``[0, 1]``.

The single entry point is :func:`relabel_cost`, which dispatches on the
two nodes' types and returns a normalized cost suitable for use as the
TED relabel weight.

This module knows nothing about the TED algorithm itself; the algorithm
will call ``relabel_cost(a, b, config, taxonomies)`` for each candidate
relabel pair.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from src.core import Node
from src.taxonomy import LeafPath, TaxonomyRegistry


# =============================================================== text distance
def _levenshtein(a: str, b: str) -> int:
    """Plain iterative Levenshtein distance."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cur[j] = min(
                cur[j - 1] + 1,
                prev[j] + 1,
                prev[j - 1] + (ca != cb),
            )
        prev = cur
    return prev[-1]


def text_distance(a: str, b: str) -> float:
    """Normalized Levenshtein distance in ``[0, 1]``."""
    if not a and not b:
        return 0.0
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return 0.0
    return _levenshtein(a, b) / max(len(a), len(b))


# =============================================================== numeric distances
def number_distance(a: float, b: float, *, min_denom: float = 1e-9) -> float:
    """Relative difference, clamped to ``[0, 1]``."""
    if a == b:
        return 0.0
    denom = max(abs(a), abs(b), min_denom)
    return min(1.0, abs(a - b) / denom)


def percent_distance(a: float, b: float) -> float:
    """Absolute difference divided by 100, clamped to ``[0, 1]``."""
    return min(1.0, abs(a - b) / 100.0)


def year_distance(a: int, b: int, *, full_distance: int = 100) -> float:
    return min(1.0, abs(a - b) / full_distance)


def date_distance(a: date, b: date, *, full_distance_years: int = 100) -> float:
    days = abs((a - b).days)
    return min(1.0, days / (full_distance_years * 365.25))


def currency_distance(a: float, b: float, *, log_scale: float = 4.0) -> float:
    """Log-scaled distance — better for figures spanning many orders of magnitude.

    ``log_scale`` is the number of base-10 orders of magnitude that
    correspond to a distance of 1.0 (default 4 → 10000× ratio = 1.0).
    """
    if a == b == 0:
        return 0.0
    if a <= 0 or b <= 0:
        return number_distance(a, b)
    diff = abs(math.log10(max(a, 1e-12)) - math.log10(max(b, 1e-12)))
    return min(1.0, diff / log_scale)


def coordinates_distance(a: tuple[float, float],
                         b: tuple[float, float],
                         *, full_distance_km: float = 20000) -> float:
    """Great-circle (haversine) distance in km, normalized by ``full_distance_km``."""
    km = _haversine(a, b)
    return min(1.0, km / full_distance_km)


def _haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = (math.sin(dlat / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(h))


# =============================================================== distribution
def distribution_distance(
    a: list[dict[str, Any]] | dict[LeafPath, float],
    b: list[dict[str, Any]] | dict[LeafPath, float],
    taxonomy_name: str,
    tax: TaxonomyRegistry,
) -> float:
    """EMD between two distributions on the same taxonomy."""
    da = _dist_to_dict(a)
    db = _dist_to_dict(b)
    return tax.get(taxonomy_name).emd(da, db)


def _dist_to_dict(dist: list[dict[str, Any]] | dict[LeafPath, float]
                  ) -> dict[LeafPath, float]:
    if isinstance(dist, dict):
        return dist
    out: dict[LeafPath, float] = {}
    for rec in dist or []:
        path = tuple(rec.get("path", ()))
        out[path] = float(rec.get("weight", 0.0))
    return out


# =============================================================== dispatcher
def relabel_cost(a: Node, b: Node,
                 *,
                 config: dict[str, Any] | None = None,
                 taxonomies: TaxonomyRegistry,
                 cost_model: dict[str, Any] | None = None) -> float:
    """Relabel cost between two leaves (or two structural nodes).

    Structural-vs-structural: label equality → 0; else type_mismatch cost.
    Leaf-vs-leaf with same type: per-type distance function.
    Leaf-vs-leaf with different type: type_mismatch cost.

    Args:
        cost_model: Resolved cost-model dict (see ``src.config.resolve_cost_model``).
            If ``None``, derived from ``config["ted_costs"]`` for backwards
            compatibility with the original flat layout.
    """
    if cost_model is None:
        from src.config import resolve_cost_model
        cost_model = resolve_cost_model(None, config) if config else {}
    type_mismatch = float(cost_model.get("type_mismatch_relabel", 1.0))
    scales = cost_model.get("scales", {})

    if a.is_structural and b.is_structural:
        return 0.0 if a.label == b.label else type_mismatch

    if a.is_structural or b.is_structural:
        return type_mismatch

    # Both leaves.
    if a.type != b.type:
        return type_mismatch

    t = a.type
    if t == "number":
        return number_distance(float(a.value), float(b.value),
                               min_denom=scales.get("number_min_denom", 1e-9))
    if t == "percent":
        return percent_distance(float(a.value), float(b.value))
    if t == "year":
        return year_distance(int(a.value), int(b.value),
                             full_distance=scales.get("year_full_distance", 100))
    if t == "date":
        if not (isinstance(a.value, date) and isinstance(b.value, date)):
            return type_mismatch
        return date_distance(a.value, b.value,
                             full_distance_years=scales.get("date_full_distance_years", 100))
    if t == "currency":
        return currency_distance(float(a.value), float(b.value),
                                 log_scale=scales.get("currency_full_distance_usd_log10", 4))
    if t == "coordinates":
        return coordinates_distance(tuple(a.value), tuple(b.value),
                                    full_distance_km=scales.get("coordinates_full_distance_km", 20000))
    if t == "distribution":
        if a.taxonomy != b.taxonomy or not a.taxonomy:
            return type_mismatch
        return distribution_distance(a.value, b.value, a.taxonomy, taxonomies)
    if t in {"wikilink", "text"}:
        return text_distance(str(a.value), str(b.value))
    # Unknown type — full mismatch.
    return type_mismatch


# =============================================================== field weights
def field_weight(path: list[str], weights: dict[str, float]) -> float:
    """Resolve the multiplicative weight for a node at ``path``.

    Uses the longest matching prefix of ``weights`` keys; falls back to
    ``weights["default"]`` (or 1.0).
    """
    default = float(weights.get("default", 1.0))
    if not path:
        return default
    # Try longest-prefix match.
    best_match: str | None = None
    for key in weights:
        if key == "default":
            continue
        parts = key.split(".")
        if path[:len(parts)] == parts:
            if best_match is None or len(parts) > len(best_match.split(".")):
                best_match = key
    return float(weights[best_match]) if best_match else default
