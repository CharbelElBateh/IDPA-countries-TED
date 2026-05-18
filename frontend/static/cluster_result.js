// Cluster result page (redesign):
// - Custom .viz-tab[data-tab] / .viz-pane[data-tab] tab system (no Bootstrap).
// - .cluster-chip click filters the viz to that cluster id.
// - Color palette uses the design-token CSS vars --c0…--c9, --c-outlier
//   so colors stay coherent with the rest of the system.

(function () {
  const $  = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  // CSS-token palette — resolved at runtime, picked up by every viz.
  const CSS_VARS = ["--c0","--c1","--c2","--c3","--c4","--c5","--c6","--c7","--c8","--c9"];
  function clusterColor(cid) {
    if (cid === -1) return getCssVar("--c-outlier") || "#bdb8af";
    return getCssVar(CSS_VARS[cid % CSS_VARS.length]) || "#2d7a82";
  }
  function getCssVar(name) {
    return getComputedStyle(document.documentElement)
      .getPropertyValue(name).trim();
  }

  const state = {
    run: null,
    isoCodes: null,
    numericCodes: null,
    color: clusterColor,
    activeFilter: null,    // cluster id currently filtered to (or null)
    scatterProjection: "mds",  // "mds" | "tsne" — set by the in-viz toggle
  };

  // ----------------------------------------------------- caption per tab
  const CAPS = {
    map: "Hover a country for cluster details. Outliers (missing fields) appear in grey.",
    scatter: "Classical MDS embedding of the pairwise distance matrix. Points close together are close in the chosen feature space.",
    dendrogram: "Bottom-up merge tree (vertical): leaves at the bottom, height = merge distance, root at the top.",
    members: "Members listed by cluster. Click a row to open the country tree.",
  };

  // ----------------------------------------------------- side panel: legend
  function renderLegend() {
    const ul = $("#cluster-legend");
    ul.innerHTML = "";

    const entries = Object.entries(state.run.cluster_sizes)
      .map(([k, v]) => [parseInt(k, 10), v])
      .filter(([k]) => k !== -1)
      .sort((a, b) => a[0] - b[0]);

    for (const [cid, n] of entries) {
      const medoid = state.run.medoids[cid] || `cluster ${cid}`;
      const li = document.createElement("li");
      li.className = `cluster-chip ${state.activeFilter === cid ? "active" : ""}`;
      li.dataset.cid = String(cid);
      li.innerHTML = `
        <span class="swatch" style="background: ${state.color(cid)};"></span>
        <span class="label">
          <span class="name">${medoid.replace(/_/g, " ")}</span>
          <span class="meta">cluster ${cid}</span>
        </span>
        <span class="ct">${n}</span>`;
      li.addEventListener("click", () => toggleFilter(cid));
      ul.appendChild(li);
    }
    // outliers chip
    const nOut = state.run.cluster_sizes["-1"] || 0;
    if (nOut > 0) {
      const li = document.createElement("li");
      li.className = `cluster-chip ${state.activeFilter === -1 ? "active" : ""}`;
      li.dataset.cid = "-1";
      li.innerHTML = `
        <span class="swatch" style="background: ${state.color(-1)};"></span>
        <span class="label">
          <span class="name">outliers</span>
          <span class="meta">missing required fields</span>
        </span>
        <span class="ct">${nOut}</span>`;
      li.addEventListener("click", () => toggleFilter(-1));
      ul.appendChild(li);
    }
  }

  function renderOutliers() {
    const ul = $("#outlier-list");
    const countEl = $("#outlier-count");
    const entries = Object.entries(state.run.outliers);
    countEl.textContent = entries.length;
    ul.innerHTML = "";
    if (entries.length === 0) {
      ul.innerHTML = '<li class="muted mono" style="font-size: 12px;">none</li>';
      return;
    }
    for (const [name, fields] of entries.sort((a, b) => a[0].localeCompare(b[0]))) {
      const li = document.createElement("li");
      li.style.cssText = "padding: 5px 0; border-bottom: 1px dashed var(--line);";
      li.innerHTML = `
        <div class="row between">
          <span class="mono" style="font-size: 12.5px; color: var(--ink);">
            ${name.replace(/_/g, " ")}
          </span>
          <span class="mono muted" style="font-size: 11px;">
            ${fields.length} missing
          </span>
        </div>
        <div style="display:flex; flex-wrap:wrap; gap: 3px; margin-top: 3px;">
          ${fields.map((m) =>
            `<span class="tag warn" style="font-size: 10px;">${m}</span>`).join("")}
        </div>`;
      ul.appendChild(li);
    }
  }

  function renderMembers() {
    const container = $("#viz-members");
    container.innerHTML = "";

    const byCluster = new Map();
    for (const [name, cid] of Object.entries(state.run.labels)) {
      if (state.activeFilter != null && state.activeFilter !== cid) continue;
      if (!byCluster.has(cid)) byCluster.set(cid, []);
      byCluster.get(cid).push(name);
    }
    const sorted = Array.from(byCluster.keys()).sort((a, b) => a - b);

    for (const cid of sorted) {
      const members = byCluster.get(cid).sort();
      const block = document.createElement("div");
      block.style.marginBottom = "18px";
      const medoidLine = cid === -1
        ? `<strong class="mono" style="font-size: 13px;">outliers</strong>`
        : `<strong class="mono" style="font-size: 13px;">
             cluster ${cid} · ${state.run.medoids[cid] ? state.run.medoids[cid].replace(/_/g, " ") : "(no medoid)"}
           </strong>`;
      block.innerHTML = `
        <div class="row mb-2">
          <span style="width:14px; height:14px; border-radius:3px;
                       background:${state.color(cid)};"></span>
          ${medoidLine}
          <span class="muted mono" style="font-size: 12px;">${members.length} members</span>
        </div>
        <div class="country-grid">
          ${members.map((m) => `
            <a class="country-card" href="/countries/${encodeURIComponent(m)}">
              <span class="cc-name">${m.replace(/_/g, " ")}</span>
              <span class="cc-iso" style="background:${state.color(cid)};
                                          color:#fff; border-color:transparent;
                                          opacity: 0.85;">
                ${cid === -1 ? "—" : cid}
              </span>
            </a>`).join("")}
        </div>`;
      container.appendChild(block);
    }
  }

  // ----------------------------------------------------- tabs
  function activateTab(tab) {
    if (!tab) return;
    $$(".viz-tab[data-tab]").forEach((t) =>
      t.classList.toggle("active", t.dataset.tab === tab));
    $$(".viz-pane[data-tab]").forEach((p) =>
      p.style.display = p.dataset.tab === tab ? "" : "none");
    $("#viz-cap").textContent = CAPS[tab] || "";

    // Re-render on every activation so the active-cluster filter is
    // always reflected. The map caches the world topology internally,
    // so this does not refetch the CDN.
    if (tab === "map" && window.renderMap) window.renderMap(state);
    else if (tab === "scatter" && window.renderScatter) window.renderScatter(state);
    else if (tab === "dendrogram" && window.renderDendrogram) window.renderDendrogram(state);
    else if (tab === "members") renderMembers();
  }
  $$(".viz-tab[data-tab]").forEach((t) =>
    t.addEventListener("click", () => activateTab(t.dataset.tab)));

  // ----------------------------------------------------- filter
  function toggleFilter(cid) {
    state.activeFilter = state.activeFilter === cid ? null : cid;
    renderLegend();
    renderFilterState();
    // Re-render whichever pane is active so the filter applies to it.
    const active = $(".viz-tab.active[data-tab]")?.dataset.tab;
    activateTab(active);
  }
  function renderFilterState() {
    const slot = $("#filter-state");
    if (state.activeFilter == null) {
      slot.innerHTML = `<span class="muted mono" style="font-size: 11px;">
        click a cluster chip to filter</span>`;
      return;
    }
    const cid = state.activeFilter;
    slot.innerHTML = `
      <span style="display: inline-flex; align-items: center; gap: 6px;
                   font-size: 12px;">
        <span style="width:10px; height:10px; border-radius:2px;
                     background: ${state.color(cid)};"></span>
        filtered · ${cid === -1 ? "outliers" : `cluster ${cid}`}
        <a href="#" data-clear style="margin-left: 8px;">clear</a>
      </span>`;
    slot.querySelector("[data-clear]")?.addEventListener("click", (e) => {
      e.preventDefault();
      toggleFilter(state.activeFilter);
    });
  }

  // ----------------------------------------------------- bootstrap
  async function fetchJsonSafe(url, fallback) {
    // Codes are only needed by the world map — a missing/!ok dataset
    // must NOT take down the legend, outliers, scatter, or members.
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error("HTTP " + res.status);
      return await res.json();
    } catch (err) {
      console.warn(`Optional dataset ${url} unavailable:`, err.message);
      return fallback;
    }
  }

  async function init() {
    const runRes = await fetch(
      `/api/cluster/runs/${encodeURIComponent(window.RUN_ID)}`);
    if (!runRes.ok) {
      throw new Error(`cluster run request failed (HTTP ${runRes.status})`);
    }
    state.run = await runRes.json();
    if (state.run && state.run.error) {
      throw new Error(state.run.error);
    }

    // These two are optional (world map only) — degrade gracefully.
    state.isoCodes = await fetchJsonSafe("/api/cluster/iso-codes", {});
    state.numericCodes = await fetchJsonSafe("/api/cluster/numeric-codes", {});

    renderLegend();
    renderOutliers();
    renderFilterState();
    activateTab("map");
  }
  init().catch((err) => {
    console.error(err);
    const frame = $("#viz-frame");
    if (frame) {
      frame.innerHTML =
        `<div class="alert danger" style="margin: 18px;">
           Failed to load cluster run: ${err.message}
         </div>`;
    }
  });
})();
