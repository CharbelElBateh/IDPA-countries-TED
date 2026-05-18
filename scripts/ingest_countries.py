"""Ingest Wikipedia country infoboxes into MongoDB using wptools.

Reads a list of country names from ``src/un_member_states.txt`` (one per
line), fetches each Wikipedia page via the ``wptools`` library, extracts
the infobox as a raw dict of wikitext values, and upserts one document
per country into Mongo (collection ``countries`` by default).

Usage::

    .venv\\Scripts\\python.exe scripts\\ingest_countries.py
    .venv\\Scripts\\python.exe scripts\\ingest_countries.py --limit 5
    .venv\\Scripts\\python.exe scripts\\ingest_countries.py --skip-existing
    .venv\\Scripts\\python.exe scripts\\ingest_countries.py --country Lebanon

Run ``docker compose up -d`` first so Mongo is reachable.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Make ``src`` importable when running as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.storage.mongo_store import MongoStore  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest")

COUNTRY_LIST_PATH = Path(__file__).resolve().parents[1] / "src" / "un_member_states.txt"


def load_country_list(path: Path = COUNTRY_LIST_PATH) -> list[str]:
    """Load country names (one per line) from ``path``."""
    raw = path.read_text(encoding="utf-8-sig").splitlines()
    names = [line.strip().lstrip("﻿") for line in raw if line.strip()]
    logger.info("Loaded %d country names from %s", len(names), path)
    return names


def fetch_infobox(name: str) -> dict:
    """Fetch one country's infobox via wptools.

    Returns a dict with keys: ``infobox`` (dict | None),
    ``template`` (str | None), ``wikitext`` (str | None).

    Raises:
        RuntimeError: on wptools failure or missing data.
    """
    import wptools

    page = wptools.page(name, silent=True)
    page.get_parse()
    data = page.data or {}

    infobox = data.get("infobox")
    if not infobox:
        raise RuntimeError(f"No infobox found for {name!r}")

    # Detect infobox template name from raw wikitext, if present.
    template = None
    wikitext = data.get("wikitext")
    if wikitext:
        head = wikitext[:500].lower()
        for candidate in ("infobox country", "infobox sovereign state",
                          "infobox former country"):
            if "{{" + candidate in head:
                template = candidate.title().replace("Infobox", "Infobox")
                break

    return {
        "infobox": infobox,
        "template": template or "Infobox country",
        "wikitext": wikitext,
    }


def ingest(
    countries: list[str],
    store: MongoStore,
    *,
    skip_existing: bool = False,
    sleep_seconds: float = 0.0,
) -> tuple[int, int, list[str]]:
    """Fetch + upsert each country. Returns (success, skipped, failures)."""
    existing = set(store.list_country_names()) if skip_existing else set()
    success = 0
    skipped = 0
    failures: list[str] = []

    for i, name in enumerate(countries, 1):
        if skip_existing and name in existing:
            logger.info("[%3d/%3d] %s — already in Mongo, skipping",
                        i, len(countries), name)
            skipped += 1
            continue

        try:
            logger.info("[%3d/%3d] %s — fetching", i, len(countries), name)
            result = fetch_infobox(name)
            store.upsert_country(
                name=name,
                infobox=result["infobox"],
                template=result["template"],
                wikitext=result["wikitext"],
            )
            success += 1
            logger.info("[%3d/%3d] %s — stored (%d fields)",
                        i, len(countries), name, len(result["infobox"]))
        except Exception as exc:  # noqa: BLE001 — wptools raises a variety
            logger.error("[%3d/%3d] %s — FAILED: %s",
                         i, len(countries), name, exc)
            failures.append(name)

        if sleep_seconds:
            time.sleep(sleep_seconds)

    return success, skipped, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--country", action="append", default=None,
        help="Ingest only the named country (repeatable). "
             "If omitted, ingests all from un_member_states.txt.",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only ingest the first N countries (after country list load).",
    )
    parser.add_argument(
        "--skip-existing", action="store_true",
        help="Skip countries already present in Mongo.",
    )
    parser.add_argument(
        "--sleep", type=float, default=0.0,
        help="Seconds to sleep between requests (be nice to Wikipedia).",
    )
    parser.add_argument(
        "--list-path", type=Path, default=COUNTRY_LIST_PATH,
        help="Path to country list file.",
    )
    args = parser.parse_args()

    countries = args.country or load_country_list(args.list_path)
    if args.limit:
        countries = countries[: args.limit]

    store = MongoStore()
    if not store.ping():
        logger.error("Cannot reach MongoDB at %s. Is the container running?",
                     store.uri)
        return 2
    store.ensure_indexes()

    logger.info("Ingesting %d countries into %s.%s",
                len(countries), store.db_name, store.collection_name)
    t0 = time.time()
    success, skipped, failures = ingest(
        countries, store,
        skip_existing=args.skip_existing,
        sleep_seconds=args.sleep,
    )
    elapsed = time.time() - t0

    logger.info("=" * 60)
    logger.info("Done in %.1fs. success=%d skipped=%d failed=%d",
                elapsed, success, skipped, len(failures))
    if failures:
        logger.warning("Failed countries: %s", ", ".join(failures))
    store.close()
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
