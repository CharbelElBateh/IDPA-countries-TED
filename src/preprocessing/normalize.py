"""Field-name normalization: alias mapping + filter-pattern drop."""

from __future__ import annotations

import re
from typing import Any


def apply_aliases(infobox: dict[str, Any],
                  aliases: dict[str, str]) -> dict[str, Any]:
    """Rename keys in ``infobox`` according to ``aliases`` (variant → canonical).

    Later values overwrite earlier ones when two variants collide; that's
    fine for our case because variants are usually mutually exclusive.
    """
    out: dict[str, Any] = {}
    for k, v in infobox.items():
        out[aliases.get(k, k)] = v
    return out


def drop_filtered(infobox: dict[str, Any],
                  filter_patterns: list[str]) -> dict[str, Any]:
    """Drop any key matching one of the regex patterns in ``filter_patterns``."""
    compiled = [re.compile(p) for p in filter_patterns]
    return {
        k: v for k, v in infobox.items()
        if not any(c.match(k) for c in compiled)
    }


def normalize_infobox(infobox: dict[str, Any],
                      aliases: dict[str, str],
                      filter_patterns: list[str]) -> dict[str, Any]:
    """Apply aliases first, then drop filtered keys."""
    return drop_filtered(apply_aliases(infobox, aliases), filter_patterns)
