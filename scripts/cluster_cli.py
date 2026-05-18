"""CLI driver for the clustering tool.

Examples (from PowerShell, after running ``docker compose up -d``)::

    .venv\\Scripts\\python.exe scripts\\cluster_cli.py \\
        --algorithm kmedoids --k 5 \\
        --fields demographics.religion,government.type

    .venv\\Scripts\\python.exe scripts\\cluster_cli.py \\
        --algorithm hierarchical_agglomerative --k 6 --linkage average \\
        --fields demographics.religion,economy.gdp_ppp.per_capita \\
        --weights demographics.religion=2.0,economy.gdp_ppp.per_capita=1.5

The result is printed as a table and (unless ``--no-cache``) saved to the
``cluster_runs`` MongoDB collection so the frontend can replay it.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running directly: `python scripts/cluster_cli.py ...`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.clustering import list_fields, run_clustering  # noqa: E402
from src.clustering.registry import list_algorithms  # noqa: E402
from src.config import list_cost_models  # noqa: E402

logger = logging.getLogger(__name__)


def _parse_kv_list(s: str) -> dict[str, float]:
    """Parse ``"a=1.0,b=2.5"`` → ``{"a": 1.0, "b": 2.5}``."""
    if not s:
        return {}
    out: dict[str, float] = {}
    for item in s.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"expected ``key=value`` in {item!r}")
        k, v = item.split("=", 1)
        out[k.strip()] = float(v.strip())
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--algorithm", "-a", required=True,
        choices=[a["name"] for a in list_algorithms()],
        help="Clustering algorithm.",
    )
    parser.add_argument(
        "--fields", "-f", required=True,
        help="Comma-separated dotted field paths "
             "(e.g. demographics.religion,government.type).",
    )
    parser.add_argument(
        "--weights", "-w", default="",
        help="Comma-separated path=weight pairs.",
    )
    parser.add_argument(
        "--cost-model", default="symmetric",
        choices=list_cost_models(),
    )
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument(
        "--linkage", default="average",
        choices=["average", "complete", "single"],
        help="(hierarchical_agglomerative only)",
    )
    parser.add_argument(
        "--distance-threshold", type=float, default=None,
        help="Cut the dendrogram at this distance instead of by k.",
    )
    parser.add_argument(
        "--init", default="build", choices=["build", "random"],
        help="(kmedoids only)",
    )
    parser.add_argument("--max-iter", type=int, default=100,
                        help="(kmedoids only)")
    parser.add_argument("--random-seed", type=int, default=0)
    parser.add_argument("--no-cache", action="store_true",
                        help="Don't write the run to MongoDB.")
    parser.add_argument("--list-fields", action="store_true",
                        help="List clusterable fields and exit.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list_fields:
        print(f"{'PATH':<40} {'GROUP':<15} {'KIND':<14} DEFAULT_WEIGHT")
        for f in list_fields():
            print(f"{f['path']:<40} {f['group']:<15} "
                  f"{f['kind']:<14} {f['default_weight']:.2f}")
        return 0

    fields = [p.strip() for p in args.fields.split(",") if p.strip()]
    weights = _parse_kv_list(args.weights)

    params: dict[str, object] = {}
    if args.algorithm == "kmedoids":
        params.update(k=args.k, init=args.init,
                      max_iter=args.max_iter, random_seed=args.random_seed)
    else:  # hierarchical_agglomerative
        if args.distance_threshold is not None:
            params["distance_threshold"] = args.distance_threshold
        else:
            params["k"] = args.k
        params["linkage"] = args.linkage

    result = run_clustering(
        algorithm=args.algorithm,
        field_paths=fields,
        weights=weights,
        cost_model=args.cost_model,
        params=params,
        cache=not args.no_cache,
    )

    _print_result(result)
    return 0


def _print_result(result) -> None:  # noqa: ANN001
    print()
    print("=" * 78)
    print(f"Algorithm:   {result.algorithm}")
    print(f"Params:      {result.params}")
    print(f"Clusters:    {len([k for k in result.cluster_sizes if k != '-1'])}")
    print(f"Outliers:    {len(result.outliers)}")
    print(f"Silhouette:  {result.silhouette}")
    print("=" * 78)

    by_cluster: dict[int, list[str]] = {}
    for name, c in result.labels.items():
        by_cluster.setdefault(c, []).append(name)
    for c in sorted(by_cluster):
        members = sorted(by_cluster[c])
        if c == -1:
            label = "OUTLIERS"
        else:
            medoid = (result.medoids[c]
                      if c < len(result.medoids) else "(none)")
            label = f"cluster {c}  medoid={medoid}"
        print(f"\n[{label}]  n={len(members)}")
        # Wrap the member list at ~10 names per line.
        for i in range(0, len(members), 6):
            print("   ", ", ".join(members[i:i + 6]))


if __name__ == "__main__":
    raise SystemExit(main())
