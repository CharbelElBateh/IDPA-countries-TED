"""Flask app: browse country infobox trees stored in MongoDB.

Currently has one tab — ``Countries`` — with a list view and a detail
view that renders the parsed country tree.

Run::

    .venv\\Scripts\\python.exe -m frontend.app
    .venv\\Scripts\\python.exe -m frontend.app --port 5050
"""

from __future__ import annotations

import argparse
import logging
from functools import lru_cache
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request

from frontend.formatting import tree_to_dict
from src.builder import build_country_tree
from src.clustering import (
    fields_grouped as cluster_fields_grouped,
    run_clustering,
)
from src.clustering.registry import list_algorithms as list_cluster_algorithms
from src.comparison import compare
from src.config import list_cost_models, load_config
from src.core import EditScript
from src.storage.mongo_store import MongoStore
from src.taxonomy import load_registry
from src.ted import list_algorithms

logger = logging.getLogger(__name__)

TEMPLATES = Path(__file__).parent / "templates"
STATIC = Path(__file__).parent / "static"


# =============================================================== caches
@lru_cache(maxsize=256)
def _cached_country_tree(name: str):
    """Cache built trees in-process so re-views are instant."""
    store = MongoStore()
    doc = store.get_country(name)
    if doc is None:
        return None
    # Synthetic trees: reconstruct directly, skip the infobox pipeline.
    if doc.get("source") == "synthetic" and doc.get("tree_dict"):
        from src.core import Tree
        from src.synthetic_tree import node_from_dict
        return Tree(node_from_dict(doc["tree_dict"]), name=name)
    cfg = load_config()
    taxonomies = load_registry()
    return build_country_tree(name, doc["infobox"],
                              config=cfg, taxonomies=taxonomies)


def clear_caches() -> None:
    _cached_country_tree.cache_clear()


# =============================================================== app
def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(TEMPLATES),
        static_folder=str(STATIC),
    )

    # ----------------------------------------------------- home
    @app.route("/")
    def index():
        countries = _list_countries()
        return render_template("countries_list.html",
                               active_tab="countries",
                               countries=countries,
                               iso_codes=_iso_codes(),
                               total_count=len(countries))

    # ----------------------------------------------------- countries
    @app.route("/countries")
    def countries_list():
        q = request.args.get("q", "").strip().lower()
        countries = _list_countries()
        if q:
            countries = [c for c in countries if q in c.lower()]
        return render_template("countries_list.html",
                               active_tab="countries",
                               countries=countries,
                               iso_codes=_iso_codes(),
                               total_count=len(_list_countries()),
                               query=q)

    @app.route("/countries/<name>")
    def country_detail(name: str):
        tree = _cached_country_tree(name)
        if tree is None:
            abort(404, description=f"No country named {name!r} in MongoDB")

        # TOC entries: one per top-level structural child.
        toc = [
            {
                "label": child.label,
                "count": sum(1 for n in child.walk() if n.is_leaf),
            }
            for child in tree.root.children
            if child.is_structural
        ]

        # Type composition for the side panel.
        type_counts: dict[str, int] = {}
        for n in tree.walk():
            if n.is_leaf and n.type:
                type_counts[n.type] = type_counts.get(n.type, 0) + 1
        type_composition = sorted(
            type_counts.items(), key=lambda kv: kv[1], reverse=True
        )

        return render_template(
            "country_detail.html",
            active_tab="countries",
            country=name,
            iso=_iso_codes().get(name, "—"),
            size=tree.size(),
            height=tree.height(),
            toc=toc,
            type_composition=type_composition,
        )

    # ----------------------------------------------------- API
    @app.route("/api/countries")
    def api_countries_list():
        return jsonify(_list_countries())

    @app.route("/api/trees", methods=["POST"])
    def api_trees_add():
        """Add a hand-crafted test tree (bracket notation) to MongoDB.

        Body: ``{"name": "<id>", "bracket": "root(a, b(c, d), e)"}``.
        Stored alongside countries with ``source="synthetic"`` so the
        existing /compare flow picks it up automatically.
        """
        from frontend.formatting import tree_to_dict
        from src.synthetic_tree import parse_bracket_tree

        payload = request.get_json(force=True, silent=True) or {}
        name = (payload.get("name") or "").strip()
        bracket = (payload.get("bracket") or "").strip()
        if not name:
            return jsonify({"error": "name is required"}), 400
        if not bracket:
            return jsonify({"error": "bracket is required"}), 400

        try:
            tree = parse_bracket_tree(bracket, name=name)
        except ValueError as exc:
            return jsonify({"error": f"parse error: {exc}",
                            "name": name}), 400

        store = MongoStore()
        if not store.ping():
            return jsonify({"error": "MongoDB unreachable"}), 503

        existing = store.get_country(name) is not None
        store.ensure_indexes()
        store.upsert_country(
            name=name,
            infobox={},
            template=None,
            wikitext=bracket,
            source="synthetic",
            extra={"tree_dict": tree_to_dict(tree.root)},
        )
        clear_caches()
        return jsonify({
            "name":    name,
            "nodes":   tree.size(),
            "height":  tree.height(),
            "updated": existing,
        })

    @app.route("/api/countries/<name>", methods=["DELETE"])
    def api_countries_delete(name: str):
        """Remove a country/tree document from Mongo (useful while testing)."""
        store = MongoStore()
        deleted = store.collection.delete_one({"_id": name}).deleted_count
        clear_caches()
        return jsonify({"deleted": int(deleted), "name": name})

    @app.route("/api/countries/<name>")
    def api_country_doc(name: str):
        store = MongoStore()
        doc = store.get_country(name)
        if doc is None:
            abort(404)
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        if "ingested_at" in doc:
            doc["ingested_at"] = doc["ingested_at"].isoformat()
        return jsonify(doc)

    @app.route("/api/countries/<name>/tree")
    def api_country_tree(name: str):
        tree = _cached_country_tree(name)
        if tree is None:
            abort(404)
        return jsonify({
            "name": tree.name,
            "size": tree.size(),
            "height": tree.height(),
            "root": tree_to_dict(tree.root),
        })

    # ===================================================== compare
    @app.route("/compare")
    def compare_form():
        return render_template(
            "compare_form.html",
            active_tab="compare",
            countries=_list_countries(),
            algorithms=list_algorithms(),
            cost_models=list_cost_models(),
            cached=_cached_comparisons(),
            preset={
                "c1": request.args.get("c1", ""),
                "c2": request.args.get("c2", ""),
                "algorithm": request.args.get("algorithm", "naive"),
                "cost_model": request.args.get("cost_model", "symmetric"),
            },
        )

    @app.route("/compare/<c1>/<c2>")
    def compare_result(c1: str, c2: str):
        algorithm = request.args.get("algorithm", "naive")
        cost_model = request.args.get("cost_model", "symmetric")
        try:
            result = compare(c1, c2, algorithm=algorithm,
                             cost_model=cost_model)
        except NotImplementedError as exc:
            return render_template("error.html",
                                   active_tab="compare",
                                   code=501,
                                   message=str(exc)), 501
        except KeyError as exc:
            msg = str(exc)
            # Only treat "country missing in Mongo" as a real 404. Any
            # other KeyError (a dict lookup inside an algorithm, a path
            # mismatch in mark-extraction, etc.) is a true server bug —
            # log the traceback and surface it as 500 so we can diagnose
            # instead of hiding behind a generic 404.
            if "No country" not in msg:
                logger.exception(
                    "compare(%s, %s, algo=%s, cm=%s) raised KeyError; "
                    "treating as 500", c1, c2, algorithm, cost_model)
                return render_template("error.html",
                                       active_tab="compare",
                                       code=500,
                                       message=f"KeyError {msg} — see server log"), 500
            return render_template("error.html",
                                   active_tab="compare",
                                   code=404,
                                   message=msg), 404
        return render_template(
            "compare_result.html",
            active_tab="compare",
            country1=c1, country2=c2,
            algorithm=algorithm,
            cost_model=cost_model,
            forward_cost=result.forward.script.total_cost,
            reverse_cost=result.reverse.script.total_cost,
            forward_ops=result.forward.script.counts_by_op(),
            reverse_ops=result.reverse.script.counts_by_op(),
            forward_metrics=result.forward.metrics,
            reverse_metrics=result.reverse.metrics,
            from_cache=result.from_cache,
        )

    @app.route("/api/algorithms")
    def api_algorithms():
        return jsonify(list_algorithms())

    @app.route("/api/cost-models")
    def api_cost_models():
        return jsonify(list_cost_models())

    @app.route("/api/compare/<c1>/<c2>")
    def api_compare(c1: str, c2: str):
        algorithm = request.args.get("algorithm", "naive")
        cost_model = request.args.get("cost_model", "symmetric")
        try:
            result = compare(c1, c2, algorithm=algorithm,
                             cost_model=cost_model)
        except NotImplementedError as exc:
            return jsonify({"error": str(exc),
                            "algorithm": algorithm}), 501
        except KeyError as exc:
            return jsonify({"error": str(exc)}), 404
        return jsonify(result.to_dict())

    @app.route("/api/scripts")
    def api_scripts_list():
        return jsonify(_cached_comparisons())

    # ===================================================== patch
    @app.route("/patch", methods=["GET"])
    def patch_form():
        return render_template(
            "patch_form.html",
            active_tab="patch",
            countries=_list_countries(),
            cached=_cached_comparisons(),
        )

    @app.route("/api/patch", methods=["POST"])
    def api_patch():
        payload = request.get_json(force=True, silent=True) or {}
        country = payload.get("country")
        script_payload = payload.get("script")
        if not country:
            return jsonify({"error": "country is required"}), 400
        if not script_payload:
            return jsonify({"error": "script is required"}), 400
        tree = _cached_country_tree(country)
        if tree is None:
            return jsonify({"error": f"unknown country {country!r}"}), 404
        try:
            script = EditScript.from_dict(script_payload)
            patched = script.apply(tree)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": f"apply failed: {exc}"}), 400
        return jsonify({
            "country":   country,
            "source":    tree_to_dict(tree.root),
            "patched":   tree_to_dict(patched.root),
            "size":      patched.size(),
            "ops":       script.counts_by_op(),
            "cost":      script.total_cost,
        })

    @app.route("/api/scripts/<script_id>")
    def api_get_script(script_id: str):
        store = MongoStore()
        doc = store.scripts.find_one({"_id": script_id})
        if doc is None:
            return jsonify({"error": "not found"}), 404
        if "computed_at" in doc:
            doc["computed_at"] = doc["computed_at"].isoformat()
        return jsonify(doc)

    # ===================================================== cluster
    @app.route("/cluster", methods=["GET"])
    def cluster_form():
        return render_template(
            "cluster_form.html",
            active_tab="cluster",
            algorithms=list_cluster_algorithms(),
            cost_models=list_cost_models(),
            fields_grouped=cluster_fields_grouped(),
            cached=_cached_cluster_runs(),
        )

    @app.route("/cluster/<run_id>", methods=["GET"])
    def cluster_result(run_id: str):
        store = MongoStore()
        doc = store.get_cluster_run(run_id)
        if doc is None:
            abort(404, description=f"No cluster run {run_id!r}")
        return render_template(
            "cluster_result.html",
            active_tab="cluster",
            run_id=run_id,
            algorithm=doc.get("algorithm"),
            params=doc.get("params", {}),
            silhouette=doc.get("silhouette"),
            n_clusters=len([k for k in doc.get("cluster_sizes", {}) if k != "-1"]),
            n_outliers=len(doc.get("outliers", {})),
        )

    @app.route("/api/cluster/fields")
    def api_cluster_fields():
        return jsonify(cluster_fields_grouped())

    @app.route("/api/cluster/algorithms")
    def api_cluster_algorithms():
        return jsonify(list_cluster_algorithms())

    @app.route("/api/cluster/runs")
    def api_cluster_runs_list():
        return jsonify(_cached_cluster_runs())

    @app.route("/api/cluster/runs/<run_id>")
    def api_cluster_run_get(run_id: str):
        store = MongoStore()
        doc = store.get_cluster_run(run_id)
        if doc is None:
            return jsonify({"error": "not found"}), 404
        if "computed_at" in doc and doc["computed_at"] is not None:
            doc["computed_at"] = doc["computed_at"].isoformat()
        return jsonify(doc)

    @app.route("/api/cluster/runs/<run_id>", methods=["DELETE"])
    def api_cluster_run_delete(run_id: str):
        store = MongoStore()
        deleted = store.delete_cluster_run(run_id)
        return jsonify({"deleted": deleted})

    @app.route("/api/cluster/run", methods=["POST"])
    def api_cluster_run():
        payload = request.get_json(force=True, silent=True) or {}
        algorithm = payload.get("algorithm")
        fields = payload.get("fields") or []
        weights = payload.get("weights") or {}
        cost_model = payload.get("cost_model", "symmetric")
        params = payload.get("params") or {}

        if not algorithm:
            return jsonify({"error": "algorithm is required"}), 400
        if not fields:
            return jsonify({"error": "at least one field is required"}), 400

        try:
            result = run_clustering(
                algorithm=algorithm,
                field_paths=fields,
                weights={k: float(v) for k, v in weights.items()},
                cost_model=cost_model,
                params=params,
                cache=True,
            )
        except (KeyError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001
            logger.exception("Clustering failed")
            return jsonify({"error": f"clustering failed: {exc}"}), 500

        d = result.to_dict()
        store = MongoStore()
        d["id"] = store.cluster_run_key(d)
        return jsonify(d)

    @app.route("/api/cluster/iso-codes")
    def api_iso_codes():
        """Mapping from country name → ISO-3 code for the world-map viz."""
        path = Path(__file__).resolve().parents[1] / "data" / "country_iso_codes.json"
        return _send_json_file(path)

    @app.route("/api/cluster/numeric-codes")
    def api_numeric_codes():
        """Mapping from country name → ISO-3166 numeric code (string).

        The world-atlas TopoJSON we render in ``cluster_map.js`` keys its
        features by numeric ISO; this endpoint reverses that lookup so
        each country tile can be colored by its cluster.
        """
        path = Path(__file__).resolve().parents[1] / "data" / "country_numeric_codes.json"
        return _send_json_file(path)

    # ----------------------------------------------------- errors
    @app.errorhandler(404)
    def not_found(err):
        return render_template("error.html",
                               active_tab="countries",
                               code=404,
                               message=str(err.description)), 404

    return app


# =============================================================== helpers
def _list_countries() -> list[str]:
    """Cached fetch of country names from Mongo."""
    store = MongoStore()
    return store.list_country_names()


@lru_cache(maxsize=1)
def _iso_codes() -> dict[str, str]:
    """Static {country_name: ISO-3} map for navbar/grid badges."""
    import json
    path = Path(__file__).resolve().parents[1] / "data" / "country_iso_codes.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _cached_comparisons() -> list[dict]:
    """List previously computed comparisons (summary only)."""
    store = MongoStore()
    out = []
    for row in store.list_edit_scripts():
        if row.get("computed_at"):
            row["computed_at"] = row["computed_at"].isoformat()
        out.append(row)
    return out


def _cached_cluster_runs() -> list[dict]:
    """List previously computed cluster runs (summary only)."""
    store = MongoStore()
    out = []
    for row in store.list_cluster_runs():
        if row.get("computed_at"):
            row["computed_at"] = row["computed_at"].isoformat()
        out.append(row)
    return out


def _send_json_file(path: Path):
    """Send a JSON file from disk with the correct mimetype.

    If the file is missing, return an empty JSON object with 200 rather
    than letting ``FileNotFoundError`` bubble into a 500 HTML page — a
    missing optional dataset (e.g. ``data/country_*_codes.json``) must
    degrade gracefully, never crash the page that fetches it.
    """
    from flask import Response
    try:
        body = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("JSON file not found: %s — serving '{}'. "
                        "Run scripts/build_country_codes.py.", path)
        body = "{}"
    return Response(body, mimetype="application/json")


# =============================================================== main
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
        datefmt="%H:%M:%S",
    )

    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
