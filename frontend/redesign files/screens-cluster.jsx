/* ============================================================
   IDPA — Cluster form + Cluster result
   ============================================================ */

function ScreenClusterForm({ go }) {
  const [algo, setAlgo] = useState("kmedoids");
  const [cm,   setCm]   = useState("symmetric");
  const [k,    setK]    = useState(5);
  const [init, setInit] = useState("build");
  const [maxIter, setMaxIter] = useState(100);
  const [seed,    setSeed]    = useState(0);
  const [linkage, setLinkage] = useState("average");
  const [dThresh, setDThresh] = useState("");

  // selection: path -> { on, weight }
  const initSel = useMemo(() => {
    const m = {};
    Object.values(FEATURE_GROUPS).flat().forEach(f => {
      m[f.path] = { on: PRESET_PATHS.has(f.path), w: f.w };
    });
    return m;
  }, []);
  const [sel, setSel] = useState(initSel);

  const setRow = (path, patch) => setSel(s => ({ ...s, [path]: { ...s[path], ...patch } }));
  const allFields = Object.values(FEATURE_GROUPS).flat();
  const total     = allFields.length;
  const onCount   = Object.values(sel).filter(s => s.on).length;
  const totalW    = Object.entries(sel).filter(([_,s]) => s.on).reduce((a,[_,s]) => a + Number(s.w || 0), 0);

  const bulkAll  = () => setSel(s => { const n = {...s}; Object.keys(n).forEach(k => n[k] = { ...n[k], on: true });  return n; });
  const bulkNone = () => setSel(s => { const n = {...s}; Object.keys(n).forEach(k => n[k] = { ...n[k], on: false }); return n; });
  const bulkPreset = () => setSel(s => { const n = {...s}; Object.keys(n).forEach(k => n[k] = { ...n[k], on: PRESET_PATHS.has(k) }); return n; });

  const groupNames = Object.keys(FEATURE_GROUPS);
  const groupSelected = (g) => FEATURE_GROUPS[g].filter(f => sel[f.path].on).length;

  return (
    <div className="screen">
      <div className="page-head">
        <div>
          <div className="eyebrow">Unsupervised grouping</div>
          <h1>Cluster countries</h1>
          <p className="lede">
            Group the 192 UN member states by similarity on a chosen set of
            typed infobox fields. Per-leaf-type distance from{" "}
            <code>src/distances.py</code> (Levenshtein for text, log-scale for
            currency, EMD over taxonomies for distributions, haversine for
            coordinates).
          </p>
        </div>
      </div>

      {/* parameters card */}
      <div className="params-card">
        <div className="params-row">
          <div className="pleft">
            <span className="label">Algorithm</span>
            <p className="hint">Two implementations. k-medoids is fast and gives clean assignments; agglomerative gives a merge tree.</p>
          </div>
          <div className="pright">
            <span className="seg">
              <span className={`opt ${algo==="kmedoids"?"active":""}`} onClick={() => setAlgo("kmedoids")}>k-medoids</span>
              <span className={`opt ${algo==="hierarchical_agglomerative"?"active":""}`} onClick={() => setAlgo("hierarchical_agglomerative")}>hierarchical_agglomerative</span>
            </span>
            <div className="field">
              <label>Cost model</label>
              <select className="select" value={cm} onChange={e => setCm(e.target.value)}>
                <option value="symmetric">symmetric</option>
                <option value="asymmetric">asymmetric</option>
              </select>
            </div>
          </div>
        </div>

        <div className="params-row">
          <div className="pleft">
            <span className="label">{algo === "kmedoids" ? "k-medoids knobs" : "Linkage knobs"}</span>
            <p className="hint">
              {algo === "kmedoids"
                ? "Choose number of clusters and initialization strategy."
                : "Linkage criterion; optional distance threshold overrides k by cutting the dendrogram at a given height."}
            </p>
          </div>
          <div className="pright">
            {algo === "kmedoids" ? (
              <Fragment>
                <div className="field k">
                  <label>k (clusters)</label>
                  <input className="input mono" type="number" min={2} max={20} value={k} onChange={e => setK(+e.target.value)} />
                </div>
                <div className="field">
                  <label>init</label>
                  <select className="select" value={init} onChange={e => setInit(e.target.value)}>
                    <option value="build">build (greedy)</option>
                    <option value="random">random</option>
                  </select>
                </div>
                <div className="field k">
                  <label>max_iter</label>
                  <input className="input mono" type="number" min={1} max={1000} value={maxIter} onChange={e => setMaxIter(+e.target.value)} />
                </div>
                <div className="field k">
                  <label>random_seed</label>
                  <input className="input mono" type="number" value={seed} onChange={e => setSeed(+e.target.value)} />
                </div>
              </Fragment>
            ) : (
              <Fragment>
                <div className="field k">
                  <label>k (clusters)</label>
                  <input className="input mono" type="number" min={2} max={20} value={k} onChange={e => setK(+e.target.value)} />
                </div>
                <div className="field">
                  <label>linkage</label>
                  <select className="select" value={linkage} onChange={e => setLinkage(e.target.value)}>
                    <option value="average">average</option>
                    <option value="complete">complete</option>
                    <option value="single">single</option>
                  </select>
                </div>
                <div className="field">
                  <label>distance threshold <span className="muted" style={{ textTransform:"none" }}>(overrides k)</span></label>
                  <input className="input mono" type="number" step={0.01} placeholder="optional"
                         value={dThresh} onChange={e => setDThresh(e.target.value)} />
                </div>
              </Fragment>
            )}
          </div>
        </div>
      </div>

      {/* features card */}
      <div className="features-card">
        <div className="features-head">
          <h3>
            Features
            <span className="ct">{onCount}/{total} on</span>
            <span className="muted mono" style={{ fontSize: 11.5, fontWeight: 400 }}>
              · Σw = {totalW.toFixed(1)}
            </span>
          </h3>
          <div className="features-bulk">
            <button className="btn sm" onClick={bulkPreset}><Icon name="filter" size={11}/> Preset · politics + economy + religion</button>
            <button className="btn sm" onClick={bulkAll}>Select all</button>
            <button className="btn sm" onClick={bulkNone}>Clear</button>
          </div>
        </div>

        {groupNames.map(g => {
          const fields = FEATURE_GROUPS[g];
          const onG = groupSelected(g);
          return (
            <details className="feature-group" key={g} open={onG > 0 || ["government","economy","demographics"].includes(g)}>
              <summary>
                <span></span>
                <span className="g-name">{g}</span>
                <span className="g-meta">{fields.length} fields · {fields.map(f => f.kind).filter((v,i,a) => a.indexOf(v)===i).join(", ")}</span>
                <GroupSpark on={onG} total={fields.length} />
                <span className={`g-ct ${onG ? "has" : ""}`}>{onG}/{fields.length}</span>
              </summary>
              <div className="feature-list">
                {fields.map(f => {
                  const s = sel[f.path];
                  return (
                    <label key={f.path} className={`feature-row ${s.on ? "on" : "off"}`}>
                      <input type="checkbox" className="checkbox" checked={s.on}
                             onChange={e => setRow(f.path, { on: e.target.checked })} />
                      <span className="fl">
                        <span className="fn"><FieldPath path={f.path} /></span>
                        <TypeBadge type={f.kind} />
                      </span>
                      <span className="weight">
                        w
                        <input className="winput mono" type="number" step="0.1" min="0"
                               value={s.w}
                               disabled={!s.on}
                               onChange={e => setRow(f.path, { w: e.target.value })} />
                      </span>
                    </label>
                  );
                })}
              </div>
            </details>
          );
        })}
      </div>

      <div className="run-bar">
        <div className="summary">
          <span><span className="k">algorithm</span> <span className="v">{algo}</span></span>
          <span><span className="k">k</span> <span className="v">{k}</span></span>
          <span><span className="k">features</span> <span className="v">{onCount}</span></span>
          <span><span className="k">Σ weight</span> <span className="v">{totalW.toFixed(1)}</span></span>
          <span><span className="k">cost</span> <span className="v">{cm}</span></span>
        </div>
        <button className="btn lg">Save preset…</button>
        <button className="btn primary lg" onClick={() => go({ name: "cluster-result" })}>
          <Icon name="play" size={12}/> Run clustering
        </button>
      </div>

      <h3 className="mt-6 mb-2">
        Recent runs <span className="muted mono" style={{ fontSize: 13, fontWeight: 400 }}>· {RECENT_RUNS.length}</span>
      </h3>
      <div className="runs-grid">
        {RECENT_RUNS.map((r, i) => (
          <a className="run-card" key={i} onClick={() => go({ name: "cluster-result" })}>
            <div className="rc-head">
              <span className="rc-algo">{r.algorithm}</span>
              <span className="rc-time"><Icon name="history" size={11}/> {r.when.slice(5)}</span>
            </div>
            <div className="rc-stats">
              <div className="rc-stat"><div className="v">{r.k}</div><div className="k">clusters</div></div>
              <div className="rc-stat"><div className="v">{r.n_outliers}</div><div className="k">outliers</div></div>
              <div className="rc-stat"><div className="v">{r.silhouette.toFixed(2)}</div><div className="k">silhouette</div></div>
            </div>
            <div className="rc-fields">
              {r.fields.map(f => <span className="tk" key={f}>{f}</span>)}
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}

/* ----- cluster result ----- */
function ClusterMapMock({ activeCluster, onPickCluster }) {
  // mock world map: continents as simple grouped blobs
  // followed by 192 dots colored by cluster
  const continents = [
    { d:"M 75 110 Q 110 88 165 96 Q 230 86 270 110 Q 295 132 285 168 Q 260 198 200 200 Q 150 205 110 184 Q 78 168 70 142 Z", name:"NA" },
    { d:"M 235 220 Q 260 218 280 240 Q 295 280 270 320 Q 245 360 220 350 Q 200 320 205 280 Q 218 240 235 220 Z", name:"SA" },
    { d:"M 360 100 Q 410 92 450 110 Q 490 130 478 162 Q 470 188 430 195 Q 380 198 355 175 Q 340 142 360 100 Z", name:"EU" },
    { d:"M 400 200 Q 440 210 470 240 Q 500 290 470 340 Q 430 380 390 355 Q 360 310 370 260 Q 380 220 400 200 Z", name:"AF" },
    { d:"M 510 90 Q 580 70 660 100 Q 740 130 760 175 Q 750 215 690 230 Q 600 240 530 210 Q 480 175 510 90 Z", name:"AS" },
    { d:"M 690 290 Q 740 282 780 305 Q 800 332 775 360 Q 730 370 700 350 Q 680 325 690 290 Z", name:"OC" },
  ];

  const dots = COUNTRIES.map(([name, iso], i) => {
    const cid = COUNTRY_CLUSTERS[name];
    const p = placeDot(iso);
    return { name, iso, cid, x: p.x * 760 + 40, y: p.y * 380 + 60 };
  });
  const colorFor = (cid) =>
    cid === -1 ? "var(--c-outlier)" : ["var(--c0)","var(--c1)","var(--c2)","var(--c3)","var(--c4)"][cid];

  return (
    <svg width="100%" height="100%" viewBox="0 0 840 480" preserveAspectRatio="xMidYMid meet">
      <defs>
        <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="1" fill="#ece6d6"/>
        </pattern>
      </defs>
      <rect width="840" height="480" fill="url(#grid)" />
      {/* graticule */}
      {[80, 160, 240, 320, 400].map(y => (
        <line key={y} x1="20" x2="820" y1={y} y2={y} stroke="#e7e0cc" strokeDasharray="2 4"/>
      ))}
      {[160, 240, 320, 400, 480, 560, 640, 720].map(x => (
        <line key={x} y1="40" y2="440" x1={x} x2={x} stroke="#e7e0cc" strokeDasharray="2 4"/>
      ))}
      {/* continents */}
      {continents.map((c, i) => (
        <path key={i} d={c.d} fill="#f3eede" stroke="#d6cfbf" strokeWidth="1"/>
      ))}
      {/* country dots */}
      {dots.map(d => {
        const isActive = activeCluster == null || activeCluster === d.cid;
        return (
          <circle key={d.name} cx={d.x} cy={d.y} r={isActive ? 5.5 : 3}
                  fill={colorFor(d.cid)}
                  fillOpacity={isActive ? 0.9 : 0.25}
                  stroke="#1d1a16" strokeWidth="0.6" strokeOpacity="0.35"
                  onClick={() => onPickCluster && onPickCluster(d.cid)}
                  style={{ cursor:"pointer" }}>
            <title>{d.name} · cluster {d.cid === -1 ? "outlier" : d.cid}</title>
          </circle>
        );
      })}
      {/* legend bottom */}
      <g transform="translate(40 446)" fontFamily="var(--font-mono)" fontSize="10" fill="#7a7268">
        <text>graticule · equirectangular · cluster colors below</text>
      </g>
    </svg>
  );
}

function ClusterScatterMock({ activeCluster }) {
  // 192 mock points in a 2D MDS embedding
  const pts = COUNTRIES.map(([name, iso]) => {
    const cid = COUNTRY_CLUSTERS[name];
    let h = 0; for (let i = 0; i < name.length; i++) h = (h * 33 + name.charCodeAt(i)) | 0;
    const seed = (h ^ (h >>> 8)) & 0xffff;
    // place near cluster centroid
    const centers = [[180,180],[640,160],[420,360],[700,340],[200,360],[420,180]];
    const c = centers[cid === -1 ? 5 : cid];
    const r1 = ((seed & 0xff) / 255 - 0.5) * 130;
    const r2 = (((seed >> 8) & 0xff) / 255 - 0.5) * 130;
    return { x: c[0] + r1, y: c[1] + r2, cid, name };
  });
  const colorFor = (cid) =>
    cid === -1 ? "var(--c-outlier)" : ["var(--c0)","var(--c1)","var(--c2)","var(--c3)","var(--c4)"][cid];

  return (
    <svg width="100%" height="100%" viewBox="0 0 840 480">
      {/* axes */}
      <g stroke="#d6cfbf" strokeWidth="1">
        <line x1="60"  x2="60"  y1="40"  y2="440"/>
        <line x1="60"  x2="800" y1="440" y2="440"/>
      </g>
      {[0,1,2,3,4].map(i => (
        <g key={i}>
          <text x={60 + i*180} y="460" textAnchor="middle"
                fontFamily="var(--font-mono)" fontSize="11" fill="#7a7268">{(i*0.2 - 0.4).toFixed(1)}</text>
          <text x="48" y={440 - i*100} textAnchor="end" dominantBaseline="middle"
                fontFamily="var(--font-mono)" fontSize="11" fill="#7a7268">{(i*0.2 - 0.4).toFixed(1)}</text>
          <line x1="60" x2="800" y1={440 - i*100} y2={440 - i*100} stroke="#ece6d6" strokeDasharray="2 4"/>
          <line y1="40" y2="440" x1={60 + i*180} x2={60 + i*180} stroke="#ece6d6" strokeDasharray="2 4"/>
        </g>
      ))}
      <text x="430" y="478" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="11" fill="#7a7268">MDS-1</text>
      <text x="20"  y="240" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="11" fill="#7a7268" transform="rotate(-90 20 240)">MDS-2</text>

      {pts.map((p, i) => {
        const isActive = activeCluster == null || activeCluster === p.cid;
        return (
          <circle key={i} cx={p.x} cy={p.y} r={isActive ? 5 : 3}
                  fill={colorFor(p.cid)}
                  fillOpacity={isActive ? 0.78 : 0.2}
                  stroke="#1d1a16" strokeWidth="0.5" strokeOpacity="0.25">
            <title>{p.name}</title>
          </circle>
        );
      })}
    </svg>
  );
}

function ClusterMembersMock({ activeCluster }) {
  const clusters = CLUSTER_RESULT.clusters;
  const list = [];
  COUNTRIES.forEach(([name]) => {
    const cid = COUNTRY_CLUSTERS[name];
    if (cid === -1) return;
    if (activeCluster != null && activeCluster !== cid) return;
    list.push({ name, cid });
  });
  // group
  const grouped = {};
  list.forEach(it => (grouped[it.cid] = grouped[it.cid] || []).push(it.name));
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:18 }}>
      {clusters
        .filter(c => activeCluster == null || activeCluster === c.id)
        .map(c => (
          <div key={c.id}>
            <div className="row mb-2">
              <span style={{ width:14, height:14, borderRadius:3, background:`var(--c${c.id})` }}></span>
              <strong className="mono" style={{ fontSize:13 }}>
                cluster {c.id} · {c.medoid}
              </strong>
              <span className="muted mono" style={{ fontSize:12 }}>
                {(grouped[c.id] || []).length} members · {c.note}
              </span>
            </div>
            <div className="country-grid">
              {(grouped[c.id] || []).map(n => (
                <a key={n} className="country-card">
                  <span className="cc-name">{n}</span>
                  <span className="cc-iso" style={{ background:`var(--c${c.id})`, color:"#fff",
                                                    borderColor:"transparent", opacity: 0.85 }}>
                    {c.id}
                  </span>
                </a>
              ))}
            </div>
          </div>
        ))}
    </div>
  );
}

function ClusterDendrogramMock() {
  // simple decorative dendrogram
  const lines = [];
  function gen(x, y, w, depth) {
    if (depth === 0 || w < 6) return;
    const split = y + (Math.random() - 0.5) * 40;
    lines.push(["v", x, y - 40, y + 40]);
    lines.push(["h", x, x + w, y - 40]);
    lines.push(["h", x, x + w, y + 40]);
    gen(x + w, y - 40, w * 0.65, depth - 1);
    gen(x + w, y + 40, w * 0.65, depth - 1);
  }
  // run a deterministic 5-level dendro
  const branches = [];
  function det(x, y, w, depth, id) {
    if (depth === 0) {
      branches.push({ x: x + w, y, name: ["Iceland","Norway","Sweden","Denmark","Finland","Estonia","Latvia","Lithuania"][id % 8], cid: id % 5 });
      return;
    }
    const sp = w * 0.55;
    const up = y - 30 * (1 + depth*0.4);
    const dn = y + 30 * (1 + depth*0.4);
    branches.push({ kind:"vline", x, y1: up, y2: dn });
    branches.push({ kind:"hline", x, x2: x + sp, y: up });
    branches.push({ kind:"hline", x, x2: x + sp, y: dn });
    det(x + sp, up, w - sp, depth - 1, id * 2);
    det(x + sp, dn, w - sp, depth - 1, id * 2 + 1);
  }
  det(40, 240, 700, 4, 1);
  return (
    <svg width="100%" height="100%" viewBox="0 0 800 480">
      {branches.map((b, i) => {
        if (b.kind === "vline") return <line key={i} x1={b.x} x2={b.x} y1={b.y1} y2={b.y2} stroke="#3a3530" strokeWidth="1.2"/>;
        if (b.kind === "hline") return <line key={i} x1={b.x} x2={b.x2} y1={b.y} y2={b.y} stroke="#3a3530" strokeWidth="1.2"/>;
        return (
          <g key={i}>
            <circle cx={b.x} cy={b.y} r="3" fill={`var(--c${b.cid})`}/>
            <text x={b.x + 8} y={b.y + 3} fontFamily="var(--font-mono)" fontSize="10" fill="#3a3530">{b.name}</text>
          </g>
        );
      })}
      <text x="400" y="468" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="11" fill="#7a7268">
        merge distance →
      </text>
    </svg>
  );
}

function ScreenClusterResult({ go }) {
  const r = CLUSTER_RESULT;
  const [tab, setTab] = useState("map");
  const [active, setActive] = useState(null);

  return (
    <div className="screen">
      <div className="crumb">
        <a onClick={(e) => { e.preventDefault(); go({ name: "cluster-form" }); }}>Cluster</a>
        <span className="sep">›</span>
        <span className="cur">{r.algorithm} · k={r.k}</span>
      </div>

      <div className="cluster-result-head">
        <div>
          <div className="eyebrow">Cluster run · 2026-05-17 14:08</div>
          <h2>
            Cluster result
            <span className="sub">· {r.algorithm} · k = {r.k}</span>
          </h2>
        </div>
        <div className="page-head-meta">
          <div className="page-stat"><span className="v">{r.k}</span><span className="k">clusters</span></div>
          <div className="page-stat"><span className="v">{r.n_outliers}</span><span className="k">outliers</span></div>
          <div className="page-stat"><span className="v">{r.silhouette.toFixed(3)}</span><span className="k">silhouette</span></div>
          <div className="page-stat"><span className="v">{r.fields.length}</span><span className="k">features</span></div>
          <button className="btn" onClick={() => go({ name: "cluster-form" })}>← New run</button>
        </div>
      </div>

      <div className="cluster-result-grid">
        <div>
          <div className="viz-tabs">
            <span className={`viz-tab ${tab==="map"?"active":""}`}        onClick={() => setTab("map")}><span className="icon"><Icon name="map" size={14}/></span> World map</span>
            <span className={`viz-tab ${tab==="scatter"?"active":""}`}    onClick={() => setTab("scatter")}><span className="icon"><Icon name="scatter" size={14}/></span> 2D scatter <span className="muted mono" style={{ fontSize: 11 }}>· MDS</span></span>
            <span className={`viz-tab ${tab==="dendro"?"active":""}`}     onClick={() => setTab("dendro")}><span className="icon"><Icon name="tree" size={14}/></span> Dendrogram</span>
            <span className={`viz-tab ${tab==="members"?"active":""}`}    onClick={() => setTab("members")}><span className="icon"><Icon name="list" size={14}/></span> Members</span>
            <span className="flex-1"></span>
            <span className="viz-tab" style={{ cursor:"default", color:"var(--muted)" }}>
              {active != null
                ? <span><Icon name="filter" size={12}/> filtered · cluster {active}</span>
                : <span className="muted mono" style={{ fontSize:11 }}>click a cluster chip to filter</span>}
              {active != null && <a onClick={() => setActive(null)} style={{ marginLeft:8 }}>clear</a>}
            </span>
          </div>
          <div className="viz-card">
            <div className="viz-frame">
              {tab === "map"     && <ClusterMapMock     activeCluster={active} onPickCluster={(c) => setActive(c)} />}
              {tab === "scatter" && <ClusterScatterMock activeCluster={active} />}
              {tab === "dendro"  && <ClusterDendrogramMock />}
              {tab === "members" && (
                <div style={{ padding: 18, height: "100%", overflow:"auto" }}>
                  <ClusterMembersMock activeCluster={active} />
                </div>
              )}
            </div>
            <p className="viz-cap">
              {tab === "map"     && <>Hover a country for cluster details. Outliers (missing fields) appear in grey.</>}
              {tab === "scatter" && <>Classical MDS embedding of the pairwise distance matrix. Points close together are close in the feature space.</>}
              {tab === "dendro"  && <>Bottom-up merge tree. Horizontal position = merge distance; cut at distance 0.42 yields k = 5.</>}
              {tab === "members" && <>Members listed by cluster. Click a row to open the country tree.</>}
            </p>
          </div>
        </div>

        <aside className="side-card">
          <div className="card">
            <div className="card-header">
              <h3>Configuration</h3>
              <span className="muted mono" style={{ fontSize: 11 }}>params.json</span>
            </div>
            <div className="card-body tight">
              <dl className="kv">
                <dt>algorithm</dt><dd>{r.algorithm}</dd>
                <dt>k</dt>        <dd>{r.k}</dd>
                <dt>init</dt>     <dd>build</dd>
                <dt>cost_model</dt><dd>symmetric</dd>
                <dt>seed</dt>     <dd>0</dd>
              </dl>
              <div style={{ borderTop: "1px dashed var(--line)", marginTop: 8, paddingTop: 8 }}>
                <div className="label mb-2">Features ({r.fields.length})</div>
                <div style={{ display:"flex", flexWrap:"wrap", gap: 4 }}>
                  {r.fields.map(f => (
                    <span key={f} className="tag" style={{ fontSize: 10.5 }}>{f}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h3>Cluster sizes</h3>
              <span className="muted mono" style={{ fontSize: 11 }}>click to filter</span>
            </div>
            <div className="card-body" style={{ padding: 8 }}>
              {r.clusters.map(c => (
                <div key={c.id}
                     className={`cluster-chip ${active === c.id ? "active" : ""}`}
                     onClick={() => setActive(active === c.id ? null : c.id)}>
                  <span className="swatch" style={{ background: `var(--c${c.id})` }}></span>
                  <span className="label">
                    <span className="name">{c.medoid}</span>
                    <span className="meta">{c.note}</span>
                  </span>
                  <span className="ct">{c.size}</span>
                </div>
              ))}
              <div className={`cluster-chip ${active === -1 ? "active" : ""}`}
                   onClick={() => setActive(active === -1 ? null : -1)}>
                <span className="swatch" style={{ background: "var(--c-outlier)" }}></span>
                <span className="label">
                  <span className="name">outliers</span>
                  <span className="meta">missing required fields</span>
                </span>
                <span className="ct">{r.n_outliers}</span>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h3>Outliers</h3>
              <span className="muted mono" style={{ fontSize: 11 }}>{r.outliers.length}</span>
            </div>
            <div className="card-body tight">
              {r.outliers.map(o => (
                <div key={o.name} style={{ padding: "5px 0", borderBottom: "1px dashed var(--line)" }}>
                  <div className="row between">
                    <span className="mono" style={{ fontSize: 12.5, color: "var(--ink)" }}>{o.name}</span>
                    <span className="mono muted" style={{ fontSize: 11 }}>{o.missing.length} missing</span>
                  </div>
                  <div style={{ display:"flex", flexWrap:"wrap", gap: 3, marginTop: 3 }}>
                    {o.missing.map(m => <span key={m} className="tag warn" style={{ fontSize: 10 }}>{m}</span>)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

Object.assign(window, { ScreenClusterForm, ScreenClusterResult });
