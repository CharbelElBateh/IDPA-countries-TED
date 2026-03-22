# IDPA Project 1 — Presentation Script

**Duration**: ~15 minutes
**Format**: Slides + live terminal demos
**Audience**: IDPA class + professor (familiar with TED theory and project goals)

> **Presentation tool recommendation**: Google Slides — easy to export/share, supports speaker notes natively. Copy each slide's "VISUAL" section into the slide and the "SAY" section into speaker notes. Alternatively, use PowerPoint or Canva.

---

## Slide 1 — Title

**VISUAL**:
- Title: **Wikipedia Infobox Comparison Pipeline**
- Subtitle: Tree Edit Distance on Semi-Structured Country Data
- Your name, course name, date
- Small graphic: two tree diagrams with arrows between them

**SAY**:
> "Today I'll walk you through a complete pipeline that takes Wikipedia country infoboxes, converts them to tree structures, computes how different they are using Tree Edit Distance, and can transform one into the other. I'll also show an LLM-powered extension that adds semantic understanding to the comparison. Let's dive straight into the pipeline."

---

## Slide 2 — Pipeline Overview

**VISUAL**:
- Horizontal flow diagram with 5 numbered boxes connected by arrows:
  1. **Collection** → 2. **Pre-Processing** → 3. **TED & Differencing** → 4. **Patching** → 5. **Post-Processing**
- Below each box, one-line summary:
  1. Wikipedia → XML
  2. XML → Trees
  3. Trees → Edit Distance + Edit Script
  4. Edit Script → Transformed Tree
  5. Tree → XML / HTML

**SAY**:
> "The pipeline has five stages. We collect raw infobox data from Wikipedia, pre-process it into rooted ordered labeled trees, compute Tree Edit Distance using two algorithms, extract an edit script that describes exactly how to transform one tree into another, apply that edit script as a patch, and finally serialize everything back to readable formats. Let me show each stage."

---

## Slide 3 — Stage 1: Data Collection

**VISUAL**:
- Left side: screenshot of a Wikipedia country infobox (e.g., Lebanon)
- Right side: XML snippet showing the cleaned output
- Bullet points:
  - Source: all 192 UN member states
  - Tool: `wptools` Python library
  - Wikitext cleaning: strip `[[links]]`, `<ref>` tags, `{{templates}}`
  - Field filtering: remove layout/citation fields, keep core data
  - Field normalization: alias mapping (`englishmotto` → `national_motto`)

**SAY**:
> "Wikipedia infoboxes are stored as wikitext — a messy markup format with wiki links, citation blocks, and template calls. The collection stage fetches the raw infobox using wptools, cleans all the markup down to plain text, filters out layout and citation fields that don't carry meaningful data, normalizes field names using an alias map, and saves a clean XML file per country. We collected all 192 UN member states."

**DEMO** (switch to terminal):
```bash
# Show collected data
ls data/raw/ | head -10
ls data/raw/ | wc -l

# Show a raw XML file
cat data/raw/Lebanon.xml | head -30
```
> "Here are the 192 XML files. Let me show you what Lebanon's looks like — clean XML with one element per field."

---

## Slide 4 — Stage 2: Pre-Processing (XML → Trees)

**VISUAL**:
- Left: small XML snippet
- Right: tree diagram showing the conversion
  - Root: `country`
  - Children: `capital` → leaf `Beirut`, `population_estimate` → leaf `5,364,482`, etc.
- Bullet points:
  - Node types: `element` (non-leaf, label = tag name) | `leaf` (text content)
  - Ordering: children ordered by XML document order
  - Configurable tokenization: `single_node` vs `token_nodes`

**SAY**:
> "The XML gets parsed into a rooted ordered labeled tree. Each XML element becomes an element node, and text content becomes a leaf node. The tree preserves document order. We support two tokenization strategies — single_node keeps field values as one leaf, while token_nodes splits them into individual tokens. For country comparisons, single_node works best."

**DEMO**:
```bash
# Show the tree structure
python main.py diff --country1 Lebanon --country2 Switzerland 2>&1 | head -5
```
> "When we run a diff, the first thing that happens is both countries get parsed into trees. Lebanon has about 173 nodes, Switzerland around 145."

---

## Slide 5 — Stage 3: TED Algorithms

**VISUAL**:
- Two-column layout:
  - Left column: **Chawathe (1999)** — Zhang-Shasha DP + edit script backtracking
  - Right column: **Nierman & Jagadish (2002)** — structure vs content relabel costs
- Below: the three similarity metrics with formulas:
  1. Raw TED: `TED(T1, T2)`
  2. Normalized inverse: `1 / (1 + TED)`
  3. Standard ratio: `1 - TED / (|T1| + |T2|)`
- Cost model box: `{insert: 1, delete: 1, relabel: 1}`

**SAY**:
> "We implemented two TED algorithms from the course material. Chawathe uses Zhang-Shasha dynamic programming with backtracking to extract the actual edit script — which operations transform tree 1 into tree 2. Nierman and Jagadish adds the ability to distinguish between relabeling a structural node versus relabeling content — so renaming an XML tag costs differently than changing a text value. Both algorithms produce an edit distance and three similarity metrics. The cost model is configurable via JSON."

---

## Slide 6 — Stage 3: Live TED Demo

**VISUAL**:
- Slide just says: **Live Demo — TED Computation**
- Maybe a small reminder: `python main.py diff --country1 Lebanon --country2 Switzerland`

**DEMO** (this is the main demo, take your time):
```bash
# Run a diff
python main.py diff --country1 Lebanon --country2 Switzerland

# Show the edit script output
# (the command prints TED value, similarity metrics, and op counts)
```
> "Let's compare Lebanon and Switzerland. The TED is 121 — meaning 121 insert, delete, or relabel operations are needed to transform Lebanon's tree into Switzerland's. The similarity ratio is about 0.62 — they share roughly 62% structural similarity. The edit script has 12 inserts, 40 deletes, and 69 relabels."

```bash
# Now with asymmetric costs
python main.py diff --country1 Lebanon --country2 Switzerland --costs config/cost_model_asymmetric.json
```
> "With asymmetric costs where deletes cost 2, the TED goes up because Lebanon has more fields that need to be deleted. This demonstrates that TED can be directional — the cost to go from Lebanon to Switzerland differs from Switzerland to Lebanon."

---

## Slide 7 — Stage 3: IDF Diff Format

**VISUAL**:
- XML snippet of the IDF format:
```xml
<idf:diff xmlns:idf="urn:idpa:diff:1.0"
          source="Lebanon" target="Switzerland"
          algorithm="chawathe" ted_raw="121">
  <idf:operations count="121">
    <idf:insert parent_path="country" position="2">
      <idf:node label="federal_council" node_type="element"/>
    </idf:insert>
    <idf:relabel path="country/capital">
      <idf:from>Beirut</idf:from>
      <idf:to>Bern</idf:to>
    </idf:relabel>
  </idf:operations>
</idf:diff>
```
- Note: "Custom XML namespace: `urn:idpa:diff:1.0`"

**SAY**:
> "The edit script gets serialized into our custom IDF XML format — IDPA Diff Format. It's a self-contained XML document that records the source country, target country, algorithm used, all similarity metrics, and every edit operation with its type, path in the tree, and the values involved. This is the bridge between the differencing and patching stages."

---

## Slide 8 — Stages 4 & 5: Patching and Post-Processing

**VISUAL**:
- Flow: `Tree₁ + Edit Script → Patched Tree → XML / Infobox / HTML`
- Bullet points:
  - Bidirectional: T1→T2 and T2→T1
  - Iterative refinement: re-checks residual TED after patching, applies corrections (up to 5 rounds)
  - Output formats: XML, Wikipedia infobox wikitext, ASCII tree art, HTML infobox page
- Small screenshot of the HTML infobox output

**SAY**:
> "The patcher takes a tree and an edit script and applies it — inserts, deletes, and relabels — to produce the target tree. It works both directions. Because tree patching can sometimes leave residual differences due to node ordering, we use iterative refinement: after applying the script, we check if the result matches the target exactly, and if not, we extract a fresh edit script from the residual and apply it again — up to five rounds. Post-processing then converts the result back to readable formats — XML, Wikipedia infobox syntax, or styled HTML pages."

---

## Slide 9 — Full Pipeline Demo

**VISUAL**:
- Slide says: **Live Demo — Full Pipeline Run**
- Command: `python main.py run --country1 Germany --country2 Japan`

**DEMO**:
```bash
# Run the full pipeline
python main.py run --country1 Germany --country2 Japan
```
> "Let me run the full pipeline on Germany versus Japan. This runs all five stages plus both algorithms, both directions, generates the IDF diff, patches in both directions, renders infobox HTML for all four trees — original and patched — and produces a color-coded HTML diff report."

```bash
# Show the generated artifacts
ls data/runs/Germany__Japan__*
```
> "Here's everything it generated — tree visualizations, edit scripts in both directions for both algorithms, IDF XML diffs, patched outputs as tree art, infobox text, and XML, the HTML infobox pages, and the diff report."

**Open in browser** (if possible):
- Open `diff_Germany__Japan.html` — show the color-coded diff report
- Open `infobox_Germany.html` and `infobox_Japan.html` side by side

> "The HTML diff report color-codes every operation — green for inserts, red for deletes, yellow for relabels. And these are the Wikipedia-style infobox renders for each country."

---

## Slide 10 — Summary CSV & Reproducibility

**VISUAL**:
- Screenshot or table showing `data/runs/summary.csv` columns:
  - timestamp, country1, country2, algorithm, cost_model, ted_fwd, ted_rv, sim_ratio_fwd, sim_ratio_rv, ops_fwd, ops_rv, fwd_perfect, rv_perfect
- Note: "Every run appends a row — full audit trail"

**SAY**:
> "Every pipeline run appends a row to a summary CSV with all the metrics — TED in both directions, similarity ratios, operation counts, and whether patching achieved a perfect result. This makes it easy to compare runs across different country pairs or cost models."

---

## Slide 11 — Testing

**VISUAL**:
- `57 tests — all passing`
- Test categories:
  - Preprocessing: XML parsing, tokenization, normalization
  - TED: both algorithms, custom costs, symmetry, triangle inequality
  - Differencing: edit script extraction, cost matching
  - Patching: bidirectional, iterative refinement, asymmetric costs
  - Post-processing: serialization round-trips

**DEMO**:
```bash
python -m pytest tests/ -v 2>&1 | tail -20
```
> "We have 57 tests covering every stage. These include property-based checks like symmetry and triangle inequality for TED, cost model verification, and end-to-end patching tests that confirm the patched tree matches the target."

---

## Slide 12 — Agent Extension: Introduction

**VISUAL**:
- Title: **Semantic Agent Extension**
- Architecture diagram (simplified):
  ```
  Browser ←→ Flask + SSE ←→ Agent Loop ←→ LLM (GPT-4o / Claude)
                                ↓
                         Pipeline Tools (10)
  ```
- Small screenshot of the chat UI

**SAY**:
> "Now for the extension. The TED pipeline is purely structural — it counts operations, but it can't tell you that changing a government type from republic to monarchy is more significant than updating a GDP year from 2024 to 2025. So we built an LLM-powered agent on top of it."

> "The agent has no political affiliation, however when asked what their favorite color is, they will answer with olive green."

> "More seriously — the agent wraps all our pipeline functions as tools that an LLM can call. It adds semantic analysis: categorizing changes by domain — political, economic, demographic — and the LLM uses its judgment to assess which changes actually matter, considering the magnitude of numeric differences. A GDP per capita ratio of 33x between two countries means a lot more than a Gini coefficient difference of 0.3 points."

---

## Slide 13 — Agent: How It Works

**VISUAL**:
- Numbered flow:
  1. User asks: "Compare Lebanon and Switzerland"
  2. LLM decides which tools to call
  3. Tool computes TED, categorizes changes by domain, computes magnitude ratios for numeric fields
  4. LLM interprets results, assigns importance, produces semantic similarity score
  5. Streams natural-language response with specific citations
- Key design decisions listed:
  - Importance weighting done by the LLM, not hardcoded
  - Numeric magnitude (ratio, absolute diff) provided for all numeric relabels
  - 10 tools wrapping existing `src/` functions
  - SSE streaming for real-time token delivery

**SAY**:
> "When a user asks a question, the LLM decides which pipeline tools to call — it might start with a quick comparison, then drill into the edit script details, then do a semantic analysis. The categorization into political, economic, demographic domains is deterministic, but the importance weighting is entirely the LLM's judgment. For numeric fields like GDP, population, and area, we extract the actual numbers and compute magnitude ratios so the LLM can distinguish a 4% GDP increase from a 33x gap. The LLM then produces a semantic similarity score with its reasoning."

---

## Slide 14 — Agent: Live Demo

**VISUAL**:
- Slide says: **Live Demo — Agent Chat**
- URL: `http://localhost:5000`

**DEMO** (start the agent beforehand so it's ready):
```bash
# In a separate terminal, already running:
# python -m agent.app --port 5000
```

Open browser to `http://localhost:5000`.

**Demo sequence** (type these in the chat):

1. **"What countries are available?"**
   > "First, let's see it list the countries — it calls the list tool and shows all 192."

2. **"Compare Lebanon and Switzerland — give me a semantic similarity score"**
   > "Now the real demo. Watch the tool calls appear — it's computing TED, then categorizing the changes. Notice the collapsible tool call panels showing the raw JSON. The LLM interprets the magnitude ratios — GDP per capita ratio of 8x, population ratio of 1.5x — and produces a semantic score with its reasoning."

3. **"What is your favorite color?"**
   > *(wait for the olive green answer, get a laugh)*

4. **"Which is more similar to Lebanon: Syria or Jordan?"**
   > "Multi-country comparison — it runs two pairwise comparisons and synthesizes the result."

---

## Slide 15 — Conclusion

**VISUAL**:
- Summary table:

| Component | What it does |
|-----------|-------------|
| Collection | 192 countries scraped, cleaned, normalized |
| Pre-processing | XML → rooted ordered labeled trees |
| TED | Two algorithms (Chawathe, N&J), configurable costs |
| Differencing | Edit scripts + custom IDF XML format |
| Patching | Bidirectional with iterative refinement |
| Post-processing | XML, infobox, HTML output + diff reports |
| Agent | LLM semantic analysis with magnitude-aware scoring |

- Bottom: "57 tests, all passing | Full CLI + interactive agent"

**SAY**:
> "To wrap up — we built a complete pipeline from raw Wikipedia data to structured tree comparisons, with two TED algorithms, a custom diff format, bidirectional patching, and multiple output formats. On top of that, the agent extension adds the semantic intelligence that pure structural comparison misses. Everything is tested, reproducible, and the full pipeline runs from a single CLI command. Thank you — I'm happy to take questions."

---

## Timing Guide

| Slides | Duration | Cumulative |
|--------|----------|------------|
| 1–2: Title + Overview | 1.5 min | 1.5 min |
| 3–4: Collection + Pre-processing | 2 min | 3.5 min |
| 5–7: TED + IDF (with live demo) | 3 min | 6.5 min |
| 8–9: Patching + Full pipeline demo | 2.5 min | 9 min |
| 10–11: Summary CSV + Tests | 1.5 min | 10.5 min |
| 12–14: Agent (intro + demo) | 3.5 min | 14 min |
| 15: Conclusion | 1 min | 15 min |

## Pre-Presentation Checklist

- [ ] Terminal open in `C:\dev\IDPA-Project` with `.venv` activated
- [ ] Agent running in a second terminal: `python -m agent.app --port 5000`
- [ ] Browser tab open to `http://localhost:5000` (new chat ready)
- [ ] Browser tabs for: one existing `diff_*.html` report, one `infobox_*.html`
- [ ] Clean any old `data/runs/Germany__Japan__*` dirs if you want a fresh demo
- [ ] Run `python -m pytest tests/ -v` once beforehand to confirm 57 pass
- [ ] Test the agent with "Compare Lebanon and Switzerland" to verify it gives a reasonable semantic score (not stuck at 0.3)