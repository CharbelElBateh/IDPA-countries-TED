// 2D scatter — one point per country, colored by cluster.
//
// Two pre-computed projections are available, selected by the in-viz
// "Projection" toggle. state.scatterProjection is "mds" (default) or
// "tsne":
//   - mds:  classical Torgerson MDS, faithful to pairwise distances.
//           state.run.mds_2d holds the coords; state.run.mds_variance
//           is the per-axis % variance diagnostic that says how much
//           of the structure is actually visible in 2D.
//   - tsne: t-SNE on the same distance matrix. Preserves *cluster*
//           separation much better when the MDS variance shows lots
//           of structure hidden in higher axes, BUT the absolute
//           distances on screen are not meaningful — only the grouping
//           is. state.run.tsne_2d holds the coords; no variance.
//
// Outliers don't participate in either embedding, so they aren't drawn.
// See docs/08-design-decisions.md s16 for the rationale.

(function () {
  window.renderScatter = function (state) {
    const container = document.getElementById("viz-scatter");
    container.innerHTML = "";

    const width = container.clientWidth || 900;
    const height = container.clientHeight || 600;
    const margin = { top: 40, right: 24, bottom: 52, left: 58 };

    // Which projection — fall back to MDS if t-SNE coords aren't
    // present (older cached runs predate the field).
    const hasTsne = state.run.tsne_2d
      && Object.keys(state.run.tsne_2d).length > 0;
    let projection = state.scatterProjection || "mds";
    if (projection === "tsne" && !hasTsne) projection = "mds";

    appendProjectionToggle(container, projection, hasTsne, state);
    updateScatterCaption(projection);

    const coordSrc = projection === "tsne"
      ? state.run.tsne_2d
      : state.run.mds_2d;

    const points = Object.entries(coordSrc).map(([name, xy]) => ({
      name,
      x: xy[0],
      y: xy[1],
      cluster: state.run.labels[name],
    }));

    if (points.length === 0) {
      container.innerHTML =
        '<div class="alert alert-warning m-3">No 2D coordinates available.</div>';
      return;
    }

    const x = d3.scaleLinear()
      .domain(d3.extent(points, (d) => d.x)).nice()
      .range([margin.left, width - margin.right]);
    const y = d3.scaleLinear()
      .domain(d3.extent(points, (d) => d.y)).nice()
      .range([height - margin.bottom, margin.top]);

    const svg = d3.select(container)
      .append("svg")
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("width", "100%")
      .attr("height", "100%");

    // Reference grid. A classical-MDS embedding has NO intrinsic axes
    // or units — only the *relative distance* between two points is
    // meaningful (it approximates their dissimilarity in the chosen
    // feature). So we draw a faint grid purely for visual scale and
    // deliberately hide the arbitrary numeric tick values, then label
    // what the plot actually means.
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const gx = svg.append("g")
      .attr("class", "mds-grid")
      .attr("transform", `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(x).ticks(6).tickSize(-innerH).tickFormat(""));
    const gy = svg.append("g")
      .attr("class", "mds-grid")
      .attr("transform", `translate(${margin.left},0)`)
      .call(d3.axisLeft(y).ticks(6).tickSize(-innerW).tickFormat(""));
    gx.select(".domain").remove();
    gy.select(".domain").remove();

    // Axis titles.
    const axisLabel = projection === "tsne" ? "t-SNE" : "MDS";
    svg.append("text")
      .attr("class", "mds-axis-title")
      .attr("x", margin.left + innerW / 2)
      .attr("y", height - 12)
      .attr("text-anchor", "middle")
      .text(`${axisLabel} dimension 1  →`);
    svg.append("text")
      .attr("class", "mds-axis-title")
      .attr("transform", "rotate(-90)")
      .attr("x", -(margin.top + innerH / 2))
      .attr("y", 16)
      .attr("text-anchor", "middle")
      .text(`${axisLabel} dimension 2  →`);

    // What the grid means (so the values aren't a mystery).
    // t-SNE distances are NOT proportional to dissimilarity, so the
    // grid note has to say something different for the t-SNE view.
    const gridNoteText = projection === "tsne"
      ? "Grid = visual scale only. t-SNE coords have NO meaningful "
        + "units; only WHICH clusters are near each other is interpretable."
      : "Grid = visual scale only. Axes are arbitrary MDS units; "
        + "distance between points ≈ dissimilarity (closer = more similar).";
    svg.append("text")
      .attr("class", "mds-note")
      .attr("x", margin.left)
      .attr("y", 20)
      .text(gridNoteText);

    // Variance-explained diagnostic — only for the MDS projection
    // (t-SNE has no eigenvalue spectrum). Sits on a second line below
    // the grid note. Older cached runs may lack mds_variance entirely;
    // render nothing in that case.
    const variance = state.run.mds_variance;
    if (projection === "mds"
        && Array.isArray(variance) && variance.length > 0) {
      svg.append("text")
        .attr("class", "mds-note")
        .attr("x", margin.left)
        .attr("y", 36)
        .text(formatVariance(variance));
    }

    // Active-cluster filter: when set, only this cluster is solid;
    // the rest are faded so the selection stands out.
    const flt = state.activeFilter;
    const isDim = (cid) => flt != null && cid !== flt;

    // Convex hulls per cluster — gives a soft shape behind each group.
    const byCluster = d3.group(points, (d) => d.cluster);
    const hullGroup = svg.append("g").attr("opacity", 0.18);
    for (const [cid, members] of byCluster) {
      if (cid < 0 || members.length < 3) continue;
      if (isDim(cid)) continue;
      const coords = members.map((m) => [x(m.x), y(m.y)]);
      const hull = d3.polygonHull(coords);
      if (!hull) continue;
      hullGroup.append("path")
        .attr("d", "M" + hull.map((p) => p.join(",")).join("L") + "Z")
        .attr("fill", state.color(cid))
        .attr("stroke", state.color(cid))
        .attr("stroke-width", 2);
    }

    // Tooltip.
    const tooltip = d3.select(container)
      .append("div")
      .attr("class", "scatter-tooltip")
      .style("position", "absolute")
      .style("padding", "6px 10px")
      .style("background", "rgba(0,0,0,0.8)")
      .style("color", "#fff")
      .style("border-radius", "4px")
      .style("font-size", "13px")
      .style("pointer-events", "none")
      .style("opacity", 0);

    const medoidSet = new Set(state.run.medoids);

    // Points.
    svg.append("g")
      .selectAll("circle")
      .data(points)
      .join("circle")
      .attr("cx", (d) => x(d.x))
      .attr("cy", (d) => y(d.y))
      .attr("r",  (d) => medoidSet.has(d.name) ? 7 : 4)
      .attr("fill", (d) => state.color(d.cluster))
      .attr("stroke", (d) => medoidSet.has(d.name) ? "#000" : "#fff")
      .attr("stroke-width", (d) => medoidSet.has(d.name) ? 2 : 0.8)
      .attr("opacity", (d) => isDim(d.cluster) ? 0.12 : 1)
      .style("cursor", "pointer")
      .on("mouseover", function (event, d) {
        d3.select(this).attr("r", medoidSet.has(d.name) ? 9 : 6);
        const cluster = d.cluster === -1 ? "outlier" : `cluster ${d.cluster}`;
        const star = medoidSet.has(d.name) ? " ★ medoid" : "";
        tooltip
          .html(`<strong>${d.name.replace(/_/g, " ")}</strong><br>${cluster}${star}`)
          .style("opacity", 1);
      })
      .on("mousemove", function (event) {
        const r = container.getBoundingClientRect();
        tooltip
          .style("left", (event.clientX - r.left + 12) + "px")
          .style("top",  (event.clientY - r.top + 12) + "px");
      })
      .on("mouseout", function (event, d) {
        d3.select(this).attr("r", medoidSet.has(d.name) ? 7 : 4);
        tooltip.style("opacity", 0);
      })
      .on("click", function (event, d) {
        window.location.href = `/countries/${encodeURIComponent(d.name)}`;
      });

    // Medoid labels.
    svg.append("g")
      .selectAll("text")
      .data(points.filter((d) => medoidSet.has(d.name)))
      .join("text")
      .attr("x", (d) => x(d.x) + 10)
      .attr("y", (d) => y(d.y) + 4)
      .attr("font-size", 12)
      .attr("font-weight", 600)
      .attr("opacity", (d) => isDim(d.cluster) ? 0.12 : 1)
      .text((d) => d.name.replace(/_/g, " "));
  };

  function formatVariance(variance) {
    const ax1 = variance[0] || 0;
    const ax2 = variance[1] || 0;
    const ax3 = variance[2] || 0;
    const visible = ax1 + ax2;
    if (variance.length === 1) {
      return `Axis 1 explains ${ax1.toFixed(1)}% of variance (feature is 1-D)`;
    }
    const rest = Math.max(0, 100 - visible - ax3);
    const restNote = rest > 0.05
      ? ` · ${rest.toFixed(1)}% hidden in axes 4+`
      : "";
    return `Axes 1+2 explain ${visible.toFixed(1)}% of variance`
         + ` · axis 3: +${ax3.toFixed(1)}%${restNote}`;
  }

  function appendProjectionToggle(container, projection, hasTsne, state) {
    // Pill toggle overlaid in the top-right of the scatter container.
    // Uses the existing .btn-group + .btn.sm + .btn.active design-token
    // styles so it matches the rest of the UI.
    const tsneDisabled = hasTsne ? "" : "disabled";
    const tsneTitle = hasTsne
      ? ""
      : 'title="No t-SNE coordinates cached for this run — re-run to compute"';
    const wrap = document.createElement("div");
    wrap.className = "btn-group";
    wrap.style.cssText =
      "position: absolute; top: 10px; right: 14px; z-index: 2;";
    wrap.innerHTML = `
      <button class="btn sm ${projection === "mds" ? "active" : ""}"
              data-proj="mds">MDS</button>
      <button class="btn sm ${projection === "tsne" ? "active" : ""}"
              data-proj="tsne" ${tsneDisabled} ${tsneTitle}>t-SNE</button>
    `;
    wrap.querySelectorAll("button[data-proj]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (btn.disabled) return;
        const next = btn.dataset.proj;
        if (next === state.scatterProjection) return;
        state.scatterProjection = next;
        window.renderScatter(state);
      });
    });
    container.appendChild(wrap);
  }

  function updateScatterCaption(projection) {
    const cap = document.getElementById("viz-cap");
    if (!cap) return;
    cap.textContent = projection === "tsne"
      ? "t-SNE projection: WHICH clusters are near each other is "
        + "meaningful, but absolute distances on screen are NOT — "
        + "unlike MDS. Use this view when the MDS variance diagnostic "
        + "shows a lot of structure hidden in higher axes."
      : "Classical MDS embedding of the pairwise distance matrix. "
        + "Points close together are close in the chosen feature space.";
  }
})();
