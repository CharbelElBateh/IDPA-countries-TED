"""Single entry point for loading ``config/pipeline.json``."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "pipeline.json"


@lru_cache(maxsize=1)
def load_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    """Load and cache the pipeline config. Comment keys (``_comment_*``) are dropped."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_comment")}


def reload_config() -> dict[str, Any]:
    """Clear the cache and reload the config (useful in dev)."""
    load_config.cache_clear()
    return load_config()


# =============================================================== TED cost helpers
def list_cost_models(cfg: dict[str, Any] | None = None) -> list[str]:
    """Return the names of all configured TED cost models."""
    cfg = cfg or load_config()
    return list(cfg.get("ted_costs", {}).get("models", {}).keys())


def resolve_cost_model(name: str | None,
                      cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return one merged TED cost dict.

    Merges the model's base costs (insert/delete/type_mismatch_relabel/…)
    with the shared ``scales``, ``text_distance`` and ``list_distance`` keys
    so callers see one flat dict.
    """
    cfg = cfg or load_config()
    ted = cfg.get("ted_costs", {})
    models = ted.get("models", {})
    name = name or ted.get("default") or next(iter(models), None)
    if name not in models:
        raise KeyError(f"Unknown cost model {name!r}. "
                       f"Available: {list(models)}")
    merged: dict[str, Any] = {
        "scales":         ted.get("scales", {}),
        "text_distance":  ted.get("text_distance"),
        "list_distance":  ted.get("list_distance"),
    }
    merged.update(models[name])
    merged["name"] = name
    return merged
