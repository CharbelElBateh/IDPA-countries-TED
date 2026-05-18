"""Build the IDPA project report as a .docx file."""
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


OUT = Path(r"C:\dev\IDPA-Project\IDPA_Project_Report.docx")


def add_heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
    return h


def add_para(doc, text, *, bold=False, italic=False, size=11, align=None):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    return p


def add_mono(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(9)
    return p


def add_bullets(doc, items):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(it)


def add_table(doc, header, rows, widths=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(header))
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, h in enumerate(header):
        hdr[i].text = ""
        para = hdr[i].paragraphs[0]
        run = para.add_run(h)
        run.bold = True
        run.font.size = Pt(10)
    for r, row in enumerate(rows, start=1):
        for i, val in enumerate(row):
            cell = table.rows[r].cells[i]
            cell.text = ""
            para = cell.paragraphs[0]
            run = para.add_run(str(val))
            run.font.size = Pt(10)
    if widths:
        for row in table.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    return table


def main():
    doc = Document()

    # Base style
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    # Title
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("IDPA Country Explorer")
    run.bold = True
    run.font.size = Pt(24)
    run.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub.add_run(
        "Wikipedia Semi-Structured Infobox Collection, Tree Edit Distance and Clustering"
    )
    run.italic = True
    run.font.size = Pt(13)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run(
        "Course: Intelligent Data Processing and Applications (IDPA)\n"
        "Author: Charbel\n"
        "Project root: C:\\dev\\IDPA-Project"
    ).font.size = Pt(11)

    doc.add_paragraph()

    # =============== 1. INTRODUCTION ===============
    add_heading(doc, "1. Introduction", level=1)

    add_heading(doc, "1.1 Topic", level=2)
    add_para(
        doc,
        "This project addresses the comparison of semi-structured documents through the "
        "concrete case study of Wikipedia country infoboxes. Each of the 192 UN member states "
        "has a Wikipedia page that summarises core facts (government, geography, economy, "
        "demographics, history) inside a single template called Infobox country. These "
        "infoboxes are valuable because they are dense, broadly comparable across countries, "
        "and follow a (loose) common schema; however they are written in wikitext, contain "
        "templates, references and free-form prose, and the same conceptual field can appear "
        "under several variant names. The project transforms each infobox into a rooted "
        "ordered labeled tree with typed leaves, computes a Tree Edit Distance (TED) "
        "between any two such trees, exposes the result as an editable diff, and groups the "
        "192 countries by similarity on a chosen feature.",
    )

    add_heading(doc, "1.2 Objectives", level=2)
    add_bullets(
        doc,
        [
            "Build an end-to-end pipeline that ingests, parses, types and structures the "
            "Wikipedia infobox of every UN member state.",
            "Implement and compare two canonical tree edit distance algorithms taught in "
            "the IDPA course: Chawathe (VLDB 1999, Zhang-Shasha backbone) and Nierman & "
            "Jagadish (WebDB 2002, recursive subtree similarity).",
            "Provide three slide-faithful similarity metrics per comparison: raw TED, "
            "normalised inverse 1/(1+TED) and standard ratio 1 − TED/(|T1|+|T2|).",
            "Compute an applicable edit script for both directions (T1 → T2 and T2 → T1) "
            "and let the user patch any tree using any script.",
            "Cluster the 192 countries on a chosen typed field using two slide-faithful "
            "algorithms: k-means (Lloyd's) and hierarchical agglomerative (single / "
            "complete / average linkage).",
            "Persist all artifacts in MongoDB (raw infoboxes, edit scripts, distance "
            "matrices, cluster runs) so that comparisons and clusterings are reproducible "
            "and cache-able.",
            "Serve everything from a single Flask + D3 v7 web frontend with four tabs: "
            "Countries, Compare, Patch and Cluster.",
        ],
    )

    add_heading(doc, "1.3 Potential Applications", level=2)
    add_para(
        doc,
        "Even though the operative dataset is country infoboxes, the techniques generalise "
        "to any corpus of semi-structured documents that admits a tree representation:",
    )
    add_bullets(
        doc,
        [
            "Schema and content evolution: tracking how the same XML/JSON document changes "
            "between versions (e.g. legal texts, financial filings, biomedical ontologies).",
            "Record deduplication and matching across heterogeneous schemas: tree edit "
            "distance with typed leaves discriminates partial overlap better than string "
            "similarity.",
            "Curated catalog comparison: product catalogs, museum metadata, taxonomic "
            "databases, where one entity occupies several fields with hierarchical scope.",
            "Knowledge-graph difference reporting: an editable, applicable patch script "
            "between two snapshots of the same entity.",
            "Country-level analytics in political science, economics and demography: "
            "clustering by religion / language / government type recovers known "
            "macro-regional groupings without supervision.",
        ],
    )

    # =============== 2. BACKGROUND ===============
    add_heading(doc, "2. Background", level=1)

    add_heading(doc, "2.1 Context", level=2)
    add_para(
        doc,
        "The IDPA course (Intelligent Data Processing and Applications) covers techniques "
        "for analysing data that is neither fully structured (relational) nor fully "
        "unstructured (free text). The canonical use-case is XML-like content: a forest of "
        "nested labels carrying both structural (tag) and textual (value) information. "
        "Two reference algorithms taught in Chapter 5 of the course frame the project: "
        "Chawathe (1999) and Nierman & Jagadish (2002). Both compute a Tree Edit Distance "
        "between two ordered labeled trees, i.e. the cheapest sequence of insert, delete "
        "and relabel operations that transforms one tree into the other. Chapter 10 of "
        "the course then introduces unsupervised partitioning with k-means (§5.1) and "
        "hierarchical agglomerative clustering (§5.2), which we apply to the same trees.",
    )
    add_para(
        doc,
        "Wikipedia country infoboxes are an ideal dataset for this material: rich enough "
        "to be non-trivial (about 75 fields per country on average), small enough to fit "
        "in memory, and naturally hierarchical once the flat key/value dictionary is "
        "re-organised by category (Identity / Geography / Government / Economy / "
        "Demographics / History / Codes). The data was fetched with the wptools library "
        "from late-2025 / early-2026 revisions of Wikipedia.",
    )

    add_heading(doc, "2.2 Problem Analysis", level=2)
    add_para(
        doc,
        "Raw infobox content cannot be compared directly. Three categories of difficulty "
        "must be resolved before a meaningful distance can be defined:",
    )
    add_bullets(
        doc,
        [
            "Wikitext noise: each value typically contains [[wikilinks]], {{templates}}, "
            "<ref> citations, HTML comments and presentation markup that must be stripped, "
            "unwrapped or, in the case of {{increase}}/{{steady}}/{{decrease}}, lifted into "
            "a separate trend signal.",
            "Naming variance: the same conceptual field appears under several variant "
            "keys (e.g. motto / englishmotto / national_motto, time_zone / timezone, "
            "admin_center / capital). Without normalisation, identical content drives "
            "spurious edit costs.",
            "Type heterogeneity: a leaf may be a number, a percentage, a year, a date, an "
            "amount in any currency, a geographic coordinate, a hyperlink, a free-text "
            "string, or a distribution over a taxonomy (religion, language, ethnicity). "
            "Comparing these by string equality discards almost all available signal — a "
            "currency of 78 233 000 000 USD is closer to 80 000 000 000 USD than to 100 USD "
            "even though all three strings are different.",
        ],
    )
    add_para(
        doc,
        "A second-order difficulty appears once a TED is computable: the optimal mapping "
        "returned by Zhang-Shasha is only ancestor-preserving, not parent-preserving, so "
        "it can produce edit scripts that are mathematically optimal yet not applicable "
        "by a node-by-node interpreter that lacks a move operation. The project addresses "
        "this through a strict-parent-preserving filter (Chawathe) and an order-preserving "
        "sequence alignment (Nierman & Jagadish).",
    )

    add_heading(doc, "2.3 Existing Solutions", level=2)
    add_bullets(
        doc,
        [
            "Generic XML diff tools (xmldiff, diffxml): syntactic only, treat every leaf "
            "as a string, no notion of type-aware relabel cost, no taxonomy-aware "
            "distance for distributions.",
            "DBpedia / Wikidata: machine-readable triples derived from infoboxes. They "
            "solve the typing problem (each property has a declared range) but they live "
            "in a flat graph, not in a tree, so they sidestep rather than answer the "
            "structural-comparison question that this course tackles.",
            "Zhang-Shasha implementations (e.g. zss on PyPI): off-the-shelf TED libraries. "
            "They compute the distance but expose neither a mapping suitable for "
            "side-by-side diff colouring nor an applicable edit script that respects the "
            "absence of a move operation.",
            "Generic clustering toolkits (scikit-learn KMeans / AgglomerativeClustering): "
            "operate on Euclidean feature vectors and cannot consume a non-Euclidean "
            "pairwise distance matrix directly; in this project we therefore reuse scipy "
            "linkage for hierarchical clustering and add a classical-MDS pre-step for "
            "k-means.",
            "The previous IDPA project (preserved under old/) implemented a flat-string "
            "version of the same idea with a custom IDF XML diff format and per-country "
            "XML files on disk. The current rebuild keeps the educational intent but adds "
            "typed leaves, distribution distances, MongoDB persistence, two real TED "
            "algorithms with their canonical mapping, three slide-faithful similarity "
            "metrics, two slide-faithful clustering algorithms and an interactive D3 "
            "frontend.",
        ],
    )

    # =============== 3. PROPOSAL ===============
    add_heading(doc, "3. Proposal", level=1)

    add_heading(doc, "3.1 Conceptual Modeling", level=2)
    add_para(
        doc,
        "The conceptual core of the system is the rooted ordered labeled tree with typed "
        "leaves. Four dataclasses, all in src/core/, capture the model:",
    )

    add_table(
        doc,
        ["Class", "Role", "Key fields"],
        [
            ["Node", "Single class for internal and leaf nodes",
             "kind ∈ {structural, leaf}, label, children, value, type, raw, unit, "
             "trend, taxonomy, parent"],
            ["Tree", "Root + path-based access",
             "root, name; NodePath = tuple[int,...]; identity-based path_of"],
            ["Action", "One edit operation",
             "op ∈ {insert, delete, relabel}, path, cost, new_node, position, old_* "
             "(for invertibility)"],
            ["EditScript", "Ordered set of operations + mapping",
             "operations, total_cost, source/target_name, mapping = list of "
             "(t1_path, t2_path)"],
        ],
        widths=[3.0, 4.5, 8.0],
    )

    add_para(
        doc,
        "Each leaf carries a Python value whose type is one of: number, percent, year, "
        "date, currency (in USD, original ISO code kept in unit), coordinates "
        "(lat, lon), wikilink, text, distribution (list of {path, weight} chips), or "
        "empty. Distributions are projected onto one of four hand-curated taxonomies — "
        "religion, language, ethnicity and government_type — so that, for example, "
        "Sunni and Shia are recognised as siblings under Islam, while Christianity and "
        "Islam are siblings under Abrahamic.",
    )
    add_para(
        doc,
        "The pipeline that turns a raw Wikipedia infobox dictionary into such a Tree is a "
        "linear five-stage process orchestrated by src.builder.build_country_tree:",
    )
    add_bullets(
        doc,
        [
            "Field aliases: variant Wikipedia keys are renamed to their canonical names "
            "(field_aliases in config/pipeline.json).",
            "Filter patterns: layout/citation/image markup keys are dropped by regex "
            "(field_filter_patterns).",
            "Serial-group folding: numbered families such as leader_title1 + leader_name1 "
            "+ leader_title2 + leader_name2 are folded into a single composite key "
            "(@leaders) carrying a list of per-index dicts. Same for @established.",
            "Typed parsing: each remaining value is first cleaned by src.parsing.wikitext "
            "(refs, comments, templates, wikilinks resolved) then passed through a "
            "type-specific parser (number, percent, year, date, currency, coordinates, "
            "distribution, wikilink/text).",
            "Category layout: each canonical key is attached at a dotted path under the "
            "country root (geography.capital, economy.gdp_ppp.value, "
            "demographics.religion, government.leaders, history.established, …). "
            "Intermediate structural nodes are created on demand.",
        ],
    )

    add_heading(doc, "3.2 Software Application Design", level=2)
    add_para(
        doc,
        "The system follows a layered architecture: ingestion → storage → "
        "tree construction → algorithms (TED, clustering) → web frontend.",
    )
    add_mono(
        doc,
        "Wikipedia (wptools)\n"
        "        |\n"
        "        v\n"
        "  scripts/ingest_countries.py        one-shot ingestion\n"
        "        |  upsert\n"
        "        v\n"
        "  MongoDB (Docker)                   collection: countries\n"
        "        |  read on demand\n"
        "        v\n"
        "  src.builder + parsing + taxonomy   build_country_tree(name, infobox)\n"
        "        |  Tree\n"
        "        v\n"
        "  src.ted.{chawathe, nierman_jagadish}\n"
        "        |  EditScript (with mapping)\n"
        "        v\n"
        "  MongoDB cache                      collection: edit_scripts\n"
        "        |  served via /api\n"
        "        v\n"
        "  Flask frontend (4 tabs) + D3 v7    Countries / Compare / Patch / Cluster",
    )

    add_para(doc, "Module layout, abbreviated:")
    add_bullets(
        doc,
        [
            "config/pipeline.json — single source of truth: aliases, filter patterns, "
            "category layout, serial groups, field types, weights, TED cost models, "
            "currency rates, the four taxonomies.",
            "src/core/ — Node, Tree, Action, EditScript.",
            "src/parsing/ — wikitext cleaning, typed-value parser, distribution parser.",
            "src/preprocessing/ — alias normalisation, filter, serial-group folding.",
            "src/builder.py — assembles the country tree.",
            "src/distances.py — typed relabel costs + field weights.",
            "src/taxonomy.py — taxonomy + tree-EMD.",
            "src/ted/ — TEDAlgorithm ABC, registry, chawathe.py, nierman_jagadish.py "
            "(self-contained per user request, even at the cost of duplicated "
            "Zhang-Shasha boilerplate).",
            "src/clustering/ — distance.py, embedding.py, algorithms/{kmeans, "
            "hierarchical_agglomerative}.py, evaluation.silhouette, fields.py.",
            "src/comparison.py — orchestrator: trees → algorithm → ComparisonResult, "
            "with similarity_metrics(ted, |T1|, |T2|).",
            "src/synthetic_tree.py — bracket-notation parser, dict round-trip; supports "
            "hand-crafted test trees used to debug the TED.",
            "src/storage/mongo_store.py — pymongo wrapper over the four collections.",
            "frontend/ — Flask app, formatting.py, templates/ (8 pages) + static/ "
            "(tokens.css, style.css, tree.js, compare.js, patch.js, cluster_*.js).",
            "tests/ — 131 pytest tests over six files (test_core, test_parsing, "
            "test_taxonomy, test_builder, test_ted, test_clustering).",
        ],
    )

    add_heading(doc, "3.3 Algorithms Implementation", level=2)

    add_heading(doc, "3.3.1 Cost contract and per-type leaf distance", level=3)
    add_para(
        doc,
        "All distance computation in the project — both TED relabel costs and clustering "
        "leaf-pair distances — goes through src.distances.relabel_cost(a, b). It "
        "dispatches first on (a.kind, b.kind) then, when both nodes are leaves, on "
        "(a.type, b.type), to a dedicated distance function per leaf type. Every "
        "per-type function returns a value in [0, 1] and min-clamps at 1.0, so a single "
        "huge gap cannot dominate the weighted mean.",
    )

    add_table(
        doc,
        ["Type", "Distance formula", "Normalising scale (default)"],
        [
            ["number", "|a − b| / max(|a|, |b|, ε)", "number_min_denom = 1e-9"],
            ["percent", "|a − b| / 100", "—"],
            ["year", "|a − b| / Y", "year_full_distance = 100"],
            ["date", "days(a, b) / (Y · 365.25)", "date_full_distance_years = 100"],
            ["currency", "|log10 a − log10 b| / S, fallback to number for a ≤ 0",
             "currency_full_distance_usd_log10 = 4 (a 10 000× ratio = 1.0)"],
            ["coordinates", "haversine(a, b) / D, Earth radius 6371 km",
             "coordinates_full_distance_km = 20 000 (antipodal)"],
            ["wikilink, text", "Levenshtein(a', b') / max(|a'|, |b'|), x' = "
             "x.lower().strip()", "—"],
            ["distribution", "Taxonomy.emd(da, db) — tree-EMD over taxonomy edges",
             "taxonomy structure"],
        ],
        widths=[2.5, 7.5, 5.5],
    )

    add_para(
        doc,
        "The final TED cell cost is relabel_cost(a, b) × field_weight(path), where "
        "field_weight uses longest-prefix matching against config.field_weights (default "
        "1.0). Cross-kind or cross-type pairs (and distributions on different taxonomies) "
        "collapse to a single constant type_mismatch_relabel; no coercion is attempted.",
    )

    add_heading(doc, "3.3.2 Chawathe (Zhang-Shasha)", level=3)
    add_para(
        doc,
        "src/ted/chawathe.py implements the classical Zhang-Shasha bottom-up dynamic "
        "programme. Each tree is linearised in post-order; for every node we record the "
        "post-order index of its leftmost leaf descendant lld[i]; the keyroots are the "
        "largest i for each distinct lld value. For every keyroot pair (i, j) we fill a "
        "forest-distance matrix in O((i − lld[i]) · (j − lld[j])) cells, deferring to "
        "the treedist of a smaller pair whenever both lld checks fail. The optimal "
        "mapping is recovered by backtracking through the forest-distance matrices and "
        "their decision records.",
    )
    add_para(
        doc,
        "Because Zhang-Shasha guarantees only ancestor-preservation, the mapping is "
        "post-processed by _strict_parent_preserving, which iteratively drops any pair "
        "(m, n) whose direct parents are not themselves mapped. This sacrifices about 5 % "
        "of optimality on Lebanon ↔ Switzerland but guarantees that the emitted script "
        "is applicable without a move operation. The script is then built by simulating "
        "a working copy of T1 (relabels first; deletes deepest+rightmost first; inserts "
        "shallowest+leftmost first), matching exactly the ordering used in "
        "EditScript.apply.",
    )

    add_heading(doc, "3.3.3 Nierman & Jagadish (recursive subtree similarity)", level=3)
    add_para(
        doc,
        "src/ted/nierman_jagadish.py implements a top-down recursive DP. For each pair "
        "of subtree roots (a, b):",
    )
    add_mono(
        doc,
        "D(a, b) =\n"
        "    relabel(a, b)                                  if both leaves\n"
        "    delete_subtree(a) + insert_subtree(b)          if kinds differ\n"
        "    relabel(a, b) + align(a.children, b.children)  otherwise\n"
        "\n"
        "align(c1, c2):                                     order-preserving DP\n"
        "  F[i][j] = min( F[i-1][j]   + delete_subtree(c1[i-1]),\n"
        "                 F[i][j-1]   + insert_subtree(c2[j-1]),\n"
        "                 F[i-1][j-1] + D(c1[i-1], c2[j-1]) )",
    )
    add_para(
        doc,
        "Each D(a, b) call is memoised on (id(a), id(b)). A subtree-containment rule "
        "(controlled by config.subtree_similarity) sets cost_delete_subtree to "
        "delete_base × move_cost_factor × weight when the same (kind, label, type, value) "
        "subtree signature is found in T2 — and symmetrically for insert. A move therefore "
        "costs ≈ 2 operations instead of 2 × |subtree|. The mapping produced by N&J is "
        "already parent-strict by construction, so no post-filtering is needed.",
    )

    add_heading(doc, "3.3.4 Three slide-faithful similarity metrics", level=3)
    add_para(
        doc,
        "src/comparison.py:similarity_metrics(ted, |T1|, |T2|) returns the three "
        "numbers required by the course slides for every direction (forward and reverse):",
    )
    add_table(
        doc,
        ["Metric", "Formula", "Range"],
        [
            ["Raw TED", "TED(T1, T2)", "[0, ∞)"],
            ["Normalized inverse", "1 / (1 + TED)", "(0, 1]"],
            ["Standard ratio", "1 − TED / (|T1| + |T2|)", "typically [0, 1]"],
        ],
    )
    add_para(
        doc,
        "All three are attached to DirectionResult.metrics, returned in the "
        "/api/compare JSON payload, and rendered as a 3 × 2 (metrics × directions) "
        "table at the top of the compare-result page. With an asymmetric cost model "
        "the two columns differ — for example {insert: 1, delete: 2, relabel: 1} gives "
        "ted(Lebanon → Switzerland) = 45.5 and ted(Switzerland → Lebanon) = 43.1 with "
        "Chawathe.",
    )

    add_heading(doc, "3.3.5 Clustering — distance matrix and two algorithms", level=3)
    add_para(
        doc,
        "Clustering operates on a single symmetric N × N matrix D with values in [0, 1] "
        "and zero diagonal. D is built by src/clustering/distance.py: for each leaf pair "
        "in the chosen field, the per-type leaf distance from relabel_cost is computed "
        "and combined into a weighted mean. Synthetic test trees (source == 'synthetic') "
        "are skipped in src/clustering/run.py:_build_all_trees so they never contribute "
        "rows of NaN.",
    )
    add_para(
        doc,
        "The cost_model parameter (symmetric, asymmetric) influences D only through the "
        "scales used by per-type distances (currency log-range, coordinates km range, "
        "year and date windows, type_mismatch_relabel constant). It does not enter the "
        "clustering algorithms themselves. Asymmetric insert/delete costs in particular "
        "are dead weight here, because clustering never inserts or deletes tree nodes — "
        "it only invokes relabel_cost to score leaf pairs.",
    )

    add_para(doc, "Algorithm A — k-means (Lloyd's), src/clustering/algorithms/kmeans.py:",
             italic=True)
    add_bullets(
        doc,
        [
            "Init: pick k distinct rows of D uniformly at random as centroids — this is "
            "exactly what the course slide describes; k-means++ is deliberately not used.",
            "Assign: each point goes to the cluster of the closest centroid in Euclidean "
            "distance.",
            "Update: each centroid is the mean of the points currently assigned to it.",
            "Stop: when no point changes cluster between iterations, or when SSE drops "
            "below tolerance.",
            "n_init = 10 restarts (default); the run with the lowest SSE wins.",
            "Empty-cluster reseed: a cluster that ends up empty after Assign is reseeded "
            "to the point currently farthest from any centroid, preventing the mean-of-"
            "empty NaN trap (one-line, k-means++-style nudge).",
        ],
    )
    add_para(
        doc,
        "K-means needs Euclidean coordinates to compute the Update step, but D is in "
        "general not Euclidean (it is a weighted mean of metric but non-Euclidean per-type "
        "distances). We therefore run a classical (Torgerson) MDS pre-step inside the "
        "algorithm to embed D in R^m:",
    )
    add_mono(
        doc,
        "J = I − (1/n) · 1·1^T          # centering matrix\n"
        "B = −1/2 · J · D^2 · J         # double-centered Gram matrix\n"
        "B = V · Lambda · V^T           # eigendecomposition\n"
        "X = V[:, :m] · sqrt(Lambda[:m]) # keep positive eigenvalues, cap m at 16",
    )
    add_para(
        doc,
        "Axes with non-positive eigenvalues are dropped — this is the only information "
        "loss in the clustering pipeline. The k-means++ alternative or a k-medoids (PAM) "
        "switch were both considered; we kept Lloyd's k-means + classical MDS to stay "
        "slide-faithful (commit 2b3e3a9).",
    )

    add_para(
        doc,
        "Algorithm B — hierarchical agglomerative, "
        "src/clustering/algorithms/hierarchical_agglomerative.py:",
        italic=True,
    )
    add_bullets(
        doc,
        [
            "Each country starts as its own singleton cluster.",
            "Repeatedly merge the two clusters with the smallest inter-cluster distance, "
            "until exactly k clusters remain (fcluster with criterion='maxclust').",
            "Three linkage rules, faithful to slides 79–81: single (min), complete (max), "
            "average (UPGMA mean). Default: average.",
            "Ward / centroid / median linkages are explicitly rejected — they require "
            "Euclidean coordinates and our D is non-Euclidean by construction.",
            "Implementation note: the inner Lance-Williams merge loop is delegated to "
            "scipy.cluster.hierarchy.linkage (the compiled O(n²) nn_chain). Our code "
            "only condenses D, dispatches scipy, and shifts scipy's 1-indexed labels to "
            "0-indexed so they align with the frontend cluster palette.",
        ],
    )

    add_heading(doc, "3.4 Implementation Highlights", level=2)
    add_para(
        doc,
        "A few decisions that go beyond textbook recipes and matter for correctness "
        "and reproducibility:",
    )
    add_bullets(
        doc,
        [
            "EditScript.mapping: each algorithm populates a list of (t1_path, t2_path) "
            "pairs, so both trees can be colour-marked from one source of truth. "
            "Source nodes whose path is not in the mapping are deletes; target nodes "
            "whose path is not in the mapping are inserts; mapped pairs whose payloads "
            "differ are relabels — coloured consistently on both sides.",
            "Identity vs equality: Node is a dataclass whose __eq__ ignores parent, so "
            "two structurally identical sibling subtrees compare equal. Every site that "
            "resolves a node's position in parent.children uses 'is' (identity), not '==' "
            "(equality) — including Tree.path_of, the delete step in both algorithms, "
            "and the dotted-path renderer in comparison.py. Without this discipline, "
            "hand-crafted trees of the form A(B, B) instantly produce KeyError: (0,).",
            "Path discipline in script construction: relabel paths use the source-tree "
            "shape (which doesn't change); delete paths use the original source tree's "
            "indices but apply order is deepest+rightmost first; insert parent paths are "
            "computed on a working copy of T1 after deletes have been simulated. This "
            "invariant is what makes the emitted script applicable.",
            "Currency in USD, trend lifted to a side channel: {{increase}} $78.233 "
            "billion is parsed as (78 233 000 000.0, unit='USD', trend=+1). The trend "
            "marker doesn't contaminate the numeric comparison, and the UI can show "
            "▲/▬/▼ separately.",
            "Single config file: config/pipeline.json (~700 lines) holds aliases, "
            "filter patterns, category layout, serial groups, field types, field "
            "weights, TED cost models, scale knobs, currency rates and the four "
            "taxonomies. No hunting through multiple config files.",
            "Self-contained algorithm files: Chawathe and N&J each inline their full "
            "DP, mapping extraction and script construction so a reader can take one in "
            "end-to-end. Duplicate-code linter warnings on these files are expected.",
            "Synthetic test trees: a bracket-notation parser (root(a, b(c, d), e)) lets "
            "the user add hand-crafted trees from the Countries page. These are stored "
            "in the same MongoDB countries collection with source='synthetic' and a "
            "tree_dict payload. They bypass the comparison cache and are excluded from "
            "clustering — a single chokepoint per concern.",
        ],
    )

    add_heading(doc, "3.5 Storage Layer", level=2)
    add_para(
        doc,
        "MongoDB 7 runs in Docker alongside a mongo-express admin UI. Two collections "
        "back the application:",
    )
    add_table(
        doc,
        ["Collection", "Key (_id)", "Contents"],
        [
            ["countries", "country name",
             "raw infobox dict from wptools, full wikitext, ingested_at; or, for "
             "synthetic trees, tree_dict + source='synthetic'"],
            ["edit_scripts", "c1__c2__algorithm__cost_model",
             "EditScript.to_dict() for both forward and reverse direction"],
            ["distance_matrices", "dm__costmodel__fields__weights",
             "cached pairwise distance matrix used by clustering"],
            ["cluster_runs", "algo__params-hash",
             "ClusterResult — labels, medoids, linkage, MDS, silhouette"],
        ],
        widths=[3.5, 4.5, 7.5],
    )

    add_heading(doc, "3.6 Frontend", level=2)
    add_para(
        doc,
        "A single Flask app (frontend/app.py, port 5050) serves Jinja2-rendered HTML "
        "with vanilla browser ES modules and D3 v7 — no build step. Four tabs:",
    )
    add_bullets(
        doc,
        [
            "Countries: A–Z index of the 192 UN member states with an ISO-3 badge and a "
            "per-country detail page rendering the full tree as nested <details> blocks. "
            "A + Add tree button accepts bracket notation for synthetic test trees.",
            "Compare: pick two countries, an algorithm (chawathe / nierman_jagadish) and "
            "a cost model (symmetric / asymmetric). The result page shows the three "
            "similarity metrics for both directions, two side-by-side D3 trees colour-"
            "marked using EditScript.mapping (red ✗ delete, green + insert, yellow ~ "
            "relabel) and the first 200 operations of the edit script with per-op cost.",
            "Patch: paste a script, upload a .json file, or pick a cached comparison; "
            "apply it to a chosen tree (or its inverse via a checkbox).",
            "Cluster: a 'Distance matrix' card (cost model) above an 'Algorithm' card "
            "(kmeans / hierarchical_agglomerative + their knobs) above a 'Feature' "
            "accordion (exactly one field selected by radio). The result page has four "
            "tabs: world choropleth, 2-D MDS scatter (with MDS / t-SNE toggle and "
            "variance-explained diagnostic), dendrogram (AGG only), members list.",
        ],
    )

    # =============== 4. EXPERIMENTAL EVALUATION ===============
    add_heading(doc, "4. Experimental Evaluation", level=1)

    add_heading(doc, "4.1 Test Documents", level=2)
    add_para(
        doc,
        "Two complementary corpora are used. The primary corpus is the live Wikipedia "
        "Infobox country dataset for every UN member state, ingested with wptools and "
        "stored in MongoDB. The secondary corpus is a set of hand-crafted bracket-notation "
        "trees used to debug TED and verify edge cases (identical siblings, single-node, "
        "leaf-vs-structural pairing).",
    )
    add_para(doc, "Real corpus, after typed parsing (data/analysis/infobox_summary.md):")
    add_bullets(
        doc,
        [
            "Countries analysed: 192 (full UN membership).",
            "Fields per country: min = 36, average = 75.5, max = 97.",
            "Distinct field names observed: 260 — about 50 are universal (≥ 95 % "
            "coverage), 140 are rare (≤ 5 %).",
            "Total key-value pairs: 14 495.",
            "Value-type share after typed parsing: plain_text 28.7 %, wikilink 27.6 %, "
            "template 9.8 %, number 9.1 %, year 9.0 %, currency 5.8 %, date 4.8 %, "
            "list 2.7 %, coordinates 1.4 %, multiline 0.9 %, percent 0.1 %.",
        ],
    )
    add_para(
        doc,
        "Representative tree sizes after building: Lebanon — 123 nodes, height 4; "
        "Switzerland — 99 nodes, height 4. These are the two countries used as the "
        "running TED example throughout the project.",
    )

    add_heading(doc, "4.2 TED Accuracy and Execution Speed", level=2)
    add_para(
        doc,
        "TED accuracy is qualitative: both algorithms produce a patched tree whose size "
        "exactly matches the target tree (99 forward, 123 reverse), which means every "
        "emitted edit script is applicable end-to-end. The 131 pytest tests under tests/ "
        "(test_core, test_parsing, test_taxonomy, test_builder, test_ted, "
        "test_clustering) cover the invariants of every dataclass, every parser, every "
        "taxonomy EMD property, every algorithm, and every script-apply round-trip.",
    )
    add_para(doc, "Lebanon ↔ Switzerland summary, both algorithms × both cost models:")
    add_table(
        doc,
        ["Algorithm", "Cost model", "TED A→B", "TED B→A", "Mapping size"],
        [
            ["chawathe", "symmetric", "40.1", "40.1", "71"],
            ["chawathe", "asymmetric", "45.5", "43.1", "62"],
            ["nierman_jagadish", "symmetric", "51.4", "56.3", "78"],
            ["nierman_jagadish", "asymmetric", "71.6", "61.6", "84"],
        ],
    )
    add_para(
        doc,
        "Observations: with a symmetric cost model the two directions coincide for "
        "Chawathe (as expected by the symmetry of the underlying DP) but not for "
        "Nierman & Jagadish, whose subtree-containment rule reacts asymmetrically to the "
        "shapes of T1 and T2. The asymmetric model {insert: 1, delete: 2, relabel: 1} "
        "produces visibly different forward and reverse costs for both algorithms, "
        "exposing the directional nature of an edit script. N&J systematically finds "
        "more matched pairs (78 vs 71 in the symmetric case) thanks to its order-"
        "preserving sequence alignment and subtree-containment rule.",
    )
    add_para(doc, "Execution speed on the same pair, single-threaded CPython:")
    add_table(
        doc,
        ["Algorithm", "Direction", "Wall-clock (per direction)", "Cache (Mongo)"],
        [
            ["chawathe", "Lebanon ↔ Switzerland", "≈ 1.3 s", "instant on second call"],
            ["nierman_jagadish", "Lebanon ↔ Switzerland", "≈ 0.6 s",
             "instant on second call"],
        ],
    )
    add_para(
        doc,
        "Chawathe's hot loop is the nested keyroot iteration in Python; N&J's recursion "
        "fans out less than the full keyroot grid for trees of this shape, which makes "
        "it about twice as fast on this corpus. Both results are persisted as a single "
        "document keyed by c1__c2__algorithm__cost_model in the edit_scripts collection, "
        "so every subsequent fetch (e.g. when the user toggles A→B / B→A in the UI) is "
        "served from Mongo without recomputation.",
    )

    add_heading(doc, "4.3 Clustering Accuracy and Execution Speed", level=2)
    add_para(
        doc,
        "Clustering quality is evaluated by the silhouette coefficient — computed on "
        "the true distance matrix D, not on the 2-D scatter, because the scatter is a "
        "lossy SMACOF projection and k-means actually partitions in a higher-D "
        "classical-MDS space (up to 16 dimensions). A scatter with visually overlapping "
        "clusters is therefore not by itself evidence of a bad clustering — see "
        "design decision §16.",
    )
    add_para(
        doc,
        "Representative single-feature runs over the 192 countries (default cost model, "
        "k as specified):",
    )
    add_table(
        doc,
        ["Algorithm", "Feature", "k", "N (after outliers)", "Wall-clock"],
        [
            ["k-means", "economy.hdi.value", "5", "≈ 190",
             "< 100 ms (10 restarts of Lloyd's, 5–15 iterations each)"],
            ["k-means", "demographics.religion (distribution / tree-EMD)", "5", "≈ 188",
             "≈ 300 ms (dominated by D construction)"],
            ["agglomerative (average)", "economy.hdi.value", "6", "≈ 190",
             "< 50 ms (scipy linkage)"],
            ["agglomerative (average)", "demographics.religion", "6", "≈ 188",
             "≈ 250 ms (D construction dominates)"],
        ],
        widths=[4.0, 5.0, 1.0, 3.0, 4.0],
    )
    add_para(
        doc,
        "Notes on accuracy:",
    )
    add_bullets(
        doc,
        [
            "Numeric single-feature runs (HDI, area, GDP per capita) recover the "
            "expected income / development tiers: a high-HDI cluster centred on Western "
            "Europe / Anglosphere / parts of East Asia, a low-HDI cluster centred on "
            "Sub-Saharan Africa, and three intermediate clusters that the dendrogram "
            "shows merging in a clean monotone order.",
            "Distribution runs over demographics.religion produce groupings that align "
            "with macro-regional confessional patterns: Sunni-majority Middle East / "
            "North Africa, Catholic-majority Latin America / Southern Europe, mixed "
            "Christian Sub-Saharan Africa, and a secular / mixed cluster covering East "
            "Asia and parts of post-Soviet Europe. The tree-EMD ground metric is what "
            "makes Sunni and Shia closer than Sunni and Catholic — string-equality "
            "alone would scatter the same countries randomly.",
            "Distribution runs over government.type cluster parliamentary republics, "
            "presidential republics, constitutional monarchies and absolute monarchies "
            "into visually coherent blocks of the dendrogram, with the linkage threshold "
            "controlling how fine the regime typology becomes.",
        ],
    )
    add_para(
        doc,
        "Notes on speed: the dominating cost in every run is the construction of the "
        "192 × 192 distance matrix (≈ 18 000 pairs), not the clustering itself. For "
        "scalar single-feature runs the per-pair work is O(1) and the whole pipeline "
        "completes in well under 100 ms. For distribution single-feature runs the "
        "per-pair work is a tree-EMD over a taxonomy with a few dozen leaves, which "
        "raises the total to a few hundred milliseconds. Both runs are persisted into "
        "the cluster_runs collection (with their D in distance_matrices) so re-opening "
        "the result page is instantaneous.",
    )

    add_heading(doc, "4.4 Robustness Findings", level=2)
    add_bullets(
        doc,
        [
            "Identical-sibling regression: hand-crafted trees of the form A(B, B) "
            "previously triggered KeyError: (0,) in the compare page because "
            "list.index used equality and collapsed structurally identical siblings to "
            "the same path. The identity-based path_of fix in src/core/tree.py — "
            "together with similar identity fixes in both algorithms' delete steps and "
            "in src.comparison._dotted — resolves the issue and is covered by tests in "
            "test_core / test_ted.",
            "Synthetic trees and the comparison cache: because the user routinely edits "
            "a synthetic tree under the same name, comparison results are never read "
            "from the edit_scripts cache when either side is synthetic. The clustering "
            "pipeline also skips synthetic documents up-front so they cannot pollute D.",
            "Cross-kind safety in N&J: when the recursion considers pairing a leaf with "
            "a structural node, the cost is set to delete_subtree + insert_subtree and "
            "the mapping extractor skips the pair, so the script builder emits a delete "
            "+ insert pair rather than an impossible relabel.",
        ],
    )

    # =============== 5. CONCLUSION ===============
    add_heading(doc, "5. Conclusion", level=1)

    add_heading(doc, "5.1 Synthesis", level=2)
    add_para(
        doc,
        "The IDPA Country Explorer is a complete, end-to-end implementation of the "
        "course material applied to a real semi-structured dataset. From the raw "
        "Wikipedia infobox of every UN member state, the pipeline produces a typed, "
        "hierarchical tree; two canonical TED algorithms with three slide-faithful "
        "similarity metrics; an applicable, invertible edit script with a node-pair "
        "mapping; two slide-faithful clustering algorithms with a non-Euclidean distance "
        "matrix and silhouette-based evaluation; and an interactive Flask + D3 frontend "
        "that exposes all of the above. The 131-test pytest suite covers the dataclass "
        "invariants, the parser edge cases, the taxonomy EMD properties, both TED "
        "algorithms and the clustering pipeline; every cached artefact (countries, "
        "edit_scripts, distance_matrices, cluster_runs) is keyed deterministically in "
        "MongoDB so that any run is reproducible and incremental.",
    )

    add_heading(doc, "5.2 Personal Experience", level=2)
    add_para(
        doc,
        "Three insights stood out during implementation.",
    )
    add_bullets(
        doc,
        [
            "Typed leaves are the single biggest leverage point. The earlier IDPA "
            "project compared leaves by string equality and produced edit costs that "
            "carried no semantic information. Once each leaf is parsed into a Python "
            "value with a per-type, bounded, scale-normalised distance, the same TED "
            "DP suddenly captures meaningful similarity — a currency 10 % off costs a "
            "small fraction of a relabel, not a full one.",
            "Optimality is not enough: the script must be applicable. Zhang-Shasha's "
            "ancestor-preserving mapping can be optimal yet non-applicable when no move "
            "operation is available; the project sacrifices about 5 % of theoretical "
            "optimality through a strict-parent-preserving filter to guarantee that "
            "every script the user sees can actually be replayed. Nierman & Jagadish "
            "side-steps this entirely through order-preserving sequence alignment of "
            "children, at the cost of a denser memoised recursion.",
            "Identity is not equality. Dataclass-generated __eq__ collapses two "
            "structurally identical sibling subtrees, which then collapses their paths "
            "in path_of, which then collapses their entries in the mapping inversion, "
            "which then crashes the compare page with KeyError. The fix is one line per "
            "site (next(i for i, c in enumerate(...) if c is cur)), but locating every "
            "site required a careful audit of the whole codebase.",
        ],
    )
    add_para(
        doc,
        "On the engineering side, keeping a single config/pipeline.json as the source "
        "of truth (700 lines, but only one place to look) and self-contained algorithm "
        "files (duplicate code accepted in exchange for end-to-end readability of each "
        "algorithm) both paid off: every parameter has a known home, and every "
        "algorithm can be read without flipping between files.",
    )

    add_heading(doc, "5.3 Project Perspectives", level=2)
    add_para(doc, "Possible extensions and improvements:", bold=False)
    add_bullets(
        doc,
        [
            "Move operations in EditScript: today a structural move costs ≈ delete + "
            "insert (mitigated for N&J by the subtree-containment rule, but still "
            "two operations). Adding a first-class move with an applicable apply() "
            "would remove the strict-parent-preserving filter and recover Zhang-"
            "Shasha optimality.",
            "Multi-feature clustering: the current design lets the user pick exactly "
            "one feature (with no per-feature weights). Reinstating a weighted multi-"
            "feature mode would let the user explore feature interactions and would "
            "make field_weights and the asymmetric cost model meaningfully visible in "
            "the cluster view.",
            "Higher-D scatter / honest single-feature views: show the variance "
            "explained by the first 2 (and 3) classical-MDS eigenvalues next to the "
            "scatter; offer a 1-D strip/histogram for numeric single features; offer "
            "a t-SNE / UMAP projection as an alternative to metric MDS; introduce 3-D "
            "only as an interactive (rotatable), evidence-gated mode.",
            "Live re-fetch from Wikipedia: today ingestion is a one-shot script. A "
            "background scheduler that refreshes a country whose Wikipedia revision "
            "id has changed, with automatic cache invalidation in edit_scripts and "
            "distance_matrices, would keep the comparisons current.",
            "Generalisation to other semi-structured corpora: the pipeline is "
            "deliberately decoupled from the country domain at the typed-tree level. "
            "Pointing the builder at a different dataset (financial filings, "
            "biomedical ontologies, product catalogues) is mostly a matter of "
            "rewriting config/pipeline.json — aliases, layout, types, weights, "
            "taxonomies — and supplying a new ingester.",
            "Move from cached comparisons to a full diff browser: with every pair of "
            "countries indexed in edit_scripts, the UI could become a navigable "
            "matrix or graph view of the 192 × 192 / 2 distinct comparisons rather "
            "than the current one-pair-at-a-time form.",
        ],
    )
    add_para(doc, "Practical uses outside of the academic context:", bold=False)
    add_bullets(
        doc,
        [
            "Educational tool for IDPA students: the side-by-side coloured diff with "
            "an editable, applicable script and the three similarity metrics is a "
            "didactic surface for the Chapter 5 / Chapter 10 material.",
            "Reference implementation for typed-tree TED + non-Euclidean clustering, "
            "useful in any domain where heterogeneous record matching is needed.",
            "Data-journalism / political-science exploration: the cluster tab "
            "recovers unsupervised macro-regional groupings that align with known "
            "confessional, linguistic and political patterns; the dendrogram exposes "
            "the merging order that a flat partition hides.",
        ],
    )

    # ============== References ==============
    add_heading(doc, "References", level=1)
    add_bullets(
        doc,
        [
            "Chawathe S. S., Comparing Hierarchical Data in External Memory, "
            "Proceedings of VLDB 1999, pp. 90–101.",
            "Nierman A. and Jagadish H. V., Evaluating Structural Similarity in XML "
            "Documents, Proceedings of WebDB 2002, pp. 61–66.",
            "Lloyd S. P., Least Squares Quantization in PCM, IEEE Transactions on "
            "Information Theory, vol. 28 no. 2, 1982, pp. 129–137.",
            "Torgerson W. S., Multidimensional Scaling: I. Theory and Method, "
            "Psychometrika, vol. 17 no. 4, 1952, pp. 401–419.",
            "Zhang K. and Shasha D., Simple Fast Algorithms for the Editing Distance "
            "Between Trees and Related Problems, SIAM Journal on Computing, vol. 18 "
            "no. 6, 1989, pp. 1245–1262.",
            "Course material: Intelligent Data Processing and Applications (IDPA), "
            "Chapters 4, 5 and 10.",
            "wptools — Python wrapper for Wikipedia / MediaWiki APIs. "
            "https://github.com/siznax/wptools",
        ],
    )

    doc.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
