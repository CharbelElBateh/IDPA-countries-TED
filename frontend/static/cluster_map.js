// World map (choropleth) — colors each country by its cluster id.
//
// Topology source: world-atlas (Natural Earth, 110m resolution) via CDN.
//   features are keyed by ISO 3166-1 numeric code (string, padded).
// We translate that to the project's Wikipedia-style country names via
// /api/cluster/numeric-codes, and look up cluster ids via state.run.labels.

(function () {
  const TOPOJSON_URL =
    "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

  window.renderMap = async function (state) {
    const container = document.getElementById("viz-map");
    container.innerHTML = "";

    const width = container.clientWidth || 900;
    const height = container.clientHeight || 600;

    // Reverse-lookup: numeric ISO → country name.
    const numericToName = {};
    for (const [name, num] of Object.entries(state.numericCodes)) {
      numericToName[String(parseInt(num, 10))] = name;
    }

    // Load topology.
    let topology;
    try {
      topology = await fetch(TOPOJSON_URL).then((r) => r.json());
    } catch (err) {
      container.innerHTML =
        `<div class="alert alert-warning m-3">
          Couldn't load the world topology from CDN. Check your network.
        </div>`;
      return;
    }
    const land = topojson.feature(topology, topology.objects.countries);

    // Set up SVG + projection.
    const svg = d3.select(container)
      .append("svg")
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("width", "100%")
      .attr("height", "100%");

    const projection = d3.geoNaturalEarth1()
      .fitSize([width, height], land);
    const path = d3.geoPath(projection);

    // Tooltip.
    const tooltip = d3.select(container)
      .append("div")
      .attr("class", "map-tooltip")
      .style("position", "absolute")
      .style("padding", "6px 10px")
      .style("background", "rgba(0,0,0,0.8)")
      .style("color", "#fff")
      .style("border-radius", "4px")
      .style("font-size", "13px")
      .style("pointer-events", "none")
      .style("opacity", 0);

    // Draw graticule (subtle).
    svg.append("path")
      .datum(d3.geoGraticule10())
      .attr("d", path)
      .attr("fill", "none")
      .attr("stroke", "#eee")
      .attr("stroke-width", 0.5);

    // Draw countries.
    svg.append("g")
      .selectAll("path")
      .data(land.features)
      .join("path")
      .attr("d", path)
      .attr("fill", (d) => {
        const id = String(parseInt(d.id, 10));
        const name = numericToName[id];
        if (!name) return "#f5f5f5";  // not in UN list (e.g. Greenland)
        const cid = state.run.labels[name];
        if (cid === undefined) return "#f5f5f5";
        return state.color(cid);
      })
      .attr("stroke", "#666")
      .attr("stroke-width", 0.4)
      .style("cursor", "pointer")
      .on("mouseover", function (event, d) {
        d3.select(this).attr("stroke", "#000").attr("stroke-width", 1.2);
        const id = String(parseInt(d.id, 10));
        const name = numericToName[id];
        let html;
        if (!name) {
          html = `<strong>${d.properties.name}</strong><br>
                  <em class="text-muted">not in UN member list</em>`;
        } else {
          const cid = state.run.labels[name];
          const isOut = cid === -1;
          const medoid = (cid >= 0 && state.run.medoids[cid])
            ? state.run.medoids[cid].replace(/_/g, " ")
            : null;
          html = `<strong>${name.replace(/_/g, " ")}</strong><br>
                  ${isOut
                    ? "Outlier (missing fields)"
                    : `Cluster ${cid}${medoid ? ` · medoid: ${medoid}` : ""}`}`;
        }
        tooltip.html(html).style("opacity", 1);
      })
      .on("mousemove", function (event) {
        const r = container.getBoundingClientRect();
        tooltip
          .style("left", (event.clientX - r.left + 12) + "px")
          .style("top",  (event.clientY - r.top + 12) + "px");
      })
      .on("mouseout", function () {
        d3.select(this).attr("stroke", "#666").attr("stroke-width", 0.4);
        tooltip.style("opacity", 0);
      })
      .on("click", function (event, d) {
        const id = String(parseInt(d.id, 10));
        const name = numericToName[id];
        if (name) window.location.href = `/countries/${encodeURIComponent(name)}`;
      });
  };
})();
