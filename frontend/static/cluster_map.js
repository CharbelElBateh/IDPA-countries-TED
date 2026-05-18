// World map (choropleth) — colors each country by its cluster id.
//
// Topology source: world-atlas (Natural Earth, 110m resolution) via CDN.
//   features are keyed by ISO 3166-1 numeric code (string, padded).
// We translate that to the project's Wikipedia-style country names via
// /api/cluster/numeric-codes, and look up cluster ids via state.run.labels.

(function () {
  const TOPOJSON_URL =
    "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

  // Cache the world topology across re-renders (the map re-renders on
  // every tab switch / filter toggle — don't refetch the CDN each time).
  let _topology = null;

  window.renderMap = async function (state) {
    const container = document.getElementById("viz-map");
    container.innerHTML = "";

    if (!state.numericCodes ||
        Object.keys(state.numericCodes).length === 0) {
      container.innerHTML =
        `<div class="alert warn" style="margin: 18px;">
           Country-code map unavailable, so the choropleth can't be
           drawn. Run <code>python scripts/build_country_codes.py</code>
           to generate <code>data/country_numeric_codes.json</code>,
           then reload. The other tabs still work.
         </div>`;
      return;
    }

    const width = container.clientWidth || 900;
    const height = container.clientHeight || 600;

    // Reverse-lookup: numeric ISO → country name.
    const numericToName = {};
    for (const [name, num] of Object.entries(state.numericCodes)) {
      numericToName[String(parseInt(num, 10))] = name;
    }

    // Load topology (cached after the first successful fetch).
    let topology = _topology;
    if (!topology) {
      try {
        topology = await fetch(TOPOJSON_URL).then((r) => r.json());
        _topology = topology;
      } catch (err) {
        container.innerHTML =
          `<div class="alert warn" style="margin: 18px;">
            Couldn't load the world topology from CDN. Check your network.
          </div>`;
        return;
      }
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
        // When a cluster filter is active, fade everything else out.
        if (state.activeFilter != null && cid !== state.activeFilter)
          return "#eceadf";
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
