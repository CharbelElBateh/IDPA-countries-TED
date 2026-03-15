# IDPA Semantic Agent

An LLM-powered extension to the IDPA pipeline that adds natural-language understanding to country comparisons.

## Why

The core pipeline computes **Tree Edit Distance (TED)** — a purely structural metric. It counts how many insert/delete/relabel operations are needed to transform one country's infobox tree into another's. Every operation costs 1 (by default), so changing a GDP year from 2022 to 2023 weighs the same as changing a government type from "republic" to "monarchy".

The agent adds a **semantic layer**: an LLM receives the categorized edit script and applies its judgment to assess which changes are fundamental vs. trivial, producing a weighted semantic similarity score alongside the structural one.

## Architecture

```
Browser (localhost:5000)
    │
    │  SSE (streaming) + REST
    ▼
Flask Backend (agent/app.py)
    │
    ├─► Agent Loop (agent/core.py)
    │       │
    │       │  litellm.completion() with tool schemas
    │       ▼
    │   LLM Provider (OpenAI / Anthropic / Ollama)
    │       │
    │       │  tool_calls
    │       ▼
    │   Pipeline Tools (agent/tools.py)
    │       10 tools wrapping existing src/ functions
    │
    └─► Chat Persistence (agent/persistence.py)
            JSON files in data/agent/chats/
```

## Components

### `app.py` — Flask Server

HTTP server with SSE streaming for real-time token delivery.

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Serve the chat UI |
| `/api/chat` | POST | Start agent interaction, returns SSE event stream |
| `/api/chats` | GET | List all saved chats |
| `/api/chats/<id>` | GET | Load a specific chat |
| `/api/chats/<id>` | DELETE | Delete a chat |
| `/api/models` | GET | Return available model presets |

SSE events: `token` (text chunk), `tool_start` (tool invoked), `tool_end` (tool result), `done`, `error`.

### `core.py` — Agent Loop

A simple tool-calling loop (no framework dependencies):

1. Send messages + tool schemas to LLM
2. Stream text tokens to client
3. If LLM returns tool_calls → execute each tool → append results → loop back to step 1
4. If LLM returns text only → done

Max 15 iterations to prevent runaway loops.

### `tools.py` — Pipeline Tools

10 tools that wrap existing `src/` functions:

| Tool | What it does |
|------|-------------|
| `list_available_countries` | Glob `data/raw/*.xml`, return 192 country names |
| `get_country_info` | Parse XML → tree, list all fields and values |
| `compare_countries` | Compute TED, return 3 similarity metrics + op counts |
| `get_edit_script_details` | Full edit script with per-operation detail |
| `collect_country` | Scrape missing country from Wikipedia via wptools |
| `get_field_value` | Look up a single field for a country |
| `compare_specific_fields` | Side-by-side comparison of specific fields |
| `compute_semantic_similarity` | TED + categorized changes for LLM to weight |
| `generate_comparison_report` | Markdown report saved to `data/agent/outputs/` |
| `run_full_pipeline` | Execute `cmd_run` with all artifacts |

### `semantic.py` — Change Categorization

Deterministic mapping of edit operations to semantic domains:

- **political**: government_type, legislature, leaders
- **economic**: GDP, currency, Gini
- **demographic**: population, ethnic groups, religion
- **geographic**: area, capital, timezone
- **cultural**: languages, national motto/anthem
- **development**: HDI
- **international**: calling codes, TLDs
- **historical**: establishment dates

**Importance weighting is NOT hardcoded.** The categorized changes are returned to the LLM, which applies its own judgment about significance. This means the semantic analysis adapts to context — the LLM can reason that "Lebanon and Syria sharing Arabic as a language is expected, but Switzerland and Lebanon both being republics is notable."

### `llm_client.py` — LLM Abstraction

Uses [litellm](https://github.com/BerriAI/litellm) for provider-agnostic API calls:

- **OpenAI**: `gpt-4o`, `gpt-4o-mini`
- **Anthropic**: `anthropic/claude-sonnet-4-20250514`, `anthropic/claude-haiku-4-5-20251001`
- **Ollama/local**: `ollama/llama3` (via `OPENAI_API_BASE`)

API keys loaded from `.env` via python-dotenv.

### `persistence.py` — Chat Storage

Each conversation saved as a JSON file in `data/agent/chats/`:

```json
{
  "id": "a1b2c3d4e5f6",
  "title": "Compare Lebanon and Switzerland",
  "model": "gpt-4o",
  "created_at": "2026-03-15T15:00:00",
  "updated_at": "2026-03-15T15:05:00",
  "messages": [...]
}
```

### `static/index.html` — Chat UI

Single-page app with:
- **Sidebar**: chat history, new chat button, model selector
- **Chat area**: user/assistant message bubbles, markdown rendering (marked.js)
- **Tool calls**: shown as collapsible `<details>` elements with JSON results
- **Streaming**: tokens appear in real-time via SSE (`EventSource`-style parsing via `fetch` + `ReadableStream`)

## Setup

```bash
# 1. Install dependencies
pip install flask litellm python-dotenv

# 2. Configure API keys
cp .env.example .env
# Edit .env with your keys

# 3. Start the server
python -m agent.app --port 5000

# Options
python -m agent.app --model gpt-4o          # default
python -m agent.app --model anthropic/claude-sonnet-4-20250514
python -m agent.app --model ollama/llama3
python -m agent.app --host 0.0.0.0          # expose to network
python -m agent.app --debug                  # Flask debug mode
```

## Data Flow Example

User asks: *"Compare Lebanon and Switzerland"*

1. LLM decides to call `compare_countries(country1="Lebanon", country2="Switzerland")`
2. Tool loads both XML files → parses to trees → normalizes → computes TED via Chawathe
3. Returns: `{ted: 121, sim_ratio: 0.62, ops: {insert: 12, delete: 40, relabel: 69}}`
4. LLM may then call `compute_semantic_similarity(...)` for deeper analysis
5. Tool returns categorized changes: 69 relabels broken down by political/economic/etc.
6. LLM interprets the changes, assigns importance, produces a semantic score
7. LLM streams a natural-language response explaining the comparison

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| flask | >=3.0 | Web server + SSE streaming |
| litellm | >=1.40 | Multi-provider LLM abstraction |
| python-dotenv | >=1.0 | Load API keys from .env |

All other dependencies (wptools, pytest, etc.) are from the core pipeline.
