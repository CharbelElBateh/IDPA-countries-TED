"""Fold serial numbered fields (``leader_title1``+``leader_name1``, …) into
composite groups.

Each rule in the config's ``serial_groups`` table looks like::

    {
        "patterns": {"title": "^leader_title(\\d+)$",
                     "name":  "^leader_name(\\d+)$"},
        "child_label": "leader",
        "index_key": "index"
    }

After folding, the input dict gains a key named like the rule
(``"@leaders"``) whose value is a list of per-index dicts. The matched
original keys are removed.
"""

from __future__ import annotations

import re
from typing import Any


def apply_serial_groups(infobox: dict[str, Any],
                        rules: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Apply every serial-group rule. Returns a new dict; input is unmodified."""
    out = dict(infobox)
    for group_id, rule in rules.items():
        out = _apply_one(out, group_id, rule)
    return out


def _apply_one(infobox: dict[str, Any], group_id: str,
               rule: dict[str, Any]) -> dict[str, Any]:
    patterns: dict[str, re.Pattern] = {
        slot: re.compile(pat) for slot, pat in rule["patterns"].items()
    }
    index_key = rule.get("index_key", "index")
    items: dict[int, dict[str, Any]] = {}
    consumed: set[str] = set()

    for field, value in infobox.items():
        for slot, pat in patterns.items():
            m = pat.match(field)
            if m:
                idx = int(m.group(1))
                items.setdefault(idx, {})[slot] = value
                consumed.add(field)
                break

    if not items:
        return infobox

    out = {k: v for k, v in infobox.items() if k not in consumed}
    out[group_id] = [
        {index_key: idx, **items[idx]}
        for idx in sorted(items.keys())
    ]
    return out
