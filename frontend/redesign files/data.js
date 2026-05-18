/* ============================================================
   IDPA mock data — realistic enough to design with
   ============================================================ */

const COUNTRIES = [
  ["Afghanistan","AF"],["Albania","AL"],["Algeria","DZ"],["Andorra","AD"],
  ["Angola","AO"],["Argentina","AR"],["Armenia","AM"],["Australia","AU"],
  ["Austria","AT"],["Azerbaijan","AZ"],["Bahrain","BH"],["Bangladesh","BD"],
  ["Belgium","BE"],["Bhutan","BT"],["Bolivia","BO"],["Bosnia and Herzegovina","BA"],
  ["Botswana","BW"],["Brazil","BR"],["Bulgaria","BG"],["Burkina Faso","BF"],
  ["Burundi","BI"],["Cambodia","KH"],["Cameroon","CM"],["Canada","CA"],
  ["Chile","CL"],["China","CN"],["Colombia","CO"],["Costa Rica","CR"],
  ["Croatia","HR"],["Cuba","CU"],["Cyprus","CY"],["Czech Republic","CZ"],
  ["Denmark","DK"],["Ecuador","EC"],["Egypt","EG"],["Estonia","EE"],
  ["Ethiopia","ET"],["Finland","FI"],["France","FR"],["Georgia","GE"],
  ["Germany","DE"],["Ghana","GH"],["Greece","GR"],["Guatemala","GT"],
  ["Honduras","HN"],["Hungary","HU"],["Iceland","IS"],["India","IN"],
  ["Indonesia","ID"],["Iran","IR"],["Iraq","IQ"],["Ireland","IE"],
  ["Israel","IL"],["Italy","IT"],["Jamaica","JM"],["Japan","JP"],
  ["Jordan","JO"],["Kazakhstan","KZ"],["Kenya","KE"],["Kuwait","KW"],
  ["Laos","LA"],["Latvia","LV"],["Lebanon","LB"],["Liberia","LR"],
  ["Libya","LY"],["Lithuania","LT"],["Luxembourg","LU"],["Madagascar","MG"],
  ["Malawi","MW"],["Malaysia","MY"],["Mali","ML"],["Malta","MT"],
  ["Mexico","MX"],["Moldova","MD"],["Mongolia","MN"],["Montenegro","ME"],
  ["Morocco","MA"],["Mozambique","MZ"],["Myanmar","MM"],["Namibia","NA"],
  ["Nepal","NP"],["Netherlands","NL"],["New Zealand","NZ"],["Nicaragua","NI"],
  ["Niger","NE"],["Nigeria","NG"],["North Macedonia","MK"],["Norway","NO"],
  ["Oman","OM"],["Pakistan","PK"],["Panama","PA"],["Paraguay","PY"],
  ["Peru","PE"],["Philippines","PH"],["Poland","PL"],["Portugal","PT"],
  ["Qatar","QA"],["Romania","RO"],["Russia","RU"],["Rwanda","RW"],
  ["Saudi Arabia","SA"],["Senegal","SN"],["Serbia","RS"],["Singapore","SG"],
  ["Slovakia","SK"],["Slovenia","SI"],["Somalia","SO"],["South Africa","ZA"],
  ["South Korea","KR"],["Spain","ES"],["Sri Lanka","LK"],["Sudan","SD"],
  ["Sweden","SE"],["Switzerland","CH"],["Syria","SY"],["Tajikistan","TJ"],
  ["Tanzania","TZ"],["Thailand","TH"],["Tunisia","TN"],["Turkey","TR"],
  ["Turkmenistan","TM"],["Tuvalu","TV"],["Uganda","UG"],["Ukraine","UA"],
  ["United Arab Emirates","AE"],["United Kingdom","GB"],["United States","US"],
  ["Uruguay","UY"],["Uzbekistan","UZ"],["Venezuela","VE"],["Vietnam","VN"],
  ["Yemen","YE"],["Zambia","ZM"],["Zimbabwe","ZW"],
];

/* ----- a deeply-rendered tree for Lebanon ----- */
const LEBANON_TREE = {
  name: "Lebanon",
  iso: "LB",
  size: 142,
  height: 4,
  root: {
    label: "country",
    children: [
      { kind: "structural", label: "identity", count: 4, leaves: [
        { label: "official_name",  type: "text",     value: "Lebanese Republic" },
        { label: "common_name",    type: "text",     value: "Lebanon" },
        { label: "demonym",        type: "text",     value: "Lebanese" },
        { label: "motto",          type: "text",     value: "—" },
      ]},
      { kind: "structural", label: "geography", count: 8, leaves: [
        { label: "capital",        type: "wikilink", value: "Beirut" },
        { label: "largest_city",   type: "wikilink", value: "Beirut" },
        { label: "area.km2",       type: "number",   value: 10452, unit: "km²" },
        { label: "area.water_pct", type: "percent",  value: 1.6 },
        { label: "coordinates",    type: "coordinates", value: [33.8547, 35.8623] },
        { label: "climate",        type: "text",     value: "Mediterranean" },
        { label: "borders.count",  type: "number",   value: 2 },
        { label: "coastline_km",   type: "number",   value: 225, unit: "km" },
      ]},
      { kind: "structural", label: "government", count: 7, leaves: [
        { label: "type",           type: "text",     value: "Unitary parliamentary confessionalist republic" },
        { label: "head_of_state",  type: "wikilink", value: "Joseph Aoun" },
        { label: "head_of_gov",    type: "wikilink", value: "Najib Mikati" },
        { label: "legislature",    type: "wikilink", value: "Parliament of Lebanon" },
        { label: "independence",   type: "date",     value: "1943-11-22" },
        { label: "established",    type: "year",     value: 1920 },
        { label: "constitution",   type: "year",     value: 1926 },
      ]},
      { kind: "structural", label: "economy", count: 9, leaves: [
        { label: "gdp_nominal.value", type: "currency", value: 23130000000, trend: -1 },
        { label: "gdp_nominal.year",  type: "year",     value: 2023 },
        { label: "gdp_ppp.value",     type: "currency", value: 78230000000, trend: -1 },
        { label: "gdp_per_capita",    type: "currency", value: 4136,        trend: -1 },
        { label: "currency",          type: "wikilink", value: "Lebanese pound" },
        { label: "currency_code",     type: "text",     value: "LBP" },
        { label: "inflation",         type: "percent",  value: 221.3, trend: 1 },
        { label: "unemployment",      type: "percent",  value: 29.6,  trend: 1 },
        { label: "gini",              type: "number",   value: 31.8 },
      ]},
      { kind: "structural", label: "demographics", count: 8, leaves: [
        { label: "population",   type: "number",  value: 5364482, trend: -1 },
        { label: "density.km2",  type: "number",  value: 560,     unit: "/km²" },
        { label: "median_age",   type: "number",  value: 33.7,    unit: "yr" },
        { label: "life_exp",     type: "number",  value: 78.9,    unit: "yr", trend: 1 },
        { label: "languages",    type: "distribution", value: [
            { path: ["Arabic"],   weight: 0.95 },
            { path: ["French"],   weight: 0.40 },
            { path: ["English"],  weight: 0.30 },
            { path: ["Armenian"], weight: 0.04 },
        ]},
        { label: "religion",     type: "distribution", value: [
            { path: ["Islam","Sunni"],     weight: 0.317 },
            { path: ["Islam","Shia"],      weight: 0.317 },
            { path: ["Christianity","Maronite"], weight: 0.21 },
            { path: ["Christianity","Greek Orthodox"], weight: 0.08 },
            { path: ["Druze"],             weight: 0.045 },
            { path: ["Other"],             weight: 0.031 },
        ]},
        { label: "urban_pct",    type: "percent", value: 88.9 },
        { label: "literacy",     type: "percent", value: 95.1, trend: 1 },
      ]},
      { kind: "structural", label: "codes", count: 4, leaves: [
        { label: "iso_3166_a2", type: "text", value: "LB" },
        { label: "iso_3166_a3", type: "text", value: "LBN" },
        { label: "calling",     type: "text", value: "+961" },
        { label: "tld",         type: "text", value: ".lb" },
      ]},
    ],
  },
};

/* ----- distribution swatch palette for chips ----- */
const DIST_PALETTE = ["#2d7a82","#c2691d","#6b4f8a","#9b8a1a","#b04a5a","#3a6ab0","#4a7a3a"];

/* ----- compare diff (Lebanon -> Switzerland) ----- */
const COMPARE_DATA = {
  country1: "Lebanon",
  country2: "Switzerland",
  algorithm: "chawathe",
  cost_model: "symmetric",
  forward_cost: 40.13,
  reverse_cost: 38.71,
  forward_ops: { delete: 8, insert: 12, relabel: 23 },
  reverse_ops: { delete: 12, insert: 8, relabel: 23 },
  script: [
    { op: "relabel", path: "government.type",            from: "parliamentary confessionalist",      to: "directorial federal republic",      cost: 2.1 },
    { op: "relabel", path: "geography.capital",          from: "Beirut",                              to: "Bern",                              cost: 0.8 },
    { op: "relabel", path: "demographics.population",    from: "5,364,482",                           to: "8,776,300",                         cost: 0.7 },
    { op: "delete",  path: "economy.inflation",          from: "221.3%",                              to: null,                                cost: 1.4 },
    { op: "insert",  path: "economy.export_partners",    from: null,                                  to: "DE, US, IT, FR",                    cost: 1.2 },
    { op: "relabel", path: "demographics.religion",      from: "Islam 63%, Christianity 29%, Druze 4%", to: "Christianity 65%, none 30%",      cost: 3.4 },
    { op: "relabel", path: "economy.gdp_nominal.value",  from: "$23.13B",                             to: "$818.43B",                          cost: 2.8 },
    { op: "relabel", path: "economy.currency",           from: "Lebanese pound",                      to: "Swiss franc",                       cost: 1.0 },
    { op: "insert",  path: "geography.elevation.max",    from: null,                                  to: "4634 m",                            cost: 0.6 },
    { op: "insert",  path: "geography.elevation.min",    from: null,                                  to: "193 m",                             cost: 0.6 },
    { op: "delete",  path: "geography.coastline_km",     from: "225 km",                              to: null,                                cost: 0.5 },
    { op: "relabel", path: "demographics.languages",     from: "Arabic, French, English",             to: "German, French, Italian, Romansh",  cost: 2.5 },
    { op: "relabel", path: "geography.area.km2",         from: "10,452",                              to: "41,285",                            cost: 0.6 },
    { op: "relabel", path: "demographics.life_exp",      from: "78.9 yr",                             to: "83.8 yr",                           cost: 0.3 },
  ],
};

/* ----- cluster fields ----- */
const FEATURE_GROUPS = {
  identity: [
    { path: "identity.official_name", label: "official_name", kind: "text",     w: 0.5 },
    { path: "identity.common_name",   label: "common_name",   kind: "text",     w: 0.5 },
    { path: "identity.demonym",       label: "demonym",       kind: "text",     w: 0.3 },
    { path: "identity.motto",         label: "motto",         kind: "text",     w: 0.3 },
  ],
  geography: [
    { path: "geography.capital",       label: "capital",       kind: "wikilink",    w: 0.5 },
    { path: "geography.largest_city",  label: "largest_city",  kind: "wikilink",    w: 0.5 },
    { path: "geography.area.km2",      label: "area.km2",      kind: "number",      w: 1.0 },
    { path: "geography.coordinates",   label: "coordinates",   kind: "coordinates", w: 1.2 },
    { path: "geography.climate",       label: "climate",       kind: "text",        w: 0.8 },
    { path: "geography.borders.count", label: "borders.count", kind: "number",      w: 0.6 },
  ],
  government: [
    { path: "government.type",         label: "type",          kind: "text",     w: 1.6 },
    { path: "government.head_of_state",label: "head_of_state", kind: "wikilink", w: 0.4 },
    { path: "government.head_of_gov",  label: "head_of_gov",   kind: "wikilink", w: 0.4 },
    { path: "government.legislature",  label: "legislature",   kind: "wikilink", w: 0.6 },
    { path: "government.independence", label: "independence",  kind: "date",     w: 0.8 },
    { path: "government.established",  label: "established",   kind: "year",     w: 0.8 },
  ],
  economy: [
    { path: "economy.gdp_nominal.value", label: "gdp_nominal.value", kind: "currency", w: 1.4 },
    { path: "economy.gdp_ppp.value",     label: "gdp_ppp.value",     kind: "currency", w: 1.4 },
    { path: "economy.gdp_per_capita",    label: "gdp_per_capita",    kind: "currency", w: 1.6 },
    { path: "economy.currency",          label: "currency",          kind: "wikilink", w: 0.6 },
    { path: "economy.inflation",         label: "inflation",         kind: "percent",  w: 1.0 },
    { path: "economy.unemployment",      label: "unemployment",      kind: "percent",  w: 1.0 },
    { path: "economy.gini",              label: "gini",              kind: "number",   w: 1.0 },
  ],
  demographics: [
    { path: "demographics.population",  label: "population",  kind: "number",       w: 1.2 },
    { path: "demographics.density.km2", label: "density.km2", kind: "number",       w: 1.0 },
    { path: "demographics.median_age",  label: "median_age",  kind: "number",       w: 0.8 },
    { path: "demographics.life_exp",    label: "life_exp",    kind: "number",       w: 0.8 },
    { path: "demographics.languages",   label: "languages",   kind: "distribution", w: 1.6 },
    { path: "demographics.religion",    label: "religion",    kind: "distribution", w: 1.8 },
    { path: "demographics.urban_pct",   label: "urban_pct",   kind: "percent",      w: 0.8 },
    { path: "demographics.literacy",    label: "literacy",    kind: "percent",      w: 0.6 },
  ],
  codes: [
    { path: "codes.iso_3166_a2", label: "iso_3166_a2", kind: "text", w: 0.2 },
    { path: "codes.iso_3166_a3", label: "iso_3166_a3", kind: "text", w: 0.2 },
    { path: "codes.calling",     label: "calling",     kind: "text", w: 0.2 },
    { path: "codes.tld",         label: "tld",         kind: "text", w: 0.2 },
  ],
};

/* preset: politics + economy + religion */
const PRESET_PATHS = new Set([
  "government.type", "government.legislature", "government.independence",
  "economy.gdp_per_capita", "economy.gdp_nominal.value", "economy.inflation",
  "economy.gini", "demographics.religion",
]);

/* ----- mock cluster result (5 clusters + 8 outliers) ----- */
const CLUSTER_RESULT = {
  algorithm: "kmedoids",
  k: 5,
  n_outliers: 8,
  silhouette: 0.421,
  fields: ["government.type", "economy.gdp_per_capita", "demographics.religion",
           "economy.inflation", "demographics.population"],
  clusters: [
    { id: 0, medoid: "France",  size: 41, color: "var(--c0)", note: "high-income parliamentary / mixed Christian" },
    { id: 1, medoid: "Brazil",  size: 38, color: "var(--c1)", note: "middle-income presidential / Catholic-majority" },
    { id: 2, medoid: "Egypt",   size: 27, color: "var(--c2)", note: "Sunni-majority republic" },
    { id: 3, medoid: "Vietnam", size: 24, color: "var(--c3)", note: "single-party / mixed religion" },
    { id: 4, medoid: "Iceland", size: 19, color: "var(--c4)", note: "small high-income / Protestant" },
  ],
  outliers: [
    { name: "Tuvalu",       missing: ["economy.gdp_ppp.value", "economy.inflation"] },
    { name: "North Korea",  missing: ["economy.gdp_nominal.value", "economy.gini"] },
    { name: "Vatican City", missing: ["economy.gdp_nominal.value", "demographics.life_exp"] },
    { name: "Andorra",      missing: ["economy.gini"] },
    { name: "Nauru",        missing: ["economy.gdp_per_capita", "economy.inflation"] },
    { name: "South Sudan",  missing: ["economy.gini", "demographics.life_exp"] },
    { name: "Eritrea",      missing: ["economy.gdp_per_capita", "economy.inflation"] },
    { name: "Somalia",      missing: ["economy.gini", "demographics.literacy"] },
  ],
};

/* mock recent runs */
const RECENT_RUNS = [
  { algorithm: "kmedoids",                  k: 5, n_outliers: 8,  silhouette: 0.421, fields: ["government.type","economy.gdp_per_capita","demographics.religion","economy.inflation","demographics.population"], when: "2026-05-17 14:08" },
  { algorithm: "hierarchical_agglomerative",k: 6, n_outliers: 11, silhouette: 0.387, fields: ["demographics.religion","demographics.languages","government.type"], when: "2026-05-17 11:42" },
  { algorithm: "kmedoids",                  k: 8, n_outliers: 4,  silhouette: 0.298, fields: ["economy.gdp_per_capita","economy.gini","demographics.urban_pct","demographics.literacy"], when: "2026-05-16 18:21" },
  { algorithm: "hierarchical_agglomerative",k: 4, n_outliers: 12, silhouette: 0.453, fields: ["government.type","government.legislature","demographics.religion"], when: "2026-05-16 09:55" },
  { algorithm: "kmedoids",                  k: 5, n_outliers: 6,  silhouette: 0.402, fields: ["economy.gdp_nominal.value","economy.gdp_ppp.value","economy.gdp_per_capita","economy.inflation"], when: "2026-05-15 22:10" },
];

/* mock map dots: project country onto fake xy in a world rect */
function placeDot(iso) {
  // pseudo-random but deterministic
  let h = 0;
  for (let i = 0; i < iso.length; i++) h = (h * 31 + iso.charCodeAt(i)) | 0;
  const x = ((h & 0xff) / 255) * 0.86 + 0.07;
  const y = (((h >> 8) & 0xff) / 255) * 0.65 + 0.18;
  return { x, y };
}

// assign each country to a cluster deterministically
const COUNTRY_CLUSTERS = (() => {
  const out = {};
  COUNTRIES.forEach(([name, iso], i) => {
    let cid;
    const outlierNames = new Set(CLUSTER_RESULT.outliers.map(o => o.name));
    if (outlierNames.has(name)) cid = -1;
    else cid = (iso.charCodeAt(0) + iso.charCodeAt(1) + i) % 5;
    out[name] = cid;
  });
  return out;
})();

Object.assign(window, {
  COUNTRIES, LEBANON_TREE, DIST_PALETTE, COMPARE_DATA,
  FEATURE_GROUPS, PRESET_PATHS, CLUSTER_RESULT, RECENT_RUNS,
  COUNTRY_CLUSTERS, placeDot,
});
