# IDPA Project 1 — Wikipedia Infobox TED Pipeline

A Python pipeline that collects Wikipedia country infoboxes, converts them to rooted ordered labeled trees, computes Tree Edit Distance (TED) using two algorithms, and produces structured diffs and patches.

## Overview

The pipeline has 5 stages:

1. **Collection** — Fetch infobox data for all 193 UN member states via `wptools`, clean wikitext markup, and save as XML.
2. **Pre-processing** — Parse XML into rooted ordered labeled trees with configurable tokenization.
3. **TED & Differencing** — Compute tree edit distance using Chawathe (1999) and Nierman & Jagadish (2002), extract edit scripts, and output diffs in a custom IDF XML format.
4. **Patching** — Apply edit scripts to transform one tree into another (bidirectional).
5. **Post-processing** — Serialize trees back to XML/wikitext and generate color-coded HTML diff reports.

## Requirements

- Python 3.10+
- [wptools](https://github.com/siznax/wptools)
- pytest (for running tests)

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # Linux/macOS

pip install wptools pytest
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
│   └── postprocessing/      # Serializer, HTML reporter
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