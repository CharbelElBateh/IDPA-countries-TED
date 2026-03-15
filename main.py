"""
IDPA Project 1 — Wikipedia Infobox TED Pipeline
Entry point / CLI driver.

Usage examples:
    # Run the full pipeline for two countries (all stages, full logs):
    python main.py run --country1 Lebanon --country2 Switzerland
    python main.py                                     # same as above (defaults)

    # Individual stages:
    python main.py collect --country Lebanon
    python main.py collect --all
    python main.py diff --country1 Lebanon --country2 Switzerland
    python main.py diff --country1 Lebanon --country2 Switzerland --algorithm nierman_jagadish
    python main.py patch --country1 Lebanon --country2 Switzerland
    python main.py patch --country1 Lebanon --country2 Switzerland --direction reverse
"""

import argparse
import csv
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

RAW_DIR    = Path('data/raw')
CONFIG_DIR = Path('config')
LOGS_DIR   = Path('logs')


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(log_file: Path | None = None, verbose: bool = False) -> logging.Logger:
    """Configure root logger with console + optional file handler."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    console_level = logging.DEBUG if verbose else logging.INFO
    console_fmt = logging.Formatter(
        '%(asctime)s  %(levelname)-8s  %(message)s',
        datefmt='%H:%M:%S',
    )
    import io
    stdout_utf8 = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    ch = logging.StreamHandler(stdout_utf8)
    ch.setLevel(console_level)
    ch.setFormatter(console_fmt)
    root.addHandler(ch)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_fmt = logging.Formatter(
            '%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(file_fmt)
        root.addHandler(fh)

    return logging.getLogger('pipeline')


# ---------------------------------------------------------------------------
# Stage 1: collect
# ---------------------------------------------------------------------------

def cmd_collect(args):
    log = logging.getLogger('pipeline.collect')
    from src.collection.scraper import scrape_country, scrape_all_countries, UN_MEMBER_STATES

    out_dir = Path(args.output) if args.output else None

    if args.all:
        log.info(f"Scraping all {len(UN_MEMBER_STATES)} UN member states …")
        results = scrape_all_countries(UN_MEMBER_STATES, output_dir=out_dir)
        ok = sum(1 for p in results.values() if p)
        log.info(f"Done: {ok}/{len(UN_MEMBER_STATES)} countries collected.")
    elif args.country:
        for country in args.country:
            log.info(f"Collecting: {country}")
            scrape_country(country, output_dir=out_dir)
    else:
        log.error("Specify --country <name> or --all")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _load_costs(costs_path: Path | None) -> dict:
    path = costs_path or CONFIG_DIR / 'cost_model_default.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return {'insert': 1, 'delete': 1, 'relabel': 1}


def _load_tree(country: str, raw_dir: Path, strategy: str | None = None):
    from src.preprocessing.xml_parser import parse_xml_file
    from src.preprocessing.normalizer import normalize_tree

    xml_path = raw_dir / f"{country.replace(' ', '_')}.xml"
    if not xml_path.exists():
        logging.getLogger('pipeline').error(
            f"XML not found: {xml_path}  — run 'collect' first."
        )
        sys.exit(1)

    tree = parse_xml_file(xml_path, strategy=strategy)
    normalize_tree(tree)
    return tree


# ---------------------------------------------------------------------------
# Stage 2+3: diff
# ---------------------------------------------------------------------------

def cmd_diff(args):
    log = logging.getLogger('pipeline.diff')
    from src.differencing.edit_script import extract_edit_script
    from src.differencing.diff_formatter import diff_to_idf
    from src.ted.similarity import compute_similarity

    raw_dir = Path(args.raw_dir) if args.raw_dir else RAW_DIR
    costs   = _load_costs(Path(args.costs) if args.costs else None)
    algorithm = args.algorithm

    T1 = _load_tree(args.country1, raw_dir, strategy=args.strategy)
    T2 = _load_tree(args.country2, raw_dir, strategy=args.strategy)

    log.info(f"Computing TED ({algorithm}): {args.country1} vs {args.country2}")
    log.info(f"  |T1| = {T1.size()} nodes  ({args.country1})")
    log.info(f"  |T2| = {T2.size()} nodes  ({args.country2})")

    ted, script = extract_edit_script(T1, T2, costs, algorithm=algorithm)
    metrics = compute_similarity(ted, T1, T2)

    log.info(f"  TED (raw)          = {metrics['raw_ted']}")
    log.info(f"  sim_inverse        = {metrics['sim_inverse']:.6f}  (1 / (1 + TED))")
    log.info(f"  sim_ratio          = {metrics['sim_ratio']:.6f}  (1 - TED / (|T1|+|T2|))")
    log.info(f"  edit script ops    = {len(script)}  (cost={script.total_cost})")

    if args.output:
        out_path = Path(args.output)
    else:
        out_dir = Path('data/diffs')
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = (
            f"{args.country1.replace(' ', '_')}"
            f"__{args.country2.replace(' ', '_')}"
            f"__{algorithm}.idf.xml"
        )
        out_path = out_dir / fname

    diff_to_idf(
        args.country1, args.country2, algorithm,
        metrics['raw_ted'], metrics['sim_inverse'], metrics['sim_ratio'],
        script, output_path=out_path,
    )
    log.info(f"  IDF diff written → {out_path}")


# ---------------------------------------------------------------------------
# Stage 5: patch
# ---------------------------------------------------------------------------

def cmd_patch(args):
    log = logging.getLogger('pipeline.patch')
    from src.patching.patcher import apply_edit_script
    from src.differencing.edit_script import extract_edit_script
    from src.postprocessing.serializer import write_tree_xml

    raw_dir = Path(args.raw_dir) if args.raw_dir else RAW_DIR
    costs   = _load_costs(Path(args.costs) if args.costs else None)

    T1 = _load_tree(args.country1, raw_dir, strategy=args.strategy)
    T2 = _load_tree(args.country2, raw_dir, strategy=args.strategy)

    log.info(f"Extracting edit script: {args.country1} → {args.country2}")
    ted, script = extract_edit_script(T1, T2, costs, algorithm=args.algorithm)
    log.info(f"  TED={ted}  ops={len(script)}")

    direction = args.direction or 'forward'
    if direction == 'forward':
        patched = apply_edit_script(T1, script, target=T2, costs=costs)
    else:
        # Compute a fresh T2→T1 edit script for correct reverse application
        _, rev_script = extract_edit_script(T2, T1, costs, algorithm=args.algorithm)
        patched = apply_edit_script(T2, rev_script, target=T1, costs=costs)

    if args.output:
        out_path = Path(args.output)
    else:
        out_dir = Path('data/patched')
        out_dir.mkdir(parents=True, exist_ok=True)
        label = (
            f"{args.country1}_to_{args.country2}"
            if direction == 'forward' else
            f"{args.country2}_to_{args.country1}"
        )
        out_path = out_dir / f"{label.replace(' ', '_')}.xml"

    write_tree_xml(patched, out_path)
    log.info(f"  Patched tree → {out_path}")


# ---------------------------------------------------------------------------
# Stage 6: postprocess — render infobox HTML from a country XML
# ---------------------------------------------------------------------------

def cmd_postprocess(args):
    log = logging.getLogger('pipeline.postprocess')
    from src.postprocessing.infobox_renderer import write_infobox_html

    raw_dir = Path(args.raw_dir) if args.raw_dir else RAW_DIR

    country = args.country
    tree = _load_tree(country, raw_dir, strategy=args.strategy)

    if args.output:
        out_path = Path(args.output)
    else:
        out_dir = Path('data/postprocessed')
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"infobox_{country.replace(' ', '_')}.html"

    write_infobox_html(out_path, tree, country)
    log.info(f"  Infobox HTML → {out_path}")


# ---------------------------------------------------------------------------
# Full pipeline: run
# ---------------------------------------------------------------------------

def cmd_run(args):
    """Run all pipeline stages end-to-end with comprehensive logging."""
    log = logging.getLogger('pipeline')
    c1, c2 = args.country1, args.country2
    algorithm = args.algorithm
    raw_dir   = Path(args.raw_dir) if args.raw_dir else RAW_DIR
    costs     = _load_costs(Path(args.costs) if args.costs else None)

    sep = '─' * 68

    # ── RUN DIRECTORY + LOG FILE ─────────────────────────────────────────
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_dir = Path('data/runs') / f"{c1.replace(' ', '_')}__{c2.replace(' ', '_')}__{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Attach a file handler so everything from here is captured in run_dir
    _run_log_path = run_dir / f"pipeline_{c1.replace(' ', '_')}__{c2.replace(' ', '_')}.log"
    _fh = logging.FileHandler(_run_log_path, encoding='utf-8')
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(logging.Formatter(
        '%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    ))
    logging.getLogger().addHandler(_fh)

    def _save(filename: str, content: str) -> Path:
        p = run_dir / filename
        p.write_text(content, encoding='utf-8')
        log.info(f"    saved → {p}")
        return p

    # ── BANNER ──────────────────────────────────────────────────────────
    log.info(sep)
    log.info("  IDPA PIPELINE — full run")
    log.info(f"  Countries  : {c1}  vs  {c2}")
    log.info(f"  Algorithm  : {algorithm}")
    log.info(f"  Cost model : {costs}")
    log.info(f"  Run dir    : {run_dir}")
    log.info(f"  Log        : {_run_log_path}")
    log.info(sep)

    # ── STAGE 1: Data Collection ────────────────────────────────────────
    log.info("[STAGE 1]  Data Collection")
    for country in (c1, c2):
        xml_path = raw_dir / f"{country.replace(' ', '_')}.xml"
        if xml_path.exists():
            size_kb = xml_path.stat().st_size / 1024
            log.info(f"  {country}: {xml_path}  ({size_kb:.1f} KB) — already collected, skipping")
        else:
            log.info(f"  {country}: not found — collecting from Wikipedia …")
            from src.collection.scraper import scrape_country
            scrape_country(country, output_dir=raw_dir)
            if xml_path.exists():
                log.info(f"  {country}: collected → {xml_path}")
            else:
                log.error(f"  {country}: collection failed. Aborting.")
                sys.exit(1)

    # ── STAGE 2: Preprocessing ──────────────────────────────────────────
    log.info(sep)
    log.info("[STAGE 2]  Preprocessing  (XML → rooted ordered labeled tree)")

    from src.preprocessing.xml_parser import parse_xml_file
    from src.preprocessing.normalizer import normalize_tree

    strategy = getattr(args, 'strategy', None)

    T1 = parse_xml_file(raw_dir / f"{c1.replace(' ', '_')}.xml", strategy=strategy)
    T2 = parse_xml_file(raw_dir / f"{c2.replace(' ', '_')}.xml", strategy=strategy)
    normalize_tree(T1)
    normalize_tree(T2)

    def _tree_summary(tree, name):
        nodes     = list(tree.postorder())
        elements  = sum(1 for n in nodes if n.node_type == 'element')
        leaves    = sum(1 for n in nodes if n.node_type == 'leaf')
        top_fields = [c.label for c in tree.root.children]
        log.info(f"  {name}:")
        log.info(f"    Total nodes : {tree.size()}  ({elements} elements, {leaves} leaves)")
        log.info(f"    Top-level fields ({len(top_fields)}): {', '.join(top_fields)}")

    _tree_summary(T1, c1)
    _tree_summary(T2, c2)

    from src.postprocessing.serializer import tree_to_text
    _save(f"T1_{c1.replace(' ', '_')}.tree.txt", tree_to_text(T1))
    _save(f"T2_{c2.replace(' ', '_')}.tree.txt", tree_to_text(T2))

    # ── STAGE 3: TED + Similarity (both algorithms, both directions) ──────
    log.info(sep)
    log.info("[STAGE 3]  Tree Edit Distance + Similarity")

    from src.ted.chawathe import compute_ted_and_script as cw_ted_and_script
    from src.ted.nierman_jagadish import compute_ted_and_script as nj_ted_and_script
    from src.ted.similarity import compute_similarity

    log.info(f"  Running Chawathe — T1→T2 …")
    ted_cw,    script_cw    = cw_ted_and_script(T1, T2, costs)
    log.info(f"  Running Chawathe — T2→T1 …")
    ted_cw_rv, script_cw_rv = cw_ted_and_script(T2, T1, costs)
    log.info(f"  Running Nierman & Jagadish — T1→T2 …")
    ted_nj,    script_nj    = nj_ted_and_script(T1, T2, costs)
    log.info(f"  Running Nierman & Jagadish — T2→T1 …")
    ted_nj_rv, script_nj_rv = nj_ted_and_script(T2, T1, costs)

    m_cw    = compute_similarity(ted_cw,    T1, T2)
    m_cw_rv = compute_similarity(ted_cw_rv, T2, T1)
    m_nj    = compute_similarity(ted_nj,    T1, T2)
    m_nj_rv = compute_similarity(ted_nj_rv, T2, T1)

    hdr = f"  {'Direction':<18}  {'Algorithm':<22}  {'TED (cost)':>10}  {'sim_inverse':>12}  {'sim_ratio':>10}"
    div = f"  {'─'*18}  {'─'*22}  {'─'*10}  {'─'*12}  {'─'*10}"
    log.info(hdr); log.info(div)
    def _row(direction, algo, ted, m):
        log.info(f"  {direction:<18}  {algo:<22}  {ted:>10.2f}  {m['sim_inverse']:>12.6f}  {m['sim_ratio']:>10.6f}")
    _row(f"{c1}→{c2}", "Chawathe 1999",         ted_cw,    m_cw)
    _row(f"{c1}→{c2}", "Nierman & Jagadish",    ted_nj,    m_nj)
    _row(f"{c2}→{c1}", "Chawathe 1999",         ted_cw_rv, m_cw_rv)
    _row(f"{c2}→{c1}", "Nierman & Jagadish",    ted_nj_rv, m_nj_rv)
    log.info(f"  |T1|={T1.size()}  |T2|={T2.size()}")
    asymmetric = (ted_cw != ted_cw_rv or ted_nj != ted_nj_rv)
    if asymmetric:
        log.info(f"  *** Asymmetric cost model: T1→T2 cost ≠ T2→T1 cost ***")

    # pick the requested algorithm's scripts for downstream stages
    if algorithm == 'chawathe':
        ted, script, metrics         = ted_cw,    script_cw,    m_cw
        ted_rv, script_rv, metrics_rv = ted_cw_rv, script_cw_rv, m_cw_rv
    else:
        ted, script, metrics         = ted_nj,    script_nj,    m_nj
        ted_rv, script_rv, metrics_rv = ted_nj_rv, script_nj_rv, m_nj_rv

    # ── STAGE 4: Edit Script + IDF Diff ─────────────────────────────────
    log.info(sep)
    log.info("[STAGE 4]  Edit Script + IDF Diff")

    op_counts: dict[str, int] = {}
    for a in script:
        op_counts[a.op_type] = op_counts.get(a.op_type, 0) + 1

    log.info(f"  Total operations : {len(script)}  (cost = {script.total_cost})")
    for op_type, count in sorted(op_counts.items()):
        log.info(f"    {op_type:<10} : {count}")

    # Log first 10 operations in detail
    log.info(f"  First 10 operations ({algorithm}):")
    for i, a in enumerate(script):
        if i >= 10:
            break
        if a.op_type == 'relabel':
            detail = f"'{a.node.label[:40]}' → '{a.args.get('new_label','')[:40]}'"
        elif a.op_type == 'insert':
            p = a.args.get('parent')
            detail = (
                f"node='{a.node.label[:30]}'  "
                f"parent='{p.label if p else 'ROOT'}'  "
                f"pos={a.args.get('position', 0)}"
            )
        else:
            detail = f"node='{a.node.label[:50]}'"
        log.info(f"    op{i+1:>3}: {a.op_type:<8}  {detail}")

    # Write IDF
    from src.differencing.diff_formatter import diff_to_idf

    out_dir_diff = Path('data/diffs')
    out_dir_diff.mkdir(parents=True, exist_ok=True)
    idf_path = out_dir_diff / (
        f"{c1.replace(' ', '_')}__{c2.replace(' ', '_')}__{algorithm}.idf.xml"
    )
    idf_str = diff_to_idf(
        c1, c2, algorithm,
        metrics['raw_ted'], metrics['sim_inverse'], metrics['sim_ratio'],
        script, output_path=idf_path,
    )
    log.info(f"  IDF written → {idf_path}  ({len(idf_str.splitlines())} lines)")
    _save(f"idf_{algorithm}.xml", idf_str)
    _save(f"edit_script_chawathe_{c1}_to_{c2}.txt".replace(' ', '_'), str(script_cw))
    _save(f"edit_script_chawathe_{c2}_to_{c1}.txt".replace(' ', '_'), str(script_cw_rv))
    _save(f"edit_script_nierman_jagadish_{c1}_to_{c2}.txt".replace(' ', '_'), str(script_nj))
    _save(f"edit_script_nierman_jagadish_{c2}_to_{c1}.txt".replace(' ', '_'), str(script_nj_rv))

    # ── STAGE 5: Patching ────────────────────────────────────────────────
    log.info(sep)
    log.info("[STAGE 5]  Patching")

    from src.patching.patcher import apply_edit_script
    from src.ted.chawathe import compute_ted
    from src.postprocessing.serializer import write_tree_xml, tree_to_infobox, tree_to_text
    from src.postprocessing.html_reporter import write_html_diff

    out_dir_patch = Path('data/patched')
    out_dir_patch.mkdir(parents=True, exist_ok=True)

    residuals: dict[str, float] = {}

    for direction, src_tree, tgt_tree, src_name, tgt_name, dir_script in [
        ('forward', T1, T2, c1, c2, script),
        ('reverse', T2, T1, c2, c1, script_rv),
    ]:
        log.info(f"  [{direction}]  {src_name} → {tgt_name}  (script ops={len(dir_script)}  cost={dir_script.total_cost})")
        patched = apply_edit_script(src_tree, dir_script, target=tgt_tree, costs=costs)

        residual = compute_ted(patched, tgt_tree, costs)
        residuals[direction] = residual
        status = "✓ perfect" if residual == 0 else f"✗ residual TED={residual}"
        log.info(f"    patched size={patched.size()}  target size={tgt_tree.size()}  TED(patched,target)={residual}  {status}")

        patch_path = out_dir_patch / f"{src_name.replace(' ', '_')}_to_{tgt_name.replace(' ', '_')}.xml"
        write_tree_xml(patched, patch_path)
        log.info(f"    XML  written → {patch_path}")

        infobox_str = tree_to_infobox(patched)
        infobox_path = out_dir_patch / (
            f"{src_name.replace(' ', '_')}_to_{tgt_name.replace(' ', '_')}.infobox.txt"
        )
        infobox_path.write_text(infobox_str, encoding='utf-8')
        log.info(f"    infobox text → {infobox_path}")

        slug = f"{src_name.replace(' ', '_')}_to_{tgt_name.replace(' ', '_')}"
        _save(f"patched_{slug}.tree.txt", tree_to_text(patched))
        _save(f"patched_{slug}.infobox.txt", infobox_str)
        (run_dir / f"patched_{slug}.xml").write_bytes(patch_path.read_bytes())
        log.info(f"    run dir copy → {run_dir / f'patched_{slug}.xml'}")

        log.debug(f"    infobox preview (first 8 lines):")
        for ln in infobox_str.splitlines()[:8]:
            log.debug(f"      {ln}")

    # ── INFOBOX HTML RENDERINGS ───────────────────────────────────────────
    log.info(sep)
    log.info("[STAGE 6]  Post-processing: Wikipedia-style infobox HTML")

    from src.postprocessing.infobox_renderer import write_infobox_html

    # Original trees
    ib_t1_path = run_dir / f"infobox_{c1.replace(' ', '_')}.html"
    write_infobox_html(ib_t1_path, T1, c1)
    log.info(f"  Infobox HTML (T1)     → {ib_t1_path}")

    ib_t2_path = run_dir / f"infobox_{c2.replace(' ', '_')}.html"
    write_infobox_html(ib_t2_path, T2, c2)
    log.info(f"  Infobox HTML (T2)     → {ib_t2_path}")

    # Patched trees — reload from the patched outputs we saved above
    for src_name, tgt_name in [(c1, c2), (c2, c1)]:
        slug = f"{src_name.replace(' ', '_')}_to_{tgt_name.replace(' ', '_')}"
        patched_tree_path = run_dir / f"patched_{slug}.xml"
        from src.preprocessing.xml_parser import parse_xml_file
        patched_tree = parse_xml_file(patched_tree_path)
        ib_path = run_dir / f"infobox_patched_{slug}.html"
        write_infobox_html(
            ib_path, patched_tree, tgt_name,
            subtitle=f"patched from {src_name}",
        )
        log.info(f"  Infobox HTML (patched) → {ib_path}")

    # ── HTML DIFF REPORT ─────────────────────────────────────────────────
    log.info(sep)
    log.info("[STAGE 7]  Post-processing: HTML diff report")
    html_path = run_dir / f"diff_{c1.replace(' ','_')}__{c2.replace(' ','_')}.html"
    write_html_diff(
        html_path,
        c1=c1, c2=c2,
        algorithm=algorithm,
        costs=costs,
        script_fwd=script,
        script_rv=script_rv,
        T1=T1, T2=T2,
    )
    log.info(f"  HTML diff report → {html_path}")

    # ── SUMMARY CSV ──────────────────────────────────────────────────────
    summary_csv = Path('data/runs/summary.csv')
    cost_model_name = Path(args.costs).name if args.costs else 'cost_model_default.json'
    csv_row = {
        'timestamp':      ts,
        'country1':       c1,
        'country2':       c2,
        'algorithm':      algorithm,
        'cost_model':     cost_model_name,
        'ted_fwd':        ted,
        'ted_rv':         ted_rv,
        'sim_ratio_fwd':  f"{metrics['sim_ratio']:.6f}",
        'sim_ratio_rv':   f"{metrics_rv['sim_ratio']:.6f}",
        'ops_fwd':        len(script),
        'ops_rv':         len(script_rv),
        'fwd_perfect':    residuals.get('forward', -1) == 0,
        'rv_perfect':     residuals.get('reverse', -1) == 0,
    }
    write_header = not summary_csv.exists()
    with open(summary_csv, 'a', newline='', encoding='utf-8') as _f:
        writer = csv.DictWriter(_f, fieldnames=list(csv_row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(csv_row)
    log.info(f"  Summary CSV      → {summary_csv}")

    # ── SUMMARY ──────────────────────────────────────────────────────────
    log.info(sep)
    log.info("[SUMMARY]")
    log.info(f"  {c1:<20}  nodes={T1.size()}")
    log.info(f"  {c2:<20}  nodes={T2.size()}")
    log.info(f"  TED (Chawathe)       = {ted_cw}")
    log.info(f"  TED (N&J)            = {ted_nj}")
    log.info(f"  sim_inverse          = {metrics['sim_inverse']:.6f}")
    log.info(f"  sim_ratio            = {metrics['sim_ratio']:.6f}")
    log.info(f"  edit ops             = {len(script)}  "
             f"(relabel={op_counts.get('relabel',0)}  "
             f"delete={op_counts.get('delete',0)}  "
             f"insert={op_counts.get('insert',0)})")
    log.info(f"  IDF diff             → {idf_path}")
    log.info(f"  HTML diff report     → {html_path}")
    log.info(f"  summary CSV          → {summary_csv}")
    log.info(f"  patched outputs      → {out_dir_patch}/")
    log.info(f"  run artifacts        → {run_dir}/")
    log.info(sep)


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='IDPA Project 1 — Wikipedia Infobox TED Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py                                   # full pipeline (Lebanon vs Switzerland)\n"
            "  python main.py run --country1 Germany --country2 France\n"
            "  python main.py collect --country Germany\n"
            "  python main.py diff --country1 Lebanon --country2 Switzerland\n"
            "  python main.py patch --country1 Lebanon --country2 Switzerland\n"
            "  python main.py postprocess --country Lebanon\n"
        ),
    )
    parser.add_argument('--log-file', metavar='FILE',
                        help='Write logs to this file (default: logs/pipeline_<timestamp>.log)')
    parser.add_argument('--no-log-file', action='store_true',
                        help='Disable file logging')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Show DEBUG-level messages on terminal')

    sub = parser.add_subparsers(dest='command')

    # --- run (full pipeline) ---
    p_run = sub.add_parser('run', help='Run the full pipeline end-to-end')
    p_run.add_argument('--country1', default='Lebanon', metavar='NAME')
    p_run.add_argument('--country2', default='Switzerland', metavar='NAME')
    p_run.add_argument('--algorithm', default='chawathe',
                       choices=['chawathe', 'nierman_jagadish'])
    p_run.add_argument('--strategy', default=None,
                       choices=['single_node', 'token_nodes'])
    p_run.add_argument('--costs', metavar='FILE')
    p_run.add_argument('--raw-dir', metavar='DIR')
    p_run.set_defaults(func=cmd_run)

    # --- collect ---
    p_collect = sub.add_parser('collect', help='Fetch and save country infoboxes')
    p_collect.add_argument('--country', action='append', metavar='NAME')
    p_collect.add_argument('--all', action='store_true')
    p_collect.add_argument('--output', metavar='DIR')
    p_collect.set_defaults(func=cmd_collect)

    # --- diff ---
    p_diff = sub.add_parser('diff', help='Compute TED and produce IDF diff')
    p_diff.add_argument('--country1', required=True, metavar='NAME')
    p_diff.add_argument('--country2', required=True, metavar='NAME')
    p_diff.add_argument('--algorithm', default='chawathe',
                        choices=['chawathe', 'nierman_jagadish'])
    p_diff.add_argument('--strategy', default=None,
                        choices=['single_node', 'token_nodes'])
    p_diff.add_argument('--costs', metavar='FILE')
    p_diff.add_argument('--raw-dir', metavar='DIR')
    p_diff.add_argument('--output', metavar='FILE')
    p_diff.set_defaults(func=cmd_diff)

    # --- patch ---
    p_patch = sub.add_parser('patch', help='Apply edit script to transform a tree')
    p_patch.add_argument('--country1', required=True, metavar='NAME')
    p_patch.add_argument('--country2', required=True, metavar='NAME')
    p_patch.add_argument('--direction', choices=['forward', 'reverse'], default='forward')
    p_patch.add_argument('--algorithm', default='chawathe',
                         choices=['chawathe', 'nierman_jagadish'])
    p_patch.add_argument('--strategy', default=None,
                         choices=['single_node', 'token_nodes'])
    p_patch.add_argument('--costs', metavar='FILE')
    p_patch.add_argument('--raw-dir', metavar='DIR')
    p_patch.add_argument('--output', metavar='FILE')
    p_patch.set_defaults(func=cmd_patch)

    # --- postprocess ---
    p_post = sub.add_parser('postprocess',
                            help='Render a country infobox as Wikipedia-style HTML')
    p_post.add_argument('--country', required=True, metavar='NAME')
    p_post.add_argument('--strategy', default=None,
                        choices=['single_node', 'token_nodes'])
    p_post.add_argument('--raw-dir', metavar='DIR')
    p_post.add_argument('--output', metavar='FILE')
    p_post.set_defaults(func=cmd_postprocess)

    args = parser.parse_args()

    # Default: no subcommand → run full pipeline
    if args.command is None:
        args.command  = 'run'
        args.country1 = 'Lebanon'
        args.country2 = 'Switzerland'
        args.algorithm = 'chawathe'
        args.strategy  = None
        args.costs     = None
        args.raw_dir   = None
        args.func      = cmd_run

    # Set up logging — for 'run' the log file is created inside the run
    # directory (cmd_run adds the handler).  For all other commands it goes
    # to the logs/ folder as before.
    if args.no_log_file:
        log_file = None
    elif args.log_file:
        log_file = Path(args.log_file)
    elif getattr(args, 'command', None) == 'run':
        log_file = None   # cmd_run will attach its own handler
    else:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        c1 = getattr(args, 'country1', None)
        c2 = getattr(args, 'country2', None)
        if c1 and c2:
            slug = f"{c1.replace(' ', '_')}__{c2.replace(' ', '_')}_"
        else:
            slug = ''
        log_file = LOGS_DIR / f"pipeline_{slug}{ts}.log"

    setup_logging(log_file=log_file, verbose=args.verbose)

    if log_file:
        logging.getLogger('pipeline').info(f"Log file: {log_file}")

    args.func(args)


if __name__ == '__main__':
    main()