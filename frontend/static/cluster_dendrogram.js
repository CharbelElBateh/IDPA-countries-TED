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
        '<div class="alert warn" style="margin: 18px;">No linkage matrix (algorithm did not produce one).</div>';
      return;
    }

    // d3.cluster() expects names in the leaf order matching cluster ids
    // 0..n-1, which is the alphabetical order used by build_distance_matrix.
    const names = Object.keys(state.run.mds_2d).sort();

    const rootData = buildHierarchy(linkage, names);
    const root = d3.hierarchy(rootData);

    const n = names.length;
    // Vertical orientation: leaves spread across the X axis at the
    // bottom, merge distance on the Y axis (root at the top). Wide SVG
    // + horizontal scroll keeps all n leaf labels legible.
    const colWidth = 16;
    const margin = { top: 28, right: 24, bottom: 168, left: 64 };
    const innerW = Math.max(
      (container.clientWidth || 900) - margin.left - margin.right,
      n * colWidth);
    const plotH = 440;
    const width = innerW + margin.left + margin.right;
    const height = plotH + margin.top + margin.bottom;

    const cluster = d3.cluster()
      .size([innerW, plotH])
      .separation(() => 1);
    cluster(root);

    // Re-map y by merge distance so the dendrogram is metric, not just
    // topological. distance 0 → bottom (plotH); max distance → top (0).
    const maxDist = d3.max(root.descendants(), (d) => d.data.height || 0) || 1;
    const distScale = d3.scaleLinear()
      .domain([0, maxDist]).range([plotH, 0]);
    root.each((d) => { d.y = distScale(d.data.height || 0); });

    const svg = d3.select(container)
      .append("svg")
      .attr("width", width)
      .attr("height", height);

    const g = svg.append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const flt = state.activeFilter;
    const clusterOf = (leaf) => state.run.labels[leaf.data.name];
    const isDim = (leaf) => flt != null && clusterOf(leaf) !== flt;
    const colorOf = (leaf) => state.color(clusterOf(leaf));

    // Links — rectangular connectors: horizontal bar at the parent's
    // height, then a vertical drop to each child.
    g.append("g")
      .attr("class", "dendro-links")
      .selectAll("path")
      .data(root.links())
      .join("path")
      .attr("d", (d) => {
        const sx = d.source.x, sy = d.source.y;
        const tx = d.target.x, ty = d.target.y;
        return `M${sx},${sy} H${tx} V${ty}`;
      });

    // Merge-distance axis (vertical, left).
    const axis = d3.axisLeft(distScale).ticks(6)
      .tickFormat(d3.format(".2f"));
    g.append("g").attr("class", "dendro-axis").call(axis);
    g.append("text")
      .attr("class", "dendro-axis-title")
      .attr("transform", "rotate(-90)")
      .attr("x", -plotH / 2)
      .attr("y", -46)
      .attr("text-anchor", "middle")
      .text("merge distance");

    // Leaves at the bottom: color swatch + rotated label.
    const leafG = g.append("g")
      .selectAll("g")
      .data(root.leaves())
      .join("g")
      .attr("transform", (d) => `translate(${d.x},${plotH})`)
      .attr("opacity", (d) => isDim(d) ? 0.15 : 1);

    leafG.append("circle")
      .attr("r", 4)
      .attr("fill", (d) => colorOf(d));

    leafG.append("text")
      .attr("transform", "rotate(90)")
      .attr("x", 8)
      .attr("dy", "0.32em")
      .attr("font-size", 10)
      .attr("text-anchor", "start")
      .style("cursor", "pointer")
      .text((d) => d.data.name.replace(/_/g, " "))
      .on("click", (event, d) => {
        window.location.href = `/countries/${encodeURIComponent(d.data.name)}`;
      });
  };
})();
