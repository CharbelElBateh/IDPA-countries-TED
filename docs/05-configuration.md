# 05 · Configuration — `config/pipeline.json`

A single JSON file holds every parameter that drives the pipeline.
Loaded once via `src.config.load_config()` (cached). Comment keys
prefixed `_comment_*` are stripped after read.

## Top-level keys

```
version            "2.0"
description        free-text
field_aliases      variant → canonical key map (preprocessing)
field_filter_patterns  list of regex; matching keys are dropped
category_layout    canonical key → dotted tree path
serial_groups      rules to fold leader_title*+leader_name* into composites
field_types        explicit type hint per canonical key
field_weights      multiplier per dotted path; "default" = 1.0
subtree_similarity { enabled, move_cost_factor }
ted_costs          { default, models, scales, text_distance, list_distance }
currency_to_usd    ISO 4217 → USD rate
taxonomies         religion / language / ethnicity / government_type
```

## `subtree_similarity`

```json
{
  "enabled":          true,
  "move_cost_factor": 1.0
}
```

Read by N&J only. When `enabled`, inserting (or deleting) a subtree
that already exists in the other tree costs `base × move_cost_factor
× weight` instead of `sum of per-node costs`. Disable to fall back to
classic Selkow-style alignment.

## `ted_costs`

```json
{
  "default": "symmetric",
  "models": {
    "symmetric":  { "insert": 1.0, "delete": 1.0, "type_mismatch_relabel": 1.0, "missing_vs_present": 1.0 },
    "asymmetric": { "insert": 1.0, "delete": 2.0, "type_mismatch_relabel": 1.0, "missing_vs_present": 1.0 }
  },
  "scales": {
    "number_min_denom":              1e-9,
    "year_full_distance":            100,
    "date_full_distance_years":      100,
    "coordinates_full_distance_km":  20000,
    "currency_full_distance_usd_log10": 4
  },
  "text_distance": "normalized_levenshtein",
  "list_distance": "emd"
}
```

`src.config.resolve_cost_model(name)` returns the merged dict for one
model — base costs plus the shared `scales`, `text_distance`,
`list_distance`. `list_algorithms()` (in `src.ted`) and
`list_cost_models()` (in `src.config`) drive the dropdowns in the
Compare form.

`scales` parameters tune the per-type relabel distances; see
[04-algorithms.md](04-algorithms.md) for what each scale means.

## `category_layout` (excerpt)

```json
"conventional_long_name":   "identity.long_name",
"capital":                  "geography.capital",
"area_km2":                 "geography.area.km2",
"GDP_PPP":                  "economy.gdp_ppp.value",
"GDP_PPP_year":             "economy.gdp_ppp.year",
"GDP_PPP_per_capita":       "economy.gdp_ppp.per_capita",
"religion":                 "demographics.religion",
"@leaders":                 "government.leaders",
"@established":             "history.established"
```

A leading `@` is the convention for synthetic keys produced by
`serial_groups`. The builder creates the intermediate structural nodes
(e.g. `geography`, then `area`) on demand.

## `field_types` (excerpt)

```json
"area_km2":                "number",
"percent_water":           "percent",
"GDP_PPP":                 "currency",
"GDP_PPP_year":            "year",
"established_date1":       "date",
"coordinates":             "coordinates",
"religion":                "distribution:religion",
"ethnic_groups":           "distribution:ethnicity",
"official_languages":      "distribution:language",
"government_type":         "wikilink",
"capital":                 "wikilink",
"national_motto":          "text"
```

Distribution types are prefixed `distribution:<taxonomy_name>` so the
builder knows which taxonomy to project onto.

## `field_weights` (excerpt)

```json
"default":                   1.0,
"geography.capital":         2.0,
"government.type":           2.5,
"government.leaders":        1.0,
"economy.gdp_ppp":           1.8,
"economy.hdi":               1.5,
"demographics.religion":     1.8,
"codes":                     0.3,
"identity.long_name":        0.5
```

Resolved via longest-prefix match in `src.distances.field_weight`.
"Codes" weights are small so cctld differences are barely noticed;
core identity / politics / economy fields get the highest weights.

## `currency_to_usd`

Approximate mid-decade rates (the project's "now" is 2026). Lebanon's
pound is `0.000011 USD/LBP` etc. Replace with a live source if
exactness matters.

## `taxonomies`

Four hand-curated category trees, each shaped like:

```json
"religion": {
  "tree": {
    "Abrahamic": {
      "Christianity": {
        "Catholic":  {"aliases": ["catholic", "roman catholic"]},
        ...
      },
      "Islam": {
        "Sunni": {"aliases": ["sunni"]},
        "Shia":  {"aliases": ["shia", "shiite", "twelver", "alawite"]},
        ...
      }
    },
    "Irreligious": { "None": {"aliases": ["none", "irreligious"]} }
  }
}
```

Each leaf — and internal node with explicit `aliases` — is matchable
against wikitext via `Taxonomy.match(text)` (longest-alias-wins
substring match). The four taxonomies are: `religion`, `language`,
`ethnicity`, `government_type`.

### Distance & EMD

`Taxonomy.ground_distance(leaf_a, leaf_b)` is the **normalized
tree-edge distance**: `path_length(a,b) / diameter`. Two siblings
under the same parent are close; leaves in different top-level
branches are far.

`Taxonomy.emd(dist1, dist2)` is the **Earth Mover's Distance** with
the tree-edge ground metric, computed using the closed-form
sum-over-edges formula (`|F1(e) − F2(e)|` for each edge `e`,
normalized by diameter). Symmetric, in `[0, 1]`, and order-independent
on the leaves.
