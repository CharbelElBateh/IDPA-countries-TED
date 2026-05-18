/* Side-by-side diff visualization for the Compare page.
 *
 * Builds two TreeView instances (source on the left, target on the right)
 * and switches direction (A→B / B→A) by re-fetching the comparison and
 * re-wiring the marks.
 */
(function () {
  const { country1, country2, algorithm, cost_model } = window.COMPARE_DATA;
  const params = new URLSearchParams({ algorithm, cost_model });
  const url = `/api/compare/${encodeURIComponent(country1)}/${encodeURIComponent(country2)}?${params}`;

  const sourceLabel = document.getElementById("side-source-label");
  const targetLabel = document.getElementById("side-target-label");
  const scriptPanel = document.getElementById("script-panel");

  let cached = null;     // server response
  let direction = "forward";
  let sourceView = null;
  let targetView = null;

  fetch(url)
    .then((r) => {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then((data) => {
      if (data.error) throw new Error(data.error);
      cached = data;
      renderDirection();
      wireToolbar();
    })
    .catch((err) => {
      document.getElementById("tree-canvas-source").innerHTML =
        '<div class="alert alert-danger m-3">Failed: ' + err.message + "</div>";
    });

  function renderDirection() {
    const dir = cached[direction];
    const [srcName, tgtName] = direction === "forward"
      ? [country1, country2]
      : [country2, country1];

    sourceLabel.innerHTML = `Source · <code>${srcName}</code>`;
    targetLabel.innerHTML = `Target · <code>${tgtName}</code>`;

    sourceView = TreeView.fromData(
      "tree-canvas-source",
      { root: dir.source },
      { initialDepth: 1, marks: dir.source_marks }
    );
    targetView = TreeView.fromData(
      "tree-canvas-target",
      { root: dir.target },
      { initialDepth: 1, marks: dir.target_marks }
    );

    renderScript(dir.script.operations, dir.total_cost, dir.op_counts);
  }

  function renderScript(ops, totalCost, counts) {
    const counts_html = `
      <span class="badge bg-warning text-dark me-2">${counts.relabel || 0} relabel</span>
      <span class="badge bg-danger me-2">${counts.delete || 0} delete</span>
      <span class="badge bg-success me-2">${counts.insert || 0} insert</span>
      <span class="text-muted ms-2">total cost: <strong>${(totalCost || 0).toFixed(2)}</strong></span>
    `;
    if (!ops.length) {
      scriptPanel.innerHTML = counts_html + '<div class="text-muted">No operations.</div>';
      return;
    }
    const rows = ops.slice(0, 200).map((op) => {
      const path = "(" + op.path.join("→") + ")";
      let detail = "";
      if (op.op === "relabel") {
        detail = `<code>${esc(op.old_label || "")}</code> → <code>${esc(op.new_node ? op.new_node.label : "?")}</code>`;
      } else if (op.op === "delete") {
        detail = `<code>${esc(op.old_label || "")}</code>`;
      } else {
        detail = `<code>${esc(op.new_node ? op.new_node.label : "?")}</code> @ position ${op.position}`;
      }
      return `<tr>
        <td><span class="badge bg-${opColor(op.op)}">${op.op}</span></td>
        <td><code class="small">${path}</code></td>
        <td>${detail}</td>
        <td class="text-end small text-muted">${op.cost.toFixed(2)}</td>
      </tr>`;
    }).join("");
    const more = ops.length > 200
      ? `<div class="text-muted small">+ ${ops.length - 200} more (truncated)</div>` : "";
    scriptPanel.innerHTML = counts_html + `
      <div class="table-responsive mt-2">
        <table class="table table-sm script-table mb-0">
          <thead><tr><th>op</th><th>path</th><th>detail</th><th class="text-end">cost</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>${more}`;
  }

  function opColor(op) {
    return { relabel: "warning text-dark", delete: "danger", insert: "success" }[op] || "secondary";
  }

  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function wireToolbar() {
    document.getElementById("btn-dir-fwd").addEventListener("click", () => switchDir("forward"));
    document.getElementById("btn-dir-rev").addEventListener("click", () => switchDir("reverse"));
    document.getElementById("btn-expand-all").addEventListener("click", () => {
      [sourceView, targetView].forEach((v) => { if (v) { v.expandAll(); v.update(v.root); v.fitToView(); } });
    });
    document.getElementById("btn-collapse-all").addEventListener("click", () => {
      [sourceView, targetView].forEach((v) => v && v.collapseToRoot());
    });
    document.getElementById("btn-fit").addEventListener("click", () => {
      [sourceView, targetView].forEach((v) => v && v.fitToView());
    });
  }

  function switchDir(dir) {
    if (dir === direction) return;
    direction = dir;
    document.getElementById("btn-dir-fwd").classList.toggle("active", dir === "forward");
    document.getElementById("btn-dir-rev").classList.toggle("active", dir === "reverse");
    renderDirection();
  }
})();
