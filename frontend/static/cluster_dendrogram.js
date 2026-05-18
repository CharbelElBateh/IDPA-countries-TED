// Dendrogram — built from scipy's linkage matrix.
//
// scipy.cluster.hierarchy.linkage emits one row per merge:
//   [cluster_a, cluster_b, distance, leaf_count]
// where cluster ids 0..n-1 are the original points (alphabetical name order)
// and ids n..2n-2 are the merges in order. We rebuild that as a d3.hierarchy
// node so d3.cluster() can lay it out.

(function () {
  function buildHierarchy(linkage, names) {
    const n = names.length;
    // node[id] for each cluster id (both leaves and merges).
    const node = new Map();
    for (let i = 0; i < n; i++) {
      node.set(i, { id: i, name: names[i], height: 0, children: null });
    }
    for (let i = 0; i < linkage.length; i++) {
      const [a, b, dist] = linkage[i];
      const newId = n + i;
      node.set(newId, {
        id: newId,
        height: dist,
        children: [node.get(a), node.get(b)],
      });
    }
    // The last merge is the root.
    return node.get(n + linkage.length - 1);
  }

  window.renderDendrogram = function (state) {
    const container = document.getElementById("viz-dendrogram");
    container.innerHTML = "";

    const linkage = state.run.linkage;
    if (!linkage || linkage.length === 0) {
      container.innerHTML =
        '<div class="alert alert-warning m-3">No linkage matrix (algorithm did not produce one).</div>';
      return;
    }

    // d3.cluster() expects names in the leaf order matching cluster ids
    // 0..n-1, which is the alphabetical order used by build_distance_matrix.
    const names = Object.keys(state.run.mds_2d).sort();

    const rootData = buildHierarchy(linkage, names);
    const root = d3.hierarchy(rootData);

    const n = names.length;
    const rowHeight = 14;
    const width = container.clientWidth || 900;
    const margin = { top: 20, right: 240, bottom: 20, left: 40 };
    const innerH = n * rowHeight;
    const innerW = Math.max(400, width - margin.left - margin.right);
    const height = innerH + margin.top + margin.bottom;

    const cluster = d3.cluster()
      .size([innerH, innerW])
      .separation(() => 1);
    cluster(root);

    // Re-map x (horizontal) by merge distance so the dendrogram is
    // metric, not just topological.
    const maxDist = d3.max(root.descendants(), (d) => d.data.height || 0);
    const distScale = d3.scaleLinear().domain([0, maxDist]).range([0, innerW]);
    root.each((d) => {
      d.y_orig = d.y;             // keep the original (for leaf rightmost)
      d.y = distScale(d.data.height);
    });
    // Leaves stay at the far right (height = 0 → y = 0; rotate so leaves are at right).
    // We flip orientation: x is vertical, y horizontal; leaves at right means y = innerW.
    root.each((d) => {
      if (!d.children) d.y = innerW;
    });

    const svg = d3.select(container)
      .append("svg")
      .attr("width", width)
      .attr("height", height);

    const g = svg.append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Color each leaf by its cluster.
    const colorOf = (leaf) => state.color(state.run.labels[leaf.data.name]);

    // Links — right-angle (rectangular) connectors are clearer than splines
    // for dendrograms.
    g.append("g")
      .attr("fill", "none")
      .attr("stroke", "#666")
      .attr("stroke-width", 1)
      .selectAll("path")
      .data(root.links())
      .join("path")
      .attr("d", (d) => {
        const sx = d.source.x, sy = d.source.y;
        const tx = d.target.x, ty = d.target.y;
        // Horizontal then vertical (right-angle).
        return `M${sy},${sx} H${ty} V${tx}`;
      });

    // Internal-node distance ticks (sparse).
    const tickAxis = d3.axisTop(distScale)
      .ticks(6)
      .tickFormat(d3.format(".2f"));
    g.append("g")
      .attr("color", "#999")
      .attr("transform", "translate(0,0)")
      .call(tickAxis);

    // Leaves: label + color swatch.
    const leafG = g.append("g")
      .selectAll("g")
      .data(root.leaves())
      .join("g")
      .attr("transform", (d) => `translate(${d.y},${d.x})`);

    leafG.append("circle")
      .attr("r", 4)
      .attr("fill", (d) => colorOf(d));

    leafG.append("text")
      .attr("x", 8)
      .attr("dy", "0.32em")
      .attr("font-size", 11)
      .style("cursor", "pointer")
      .text((d) => d.data.name.replace(/_/g, " "))
      .on("click", (event, d) => {
        window.location.href = `/countries/${encodeURIComponent(d.data.name)}`;
      });
  };
})();
