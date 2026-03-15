# Open Questions — Project 1

Questions still needing clarification before implementation.

---

## Design Questions (Pending)

*None — all questions resolved.*

---

## Resolved Questions (for reference)

| #  | Question                  | Answer                                                                                                                                        |
|----|---------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| 1  | Node types                | `element` (non-leaf) and `leaf` (text value)                                                                                                  |
| 2  | Tokenization              | Configurable via `config/tokenization.json`                                                                                                   |
| 3  | TED algorithm             | Implement BOTH Chawathe and Nierman & Jagadish, compare                                                                                       |
| 4  | Cost model                | Input JSON file                                                                                                                               |
| 5  | Similarity metrics        | All three: raw TED, `1/(1+TED)`, `1 - TED/(\|T1\|+ \|T2\|)`                                                                                   |
| 6  | Diff format               | Custom IDF XML (see CLAUDE.md)                                                                                                                |
| 7  | Storage                   | Plain XML files                                                                                                                               |
| 8  | Wikipedia extraction      | `wptools`                                                                                                                                     |
| 9  | UI                        | Functions + terminal prints/logs                                                                                                              |
| 10 | Team                      | Student + Claude                                                                                                                              |
| 11 | Course                    | Intelligent Data Processing and Applications (IDPA)                                                                                           |
| 12 | Test framework            | pytest                                                                                                                                        |
| 13 | Multi-value fields (Q1)   | **Option B**: `token_nodes` strategy creates `<item>` children; `single_node` creates flat leaf. Configurable via `config/tokenization.json`. |
| 14 | Ranking fields (Q2)       | **Included by default**; remove by adding to `_FILTER_PATTERNS` in `src/collection/xml_formatter.py` if needed.                               |
| 15 | established grouping (Q3) | **Grouped**: `<established><event><label>…</label><date>…</date></event></established>` — implemented in `xml_formatter.py`.                  |
