# 00 · Project Context

## What it is

A pipeline that takes the Wikipedia infobox of any UN member state,
turns it into a typed, hierarchical tree, and computes a Tree Edit
Distance (TED) between any two such trees. The diff is shown in an
interactive web UI with side-by-side trees and color-coded changes.

## Course / origin

IDPA (Intelligent Data Processing and Applications). The project is a
follow-on to an earlier IDPA project that did the same thing with flat
wikitext strings; this rebuild adds typed leaves, distribution
distances, MongoDB storage, two real TED algorithms, and an
interactive D3 frontend.

## Dataset

- 192 UN member states.
- One Wikipedia article per country, fetched with `wptools`.
- Each article contributes one infobox (`Infobox country` template) —
  typically 70–90 fields per country.
- Live data from late 2025 / early 2026.

## Key empirical facts (from `data/analysis/infobox_summary.md`)

- 14,495 total key–value pairs across all 192 countries.
- 260 distinct field names observed; about 50 are "universal"
  (≥ 95% coverage) and 140 are rare (≤ 5%).
- Value-type distribution (after typing):

  | Type | Share |
  |------|------:|
  | `plain_text`   | 28.7% |
  | `wikilink`     | 27.6% |
  | `template`     |  9.8% |
  | `number`       |  9.1% |
  | `year`         |  9.0% |
  | `currency`     |  5.8% |
  | `date`         |  4.8% |
  | `list`         |  2.7% |
  | `coordinates`  |  1.4% |
  | `multiline`    |  0.9% |
  | `percent`      |  0.1% |

This skew motivated the typed-leaf design: roughly half of all values
are markup of some kind that has to be cleaned and parsed; another
quarter are numeric / temporal / categorical with structure.

## User

A single developer (Charbel). The repo lives at `C:\dev\IDPA-Project`
on Windows; the dev shell is PowerShell with WSL2 available. Python
runs through `.venv\Scripts\python.exe`.

## Constraints / preferences

- **Reproducibility**: explicit configs, deterministic dotted paths,
  cached comparison results in Mongo.
- **Each TED algorithm file is self-contained.** When this project's
  shared `zhang_shasha.py` was created, the user asked us to inline
  the Z-S backbone into each algorithm file so a reader can see the
  full algorithm in one place. Duplicate-code linter warnings on those
  files are *expected*.
- **Single source of truth for config**: `config/pipeline.json` holds
  field aliases, filter patterns, category layout, serial-group
  rules, field types, weights, TED cost models, currency rates, and
  the four taxonomies (religion, language, ethnicity, government).
- **Backwards-compat for cached scripts**: when `EditScript.mapping`
  is empty (older cached records), the frontend falls back to the
  legacy dotted-path diff logic.

## What's out of scope (for now)

- Real move operations in `EditScript` (a "move" is currently a
  delete + insert; N&J's subtree-containment rule keeps the cost low
  but the script still has two actions).
- "Both algorithms at once" in the UI — removed at user's request.
- Real-time Wikipedia re-fetching from the UI.
