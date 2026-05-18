"""Parse a wikitext field into a distribution over a taxonomy.

A *distribution* is a ``dict[LeafPath, float]`` summing to 1.0 over the
taxonomy's leaves. When the wikitext provides explicit percentages, they
are used directly; when items are merely listed, uniform mass is assigned.

Items whose alias matches an internal-with-aliases node (e.g. a generic
"Christianity" with no specified denomination) collapse onto that node's
path — distance functions handle that correctly.

Items whose alias cannot be matched are assigned to a synthetic leaf
``("__other__",)`` with the same mass; this preserves "presence of unknown
category" without leaking into known buckets.
"""

from __future__ import annotations

import re
from typing import Any

from src.parsing.wikitext import (
    expand_lists,
    handle_templates,
    resolve_wikilinks,
    strip_comments,
    strip_html_tags,
    strip_refs,
)
from src.taxonomy import LeafPath, Taxonomy

_RE_PERCENT_TAIL = re.compile(r"(.*?)\s*\(?\s*(-?\d+(?:\.\d+)?)\s*%\s*\)?\s*$")
_RE_PERCENT_LEAD = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*%\s*[—\-:•]?\s*(.+?)\s*$")


# ----------------------------------------------------------- public API
def parse_distribution(
    raw: Any,
    taxonomy: Taxonomy,
    other_leaf: LeafPath = ("__other__",),
) -> dict[LeafPath, float]:
    """Parse one infobox value into a normalized taxonomy distribution.

    Args:
        raw: Raw wikitext value from the infobox.
        taxonomy: The taxonomy to project onto.
        other_leaf: Synthetic leaf used for unmatched items.

    Returns:
        Mapping ``LeafPath → mass`` summing to 1.0 (or empty dict if input
        is empty/unparseable).
    """
    if not raw:
        return {}
    text = _pre_clean(str(raw))
    if not text:
        return {}

    items = _split_items(text)
    if not items:
        return {}

    contributions: dict[LeafPath, float] = {}
    weighted: list[tuple[LeafPath, float]] = []
    unweighted: list[LeafPath] = []

    for label, pct in items:
        path = taxonomy.match(label) or other_leaf
        if pct is None:
            unweighted.append(path)
        else:
            weighted.append((path, pct))

    # Strategy:
    #   - If any percentages are present, use them directly and assign the
    #     remaining mass uniformly to unweighted items.
    #   - Otherwise assign uniform 1/N mass to every item.
    if weighted:
        used = sum(p for _, p in weighted)
        for path, pct in weighted:
            contributions[path] = contributions.get(path, 0.0) + pct
        remaining = max(0.0, 100.0 - used)
        if unweighted and remaining > 0:
            share = remaining / len(unweighted)
            for path in unweighted:
                contributions[path] = contributions.get(path, 0.0) + share
        elif unweighted:
            # Percentages already exceed 100 — give unweighted small share.
            share = 1.0 / max(1, len(unweighted))
            for path in unweighted:
                contributions[path] = contributions.get(path, 0.0) + share
    else:
        share = 1.0 / len(unweighted)
        for path in unweighted:
            contributions[path] = contributions.get(path, 0.0) + share

    return _normalize(contributions)


# ----------------------------------------------------------- internals
def _pre_clean(text: str) -> str:
    """Lightweight cleaning, *preserving* list structure (no trend lift)."""
    s = strip_refs(text)
    s = strip_comments(s)
    s = handle_templates(s)
    s = resolve_wikilinks(s)
    s = strip_html_tags(s)
    return s.strip()


def _split_items(text: str) -> list[tuple[str, float | None]]:
    """Split into ``(label, percent_or_None)`` items.

    Splits on newlines first, then commas if no newline structure.
    """
    items = expand_lists(text)
    if items is None:
        # Single-line: try comma split if multiple commas, else single item.
        if text.count(",") >= 1 and text.count("\n") == 0:
            items = [p.strip() for p in text.split(",") if p.strip()]
        else:
            items = [text.strip()]

    out: list[tuple[str, float | None]] = []
    for item in items:
        item = item.strip()
        if not item:
            continue
        # "Christianity (40%)" or "Christianity 40%"
        m = _RE_PERCENT_TAIL.match(item)
        if m:
            label = m.group(1).strip(" :;—-")
            try:
                pct = float(m.group(2))
            except ValueError:
                pct = None
            if label:
                out.append((label, pct))
                continue
        # "40% Christianity"
        m = _RE_PERCENT_LEAD.match(item)
        if m:
            try:
                pct = float(m.group(1))
            except ValueError:
                pct = None
            label = m.group(2).strip()
            if label:
                out.append((label, pct))
                continue
        # No percent — uniform.
        out.append((item, None))
    return out


def _normalize(dist: dict[LeafPath, float]) -> dict[LeafPath, float]:
    """Normalize a distribution to total mass 1.0."""
    total = sum(v for v in dist.values() if v > 0)
    if total <= 0:
        return {}
    return {k: v / total for k, v in dist.items() if v > 0}
