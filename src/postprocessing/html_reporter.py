"""
Generate a human-readable HTML diff report for a TED edit script.

Produces a single self-contained HTML file with:
  - Run metadata (countries, algorithm, cost model)
  - Per-direction stats bar (total ops / inserts / deletes / relabels / cost)
  - Color-coded operations table: green=insert, red=delete, yellow=relabel
"""

from __future__ import annotations
from html import escape
from pathlib import Path

from classes.EditScript import EditScript
from classes.Tree import Tree


_CSS = """
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 24px;
       background: #f0f2f5; color: #222; }
h1 { margin: 0 0 4px; font-size: 1.6em; }
.subtitle { color: #666; margin-bottom: 20px; font-size: 0.95em; }
h2 { font-size: 1.15em; margin: 28px 0 10px; border-left: 4px solid #555;
     padding-left: 10px; }
.meta { background: #fff; border: 1px solid #ddd; border-radius: 8px;
        padding: 16px 20px; margin-bottom: 20px; display: inline-block; }
.meta table { border-collapse: collapse; }
.meta td { padding: 3px 16px 3px 0; font-size: 0.92em; }
.meta td:first-child { font-weight: 600; color: #555; }
.stats { display: flex; gap: 12px; margin-bottom: 14px; flex-wrap: wrap; }
.stat { background: #fff; border: 1px solid #ddd; border-radius: 8px;
        padding: 10px 18px; text-align: center; min-width: 90px; }
.stat .num { font-size: 1.8em; font-weight: 700; line-height: 1.1; }
.stat .lbl { color: #888; font-size: 0.78em; margin-top: 2px; }
.ins .num { color: #27ae60; }
.del .num { color: #e74c3c; }
.rel .num { color: #d68910; }
.tot .num { color: #2471a3; }
table.ops { width: 100%; border-collapse: collapse; background: #fff;
            border: 1px solid #ddd; border-radius: 8px; overflow: hidden;
            font-size: 0.88em; }
table.ops th { background: #3d3d3d; color: #fff; padding: 9px 12px;
               text-align: left; white-space: nowrap; }
table.ops td { padding: 6px 12px; border-top: 1px solid #eee;
               font-family: 'Cascadia Code', 'Consolas', monospace;
               vertical-align: top; }
tr.insert td  { background: #eafaf1; }
tr.delete td  { background: #fdedec; }
tr.relabel td { background: #fef9e7; }
td.op         { font-weight: 700; white-space: nowrap; }
tr.insert  td.op { color: #27ae60; }
tr.delete  td.op { color: #e74c3c; }
tr.relabel td.op { color: #d68910; }
td.idx  { color: #aaa; text-align: right; width: 40px; }
td.cost { color: #999; text-align: right; width: 50px; }
td.path { color: #888; font-size: 0.85em; max-width: 260px;
          word-break: break-all; }
"""


def generate_html_diff(
    c1: str,
    c2: str,
    algorithm: str,
    costs: dict,
    script_fwd: EditScript,
    script_rv: EditScript,
    T1: Tree,
    T2: Tree,
) -> str:
    """Return a self-contained HTML string visualising both edit scripts."""
    cost_display = {k: v for k, v in costs.items() if not k.startswith('_')}

    def _stats_html(script: EditScript) -> str:
        counts: dict[str, int] = {}
        for a in script:
            counts[a.op_type] = counts.get(a.op_type, 0) + 1
        return (
            '<div class="stats">'
            f'<div class="stat tot"><div class="num">{len(script)}</div>'
            f'<div class="lbl">ops</div></div>'
            f'<div class="stat ins"><div class="num">{counts.get("insert",0)}</div>'
            f'<div class="lbl">inserts</div></div>'
            f'<div class="stat del"><div class="num">{counts.get("delete",0)}</div>'
            f'<div class="lbl">deletes</div></div>'
            f'<div class="stat rel"><div class="num">{counts.get("relabel",0)}</div>'
            f'<div class="lbl">relabels</div></div>'
            f'<div class="stat tot"><div class="num">{script.total_cost}</div>'
            f'<div class="lbl">cost</div></div>'
            '</div>'
        )

    def _op_rows(script: EditScript) -> str:
        rows = []
        for i, a in enumerate(script, 1):
            cls = a.op_type
            if a.op_type == 'relabel':
                old = escape(a.node.label[:60])
                new = escape(a.args.get('new_label', '')[:60])
                detail = f'<b>{old}</b> &rarr; <b>{new}</b>'
                path = escape(_node_path(a.node))
            elif a.op_type == 'insert':
                p = a.args.get('parent')
                node_lbl = escape(a.node.label[:60])
                par_lbl = escape(p.label if p else 'ROOT')
                pos = a.args.get('position', 0)
                detail = (
                    f'<b>{node_lbl}</b>'
                    f' &nbsp;<span style="color:#888">parent=<i>{par_lbl}</i>'
                    f' pos={pos}</span>'
                )
                path = escape(_node_path(a.node.parent) if a.node.parent else '/')
            else:  # delete
                detail = f'<b>{escape(a.node.label[:60])}</b>'
                path = escape(_node_path(a.node))
            rows.append(
                f'<tr class="{cls}">'
                f'<td class="idx">{i}</td>'
                f'<td class="op">{a.op_type}</td>'
                f'<td>{detail}</td>'
                f'<td class="path">{path}</td>'
                f'<td class="cost">{a.cost}</td>'
                f'</tr>'
            )
        return '\n'.join(rows)

    def _section(title: str, script: EditScript) -> str:
        rows = _op_rows(script)
        return f"""
  <h2>{escape(title)}</h2>
  {_stats_html(script)}
  <table class="ops">
    <thead>
      <tr><th>#</th><th>Op</th><th>Detail</th><th>Path</th><th>Cost</th></tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Diff: {escape(c1)} vs {escape(c2)}</title>
  <style>{_CSS}</style>
</head>
<body>
  <h1>IDF Diff Report</h1>
  <p class="subtitle">Generated by IDPA TED Pipeline</p>
  <div class="meta">
    <table>
      <tr><td>Source (T1)</td><td><b>{escape(c1)}</b> &nbsp;({T1.size()} nodes)</td></tr>
      <tr><td>Target (T2)</td><td><b>{escape(c2)}</b> &nbsp;({T2.size()} nodes)</td></tr>
      <tr><td>Algorithm</td><td>{escape(algorithm)}</td></tr>
      <tr><td>Cost model</td><td><code>{escape(str(cost_display))}</code></td></tr>
    </table>
  </div>
  {_section(f"{c1} → {c2}", script_fwd)}
  {_section(f"{c2} → {c1}", script_rv)}
</body>
</html>
"""


def _node_path(node) -> str:
    if node is None:
        return '/'
    parts = []
    cur = node
    while cur is not None:
        parts.append(cur.label[:30])
        cur = cur.parent
    parts.reverse()
    return '/'.join(parts)


def write_html_diff(path: Path, **kwargs) -> str:
    """Write HTML diff to *path* and return the HTML string."""
    html = generate_html_diff(**kwargs)
    path.write_text(html, encoding='utf-8')
    return html
