# IDPA Project 1 — Wikipedia Infobox TED Pipeline

A Python pipeline that collects Wikipedia country infoboxes, converts them to rooted ordered labeled trees, computes Tree Edit Distance (TED) using two algorithms, and produces structured diffs and patches. Includes an LLM-powered agent for semantic analysis.

## Overview

The pipeline has 5 stages:

1. **Collection** — Fetch infobox data for all 192 UN member states via `wptools`, clean wikitext markup, and save as XML.
2. **Pre-processing** — Parse XML into rooted ordered labeled trees with configurable tokenization.
3. **TED & Differencing** — Compute tree edit distance using Chawathe (1999) and Nierman & Jagadish (2002), extract edit scripts, and output diffs in a custom IDF XML format.
4. **Patching** — Apply edit scripts to transform one tree into another (bidirectional).
5. **Post-processing** — Serialize trees back to XML/wikitext and generate color-coded HTML diff reports.

An optional **Agent extension** adds an LLM-powered chat interface that translates edit scripts into natural language, groups changes by semantic category, and lets the model assess importance.

## Requirements

- Python 3.10+
- [wptools](https://github.com/siznax/wptools)
- pytest (for running tests)
- flask, litellm, python-dotenv (for the agent extension)

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # Linux/macOS

pip install -r requirements.txt
```

## Usage

### Full pipeline (default: Lebanon vs Switzerland)

```bash
python main.py
python main.py run --country1 Germany --country2 France
```

### Individual stages

```bash
# Collect infobox data
python main.py collect --country Lebanon
python main.py collect --all

# Compute TED and produce IDF diff
python main.py diff --country1 Lebanon --country2 Switzerland
python main.py diff --country1 Lebanon --country2 Switzerland --algorithm nierman_jagadish

# Apply patch
python main.py patch --country1 Lebanon --country2 Switzerland
python main.py patch --country1 Lebanon --country2 Switzerland --direction reverse

# Render Wikipedia-style infobox HTML
python main.py postprocess --country Lebanon
```

### Options

| Flag | Description |
|------|-------------|
| `--algorithm` | `chawathe` (default) or `nierman_jagadish` |
| `--strategy` | `single_node` (default) or `token_nodes` |
| `--costs FILE` | Custom cost model JSON (default: `config/cost_model_default.json`) |
| `--raw-dir DIR` | Custom raw data directory |
| `-v` / `--verbose` | Show DEBUG-level messages |
| `--log-file FILE` | Custom log file path |
| `--no-log-file` | Disable file logging |

## Agent Extension

An LLM-powered chat interface for interactive country comparison with semantic analysis.

The core TED pipeline treats all changes equally (cost = 1). The agent adds a semantic layer: it receives categorized edit operations (political, economic, demographic, etc.) and applies its own judgment about which changes are fundamental vs. trivial.

See [`agent/AGENT.md`](agent/AGENT.md) for full architecture documentation.

### Quick start

```bash
# Set up API keys
cp .env.example .env
# Edit .env with your OpenAI/Anthropic keys

# Start the server
python -m agent.app --port 5000

# Options
python -m agent.app --model gpt-4o                              # default
python -m agent.app --model anthropic/claude-sonnet-4-20250514  # Anthropic
python -m agent.app --model ollama/llama3                        # local
```

Open `http://localhost:5000` and ask questions like:
- "Compare Lebanon and Switzerland"
- "What countries are available?"
- "Which is more similar to Lebanon: Syria or Switzerland?"
- "Show me the semantic differences between France and Germany"

### Agent tools

| Tool | Description |
|------|-------------|
| `list_available_countries` | List all 192 countries with data |
| `get_country_info` | Load tree, return fields + values |
| `compare_countries` | Full TED comparison + similarity metrics |
| `get_edit_script_details` | Detailed edit ops with field paths |
| `collect_country` | Scrape from Wikipedia if missing |
| `get_field_value` | Get one field's value |
| `compare_specific_fields` | Compare specific fields (no TED) |
| `compute_semantic_similarity` | TED + categorized changes for LLM to weight |
| `generate_comparison_report` | Full markdown report |
| `run_full_pipeline` | Run existing pipeline flow |

## Run Artifacts

Each `run` invocation creates a directory under `data/runs/<Country1>__<Country2>__<timestamp>/` containing:

- `pipeline_<Country1>__<Country2>.log` — full pipeline log
- `T1_<Country1>.tree.txt`, `T2_<Country2>.tree.txt` — ASCII tree visualizations
- `edit_script_*.txt` — edit scripts (forward + reverse, both algorithms)
- `idf_<algorithm>.xml` — IDF diff in XML format
- `patched_*.tree.txt`, `*.infobox.txt`, `*.xml` — patched outputs (forward + reverse)
- `infobox_<Country1>.html`, `infobox_<Country2>.html` — Wikipedia-style infobox HTML for original trees
- `infobox_patched_<C1>_to_<C2>.html`, `infobox_patched_<C2>_to_<C1>.html` — Wikipedia-style infobox HTML for patched trees
- `diff_<Country1>__<Country2>.html` — color-coded HTML diff report

A summary CSV (`data/runs/summary.csv`) is appended after every run.

## Project Structure

```
IDPA-Project/
├── main.py                  # CLI entry point
├── config/                  # Cost models, tokenization, field aliases
├── data/
│   ├── raw/                 # XML infoboxes (192 countries)
│   └── runs/                # Pipeline run artifacts
├── src/
│   ├── collection/          # Scraper, wikitext cleaner, XML formatter
│   ├── preprocessing/       # XML parser, tokenizer, normalizer
│   ├── ted/                 # Chawathe & Nierman-Jagadish TED algorithms
│   ├── differencing/        # Edit script extraction, IDF formatter
│   ├── patching/            # Tree patching (bidirectional)
│   └── postprocessing/      # Serializer, HTML reporter, infobox renderer
├── agent/                   # LLM agent extension
│   ├── app.py               # Flask server + SSE streaming
│   ├── core.py              # Agent loop (tool-calling)
│   ├── tools.py             # 10 pipeline tool wrappers
│   ├── semantic.py          # Change categorization by domain
│   ├── llm_client.py        # litellm multi-provider wrapper
│   └── static/index.html    # Chat UI
├── classes/                 # Node, Tree, Action, EditScript
└── tests/                   # 57 tests (pytest)
```

## Testing

```bash
python -m pytest tests/ -v
```

## Cost Models

- `config/cost_model_default.json` — all operations cost 1
- `config/cost_model_asymmetric.json` — delete costs 2, insert and relabel cost 1 (demonstrates directional TED asymmetry)

## TED Algorithms

| Algorithm | Reference | Notes |
|-----------|-----------|-------|
| Chawathe | VLDB 1999, pp. 90-101 | Zhang-Shasha with edit script backtracking |
| Nierman & Jagadish | WebDB 2002, pp. 61-66 | Distinguishes structure vs content relabel costs |

## Similarity Metrics

Three metrics are computed for each comparison:

1. **Raw TED** — `TED(T1, T2)`
2. **Normalized inverse** — `1 / (1 + TED(T1, T2))`
3. **Standard ratio** — `1 - TED(T1, T2) / (|T1| + |T2|)`

## License

Course project for IDPA (Intelligent Data Processing and Applications).