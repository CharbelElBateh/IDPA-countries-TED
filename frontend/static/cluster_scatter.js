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
    const margin = { top: 20, right: 20, bottom: 30, left: 30 };

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

    // Axes (subtle — MDS axes have no real meaning).
    svg.append("g")
      .attr("transform", `translate(0,${height - margin.bottom})`)
      .attr("opacity", 0.3)
      .call(d3.axisBottom(x).ticks(5));
    svg.append("g")
      .attr("transform", `translate(${margin.left},0)`)
      .attr("opacity", 0.3)
      .call(d3.axisLeft(y).ticks(5));

    // Convex hulls per cluster — gives a soft shape behind each group.
    const byCluster = d3.group(points, (d) => d.cluster);
    const hullGroup = svg.append("g").attr("opacity", 0.18);
    for (const [cid, members] of byCluster) {
      if (cid < 0 || members.length < 3) continue;
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
      .text((d) => d.name.replace(/_/g, " "));
  };
})();
