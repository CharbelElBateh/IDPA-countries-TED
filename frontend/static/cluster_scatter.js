// 2D MDS scatter — one point per country, colored by cluster.
//
// Coordinates come pre-computed from src/clustering/embedding.py and are
// stored as state.run.mds_2d = {country_name: [x, y]}. Outliers don't
// participate in MDS, so they aren't drawn.

(function () {
  window.renderScatter = function (state) {
    const container = document.getElementById("viz-scatter");
    container.innerHTML = "";

    const width = container.clientWidth || 900;
    const height = container.clientHeight || 600;
    const margin = { top: 40, right: 24, bottom: 52, left: 58 };

    const points = Object.entries(state.run.mds_2d).map(([name, xy]) => ({
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
    svg.append("text")
      .attr("class", "mds-axis-title")
      .attr("x", margin.left + innerW / 2)
      .attr("y", height - 12)
      .attr("text-anchor", "middle")
      .text("MDS dimension 1  →");
    svg.append("text")
      .attr("class", "mds-axis-title")
      .attr("transform", "rotate(-90)")
      .attr("x", -(margin.top + innerH / 2))
      .attr("y", 16)
      .attr("text-anchor", "middle")
      .text("MDS dimension 2  →");

    // What the grid means (so the values aren't a mystery).
    svg.append("text")
      .attr("class", "mds-note")
      .attr("x", margin.left)
      .attr("y", 20)
      .text("Grid = visual scale only. Axes are arbitrary MDS units; "
            + "distance between points ≈ dissimilarity (closer = more similar).");

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
})();
