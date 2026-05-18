"""MongoDB store for country infobox documents.

Document schema (one document per country)::

    {
        "_id":         <country name, e.g. "Lebanon">,
        "name":        <country name>,
        "infobox":     {<field_name>: <wikitext_value>, ...},  # raw from wptools
        "template":    <infobox template name, e.g. "Infobox country">,
        "wikitext":    <full page wikitext, optional>,
        "source":      <provenance, e.g. "wikipedia">,
        "ingested_at": <UTC datetime>,
    }

The ``name`` is also used as ``_id`` so a country can be upserted idempotently.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Iterable

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

_DEFAULT_URI = "mongodb://localhost:27017/"
_DEFAULT_DB = "idpa"
_DEFAULT_COLLECTION = "countries"
_DEFAULT_SCRIPTS_COLLECTION = "edit_scripts"
_DEFAULT_CLUSTERS_COLLECTION = "cluster_runs"
_DEFAULT_MATRICES_COLLECTION = "distance_matrices"


class MongoStore:
    """Thin wrapper around a single Mongo collection of country documents.

    Args:
        uri: Mongo connection URI. Defaults to ``$MONGO_URI`` from the
            environment, or ``mongodb://localhost:27017/`` if unset.
        db_name: Database name. Defaults to ``$MONGO_DB_NAME`` or ``idpa``.
        collection_name: Collection name. Defaults to
            ``$MONGO_COUNTRIES_COLLECTION`` or ``countries``.
        server_selection_timeout_ms: Time to wait for a server selection
            before raising. Lower values fail fast during development.
    """

    def __init__(
        self,
        uri: str | None = None,
        db_name: str | None = None,
        collection_name: str | None = None,
        server_selection_timeout_ms: int = 5000,
    ) -> None:
        load_dotenv()

        self.uri = uri or os.getenv("MONGO_URI", _DEFAULT_URI)
        self.db_name = db_name or os.getenv("MONGO_DB_NAME", _DEFAULT_DB)
        self.collection_name = (
            collection_name
            or os.getenv("MONGO_COUNTRIES_COLLECTION", _DEFAULT_COLLECTION)
        )

        self.client: MongoClient = MongoClient(
            self.uri,
            serverSelectionTimeoutMS=server_selection_timeout_ms,
        )
        self.db: Database = self.client[self.db_name]
        self.collection: Collection = self.db[self.collection_name]
        self.scripts: Collection = self.db[
            os.getenv("MONGO_SCRIPTS_COLLECTION", _DEFAULT_SCRIPTS_COLLECTION)
        ]
        self.clusters: Collection = self.db[
            os.getenv("MONGO_CLUSTERS_COLLECTION", _DEFAULT_CLUSTERS_COLLECTION)
        ]
        self.matrices: Collection = self.db[
            os.getenv("MONGO_MATRICES_COLLECTION", _DEFAULT_MATRICES_COLLECTION)
        ]

        logger.debug(
            "MongoStore initialized (db=%s, collection=%s)",
            self.db_name,
            self.collection_name,
        )

    # ------------------------------------------------------------------ admin
    def ping(self) -> bool:
        """Return True if the server is reachable, False otherwise."""
        try:
            self.client.admin.command("ping")
            return True
        except PyMongoError as exc:
            logger.warning("MongoDB ping failed: %s", exc)
            return False

    def ensure_indexes(self) -> None:
        """Create indexes used by the application (idempotent)."""
        self.collection.create_index([("name", ASCENDING)], unique=True)
        self.collection.create_index([("ingested_at", ASCENDING)])
        # Scripts: one document per unique (c1, c2, algorithm, cost_model).
        self.scripts.create_index(
            [("country1", ASCENDING), ("country2", ASCENDING),
             ("algorithm", ASCENDING), ("cost_model", ASCENDING)],
            unique=True,
        )
        self.scripts.create_index([("computed_at", ASCENDING)])
        # Cluster runs: keyed by (algorithm, params hash); also indexed by
        # ``computed_at`` for the recents list in the UI.
        self.clusters.create_index([("computed_at", ASCENDING)])
        self.clusters.create_index([("algorithm", ASCENDING)])
        # Distance matrices: ``_id`` is the deterministic
        # ``distance_matrix_key``; one index on ``computed_at`` is enough.
        self.matrices.create_index([("computed_at", ASCENDING)])

    def drop_collection(self) -> None:
        """Drop the countries collection. Destructive — use with care."""
        self.collection.drop()
        logger.warning("Dropped collection %s.%s", self.db_name, self.collection_name)

    def close(self) -> None:
        """Close the underlying Mongo client."""
        self.client.close()

    # --------------------------------------------------------------- writes
    def upsert_country(
        self,
        name: str,
        infobox: dict[str, Any],
        template: str | None = None,
        wikitext: str | None = None,
        source: str = "wikipedia",
        extra: dict[str, Any] | None = None,
    ) -> str:
        """Insert or replace one country document.

        Args:
            name: Country name (also used as ``_id``).
            infobox: Raw dict of infobox field name → wikitext value.
            template: Name of the infobox template, e.g. ``"Infobox country"``.
            wikitext: Optional full-page wikitext (kept for reproducibility).
            source: Provenance string for the data.
            extra: Optional additional fields to merge into the document.

        Returns:
            The ``_id`` (country name) of the upserted document.
        """
        doc: dict[str, Any] = {
            "_id": name,
            "name": name,
            "infobox": infobox,
            "template": template,
            "wikitext": wikitext,
            "source": source,
            "ingested_at": datetime.now(timezone.utc),
        }
        if extra:
            doc.update(extra)
        self.collection.replace_one({"_id": name}, doc, upsert=True)
        return name

    # ---------------------------------------------------------------- reads
    def get_country(self, name: str) -> dict[str, Any] | None:
        """Return the document for ``name`` or None if not present."""
        return self.collection.find_one({"_id": name})

    def list_country_names(self) -> list[str]:
        """Return all country names currently stored, sorted alphabetically."""
        return sorted(doc["_id"] for doc in self.collection.find({}, {"_id": 1}))

    def iter_countries(
        self,
        projection: dict[str, int] | None = None,
    ) -> Iterable[dict[str, Any]]:
        """Yield all country documents (optionally with a projection)."""
        cursor = self.collection.find({}, projection)
        yield from cursor

    def count(self) -> int:
        """Return the number of country documents stored."""
        return self.collection.count_documents({})

    # =============================================================== edit scripts
    def script_key(self, country1: str, country2: str,
                   algorithm: str, cost_model: str) -> str:
        """Deterministic ``_id`` for a comparison document."""
        return f"{country1}__{country2}__{algorithm}__{cost_model}"

    def get_edit_script(self, country1: str, country2: str,
                        algorithm: str, cost_model: str
                        ) -> dict[str, Any] | None:
        """Return the cached comparison document or ``None`` if not found."""
        return self.scripts.find_one(
            {"_id": self.script_key(country1, country2, algorithm, cost_model)}
        )

    def save_edit_script(self, country1: str, country2: str,
                         algorithm: str, cost_model: str,
                         forward: dict[str, Any],
                         reverse: dict[str, Any]) -> str:
        """Insert or replace a cached comparison document."""
        key = self.script_key(country1, country2, algorithm, cost_model)
        doc = {
            "_id":         key,
            "country1":    country1,
            "country2":    country2,
            "algorithm":   algorithm,
            "cost_model":  cost_model,
            "forward":     forward,
            "reverse":     reverse,
            "computed_at": datetime.now(timezone.utc),
        }
        self.scripts.replace_one({"_id": key}, doc, upsert=True)
        return key

    def list_edit_scripts(self) -> list[dict[str, Any]]:
        """Return summary records for all cached scripts."""
        projection = {
            "country1": 1, "country2": 1, "algorithm": 1,
            "cost_model": 1, "computed_at": 1,
            "forward.total_cost": 1, "reverse.total_cost": 1,
            "forward.operations": 1, "reverse.operations": 1,
        }
        out: list[dict[str, Any]] = []
        for doc in self.scripts.find({}, projection).sort("computed_at", -1):
            out.append({
                "id":         doc["_id"],
                "country1":   doc.get("country1"),
                "country2":   doc.get("country2"),
                "algorithm":  doc.get("algorithm"),
                "cost_model": doc.get("cost_model"),
                "computed_at": doc.get("computed_at"),
                "forward_cost":  doc.get("forward", {}).get("total_cost"),
                "reverse_cost":  doc.get("reverse", {}).get("total_cost"),
                "forward_ops":   len(doc.get("forward", {}).get("operations", [])),
                "reverse_ops":   len(doc.get("reverse", {}).get("operations", [])),
            })
        return out

    def delete_edit_script(self, country1: str, country2: str,
                           algorithm: str, cost_model: str) -> int:
        """Remove one cached comparison. Returns the number of docs deleted."""
        result = self.scripts.delete_one(
            {"_id": self.script_key(country1, country2, algorithm, cost_model)}
        )
        return result.deleted_count

    # =============================================================== cluster runs
    def cluster_run_key(self, result_or_dict: Any) -> str:
        """Stable ``_id`` for a clustering result.

        Hashes ``algorithm`` plus the JSON-serialized ``params`` block so
        re-running the same configuration overwrites the previous record.
        """
        import hashlib
        import json
        if hasattr(result_or_dict, "to_dict"):
            d = result_or_dict.to_dict()
        else:
            d = result_or_dict
        payload = {
            "algorithm": d["algorithm"],
            "params": d.get("params", {}),
        }
        blob = json.dumps(payload, sort_keys=True, default=str)
        digest = hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]
        return f"{d['algorithm']}__{digest}"

    def save_cluster_run(self, result: Any) -> str:
        """Insert or replace one cluster run (``ClusterResult``)."""
        d = result.to_dict() if hasattr(result, "to_dict") else dict(result)
        key = self.cluster_run_key(d)
        doc = {
            "_id":         key,
            **d,
            "computed_at": datetime.now(timezone.utc),
        }
        self.clusters.replace_one({"_id": key}, doc, upsert=True)
        return key

    def get_cluster_run(self, key: str) -> dict[str, Any] | None:
        """Return the raw cluster-run document or ``None``."""
        return self.clusters.find_one({"_id": key})

    def list_cluster_runs(self) -> list[dict[str, Any]]:
        """Summary records for the recent-runs panel in the UI."""
        projection = {
            "algorithm": 1, "params": 1, "silhouette": 1,
            "cluster_sizes": 1, "outliers": 1, "computed_at": 1,
        }
        out: list[dict[str, Any]] = []
        for doc in self.clusters.find({}, projection).sort("computed_at", -1):
            out.append({
                "id":            doc["_id"],
                "algorithm":     doc.get("algorithm"),
                "params":        doc.get("params", {}),
                "silhouette":    doc.get("silhouette"),
                "n_clusters":    len([k for k in doc.get("cluster_sizes", {})
                                      if k != "-1"]),
                "n_outliers":    len(doc.get("outliers", {})),
                "computed_at":   doc.get("computed_at"),
            })
        return out

    def delete_cluster_run(self, key: str) -> int:
        """Remove one cluster run. Returns the number of docs deleted."""
        return self.clusters.delete_one({"_id": key}).deleted_count

    # =============================================================== distance matrices
    def save_distance_matrix(self, key: str,
                             names: list[str],
                             matrix: Any) -> str:
        """Cache a pairwise distance matrix keyed by ``key``.

        ``matrix`` is a numpy 2D array or nested list; stored as nested
        lists so Mongo's BSON can encode it directly.
        """
        if hasattr(matrix, "tolist"):
            matrix = matrix.tolist()
        doc = {
            "_id":         key,
            "names":       list(names),
            "matrix":      matrix,
            "computed_at": datetime.now(timezone.utc),
        }
        self.matrices.replace_one({"_id": key}, doc, upsert=True)
        return key

    def get_distance_matrix(self, key: str) -> dict[str, Any] | None:
        """Return the cached matrix document or ``None``."""
        return self.matrices.find_one({"_id": key})

    def delete_distance_matrix(self, key: str) -> int:
        return self.matrices.delete_one({"_id": key}).deleted_count

    # ------------------------------------------------------------- context
    def __enter__(self) -> "MongoStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
