"""Pipeline tools — 10 tools wrapping existing src/ functions for the LLM agent."""

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

from agent.config import RAW_DIR, CONFIG_DIR, OUTPUTS_DIR

# ── Tool JSON schemas (OpenAI function-calling format) ────────────────────────

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_available_countries",
            "description": "List all countries that have infobox data available in data/raw/. Returns country names.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_country_info",
            "description": "Load a country's infobox tree and return its fields, values, and node count. Use this to inspect what data is available for a country.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country": {
                        "type": "string",
                        "description": "Country name (e.g. 'Lebanon', 'Switzerland')",
                    },
                },
                "required": ["country"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_countries",
            "description": "Compute Tree Edit Distance between two countries. Returns TED value, 3 similarity metrics, and a summary of the edit script (op counts by type). Use this for a quick comparison.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country1": {"type": "string", "description": "First country name"},
                    "country2": {"type": "string", "description": "Second country name"},
                    "algorithm": {
                        "type": "string",
                        "enum": ["chawathe", "nierman_jagadish"],
                        "description": "TED algorithm to use (default: chawathe)",
                    },
                },
                "required": ["country1", "country2"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_edit_script_details",
            "description": "Get detailed edit operations for transforming country1's tree into country2's. Shows each insert/delete/relabel with field paths and values. Truncated to top 30 most important changes if large.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country1": {"type": "string"},
                    "country2": {"type": "string"},
                    "algorithm": {
                        "type": "string",
                        "enum": ["chawathe", "nierman_jagadish"],
                    },
                },
                "required": ["country1", "country2"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "collect_country",
            "description": "Scrape a country's infobox from Wikipedia and save as XML. Use this if a country's data is missing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country": {"type": "string", "description": "Country name to scrape"},
                },
                "required": ["country"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_field_value",
            "description": "Get the value of a specific field for a country. Returns the field's text content or child structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country": {"type": "string"},
                    "field": {"type": "string", "description": "Field name (e.g. 'capital', 'GDP_PPP', 'government_type')"},
                },
                "required": ["country", "field"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_specific_fields",
            "description": "Compare specific fields between two countries without computing full TED. Good for targeted comparisons.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country1": {"type": "string"},
                    "country2": {"type": "string"},
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of field names to compare",
                    },
                },
                "required": ["country1", "country2", "fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_semantic_similarity",
            "description": "Compute TED and categorize changes by semantic category (political, economic, demographic, etc.). Returns structural metrics and categorized changes — you then assess importance and produce a semantic similarity score.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country1": {"type": "string"},
                    "country2": {"type": "string"},
                    "algorithm": {
                        "type": "string",
                        "enum": ["chawathe", "nierman_jagadish"],
                    },
                },
                "required": ["country1", "country2"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_comparison_report",
            "description": "Generate a full markdown comparison report between two countries, including TED metrics, semantic analysis, and field-by-field breakdown. Saved to data/agent/outputs/.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country1": {"type": "string"},
                    "country2": {"type": "string"},
                },
                "required": ["country1", "country2"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_full_pipeline",
            "description": "Run the complete IDPA pipeline for two countries: TED computation (both algorithms, both directions), edit scripts, IDF diff, patching, infobox HTML, and diff report. Returns paths to all generated artifacts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country1": {"type": "string"},
                    "country2": {"type": "string"},
                },
                "required": ["country1", "country2"],
            },
        },
    },
]


# ── Tool implementations ──────────────────────────────────────────────────────

def _country_xml_path(country: str) -> Path:
    """Resolve country name to XML path, trying common filename variants."""
    name = country.strip()
    # Try exact match, then underscore-replaced
    for variant in [name, name.replace(" ", "_")]:
        p = RAW_DIR / f"{variant}.xml"
        if p.exists():
            return p
    # Case-insensitive search
    for p in RAW_DIR.glob("*.xml"):
        if p.stem.lower().replace("_", " ") == name.lower():
            return p
    return RAW_DIR / f"{name.replace(' ', '_')}.xml"


def _load_tree(country: str):
    """Load and normalize a country's tree. Returns (tree, error_str)."""
    from src.preprocessing.xml_parser import parse_xml_file
    from src.preprocessing.normalizer import normalize_tree

    path = _country_xml_path(country)
    if not path.exists():
        return None, f"No data for '{country}'. File not found: {path.name}. Use collect_country to scrape it."
    tree = parse_xml_file(path)
    normalize_tree(tree)
    return tree, None


def _load_costs() -> dict:
    """Load default cost model."""
    cost_path = CONFIG_DIR / "cost_model_default.json"
    return json.loads(cost_path.read_text(encoding="utf-8"))


def _node_text(node) -> str:
    """Get text content of a node (leaf text or children summary)."""
    if node.is_leaf():
        return node.label
    # Collect leaf text from children
    texts = []
    for child in node.children:
        if child.is_leaf():
            texts.append(child.label)
        elif child.node_type == "element":
            # Check for item children (multi-value)
            items = [gc.label for gc in child.children if gc.is_leaf()]
            if items:
                texts.append(f"{child.label}: {', '.join(items)}")
            else:
                texts.append(f"[{child.label}]")
    return "; ".join(texts) if texts else f"[{node.label} element with {len(node.children)} children]"


def _action_to_dict(action, index: int) -> dict:
    """Convert an Action to a serializable dict."""
    from agent.semantic import _get_field_name, _get_category

    field = _get_field_name(action)
    d = {
        "index": index,
        "op": action.op_type,
        "field": field,
        "category": _get_category(field),
        "node_label": action.node.label,
        "node_type": action.node.node_type,
        "cost": action.cost,
    }
    if action.op_type == "relabel":
        d["from"] = action.node.label
        d["to"] = action.args.get("new_label", "")
    return d


# ── Dispatch table ────────────────────────────────────────────────────────────

def dispatch(name: str, arguments: dict) -> str:
    """Execute a tool by name. Returns JSON string result."""
    try:
        fn = _TOOLS.get(name)
        if not fn:
            return json.dumps({"error": f"Unknown tool: {name}"})
        result = fn(**arguments)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


# ── Individual tool functions ─────────────────────────────────────────────────

def list_available_countries() -> dict:
    countries = sorted(p.stem.replace("_", " ") for p in RAW_DIR.glob("*.xml"))
    return {"count": len(countries), "countries": countries}


def get_country_info(country: str) -> dict:
    tree, err = _load_tree(country)
    if err:
        return {"error": err}

    fields = {}
    root = tree.root
    for child in root.children:
        if child.node_type == "element":
            fields[child.label] = _node_text(child)

    return {
        "country": country,
        "node_count": tree.size(),
        "field_count": len(fields),
        "fields": fields,
    }


def compare_countries(country1: str, country2: str, algorithm: str = "chawathe") -> dict:
    from src.differencing.edit_script import extract_edit_script
    from src.ted.similarity import compute_similarity

    t1, err = _load_tree(country1)
    if err:
        return {"error": err}
    t2, err = _load_tree(country2)
    if err:
        return {"error": err}

    costs = _load_costs()
    ted, script = extract_edit_script(t1, t2, costs, algorithm=algorithm)
    sim = compute_similarity(ted, t1, t2)

    # Summarize ops
    op_counts = {"insert": 0, "delete": 0, "relabel": 0}
    for action in script:
        op_counts[action.op_type] = op_counts.get(action.op_type, 0) + 1

    return {
        "country1": country1,
        "country2": country2,
        "algorithm": algorithm,
        "t1_nodes": t1.size(),
        "t2_nodes": t2.size(),
        "ted": ted,
        "similarity": sim,
        "operations": op_counts,
        "total_operations": len(script),
    }


def get_edit_script_details(country1: str, country2: str, algorithm: str = "chawathe") -> dict:
    from src.differencing.edit_script import extract_edit_script

    t1, err = _load_tree(country1)
    if err:
        return {"error": err}
    t2, err = _load_tree(country2)
    if err:
        return {"error": err}

    costs = _load_costs()
    ted, script = extract_edit_script(t1, t2, costs, algorithm=algorithm)

    # Convert all actions
    all_ops = [_action_to_dict(a, i) for i, a in enumerate(script)]

    # Truncate if large
    truncated = len(all_ops) > 30
    shown = all_ops[:30] if truncated else all_ops

    # Category summary
    cat_counts = {}
    for op in all_ops:
        cat = op["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    return {
        "country1": country1,
        "country2": country2,
        "algorithm": algorithm,
        "ted": ted,
        "total_operations": len(all_ops),
        "showing": len(shown),
        "truncated": truncated,
        "category_summary": cat_counts,
        "operations": shown,
    }


def collect_country(country: str) -> dict:
    from src.collection.scraper import scrape_country

    path = scrape_country(country)
    if path:
        return {"success": True, "country": country, "path": str(path)}
    return {"success": False, "country": country, "error": "Failed to scrape. Check country name."}


def get_field_value(country: str, field: str) -> dict:
    tree, err = _load_tree(country)
    if err:
        return {"error": err}

    root = tree.root
    for child in root.children:
        if child.label.lower() == field.lower():
            return {
                "country": country,
                "field": child.label,
                "value": _node_text(child),
                "node_type": child.node_type,
                "child_count": len(child.children),
            }

    # Try partial match
    matches = [c for c in root.children if field.lower() in c.label.lower()]
    if matches:
        return {
            "country": country,
            "field": field,
            "error": f"Exact field '{field}' not found.",
            "similar_fields": [m.label for m in matches],
        }

    return {
        "country": country,
        "field": field,
        "error": f"Field '{field}' not found.",
        "available_fields": [c.label for c in root.children if c.node_type == "element"],
    }


def compare_specific_fields(country1: str, country2: str, fields: list[str]) -> dict:
    t1, err = _load_tree(country1)
    if err:
        return {"error": err}
    t2, err = _load_tree(country2)
    if err:
        return {"error": err}

    comparisons = {}
    for field in fields:
        v1 = None
        v2 = None
        for child in t1.root.children:
            if child.label.lower() == field.lower():
                v1 = _node_text(child)
                break
        for child in t2.root.children:
            if child.label.lower() == field.lower():
                v2 = _node_text(child)
                break
        comparisons[field] = {
            "country1_value": v1 or "(not present)",
            "country2_value": v2 or "(not present)",
            "same": v1 == v2 if (v1 and v2) else None,
        }

    return {
        "country1": country1,
        "country2": country2,
        "comparisons": comparisons,
    }


def compute_semantic_similarity(country1: str, country2: str, algorithm: str = "chawathe") -> dict:
    from src.differencing.edit_script import extract_edit_script
    from src.ted.similarity import compute_similarity
    from agent.semantic import build_change_summary

    t1, err = _load_tree(country1)
    if err:
        return {"error": err}
    t2, err = _load_tree(country2)
    if err:
        return {"error": err}

    costs = _load_costs()
    ted, script = extract_edit_script(t1, t2, costs, algorithm=algorithm)
    sim = compute_similarity(ted, t1, t2)
    change_summary = build_change_summary(script, t1, t2)

    return {
        "country1": country1,
        "country2": country2,
        "algorithm": algorithm,
        "structural": {
            "ted": ted,
            **sim,
        },
        "change_summary": change_summary,
        "note": "Use the categorized changes to assess semantic importance. "
                "A government_type change is more significant than a year update — "
                "apply your judgment to weight these changes and produce a semantic similarity score (0-1).",
    }


def generate_comparison_report(country1: str, country2: str) -> dict:
    from src.differencing.edit_script import extract_edit_script
    from src.ted.similarity import compute_similarity
    from agent.semantic import build_change_summary

    t1, err = _load_tree(country1)
    if err:
        return {"error": err}
    t2, err = _load_tree(country2)
    if err:
        return {"error": err}

    costs = _load_costs()
    ted, script = extract_edit_script(t1, t2, costs, algorithm="chawathe")
    sim = compute_similarity(ted, t1, t2)
    change_summary = build_change_summary(script, t1, t2)

    # Build markdown report with structural data
    lines = [
        f"# Country Comparison: {country1} vs {country2}",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "## Structural Similarity (TED)",
        f"- **Tree Edit Distance**: {ted}",
        f"- **{country1} nodes**: {t1.size()}, **{country2} nodes**: {t2.size()}",
        f"- **Similarity (inverse)**: {sim['sim_inverse']:.4f}",
        f"- **Similarity (ratio)**: {sim['sim_ratio']:.4f}",
        "",
        f"## Edit Operations ({change_summary['total_ops']} total)",
        f"- Inserts: {change_summary['op_counts']['insert']}",
        f"- Deletes: {change_summary['op_counts']['delete']}",
        f"- Relabels: {change_summary['op_counts']['relabel']}",
        "",
        "## Changes by Category",
    ]

    for cat, info in sorted(change_summary["categories"].items(), key=lambda x: x[1]["count"], reverse=True):
        lines.append(f"\n### {cat.title()} ({info['count']} changes: {info['inserts']}ins, {info['deletes']}del, {info['relabels']}rel)")
        for change in info["changes"][:5]:
            op = change["op_type"]
            if op == "relabel":
                lines.append(f"- **{op}** `{change['field']}`: `{change.get('from_val', '')}` → `{change.get('to_val', '')}`")
            else:
                lines.append(f"- **{op}** `{change['field']}` (`{change.get('value', change['label'])}`)")
        if info["truncated"]:
            lines.append(f"- *... and {info['count'] - 10} more*")

    report = "\n".join(lines)

    # Save to file
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = f"{country1}_vs_{country2}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    out_path = OUTPUTS_DIR / slug
    out_path.write_text(report, encoding="utf-8")

    return {
        "report_path": str(out_path),
        "report_preview": report[:2000] + ("..." if len(report) > 2000 else ""),
        "note": "This report contains structural data. Use the categorized changes to add your own "
                "semantic analysis — assess which changes are most significant and assign a semantic similarity score.",
    }


def run_full_pipeline(country1: str, country2: str) -> dict:
    """Run the full pipeline via main.py's cmd_run logic."""
    import argparse
    # Import cmd_run from main
    sys_path_orig = sys.path[:]
    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    try:
        from main import cmd_run

        args = argparse.Namespace(
            country1=country1,
            country2=country2,
            algorithm="chawathe",
            strategy=None,
            costs=None,
        )
        # cmd_run prints to stdout; capture isn't easy so just run it
        cmd_run(args)

        # Find the latest run directory
        runs_dir = Path(project_root) / "data" / "runs"
        prefix = f"{country1.replace(' ', '_')}__{country2.replace(' ', '_')}__"
        run_dirs = sorted(
            [d for d in runs_dir.iterdir() if d.is_dir() and d.name.startswith(prefix)],
            key=lambda d: d.name,
            reverse=True,
        )
        if run_dirs:
            artifacts = [str(f.relative_to(project_root)) for f in run_dirs[0].iterdir()]
            return {
                "success": True,
                "run_dir": str(run_dirs[0].relative_to(project_root)),
                "artifacts": artifacts,
            }
        return {"success": True, "note": "Pipeline ran but couldn't locate output directory."}
    except Exception as e:
        return {"error": f"Pipeline failed: {e}"}
    finally:
        sys.path = sys_path_orig


# ── Registry ──────────────────────────────────────────────────────────────────

_TOOLS = {
    "list_available_countries": list_available_countries,
    "get_country_info": get_country_info,
    "compare_countries": compare_countries,
    "get_edit_script_details": get_edit_script_details,
    "collect_country": collect_country,
    "get_field_value": get_field_value,
    "compare_specific_fields": compare_specific_fields,
    "compute_semantic_similarity": compute_semantic_similarity,
    "generate_comparison_report": generate_comparison_report,
    "run_full_pipeline": run_full_pipeline,
}
