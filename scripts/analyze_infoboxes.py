"""Analyze all infobox documents stored in MongoDB.

Reports
-------
1. Document-level stats: total countries, avg/min/max fields per country.
2. Field (key) inventory: every distinct infobox key seen, with frequency,
   coverage (% of countries that have it), and a few sample values.
3. Value-type classification: heuristic typing of each value
   (number, percent, year, date, currency, coordinates, wikilink, template,
   list, multiline, plain_text, empty), aggregated per key.
4. Per-key dominant type + type distribution.

Outputs (written under ``data/analysis/``):
- ``infobox_keys.csv``       — key, count, coverage, dominant_type, types_json
- ``infobox_values.jsonl``   — one record per (country, key) with raw value + type
- ``infobox_summary.md``     — human-readable report

Usage::

    .venv\\Scripts\\python.exe scripts\\analyze_infoboxes.py
    .venv\\Scripts\\python.exe scripts\\analyze_infoboxes.py --top 20
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.storage.mongo_store import MongoStore  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("analyze")

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "analysis"

# ---------------------------------------------------------- value-type heuristics
_RE_YEAR = re.compile(r"^\s*\d{3,4}\s*$")
_RE_NUMBER = re.compile(r"^\s*-?[\d,]+(?:\.\d+)?\s*$")
_RE_PERCENT = re.compile(r"^\s*-?[\d,]*\.?\d+\s*%\s*$")
_RE_DATE_ISO = re.compile(r"^\s*\d{4}-\d{1,2}-\d{1,2}\s*$")
_RE_DATE_DMY = re.compile(r"^\s*\d{1,2}\s+\w+\s+\d{4}\s*$")
_RE_DATE_MDY = re.compile(r"^\s*\w+\s+\d{1,2},?\s+\d{4}\s*$")
_RE_CURRENCY = re.compile(r"[$€£¥₹]|USD|EUR|GBP|JPY")
_RE_COORDS = re.compile(r"\{\{\s*coord\b", re.IGNORECASE)
_RE_TEMPLATE = re.compile(r"\{\{[^{}]+\}\}")
_RE_WIKILINK = re.compile(r"\[\[[^\[\]]+\]\]")
_RE_UNBULLETED = re.compile(r"\{\{\s*(?:unbulleted list|ubl|plainlist)",
                            re.IGNORECASE)
_RE_REF = re.compile(r"<\s*ref\b", re.IGNORECASE)


def classify_value(value: Any) -> str:
    """Return a short type label for one infobox value.

    Labels:
        empty, number, percent, year, date, currency, coordinates,
        list, template, wikilink, multiline, plain_text, non_string
    """
    if value is None:
        return "empty"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    if not isinstance(value, str):
        return "non_string"

    s = value.strip()
    if not s:
        return "empty"

    if _RE_COORDS.search(s):
        return "coordinates"
    if _RE_UNBULLETED.search(s):
        return "list"
    if "\n" in s and (s.count("\n") >= 2 or s.startswith("*")):
        return "multiline"
    if _RE_PERCENT.match(s):
        return "percent"
    if _RE_YEAR.match(s) and 1000 <= int(s) <= 2100:
        return "year"
    if _RE_NUMBER.match(s):
        return "number"
    if _RE_DATE_ISO.match(s) or _RE_DATE_DMY.match(s) or _RE_DATE_MDY.match(s):
        return "date"
    if _RE_CURRENCY.search(s):
        return "currency"
    if _RE_TEMPLATE.search(s):
        return "template"
    if _RE_WIKILINK.search(s):
        return "wikilink"
    return "plain_text"


# ---------------------------------------------------------- aggregation
def aggregate(store: MongoStore, sample_size: int = 3) -> dict[str, Any]:
    """Walk every country document and aggregate stats.

    Returns a dict with keys: ``num_countries``, ``field_counts``,
    ``field_coverage``, ``field_samples``, ``field_type_dist``,
    ``per_country_field_count``, ``value_records``.
    """
    num_countries = 0
    field_counts: Counter[str] = Counter()
    field_samples: dict[str, list[tuple[str, Any]]] = defaultdict(list)
    field_type_dist: dict[str, Counter[str]] = defaultdict(Counter)
    per_country_field_count: list[tuple[str, int]] = []
    value_records: list[dict[str, Any]] = []

    for doc in store.iter_countries(projection={"name": 1, "infobox": 1}):
        num_countries += 1
        name = doc.get("name", str(doc.get("_id")))
        infobox = doc.get("infobox") or {}
        if not isinstance(infobox, dict):
            logger.warning("%s: infobox is not a dict (%s); skipping",
                           name, type(infobox).__name__)
            continue

        per_country_field_count.append((name, len(infobox)))
        for key, value in infobox.items():
            field_counts[key] += 1
            t = classify_value(value)
            field_type_dist[key][t] += 1
            value_records.append({
                "country": name, "key": key, "type": t,
                "value": value if isinstance(value, (str, int, float, bool))
                         or value is None else repr(value),
            })
            if len(field_samples[key]) < sample_size:
                field_samples[key].append((name, value))

    field_coverage = {
        k: round(100.0 * c / num_countries, 1) if num_countries else 0.0
        for k, c in field_counts.items()
    }

    return {
        "num_countries": num_countries,
        "field_counts": field_counts,
        "field_coverage": field_coverage,
        "field_samples": field_samples,
        "field_type_dist": field_type_dist,
        "per_country_field_count": per_country_field_count,
        "value_records": value_records,
    }


def dominant_type(types: Counter[str]) -> str:
    """Return the most common type label for a field."""
    if not types:
        return "empty"
    return types.most_common(1)[0][0]


def _truncate(value: Any, width: int = 80) -> str:
    s = str(value).replace("\n", " ⏎ ")
    return s if len(s) <= width else s[: width - 1] + "…"


# ---------------------------------------------------------- output
def write_keys_csv(agg: dict[str, Any], path: Path) -> None:
    """Write one row per key: count, coverage, dominant type, full type dist."""
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["key", "count", "coverage_percent",
                    "dominant_type", "type_distribution"])
        for key, count in agg["field_counts"].most_common():
            types = agg["field_type_dist"][key]
            w.writerow([
                key, count, agg["field_coverage"][key],
                dominant_type(types),
                json.dumps(dict(types)),
            ])
    logger.info("Wrote %s", path)


def write_values_jsonl(agg: dict[str, Any], path: Path) -> None:
    """Write one JSON line per (country, key) value record."""
    with path.open("w", encoding="utf-8") as fh:
        for rec in agg["value_records"]:
            fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    logger.info("Wrote %s (%d records)", path, len(agg["value_records"]))


def write_summary_md(agg: dict[str, Any], path: Path, *, top_n: int = 30) -> None:
    """Write a human-readable Markdown summary."""
    lines: list[str] = []
    n = agg["num_countries"]
    lines.append("# Infobox Field Analysis\n")
    lines.append(f"- **Countries analyzed**: {n}")

    counts = [c for _, c in agg["per_country_field_count"]]
    if counts:
        lines.append(f"- **Fields per country**: "
                     f"min={min(counts)}, "
                     f"avg={sum(counts) / len(counts):.1f}, "
                     f"max={max(counts)}")
    lines.append(f"- **Distinct field names seen**: {len(agg['field_counts'])}\n")

    # global type distribution
    global_types: Counter[str] = Counter()
    for types in agg["field_type_dist"].values():
        global_types.update(types)
    total_values = sum(global_types.values())
    lines.append("## Value-type distribution (all key-value pairs)\n")
    lines.append("| Type | Count | % |")
    lines.append("|------|------:|--:|")
    for t, c in global_types.most_common():
        pct = 100.0 * c / total_values if total_values else 0
        lines.append(f"| `{t}` | {c} | {pct:.1f}% |")
    lines.append("")

    # top-N fields
    lines.append(f"## Top {top_n} most-common fields\n")
    lines.append("| Field | Count | Coverage | Dominant type | Sample values |")
    lines.append("|-------|------:|---------:|---------------|---------------|")
    for key, count in agg["field_counts"].most_common(top_n):
        types = agg["field_type_dist"][key]
        dom = dominant_type(types)
        samples = agg["field_samples"].get(key, [])
        sample_str = " ; ".join(
            f"_{c}_: `{_truncate(v, 60)}`" for c, v in samples
        )
        lines.append(
            f"| `{key}` | {count} | {agg['field_coverage'][key]}% | "
            f"`{dom}` | {sample_str} |"
        )
    lines.append("")

    # rare fields (coverage <= 5%)
    rare = [(k, c) for k, c in agg["field_counts"].items()
            if agg["field_coverage"][k] <= 5.0]
    rare.sort(key=lambda kv: kv[1])
    lines.append(f"## Rare fields (coverage ≤ 5%): {len(rare)}\n")
    if rare:
        lines.append("| Field | Count | Coverage | Example |")
        lines.append("|-------|------:|---------:|---------|")
        for key, count in rare[:50]:
            samples = agg["field_samples"].get(key, [])
            sample_str = (f"_{samples[0][0]}_: `{_truncate(samples[0][1], 60)}`"
                          if samples else "")
            lines.append(f"| `{key}` | {count} | "
                         f"{agg['field_coverage'][key]}% | {sample_str} |")
    lines.append("")

    # per-key type breakdown (alphabetical, all fields)
    lines.append("## Per-field type breakdown (all fields)\n")
    lines.append("| Field | Count | Coverage | Type distribution |")
    lines.append("|-------|------:|---------:|-------------------|")
    for key in sorted(agg["field_counts"]):
        count = agg["field_counts"][key]
        types = agg["field_type_dist"][key]
        type_str = ", ".join(f"`{t}`: {c}" for t, c in types.most_common())
        lines.append(f"| `{key}` | {count} | "
                     f"{agg['field_coverage'][key]}% | {type_str} |")

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote %s", path)


# ---------------------------------------------------------- main
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=30,
                        help="Top-N fields shown in the summary table.")
    parser.add_argument("--samples", type=int, default=3,
                        help="Sample values to capture per field.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR,
                        help="Directory to write CSV / JSONL / MD outputs.")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    store = MongoStore()
    if not store.ping():
        logger.error("Cannot reach MongoDB at %s.", store.uri)
        return 2

    n = store.count()
    if n == 0:
        logger.error("No country documents in %s.%s — run ingest_countries first.",
                     store.db_name, store.collection_name)
        return 3
    logger.info("Analyzing %d country documents", n)

    agg = aggregate(store, sample_size=args.samples)
    write_keys_csv(agg, args.output_dir / "infobox_keys.csv")
    write_values_jsonl(agg, args.output_dir / "infobox_values.jsonl")
    write_summary_md(agg, args.output_dir / "infobox_summary.md",
                     top_n=args.top)
    store.close()

    print(f"\nReports written to {args.output_dir}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
