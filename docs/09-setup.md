# 09 · Setup & Running

## Prerequisites

- Windows 10/11 with PowerShell (the project's primary dev environment).
- Python 3.10+ (currently using 3.14).
- Docker Desktop (for MongoDB + mongo-express).
- A `.venv` already exists at `C:\dev\IDPA-Project\.venv` with deps installed.

## First-time setup

1. **Copy the env template and pick credentials**:

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

   Replace `changeme` and the basic-auth defaults with real values.

2. **Start MongoDB + mongo-express**:

   ```powershell
   docker compose up -d
   ```

   - Mongo on `127.0.0.1:27017`.
   - mongo-express at `http://localhost:8081`.

3. **Install Python deps** (only if `.venv` doesn't already have them):

   ```powershell
   .venv\Scripts\pip.exe install -r requirements.txt
   ```

   Use a real PowerShell terminal for this (not via Claude's bash tool —
   `pip install` is known to hang there).

4. **Ingest the 192 countries** (~15 minutes):

   ```powershell
   .venv\Scripts\python.exe scripts\ingest_countries.py --skip-existing --sleep 0.2
   ```

5. **Run the analysis to verify**:

   ```powershell
   .venv\Scripts\python.exe scripts\analyze_infoboxes.py
   ```

   Outputs `data/analysis/infobox_keys.csv`, `infobox_values.jsonl`,
   `infobox_summary.md`.

## Running the app

```powershell
.venv\Scripts\python.exe -m frontend.app --port 5050
```

Open `http://127.0.0.1:5050`. Three tabs: Countries / Compare / Patch.

The Flask app is non-debug by default; static-file changes need a
hard browser refresh (Ctrl+F5). Restart the Python process to pick
up server-side changes.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```

Five test files, ~111 tests:

- `test_core.py` — Node / Tree / Action / EditScript invariants.
- `test_parsing.py` — wikitext cleaning + typed value parsing.
- `test_taxonomy.py` — Taxonomy + EMD properties.
- `test_builder.py` — end-to-end tree building + distances.
- `test_ted.py` — Chawathe + N&J behavior, including subtree
  containment.

## Common operations

### Clear cached comparisons

After changing an algorithm or cost model:

```powershell
.venv\Scripts\python.exe -c "from src.storage.mongo_store import MongoStore; print(MongoStore().scripts.delete_many({}).deleted_count, 'cleared')"
```

### Compute one comparison from the CLI

```powershell
.venv\Scripts\python.exe -c "from src.comparison import compare; r = compare('Lebanon', 'Switzerland', algorithm='nierman_jagadish', cost_model='symmetric'); print(r.forward.script.total_cost, r.forward.script.counts_by_op())"
```

### Build one country tree

```powershell
.venv\Scripts\python.exe -c "from src.storage.mongo_store import MongoStore; from src.builder import build_country_tree; t = build_country_tree('Lebanon', MongoStore().get_country('Lebanon')['infobox']); open('lebanon.tree', 'w', encoding='utf-8').write(t.to_ascii())"
```

### Kill the Flask server when port 5050 is stuck

```powershell
Get-NetTCPConnection -LocalPort 5050 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id (Get-Variable -Name _ -ValueOnly).OwningProcess -Force -ErrorAction SilentlyContinue }
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `MongoStore().ping()` returns False | Check `docker compose ps`; restart with `docker compose up -d`. |
| Frontend shows old behaviour after code change | Restart Flask; hard-refresh browser. |
| `Invalid document: cannot encode datetime.date` | Should be fixed (`EditScript.to_dict` converts to ISO). If it re-appears, look for a new typed leaf returning a `date` that isn't serialized. |
| `Cannot insert into leaf node 'X'` from N&J | The cross-kind safety logic in N&J should prevent this. If it returns, the bug is in `_extract_mapping`'s kind check. |
| `KeyError: Unknown cost model 'X'` | Only `symmetric` and `asymmetric` are configured. Check `config/pipeline.json:ted_costs.models`. |
| Patched tree size doesn't match target | The script construction has regressed — re-check the strict-parent-preserving filter (Chawathe) or the cross-kind handling (N&J). |
| "Both" still shows in the algorithm dropdown | Hard-refresh; we removed it. |

## Files to know

- `config/pipeline.json` — the single source of truth.
- `src/comparison.py` — the orchestrator.
- `src/ted/chawathe.py`, `src/ted/nierman_jagadish.py` — the algorithms.
- `frontend/app.py` — every Flask route.
- `docs/` — this directory; start at `README.md`.
- `old/` — the pre-rebuild project, untouched. Useful for reference
  on the original IDF XML format, 7-phase expansion plans, dashboard,
  agent extension.
