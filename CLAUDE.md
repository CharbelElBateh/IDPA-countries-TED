# IDPA Project 1 — Wikipedia Semi-Structured Infobox Data Collection, Comparison, and Differencing

## Project Identity
- **Course**: Intelligent Data Processing and Applications (IDPA)
- **Language**: Python (PyCharm project)
- **Root**: `C:\dev\IDPA-Project`
- **Team**: Student + Claude

---

## Objective
Build a 5-stage pipeline to compare Wikipedia country infoboxes using Tree Edit Distance (TED):
1. Data Collection → XML per country
2. Pre-Processing → rooted ordered labeled trees
3. TED + Differencing → similarity score + edit script
4. Patching → apply edit script to transform T1 ↔ T2
5. Post-Processing → back to XML / infobox format

---

## Project Structure (target)
```
IDPA-Project/
├── CLAUDE.md
├── OPEN_QUESTIONS.md
├── main.py                          # Entry point / CLI driver
├── config/
│   ├── cost_model_default.json      # Default TED cost model (all ops = 1)
│   ├── tokenization.json            # Tokenization strategy config
│   └── field_aliases.json           # Infobox field name normalization map
├── data/
│   ├── raw/                         # Raw infobox XML per country
│   └── processed/                   # Serialized tree representations
├── src/
│   ├── collection/
│   │   ├── scraper.py               # wptools-based infobox fetcher
│   │   ├── wikitext_cleaner.py      # Strip wikitext markup → plain text
│   │   └── xml_formatter.py         # Convert cleaned infobox dict → XML
│   ├── preprocessing/
│   │   ├── xml_parser.py            # XML → rooted ordered labeled tree
│   │   ├── tokenizer.py             # Text tokenization (configurable)
│   │   └── normalizer.py            # Field name normalization (alias map)
│   ├── ted/
│   │   ├── chawathe.py              # Chawathe 1999 TED algorithm
│   │   ├── nierman_jagadish.py      # Nierman & Jagadish 2002 TED algorithm
│   │   └── similarity.py            # Compute all 3 similarity metrics
│   ├── differencing/
│   │   ├── edit_script.py           # Edit script extraction (backtracking)
│   │   └── diff_formatter.py        # Format diff as IDF XML (see below)
│   ├── patching/
│   │   └── patcher.py               # Apply IDF edit script to tree
│   └── postprocessing/
│       ├── serializer.py            # Tree → XML → Wikipedia infobox text / ASCII art
│       ├── html_reporter.py         # Tree diff → color-coded HTML report
│       └── infobox_renderer.py      # Tree → Wikipedia-style infobox HTML page
├── classes/
│   ├── Node.py                      # Tree node (label, node_type, children, parent)
│   ├── Tree.py                      # Tree (root node + traversal utilities)
│   ├── Action.py                    # Edit action (op_type, cost, args)
│   └── EditScript.py                # Ordered list of Actions with total cost
└── tests/
    ├── test_collection.py
    ├── test_preprocessing.py
    ├── test_ted.py
    ├── test_differencing.py
    ├── test_patching.py
    └── test_postprocessing.py
```

---

## Component Details

### 1. Data Collection
- **Source**: All UN member states (https://en.wikipedia.org/wiki/Member_states_of_the_United_Nations)
- **Tool**: `wptools` Python library
- **Template**: Almost all countries use `Infobox country` — occasionally `Infobox sovereign state`
- **Output**: One XML file per country in `data/raw/`
- **Wikitext cleaning required**:
  - Strip wiki links: `[[Arabic]]` → `Arabic`, `[[French language|French]]` → `French`
  - Strip `<ref>...</ref>` citation blocks entirely
  - Strip `{{Cite ...}}` / `{{cite ...}}` templates
  - Strip `{{efn|...}}` footnotes
  - Strip `<!--HTML comments-->`
  - Expand `{{unbulleted list|item1|item2|...}}` → structured XML child nodes
  - Strip remaining `{{...}}` template calls

#### Field Filtering (applied before XML generation)
| Category | Action | Examples |
|---|---|---|
| Rendering/layout | Filter out | `rowclass*`, `label*`, `data*`, `titlestyle`, `bodystyle`, `subbox`, `liststyle`, `item_style`, `map_width`, `alt_*`, `image_*`, `coa_size`, `area_label*`, `area_footnote`, `area_link`, `area_data*`, `today` |
| Reference fields | Filter out | `*_ref` (Gini_ref, HDI_ref, etc.) |
| Citation spillover | Filter out | `last`, `date`, `title`, `journal`, `script-journal`, `volume`, `pages`, `url`, `url-status`, `archiveurl`, `archivedate`, `publisher` |
| Core data | Keep | `conventional_long_name`, `common_name`, `native_name`, `capital`, `largest_city`, `official_languages`, `languages`, `languages_type`, `languages2`, `languages2_type`, `demonym`, `government_type`, `leader_title*`, `leader_name*`, `legislature`, `upper_house`, `lower_house`, `established_event*`, `established_date*`, `area_km2`, `percent_water`, `population_estimate`, `population_estimate_year`, `population_census`, `population_census_year`, `population_density_km2`, `GDP_PPP`, `GDP_PPP_year`, `GDP_PPP_per_capita`, `GDP_nominal`, `GDP_nominal_year`, `GDP_nominal_per_capita`, `Gini`, `Gini_year`, `Gini_change`, `HDI`, `HDI_year`, `HDI_change`, `HDI_rank`, `currency`, `currency_code`, `time_zone`, `utc_offset`, `drives_on`, `calling_code`, `cctld`, `ethnic_groups`, `ethnic_groups_year`, `religion`, `religion_year`, `coordinates`, `national_motto`, `national_anthem`, `iso3166code` |
| Ranking fields | **Included** by default | `area_rank`, `GDP_PPP_rank`, `HDI_rank`, etc. — add to `_FILTER_PATTERNS` in `xml_formatter.py` to exclude |

#### Field Normalization (aliases)
Configured in `config/field_aliases.json`. Maps variant names → canonical names.
Known aliases discovered from exploration:
- `map_caption` / `image_map_caption` → `map_caption`
- `englishmotto` / `national_motto` → `national_motto`
- `admin_center` → `capital` (when capital field is absent)

### 2. Data Pre-Processing
- Input: country XML file
- Output: `Tree` object (rooted ordered labeled tree)
- **Node types**: `element` (non-leaf, tag name as label) | `leaf` (text content as label)
- **Ordering rules**:
  - Element child nodes: ordered by appearance in XML
  - Attribute nodes (if any): sorted alphabetically, before sub-element siblings
- **Text tokenization** (configurable via `config/tokenization.json`):
  - Tokenize on whitespace/punctuation boundaries (alphanumeric tokens)
  - e.g. `"I like data processing"` → `['I', 'like', 'data', 'processing']`
  - Config option: `single_node` (one leaf with full text) | `token_nodes` (one leaf per token)
- **Multi-value fields**: `token_nodes` strategy produces `<item>` children (Option B); `single_node` produces flat text leaf
- **established_event*/established_date* grouping**: grouped under `<established><event><label>…</label><date>…</date></event></established>`
- **Stop word removal / stemming**: NOT required
- **Typed data** (numbers, dates, booleans): treated as plain text

### 3. Document Tree Similarity & Differencing
- **Two algorithms implemented and compared**:
  1. Chawathe 1999 (VLDB) — ref: IDPA Ch. 5
  2. Nierman & Jagadish 2002 (WebDB) — ref: IDPA Ch. 5
- **Cost model**: loaded from JSON file (`config/cost_model_default.json`)
  ```json
  {
    "insert": 1,
    "delete": 1,
    "relabel": 1,
    "relabel_structure": 1,
    "relabel_content": 1
  }
  ```
- **Three similarity metrics reported**:
  1. Raw TED integer: `TED(T1, T2)`
  2. Normalized inverse: `1 / (1 + TED(T1, T2))`
  3. Standard ratio: `1 - TED(T1, T2) / (|T1| + |T2|)`
  where `|T|` = number of nodes in tree T

### 4. IDPA Diff Format (IDF)
Custom XML diff format. Namespace: `urn:idpa:diff:1.0`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<idf:diff xmlns:idf="urn:idpa:diff:1.0"
          source="Lebanon"
          target="Switzerland"
          algorithm="chawathe"
          ted_raw="42"
          sim_inverse="0.023"
          sim_normalized="0.723"
          sim_ratio="0.785">
  <idf:operations count="3">
    <idf:insert id="op1" parent_path="country/government" position="2">
      <idf:node label="federal_council" node_type="element"/>
    </idf:insert>
    <idf:delete id="op2">
      <idf:node label="president" node_type="element" path="country/government/president"/>
    </idf:delete>
    <idf:relabel id="op3" path="country/government/leader_name1">
      <idf:from>Joseph Aoun</idf:from>
      <idf:to>Karin Keller-Sutter</idf:to>
    </idf:relabel>
  </idf:operations>
</idf:diff>
```

Operations: `insert`, `delete`, `relabel`

### 5. Document Tree Patching
- Input: `Tree` + IDF diff file
- Output: transformed `Tree`
- Must work bidirectionally: T1→T2 and T2→T1

### 6. Post-Processing
- Tree → XML (pretty-printed)
- Tree → Wikipedia infobox wikitext (best-effort reconstruction)

---

## Core Classes (redesigned skeleton)

### `Node` (`classes/Node.py`)
```python
class Node:
    label: str          # tag name (element) or text content (leaf)
    node_type: str      # 'element' | 'leaf'
    children: list      # ordered list of child Nodes
    parent: Node | None
```

### `Tree` (`classes/Tree.py`)
```python
class Tree:
    root: Node
    # Utility methods: size(), get_nodes(), postorder(), etc.
```

### `Action` (`classes/Action.py`)
```python
class Action:
    op_type: str        # 'insert' | 'delete' | 'relabel'
    cost: int/float
    node: Node          # target node
    args: dict          # op-specific params (new_label, parent, position, etc.)
```

### `EditScript` (`classes/EditScript.py`)
```python
class EditScript:
    operations: list[Action]
    total_cost: int/float
```

---

## Config Files

### `config/cost_model_default.json`
```json
{
  "insert": 1,
  "delete": 1,
  "relabel": 1
}
```

### `config/tokenization.json`
```json
{
  "strategy": "single_node",
  "comment": "Options: single_node | token_nodes"
}
```

### `config/field_aliases.json`
```json
{
  "map_caption": "image_map_caption",
  "englishmotto": "national_motto"
}
```

---

## Implementation Status

| Stage | Status | Key files |
|-------|--------|-----------|
| 1. Collection | ✅ Complete | `src/collection/scraper.py`, `wikitext_cleaner.py`, `xml_formatter.py` |
| 2. Preprocessing | ✅ Complete | `src/preprocessing/xml_parser.py`, `tokenizer.py`, `normalizer.py` |
| 3. TED | ✅ Complete | `src/ted/chawathe.py`, `nierman_jagadish.py`, `similarity.py` |
| 4. Differencing | ✅ Complete | `src/differencing/edit_script.py`, `diff_formatter.py` |
| 5. Patching | ✅ Complete | `src/patching/patcher.py` (iterative refinement, asymmetric costs) |
| 6. Post-processing | ✅ Complete | `src/postprocessing/serializer.py`, `html_reporter.py` |
| CLI | ✅ Complete | `main.py` — subcommands: `collect`, `diff`, `patch`, `postprocess`, `run` |
| Tests | ✅ Complete (57) | `tests/test_preprocessing.py`, `test_ted.py`, `test_differencing.py`, `test_patching.py`, `test_postprocessing.py` |
| Data | ✅ 192 countries | All UN member states in `data/raw/` (192/192, zero failures) |

### Run Artifacts (per `run` invocation)
Each run creates `data/runs/<C1>__<C2>__<timestamp>/` containing:
- `pipeline_<C1>__<C2>.log` — full pipeline log
- `T1_<C1>.tree.txt`, `T2_<C2>.tree.txt` — ASCII art trees
- `edit_script_chawathe_<C1>_to_<C2>.txt` + reverse + N&J variants (4 files)
- `idf_<algorithm>.xml` — IDF diff
- `patched_<slug>.tree.txt` + `.infobox.txt` + `.xml` (forward + reverse)
- `infobox_<C1>.html`, `infobox_<C2>.html` — Wikipedia-style infobox HTML (original trees)
- `infobox_patched_<C1>_to_<C2>.html`, `infobox_patched_<C2>_to_<C1>.html` — Wikipedia-style infobox HTML (patched trees)
- `diff_<C1>__<C2>.html` — color-coded HTML diff report

`data/runs/summary.csv` — one row per run with TED, sim metrics, op counts, patch quality.

### Cost Models
- `config/cost_model_default.json` — all ops = 1
- `config/cost_model_asymmetric.json` — delete=2, insert=1, relabel=1 (demonstrates TED(T1→T2) ≠ TED(T2→T1))

## CLI Quick Reference
```
# Collect data
python main.py collect --country Lebanon
python main.py collect --all

# Compute TED + IDF diff
python main.py diff --country1 Lebanon --country2 Switzerland
python main.py diff --country1 Lebanon --country2 Switzerland --algorithm nierman_jagadish

# Apply patch (transform T1 → T2)
python main.py patch --country1 Lebanon --country2 Switzerland
python main.py patch --country1 Lebanon --country2 Switzerland --direction reverse

# Render Wikipedia-style infobox HTML
python main.py postprocess --country Lebanon
```

---

## Testing
- Framework: **pytest** (install: `.venv\Scripts\pip.exe install pytest`)
- Run: `.venv\Scripts\python.exe -m pytest tests/ -v`
- Tests in `tests/` directory
- Cover: unit tests per module + integration tests for full pipeline
- Use small manually-crafted trees for TED unit tests (known expected distances)

---

## Key References
- IDPA course slides/textbook (Ch. 4, 5, 6) — ask when specific algorithm details needed
- Chawathe S., VLDB 1999, pp. 90-101
- Nierman A. & Jagadish H.V., WebDB 2002, pp. 61-66
- wptools: https://github.com/siznax/wptools

---

## Open Questions
See `OPEN_QUESTIONS.md` — all resolved.
