# A Pipeline for Comparing Semi-Structured Wikipedia Data Using Tree Edit Distance

## Abstract

This report describes the design and implementation of a Python pipeline that compares Wikipedia country infoboxes using Tree Edit Distance (TED). The system collects infobox data for all 192 UN member states, converts it to rooted ordered labeled trees, computes edit distance using two algorithms — Zhang-Shasha as described by Chawathe (1999) and the structure/content-aware variant by Nierman and Jagadish (2002) — extracts edit scripts, applies them as bidirectional patches with iterative refinement, and serializes results to multiple output formats including a custom XML diff specification. A supplementary LLM-powered agent extension adds semantic categorization and magnitude-aware analysis of structural differences. The pipeline is fully tested (57 unit and integration tests), operates via a CLI interface, and produces reproducible run artifacts with an audit trail.

## 1. Introduction

Wikipedia country infoboxes are semi-structured: they share a common template but vary in which fields are present, how values are formatted, and how deeply nested the data is. Comparing two countries requires more than string matching — it requires a structural comparison that accounts for insertions, deletions, and modifications at any level of the data hierarchy.

Tree Edit Distance provides a formal framework for this. Given two rooted ordered labeled trees, TED computes the minimum-cost sequence of edit operations (insert, delete, relabel) to transform one into the other. The resulting edit script describes exactly what differs between the two structures and how to reconcile them.

This project implements TED as part of a complete data processing pipeline: from raw Wikipedia data to structured comparison artifacts. The implementation emphasizes configurability (pluggable cost models, tokenization strategies, algorithm selection), reproducibility (timestamped run directories, summary CSV), and extensibility (an agent layer that adds semantic understanding to purely structural metrics).

## 2. System Architecture

The pipeline follows a sequential five-stage architecture. Each stage is implemented as an independent module with well-defined inputs and outputs, allowing stages to be run individually or composed into a full pipeline via the CLI.

**Stage 1 — Collection** transforms Wikipedia infobox markup into clean XML. **Stage 2 — Pre-processing** parses XML into tree objects. **Stage 3 — TED and Differencing** computes edit distance and produces edit scripts in a custom XML diff format. **Stage 4 — Patching** applies edit scripts to transform one tree into another. **Stage 5 — Post-processing** serializes results to XML, Wikipedia infobox text, and styled HTML.

All components share a common object model defined in four core classes.

## 3. Object-Oriented Data Model

The tree structure is represented by four classes that separate concerns between data representation (`Node`, `Tree`), edit operations (`Action`), and operation sequencing (`EditScript`).

**Node** stores a label (the XML tag name for element nodes, or the text content for leaf nodes), a node type discriminator (`element` or `leaf`), an ordered list of children, and a back-pointer to its parent. The dual link (parent and children) enables both top-down traversal for insertion and bottom-up path construction for the diff format. XML attributes, when present, are encoded as leaf children with the label format `attr_name=attr_value`, sorted alphabetically and placed before element children. This avoids introducing a separate attribute type while preserving attribute data in the tree structure.

**Tree** wraps a root `Node` and provides traversal utilities. Postorder traversal (children before parent) is the default iteration order and is required by Zhang-Shasha. Preorder traversal (parent before children) is used during insert operations where a parent must exist before its children are created.

**Action** represents a single edit operation with its type (`insert`, `delete`, or `relabel`), a cost drawn from the active cost model, a reference to the affected node, and an operation-specific arguments dictionary. For relabel operations, arguments contain the new label and optionally a reference to the corresponding target-tree node. For insert operations, arguments contain the parent node reference and insertion position. This heterogeneous argument design trades type safety for flexibility — a pragmatic choice given that only three operation types exist.

**EditScript** is an ordered sequence of `Action` objects with a running total cost. The invariant `total_cost == sum(action.cost for action in operations)` is maintained on every add and remove. Operations are stored in application order: relabels first, then deletes (postorder, so children before parents), then inserts (preorder, so parents before children).

## 4. Data Collection

The collection stage uses the `wptools` library to fetch infobox dictionaries from the Wikipedia API. Nearly all countries use the `Infobox country` template, with a few using `Infobox sovereign state`; the scraper handles both.

Raw infobox values contain wikitext markup that must be removed before structural comparison. The cleaning pipeline processes each field value through eleven sequential transformations: stripping HTML comments, removing `<ref>` citation tags, removing `{{Cite}}` and `{{efn}}` templates, unwrapping wiki links (`[[French language|French]]` becomes `French`), expanding `{{unbulleted list}}` templates into structured items, stripping remaining template calls (with recursive depth tracking for nested braces), and normalizing whitespace. The order of these transformations matters — wiki links inside templates must survive template removal, so link unwrapping runs after template stripping.

Fields are filtered before XML generation. Layout and rendering fields (`rowclass`, `titlestyle`, `image_*`), citation spillover (`last`, `date`, `url`, `publisher`), and reference fields (`*_ref`) are excluded. The remaining core data fields (approximately 50–70 per country) are retained. Field names are normalized through an alias map loaded from a JSON configuration file, resolving variants like `englishmotto` to the canonical `national_motto`.

Grouped fields receive special treatment. Leader title/name pairs are nested under a `<leaders>` element, and established event/date pairs under an `<established>` element, each containing structured child elements rather than flat siblings. This grouping preserves the semantic association between related fields in the tree structure.

All 192 UN member states were collected successfully with a polite one-second delay between API requests.

## 5. Pre-Processing

XML files are parsed into `Tree` objects using Python's `xml.etree.ElementTree`. Each XML element becomes an element `Node` whose label is the tag name. Text content becomes a leaf `Node` whose label is the text itself.

The tokenization strategy, loaded from a JSON configuration file, determines how text content is handled. The `single_node` strategy (default) creates one leaf per field value — suitable for country comparisons where field values are atomic units. The `token_nodes` strategy splits text into alphanumeric tokens using regex (`[A-Za-z0-9]+`), creating one leaf per token — useful when sub-field granularity matters. Multi-value fields like language lists produce `<item>` child elements under the `token_nodes` strategy.

After parsing, field names are normalized by applying the alias map to all element node labels via a preorder traversal.

## 6. Tree Edit Distance

### 6.1 Zhang-Shasha with Edit Script Extraction (Chawathe 1999)

The primary TED algorithm implements Zhang-Shasha dynamic programming, optimized using key roots and leftmost leaf decomposition.

For each node, the algorithm precomputes its leftmost leaf descendant (the leaf reached by always following the first child). Nodes that share the same leftmost leaf form a chain; only the node with the highest postorder index in each chain — the key root — requires a full DP subtable computation. This reduces the number of subtable computations from O(n) to at most the number of leaves, yielding O(nm) complexity for balanced trees rather than O(n²m²) in the worst case.

The DP fills subtables `fd[r][c]` for each key root pair. The recurrence distinguishes two cases. When both nodes lie on their key root's leftmost chain, the standard three-way minimum applies: delete the T1 node (`fd[r-1][c] + cost_delete`), insert the T2 node (`fd[r][c-1] + cost_insert`), or relabel (`fd[r-1][c-1] + cost_relabel`). When a node lies off the chain, the recurrence references the previously computed subtree distance `td[i][j]`, bridging across subtree boundaries.

Edit script extraction uses backtracking through the cached DP tables. Starting from the root pair, the algorithm traces which operation was taken at each cell by comparing the current value against the three possible predecessors (using epsilon tolerance for floating-point cost models). Matched pairs — where a T1 node corresponds to a T2 node — are collected. From these, three sets of operations are derived: relabels for matched pairs with different labels, deletes for unmatched T1 nodes (processed in postorder for correctness), and inserts for unmatched T2 nodes (processed in preorder so parents are created before children).

For insert operations, the edit script records not only the new node and its position but also the `source_parent` — the T1 node that was matched to the insertion parent in T2. This reference is critical for the patcher, which uses it to locate the correct parent in the modified tree via an identity map.

### 6.2 Nierman and Jagadish (2002)

The second algorithm reuses the entire Zhang-Shasha DP infrastructure with a single modification: the relabel cost function distinguishes between structural and content relabels. When two element nodes are relabeled (tag name change), the `relabel_structure` cost applies. When two leaf nodes are relabeled (text content change), the `relabel_content` cost applies. The cost model falls back to the generic `relabel` cost if the split costs are absent.

With uniform costs (`relabel_structure == relabel_content`), both algorithms produce identical results. Divergence occurs only when the cost model assigns different weights to structural versus content changes — for instance, making tag renames expensive while keeping text updates cheap.

### 6.3 Similarity Metrics

Three metrics are computed from each TED value. The raw TED is the absolute edit distance. The normalized inverse `1/(1+TED)` maps to (0, 1] and is useful for ranking but compresses large distances. The standard ratio `1 - TED/(|T1|+|T2|)` normalizes by tree sizes, giving an intuitive percentage-like similarity.

### 6.4 Cost Models

Cost models are loaded from JSON files, making them configurable without code changes. The default model assigns unit cost to all operations. An asymmetric model with `delete=2, insert=1, relabel=1` demonstrates that TED can be directional: when deletions are penalized, the cost of transforming a larger tree into a smaller one increases relative to the reverse direction. For Lebanon (173 nodes) to Switzerland (145 nodes), the asymmetric model yields TED=157 forward versus TED=129 reverse, confirming the expected asymmetry.

## 7. IDF Diff Format

Edit scripts are serialized to a custom XML format called IDPA Diff Format (IDF), registered under the namespace `urn:idpa:diff:1.0`. The format was designed to be self-contained: the root element carries the source and target country names, the algorithm used, and all three similarity metrics as attributes. An `<idf:operations>` container holds the individual operations, each with a sequential identifier.

Insert operations record the parent path (slash-separated label sequence from root) and position index. Delete operations record the full path to the deleted node. Relabel operations record the node path and contain `<idf:from>` and `<idf:to>` child elements with the old and new labels. This path-based representation makes IDF diffs human-readable and potentially applicable without the original tree objects.

## 8. Patching

The patcher applies an edit script to a deep copy of the source tree, preserving the original. Node identity is tracked through an `id_map` dictionary that maps `id()` values of original nodes to their copies. This enables the patcher to resolve references from the edit script (which points to nodes in the original trees) to their counterparts in the working copy.

Parent lookup during insert operations uses a three-level fallback. First, the `source_parent` reference (the T1 node matched to the insertion parent) is resolved via `id_map` — this is the most reliable method since it uses exact node identity. Second, the T2 parent node itself is checked in `id_map`, which succeeds when a previous insert already registered that node. Third, as a last resort, a label-path traversal searches the tree for a node matching the parent's slash-separated path. This fallback handles edge cases where `id_map` entries are stale due to structural modifications.

Reverse patching inverts each operation: relabels swap their from/to values, deletes become inserts (at the original position), and inserts become deletes. The reversed operations are applied in reverse order.

**Iterative refinement** addresses a practical limitation. When trees differ substantially in structure, applying the edit script in one pass can leave a non-zero residual TED — typically because deleting an ancestor also removes matched descendants. After the initial pass, the patcher computes TED between the result and the target. If non-zero, it extracts a fresh edit script for the residual difference, deep-copies the result, and applies the correction. This repeats for up to five rounds. In practice, one correction round suffices; the second round's residual is typically zero.

## 9. Post-Processing

Trees are serialized to four output formats. ASCII tree art renders the hierarchical structure with box-drawing connectors for visual inspection. XML serialization reconstructs a valid XML document, converting attribute-format leaf nodes (`key=value`) back to XML attributes. Wikipedia infobox text reconstructs the `{{Infobox country}}` wikitext template, expanding `<item>` children back into `{{unbulleted list}}` calls. HTML rendering produces styled Wikipedia-like infobox pages with fields organized by section.

A color-coded HTML diff report presents both forward and reverse edit scripts as tables with green rows for inserts, red for deletes, and yellow for relabels, alongside statistics bars showing operation counts per direction.

## 10. Agent Extension

The pipeline's TED metric is purely structural — all operations cost equally regardless of semantic significance. The agent extension adds an LLM-powered layer that interprets edit scripts in context.

The deterministic component categorizes each edit operation into one of eight semantic domains (political, economic, demographic, geographic, cultural, development, international, historical) based on the field name. For relabel operations on numeric values (GDP, population, area, HDI, Gini), the system parses both the old and new values and computes a magnitude ratio, absolute difference, and direction. This gives the LLM concrete quantitative context: a GDP per capita ratio of 8.3x signals a fundamentally different economy, while a Gini ratio of 0.99 indicates near-identical inequality levels.

Importance weighting is deliberately not hardcoded. The categorized and magnitude-annotated changes are passed to the LLM, which applies its own judgment about which differences are fundamental versus trivial. This design means the semantic analysis adapts to context and can reason about relationships that static weights cannot capture.

The agent is implemented as a Flask server with SSE streaming, using litellm for provider-agnostic LLM access (supporting OpenAI, Anthropic, and local endpoints). Ten tools wrap the pipeline's core functions, and a custom tool-calling loop executes up to fifteen iterations of tool use per query. Chat histories are persisted as JSON files.

## 11. Testing

The test suite comprises 57 tests across five modules. TED tests verify algorithmic properties including symmetry (`TED(T1,T2) == TED(T2,T1)` under uniform costs), triangle inequality, cost model adherence (edit script total cost equals TED), and algorithm divergence under split relabel costs. Patching tests verify bidirectional convergence (residual TED == 0), iterative refinement behavior, and correctness under asymmetric costs. All tests use small hand-crafted trees with known expected distances, ensuring deterministic verification independent of Wikipedia data.

## 12. Conclusion

This project demonstrates that a complete TED-based comparison pipeline — from raw web data to structured diffs, bidirectional patches, and semantic analysis — can be built as a modular, configurable system. Key design decisions include: JSON-based cost models enabling experimentation without code changes, iterative refinement guaranteeing patch convergence despite structural complexity, a self-contained XML diff format preserving all comparison metadata, and an LLM extension that bridges the gap between structural metrics and semantic understanding by providing magnitude-aware change categorization without hardcoded importance weights.

The pipeline successfully processes all 192 UN member states and produces reproducible comparison artifacts with a complete audit trail. The separation between deterministic computation (TED, categorization, magnitude detection) and judgment-based assessment (LLM importance weighting) reflects a broader design principle: automate what can be formalized, and delegate what requires contextual reasoning.

## References

[1] S. Chawathe, "Comparing hierarchical data in external memory," in *Proceedings of the 25th International Conference on Very Large Data Bases (VLDB)*, Edinburgh, Scotland, 1999, pp. 90–101.

[2] A. Nierman and H. V. Jagadish, "Evaluating structural similarity in XML documents," in *Proceedings of the 5th International Workshop on the Web and Databases (WebDB)*, Madison, WI, 2002, pp. 61–66.

[3] K. Zhang and D. Shasha, "Simple fast algorithms for the editing distance between trees and related problems," *SIAM Journal on Computing*, vol. 18, no. 6, pp. 1245–1262, 1989.

[4] wptools: Wikipedia tools (Python). [Online]. Available: https://github.com/siznax/wptools

[5] litellm: Call all LLM APIs using the OpenAI format. [Online]. Available: https://github.com/BerriAI/litellm