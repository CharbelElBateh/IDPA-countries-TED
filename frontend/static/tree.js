/* Reusable D3 tree renderer.
 *
 * Exports a global TreeView with two factories:
 *
 *   TreeView.fromUrl(containerId, url, opts)  — fetches /api/.../tree
 *   TreeView.fromData(containerId, data, opts) — uses an in-memory tree dict
 *
 * The legacy auto-boot path (used by /countries/<name>) still works: any
 * element with id "tree-canvas" and a data-tree-url attribute is wired up
 * automatically on DOMContentLoaded.
 *
 * ``opts``:
 *   initialDepth  — how many levels to expand initially (default 1)
 *   marks         — { dottedPath: "delete" | "insert" | "relabel" } for diff highlighting
 *   infoPanel     — element to receive node details on click (default #node-info)
 *   onNodeClick   — extra callback fired on every node click
 */
(function () {
  const TYPE_COLORS = {
    structural:   "#1f3a5f",
    number:       "#0d6efd",
    percent:      "#0d6efd",
    year:         "#0d6efd",
    date:         "#0d6efd",
    currency:     "#198754",
    coordinates:  "#fd7e14",
    wikilink:     "#6f42c1",
    text:         "#6c757d",
    distribution: "#dc3545",
    empty:        "#adb5bd",
  };
  const MARK_COLORS = {
    delete:  "#dc3545",
    insert:  "#198754",
    relabel: "#ffc107",
  };
  const NODE_HEIGHT = 26;
  const NODE_HSPACING = 240;
  const DURATION = 220;

  let _idCounter = 0;

  class TreeView {
    constructor(container, data, opts) {
      this.container = (typeof container === "string")
        ? document.getElementById(container)
        : container;
      this.opts = Object.assign({
        initialDepth: 1,
        marks: {},
        infoPanel: document.getElementById("node-info"),
        onNodeClick: null,
      }, opts || {});
      this.bootstrap(data);
    }

    bootstrap(data) {
      this.container.innerHTML = "";
      const width = this.container.clientWidth || 800;
      const height = this.container.clientHeight || 700;

      this.svg = d3.select(this.container)
        .append("svg")
        .attr("width", "100%")
        .attr("height", height)
        .attr("class", "tree-svg");

      this.g = this.svg.append("g").attr("class", "g-root");
      this.zoom = d3.zoom().scaleExtent([0.2, 3])
        .on("zoom", (event) => this.g.attr("transform", event.transform));
      this.svg.call(this.zoom);

      this.layout = d3.tree().nodeSize([NODE_HEIGHT + 6, NODE_HSPACING]);

      this.root = d3.hierarchy(data.root || data, (d) => d.children);
      this.root.x0 = 0;
      this.root.y0 = 0;
      this.root.each((d) => (d.id = ++_idCounter));
      this.collapseBelow(this.root, this.opts.initialDepth);
      this._computeDottedPaths(this.root, []);

      this.update(this.root);
      this.fitToView();
    }

    setMarks(marks) {
      this.opts.marks = marks || {};
      this.refreshMarks();
    }

    _computeDottedPaths(node, parents) {
      // Stable dotted path with [i] disambiguation matching the backend.
      const label = node.data.label || "country";
      const siblingsSameLabel = parents.length === 0
        ? []
        : (node.parent.children || [])
            .concat(node.parent._children || [])
            .filter((c) => c.data.label === label);
      const idx = (siblingsSameLabel.length > 1)
        ? siblingsSameLabel.indexOf(node)
        : -1;
      const seg = (parents.length === 0)
        ? "" // root has no segment
        : (idx >= 0 ? `${label}[${idx}]` : label);
      const dotted = parents.length === 0
        ? ""
        : (parents.concat([seg])).join(".");
      node._dotted = dotted;
      const childList = node.children || node._children;
      if (childList) {
        const next = parents.length === 0 ? [] : parents.concat([seg]);
        childList.forEach((c) => this._computeDottedPaths(c, next));
      }
    }

    collapseBelow(d, maxDepth) {
      if (d.depth >= maxDepth && d.children) {
        d._children = d.children;
        d.children = null;
      }
      const kids = d.children || d._children;
      if (kids) kids.forEach((c) => this.collapseBelow(c, maxDepth));
    }

    expandAll(d) {
      d = d || this.root;
      if (d._children) {
        d.children = d._children;
        d._children = null;
      }
      if (d.children) d.children.forEach((c) => this.expandAll(c));
    }

    collapseToRoot() {
      if (this.root._children && !this.root.children) {
        this.root.children = this.root._children;
        this.root._children = null;
      }
      this.collapseBelow(this.root, 1);
      this.update(this.root);
      this.fitToView();
    }

    toggle(d) {
      if (d.children) {
        d._children = d.children;
        d.children = null;
      } else if (d._children) {
        d.children = d._children;
        d._children = null;
      }
    }

    markFor(d) {
      // Look up the diff mark for a node's dotted path; descendants of a
      // marked-delete subtree also inherit the mark (the backend already
      // does the descendant expansion for deletes).
      return this.opts.marks[d._dotted] || "";
    }

    update(source) {
      const data = this.layout(this.root);
      const nodes = data.descendants();
      const links = data.descendants().slice(1);
      nodes.forEach((d) => (d.y = d.depth * NODE_HSPACING));

      const g = this.g;

      const node = g.selectAll("g.node")
        .data(nodes, (d) => d.id || (d.id = ++_idCounter));

      const nodeEnter = node.enter()
        .append("g")
        .attr("class", (d) => "node " + (d.data.kind || "structural"))
        .attr("transform", () => `translate(${source.y0},${source.x0})`)
        .on("click", (event, d) => {
          this.showNodeInfo(d);
          if (this.opts.onNodeClick) this.opts.onNodeClick(d);
          if (d.data.kind === "structural" && (d.children || d._children)) {
            this.toggle(d);
            this.update(d);
          }
        });

      // Structural circles.
      nodeEnter.filter((d) => d.data.kind === "structural")
        .append("circle")
        .attr("class", "struct-circle")
        .attr("r", 1e-6);

      nodeEnter.filter((d) => d.data.kind === "structural")
        .append("text")
        .attr("dy", "0.32em")
        .attr("x", (d) => (d.children || d._children ? -12 : 12))
        .style("text-anchor", (d) => (d.children || d._children ? "end" : "start"))
        .text((d) => d.data.label)
        .clone(true).lower()
        .attr("stroke", "white")
        .attr("stroke-width", 3);

      // Leaf pills.
      const leafEnter = nodeEnter.filter((d) => d.data.kind === "leaf");
      leafEnter.each(function (d) {
        const sel = d3.select(this);
        sel.append("rect")
          .attr("class", "leaf-pill")
          .attr("x", 0)
          .attr("y", -NODE_HEIGHT / 2)
          .attr("rx", 4).attr("ry", 4)
          .attr("height", NODE_HEIGHT)
          .attr("width", 0);
        sel.append("text")
          .attr("class", "leaf-text")
          .attr("dy", "0.32em")
          .attr("x", 8)
          .text(leafText(d.data));
        const w = sel.select("text.leaf-text").node().getBBox().width + 16;
        sel.select("rect.leaf-pill").attr("width", w);
        sel.append("circle")
          .attr("class", "leaf-dot")
          .attr("r", 4);
      });

      const nodeUpdate = nodeEnter.merge(node);
      nodeUpdate.transition().duration(DURATION)
        .attr("transform", (d) => `translate(${d.y},${d.x})`);

      // Style structural circles (color + fill respect collapse state).
      nodeUpdate.select("circle.struct-circle")
        .attr("r", 6)
        .style("fill", (d) => {
          const mk = this.markFor(d);
          if (mk) return MARK_COLORS[mk];
          return d._children ? "#fff" : "#1f3a5f";
        })
        .style("stroke", (d) => {
          const mk = this.markFor(d);
          return mk ? MARK_COLORS[mk] : "#1f3a5f";
        })
        .style("stroke-width", (d) => this.markFor(d) ? 2.5 : 2);

      // Leaf pill colors (mark wins over type).
      nodeUpdate.select("rect.leaf-pill")
        .style("stroke", (d) => {
          const mk = this.markFor(d);
          return mk ? MARK_COLORS[mk] : (TYPE_COLORS[d.data.type] || "#888");
        })
        .style("stroke-width", (d) => this.markFor(d) ? 2 : 1.5)
        .style("fill", (d) => {
          const mk = this.markFor(d);
          if (mk === "delete") return "#fdecec";
          if (mk === "insert") return "#e9f7ef";
          if (mk === "relabel") return "#fff7d6";
          return "#fff";
        });

      nodeUpdate.select("circle.leaf-dot")
        .style("fill", (d) => {
          const mk = this.markFor(d);
          return mk ? MARK_COLORS[mk] : (TYPE_COLORS[d.data.type] || "#888");
        });

      node.exit().transition().duration(DURATION)
        .attr("transform", () => `translate(${source.y},${source.x})`)
        .remove()
        .select("circle").attr("r", 1e-6);

      // Links.
      const link = g.selectAll("path.link").data(links, (d) => d.id);
      const linkEnter = link.enter().insert("path", "g")
        .attr("class", "link")
        .attr("d", () => {
          const o = { x: source.x0, y: source.y0 };
          return diagonal(o, o);
        });
      linkEnter.merge(link).transition().duration(DURATION)
        .attr("d", (d) => diagonal(d, d.parent));
      link.exit().transition().duration(DURATION)
        .attr("d", () => {
          const o = { x: source.x, y: source.y };
          return diagonal(o, o);
        }).remove();

      nodes.forEach((d) => { d.x0 = d.x; d.y0 = d.y; });
    }

    refreshMarks() {
      // Re-run the styling pass without a full layout shuffle.
      this.update(this.root);
    }

    fitToView() {
      const nodes = this.root.descendants();
      if (!nodes.length) return;
      const xMin = d3.min(nodes, (d) => d.x) - 20;
      const xMax = d3.max(nodes, (d) => d.x) + 20;
      const yMin = d3.min(nodes, (d) => d.y) - 20;
      const yMax = d3.max(nodes, (d) => d.y) + 180;
      const w = this.container.clientWidth;
      const h = this.svg.attr("height") * 1;
      const scale = Math.min(w / (yMax - yMin), h / (xMax - xMin), 1.0);
      const tx = (w - scale * (yMin + yMax)) / 2;
      const ty = (h - scale * (xMin + xMax)) / 2;
      this.svg.transition().duration(400)
        .call(this.zoom.transform,
              d3.zoomIdentity.translate(tx, ty).scale(scale));
    }

    showNodeInfo(d) {
      const panel = this.opts.infoPanel;
      if (!panel) return;
      const data = d.data;
      let html = `<h6 class="mb-2">${escapeHtml(data.label)}</h6>`;
      const mk = this.markFor(d);
      if (mk) {
        html += `<div class="mb-1"><span class="badge" style="background:${MARK_COLORS[mk]}">${mk}</span></div>`;
      }
      if (data.kind === "structural") {
        const count = (d.children || d._children || []).length;
        html += `<div class="small text-muted">structural · ${count} direct children</div>`;
      } else {
        html += `<div class="mb-1"><span class="badge bg-secondary type-badge">${data.type}</span></div>`;
        html += `<div class="info-row"><span>value</span><code>${formatRich(data)}</code></div>`;
        if (data.unit) html += `<div class="info-row"><span>unit</span><code>${escapeHtml(data.unit)}</code></div>`;
        if (data.trend !== null && data.trend !== undefined)
          html += `<div class="info-row"><span>trend</span><code>${data.trend}</code></div>`;
        if (data.taxonomy)
          html += `<div class="info-row"><span>taxonomy</span><code>${escapeHtml(data.taxonomy)}</code></div>`;
        if (data.raw && String(data.raw).trim() !== String(data.value).trim())
          html += `<div class="info-row info-raw"><span>raw</span><pre>${escapeHtml(data.raw)}</pre></div>`;
      }
      panel.innerHTML = html;
      panel.classList.add("visible");
    }
  }

  // ---------------------------------------------------- factories
  TreeView.fromData = (containerId, data, opts) => new TreeView(containerId, data, opts);

  TreeView.fromUrl = (containerId, url, opts) => {
    const container = (typeof containerId === "string")
      ? document.getElementById(containerId)
      : containerId;
    container.innerHTML =
      '<div class="tree-loading text-muted">Loading tree…</div>';
    return fetch(url).then((r) => {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then((data) => new TreeView(container, data, opts));
  };

  window.TreeView = TreeView;

  // ---------------------------------------------------- formatting helpers
  function leafText(d) {
    let v = d.value;
    if (v === null || v === undefined) return d.label + ": ∅";
    if (Array.isArray(v) && d.type === "distribution") {
      const top = v.slice(0, 2)
        .map((x) => x.path.slice(-1)[0] + " " + Math.round(x.weight * 100) + "%")
        .join(", ");
      const more = v.length > 2 ? ` +${v.length - 2}` : "";
      return `${d.label}: ${top}${more}`;
    }
    if (d.type === "currency") return `${d.label}: ${fmtCurrency(v)}`;
    if (d.type === "number") return `${d.label}: ${fmtNumber(v)}`;
    if (d.type === "percent") return `${d.label}: ${fmtNumber(v)}%`;
    if (d.type === "coordinates" && Array.isArray(v)) {
      return `${d.label}: ${v[0].toFixed(2)}, ${v[1].toFixed(2)}`;
    }
    let s = String(v);
    if (s.length > 40) s = s.slice(0, 39) + "…";
    return `${d.label}: ${s}`;
  }

  function formatRich(d) {
    const v = d.value;
    if (v === null || v === undefined) return "∅";
    if (Array.isArray(v) && d.type === "distribution") {
      return v.map((x) =>
        `<div>${x.path.join(" › ")} — <strong>${(x.weight * 100).toFixed(1)}%</strong></div>`
      ).join("");
    }
    if (d.type === "currency") return fmtCurrency(v) + " <small>USD</small>";
    if (d.type === "number") return fmtNumber(v);
    if (d.type === "percent") return fmtNumber(v) + "%";
    if (Array.isArray(v)) return v.join(", ");
    return escapeHtml(String(v));
  }

  function fmtNumber(n) {
    if (Number.isInteger(n)) return n.toLocaleString();
    return Number(n).toLocaleString(undefined, { maximumFractionDigits: 4 });
  }
  function fmtCurrency(n) {
    const x = Math.abs(n), sign = n < 0 ? "-" : "";
    if (x >= 1e12) return `${sign}$${(x / 1e12).toFixed(2)}T`;
    if (x >= 1e9)  return `${sign}$${(x / 1e9).toFixed(2)}B`;
    if (x >= 1e6)  return `${sign}$${(x / 1e6).toFixed(2)}M`;
    if (x >= 1e3)  return `${sign}$${(x / 1e3).toFixed(1)}K`;
    return `${sign}$${x.toFixed(2)}`;
  }
  function diagonal(s, t) {
    return `M ${s.y} ${s.x}
            C ${(s.y + t.y) / 2} ${s.x},
              ${(s.y + t.y) / 2} ${t.x},
              ${t.y} ${t.x}`;
  }
  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // ---------------------------------------------------- legacy auto-boot
  document.addEventListener("DOMContentLoaded", () => {
    const el = document.getElementById("tree-canvas");
    if (el && el.dataset.treeUrl) {
      const view = TreeView.fromUrl(el, el.dataset.treeUrl, { initialDepth: 1 });
      view.then((v) => {
        const eb = document.getElementById("btn-expand-all");
        const cb = document.getElementById("btn-collapse-all");
        const fb = document.getElementById("btn-fit");
        if (eb) eb.addEventListener("click", () => { v.expandAll(); v.update(v.root); v.fitToView(); });
        if (cb) cb.addEventListener("click", () => v.collapseToRoot());
        if (fb) fb.addEventListener("click", () => v.fitToView());
      });
    }
  });
})();
