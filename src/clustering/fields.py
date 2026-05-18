"""Curated list of clusterable fields with a category grouping.

Derived from ``config.category_layout`` — each entry is a dotted leaf
path that ``Tree.find_by_label`` can resolve. The frontend renders this
as a grouped multi-select; the user picks one or more.

Distribution fields (religion / languages / ethnic_groups) use the EMD
ground-distance and behave very differently from text fields, so we
flag them in ``meta`` for the UI to call out.
"""

from __future__ import annotations

from typing import Any

# (path, label, kind, default_weight)
#   kind ∈ {"text", "wikilink", "number", "currency", "year", "percent",
#           "coordinates", "distribution", "date"}
_FIELDS: list[tuple[str, str, str, str, float]] = [
    # ─────────────────── Identity
    ("identity.long_name",       "Official long name",   "Identity", "text",        0.5),
    ("identity.common_name",     "Common name",          "Identity", "text",        0.5),
    ("identity.demonym",         "Demonym",              "Identity", "wikilink",    0.5),
    ("identity.motto",           "National motto",       "Identity", "text",        0.3),
    ("identity.anthem",          "National anthem",      "Identity", "text",        0.3),
    # ─────────────────── Geography
    ("geography.capital",        "Capital",              "Geography", "wikilink",   2.0),
    ("geography.largest_city",   "Largest city",         "Geography", "text",       1.0),
    ("geography.coordinates",    "Coordinates (haversine)", "Geography", "coordinates", 1.0),
    ("geography.area.km2",       "Area (km²)",           "Geography", "number",     1.5),
    ("geography.area.water_pct", "Area: % water",        "Geography", "percent",    0.5),
    ("geography.timezone",       "Timezone",             "Geography", "wikilink",   0.3),
    ("geography.drives_on",      "Drives on",            "Geography", "text",       0.3),
    # ─────────────────── Government
    ("government.type",          "Government type",      "Government", "wikilink",  2.5),
    ("government.legislature",   "Legislature",          "Government", "wikilink",  1.0),
    # ─────────────────── Economy
    ("economy.gdp_ppp.value",        "GDP PPP",          "Economy", "currency",     1.8),
    ("economy.gdp_ppp.per_capita",   "GDP PPP per capita", "Economy", "currency",   1.8),
    ("economy.gdp_nominal.value",    "GDP nominal",      "Economy", "currency",     1.5),
    ("economy.gdp_nominal.per_capita", "GDP nominal per capita", "Economy", "currency", 1.5),
    ("economy.gini.value",       "Gini",                 "Economy", "number",       1.2),
    ("economy.hdi.value",        "HDI",                  "Economy", "number",       1.5),
    ("economy.currency",         "Currency",             "Economy", "wikilink",     0.5),
    # ─────────────────── Demographics
    ("demographics.population.estimate", "Population (estimate)", "Demographics", "number", 1.5),
    ("demographics.population.density",  "Population density",    "Demographics", "number", 1.0),
    ("demographics.religion",    "Religion (EMD)",       "Demographics", "distribution", 1.8),
    ("demographics.languages",   "Languages (EMD)",      "Demographics", "distribution", 1.5),
    ("demographics.ethnic_groups", "Ethnic groups (EMD)", "Demographics", "distribution", 1.5),
    # ─────────────────── Codes (low default weight — superficial)
    ("codes.iso3166",            "ISO-3166 code",        "Codes", "text",           0.3),
    ("codes.cctld",              "ccTLD",                "Codes", "wikilink",       0.3),
    ("codes.calling_code",       "Calling code",         "Codes", "wikilink",       0.3),
]


def list_fields() -> list[dict[str, Any]]:
    """Return all clusterable fields as ``{path, label, group, kind, default_weight}``."""
    return [
        {
            "path": path,
            "label": label,
            "group": group,
            "kind": kind,
            "default_weight": default_weight,
        }
        for (path, label, group, kind, default_weight) in _FIELDS
    ]


def fields_grouped() -> dict[str, list[dict[str, Any]]]:
    """Same as ``list_fields`` but pre-grouped by category for the UI."""
    out: dict[str, list[dict[str, Any]]] = {}
    for entry in list_fields():
        out.setdefault(entry["group"], []).append(entry)
    return out


def default_weights() -> dict[str, float]:
    """Convenience: ``{path: default_weight}`` for the CLI's default run."""
    return {path: dw for (path, _, _, _, dw) in _FIELDS}


def field_paths() -> list[str]:
    """All clusterable paths, in declaration order."""
    return [path for (path, _, _, _, _) in _FIELDS]
