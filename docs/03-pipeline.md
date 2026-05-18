# 03 · Pipeline

How a raw Mongo document becomes a typed, structurally-grouped `Tree`.

The end-to-end orchestrator is `src.builder.build_country_tree(name,
infobox)`. The stages below are executed in order, top to bottom.

```
raw wptools infobox dict
        │
        ▼
1. apply field aliases       (src.preprocessing.normalize.apply_aliases)
        │
        ▼
2. drop filtered fields      (src.preprocessing.normalize.drop_filtered)
        │
        ▼
3. fold serial groups        (src.preprocessing.grouping.apply_serial_groups)
        │   leader_title1+leader_name1+leader_title2+leader_name2  →  @leaders
        │   established_event1+established_date1+…                 →  @established
        │
        ▼
4. for each remaining key:
   - look up target tree path in   config.category_layout
   - look up type hint in           config.field_types
   - parse the wikitext value       (src.parsing.{wikitext, typed, distribution})
   - attach as a leaf or composite under the right structural ancestor
        │
        ▼
5. emit a Tree rooted at "country"
```

## Stage 1: Field aliases

Variant Wikipedia field names → canonical names. From
`config.field_aliases`:

```json
{
  "time_zone": "timezone",
  "iso_code":  "iso3166code",
  "englishmotto": "national_motto",
  "motto":        "national_motto",
  "admin_center": "capital",
  ...
}
```

Pure rename; no type changes.

## Stage 2: Filter patterns

`config.field_filter_patterns` is a list of regex patterns. Anything
matching is dropped before tree construction:

```
^image_   ^flag_   ^coa_   ^map_   .*_ref$
^url      ^archiveurl   ^publisher  ^journal
^rowclass ^label\d*$    ^data\d*$
```

These are layout / citation / image markup that don't carry country
data.

## Stage 3: Serial-group folding

Some Wikipedia fields are numbered: `leader_title1`, `leader_name1`,
`leader_title2`, … each rule in `config.serial_groups` matches a
family of patterns and emits a synthetic composite key:

```json
"@leaders": {
  "patterns": {
    "title": "^leader_title(\\d+)$",
    "name":  "^leader_name(\\d+)$"
  },
  "child_label": "leader",
  "index_key":   "index"
}
```

After folding, the dict contains a `@leaders` key with a list of
per-index dicts:

```python
[
  {"index": 1, "title": "President",      "name": "Joseph Aoun"},
  {"index": 2, "title": "Prime Minister", "name": "Nawaf Salam"},
  ...
]
```

Same for `@established` (event + date).

## Stage 4: Typed parsing

Each leaf is parsed through `src.parsing.typed.parse_value(raw, type_hint, rates)`:

1. **Clean wikitext** (`src.parsing.wikitext.clean`):
   - Strip `<ref>…</ref>` (inline + self-closing).
   - Strip HTML comments `<!-- … -->`.
   - Lift `{{increase}} / {{decrease}} / {{steady}}` into a trend
     signal (returned separately).
   - Handle templates: drop citation-like (`{{cite …}}`), unwrap
     cosmetic (`{{lang|en|X}} → X`), expand list templates
     (`{{ubl|a|b}} → "a\nb"`), preserve `{{coord|…}}` as a sentinel.
   - Resolve wikilinks (`[[X|Y]] → Y`, `[[X]] → X`).
   - Drop remaining HTML tags.
2. **Type-specific parser** (depending on `type_hint`):

   | hint | parser |
   |------|--------|
   | `number`       | digit-grouping + magnitude suffix ("billion", "million") |
   | `percent`      | trailing `%` (or bare number when hinted) |
   | `year`         | 3–4 digit year, BCE-aware (negative integers) |
   | `date`         | ISO, DMY ("15 March 2024"), MDY ("March 15, 2024"), year-only |
   | `currency`     | currency symbol/code + amount + magnitude, converted to USD via `config.currency_to_usd` rates |
   | `coordinates`  | `{{coord|lat|lon}}` decimal or DMS, or `"lat,lon"` |
   | `wikilink`     | the already-resolved string |
   | `distribution` | parsed by `src.parsing.distribution.parse_distribution` |

3. **`detect_type`** falls back to heuristic typing when no hint is given.

Returns `(value, type, trend, unit)`.

### Distribution parsing

For `religion`, `ethnic_groups`, `languages`. Splits the cleaned
wikitext into items (newline, comma, or `{{ubl}}` expansion), tries to
extract a percentage per item, falls back to uniform mass:

```python
parse_distribution(raw, taxonomy) -> dict[LeafPath, float]
```

Each item's text is matched against the taxonomy's aliases (longest
match wins). Unmatched items go to a synthetic `("__other__",)` leaf.
The result is normalized to total mass 1.

Final shape stored on the leaf:

```json
[
  {"path": ["Abrahamic", "Islam", "Sunni"], "weight": 0.55},
  {"path": ["Abrahamic", "Christianity", "Catholic"], "weight": 0.35},
  {"path": ["__other__"], "weight": 0.10}
]
```

## Stage 5: Category layout

`config.category_layout` maps each canonical field name (or synthetic
serial-group key) to a dotted target path under the `country` root:

```json
"capital":           "geography.capital",
"GDP_PPP":           "economy.gdp_ppp.value",
"GDP_PPP_year":      "economy.gdp_ppp.year",
"GDP_PPP_per_capita":"economy.gdp_ppp.per_capita",
"religion":          "demographics.religion",
"@leaders":          "government.leaders",
"@established":      "history.established"
```

The builder walks the dotted path, creates intermediate structural
nodes on demand (e.g. `geography`, then `area`), and attaches the leaf
or composite at the leaf position.

Fields *not* in `category_layout` go to `unmapped.<field_name>` so
nothing is silently dropped during the rebuild.

## Resulting tree shape

```
country
├── identity            (long_name, common_name, native_name, demonym, motto, anthem)
├── geography           (capital, largest_city, coordinates, area/{km2,rank,water_pct}, timezone, utc_offset, drives_on)
├── government          (type, legislature, upper_house, lower_house, leaders/[leader/{title,name,index}, …])
├── economy             (gdp_ppp/{value,year,rank,per_capita}, gdp_nominal/{…}, gini/{…}, hdi/{…}, currency)
├── demographics        (population/{estimate,estimate_year,…}, languages, religion, ethnic_groups, …)
├── history             (established/[event/{event,date,index}, …])
├── codes               (iso3166, cctld, calling_code)
└── unmapped            (anything the layout doesn't claim)
```

For Lebanon: 123 nodes, height 4. For Switzerland: 99 nodes, height 4.

## Caching / reuse

The `frontend.app._cached_country_tree(name)` is an `lru_cache` so
re-views of a country page don't re-build the tree. Cache is in-process
only; restart the server to refresh.
