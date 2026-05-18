/* ============================================================
   IDPA — Compare form, Compare result, Patch screens
   ============================================================ */

function ScreenCompareForm({ go, c1pre, c2pre }) {
  const [c1, setC1] = useState(c1pre || "Lebanon");
  const [c2, setC2] = useState(c2pre || "Switzerland");
  const [algo, setAlgo] = useState("chawathe");
  const [cm,   setCm]   = useState("symmetric");

  const submit = (e) => {
    e.preventDefault();
    if (c1 && c2) go({ name: "compare-result", c1, c2, algo, cm });
  };
  return (
    <div className="screen">
      <div className="page-head">
        <div>
          <div className="eyebrow">Tree-edit diff</div>
          <h1>Compare two countries</h1>
          <p className="lede">
            Compute a structural diff between any pair of country trees, with
            colored insert / delete / relabel marks projected onto both sides.
          </p>
        </div>
      </div>

      <form onSubmit={submit} className="card">
        <div className="card-body" style={{ display:"grid",
              gridTemplateColumns:"1fr 1fr auto 1fr 1fr auto", gap:16, alignItems:"end" }}>
          <div className="field">
            <label>Country A</label>
            <select className="select" value={c1} onChange={e => setC1(e.target.value)}>
              {COUNTRIES.map(([n]) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Country B</label>
            <select className="select" value={c2} onChange={e => setC2(e.target.value)}>
              {COUNTRIES.map(([n]) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <span className="mono muted" style={{ fontSize:18, paddingBottom:8 }}>↔</span>
          <div className="field">
            <label>Algorithm</label>
            <select className="select" value={algo} onChange={e => setAlgo(e.target.value)}>
              <option value="chawathe">chawathe</option>
              <option value="nierman_jagadish">nierman_jagadish</option>
            </select>
          </div>
          <div className="field">
            <label>Cost model</label>
            <select className="select" value={cm} onChange={e => setCm(e.target.value)}>
              <option value="symmetric">symmetric</option>
              <option value="asymmetric">asymmetric</option>
            </select>
          </div>
          <button type="submit" className="btn primary lg">
            Compute <Icon name="arrow-right" size={14}/>
          </button>
        </div>
      </form>

      <h3 className="mt-6 mb-2">Cached comparisons <span className="muted mono" style={{ fontSize:13 }}>· 4</span></h3>
      <div className="card">
        <table style={{ width:"100%", borderCollapse:"collapse", fontFamily:"var(--font-mono)", fontSize:12 }}>
          <thead>
            <tr style={{ background:"var(--paper-2)", color:"var(--muted)",
                         textTransform:"uppercase", fontSize:10.5, letterSpacing:0.06 + "em" }}>
              <th style={{ textAlign:"left", padding:"8px 14px", fontWeight:500 }}>Pair</th>
              <th style={{ textAlign:"left", padding:"8px 14px", fontWeight:500 }}>Algorithm</th>
              <th style={{ textAlign:"left", padding:"8px 14px", fontWeight:500 }}>Cost model</th>
              <th style={{ textAlign:"right", padding:"8px 14px", fontWeight:500 }}>A→B</th>
              <th style={{ textAlign:"right", padding:"8px 14px", fontWeight:500 }}>B→A</th>
              <th style={{ textAlign:"left", padding:"8px 14px", fontWeight:500 }}>Computed</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {[
              ["Lebanon","Switzerland","chawathe","symmetric", 40.13, 38.71, "2026-05-17 14:08", 43],
              ["France","Germany","chawathe","symmetric", 18.42, 17.93, "2026-05-17 09:55", 22],
              ["Brazil","Argentina","nierman_jagadish","symmetric", 21.07, 22.18, "2026-05-16 22:41", 27],
              ["Egypt","Saudi_Arabia","chawathe","asymmetric", 24.83, 19.71, "2026-05-16 18:21", 31],
            ].map((r, i) => (
              <tr key={i} style={{ borderTop:"1px solid var(--line)" }}>
                <td style={{ padding:"8px 14px" }}>
                  <code>{r[0]}</code> <span className="muted">→</span> <code>{r[1]}</code>
                </td>
                <td style={{ padding:"8px 14px" }}><span className="tag accent">{r[2]}</span></td>
                <td style={{ padding:"8px 14px" }}><span className="tag">{r[3]}</span></td>
                <td style={{ padding:"8px 14px", textAlign:"right" }}>
                  <strong>{r[4].toFixed(2)}</strong> <span className="muted">· {r[7]}r/8d/12i</span>
                </td>
                <td style={{ padding:"8px 14px", textAlign:"right" }}><strong>{r[5].toFixed(2)}</strong></td>
                <td style={{ padding:"8px 14px", color:"var(--muted)" }}>{r[6]}</td>
                <td style={{ padding:"8px 14px", textAlign:"right" }}>
                  <a className="btn sm" onClick={() => go({ name: "compare-result", c1: r[0], c2: r[1] })}>view</a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ----- compare result ----- */
function MockNode({ x, y, kind = "structural", mark, children }) {
  const cls = ["mnode", kind === "leaf" ? "" : "structural", mark || ""].filter(Boolean).join(" ");
  return (
    <div className={cls} style={{ left: x, top: y }}>{children}</div>
  );
}

function MockTreePane({ side = "a", marks }) {
  // hand-laid little tree
  const items = [
    [10,  20,  "structural", null,         "country"],
    [120, 0,   "structural", marks.identity, "identity"],
    [120, 38,  "structural", marks.geography, "geography"],
    [120, 76,  "structural", marks.government, "government"],
    [120, 114, "structural", marks.economy, "economy"],
    [120, 152, "structural", marks.demographics, "demographics"],
    [120, 190, "structural", marks.codes, "codes"],

    [250, 0,   "leaf", null, side==="a"?"Lebanese Republic":"Swiss Confederation"],
    [250, 28,  "leaf", null, side==="a"?"Lebanese":"Swiss"],

    [250, 60,  "leaf", marks.capital,    side==="a"?"capital · Beirut":"capital · Bern"],
    [250, 88,  "leaf", marks.area,       side==="a"?"area.km2 · 10,452":"area.km2 · 41,285"],
    [250, 116, "leaf", side==="a"?"delete":null, side==="a"?"coastline_km · 225":null],
    [250, 144, "leaf", side==="b"?"insert":null, side==="b"?"elevation.max · 4634":null],

    [250, 176, "leaf", marks.govtype,    side==="a"?"type · parliamentary":"type · directorial federal"],
    [250, 204, "leaf", null,             side==="a"?"head_of_state":"president (rotating)"],
    [250, 232, "leaf", null,             side==="a"?"legislature":"Federal Assembly"],

    [490, 60,  "leaf", marks.gdp,        side==="a"?"gdp_nominal · $23.13B":"gdp_nominal · $818.4B"],
    [490, 88,  "leaf", marks.gdp,        side==="a"?"gdp_per_capita · $4,136":"gdp_per_capita · $93,259"],
    [490, 116, "leaf", side==="a"?"delete":null,  side==="a"?"inflation · 221.3%":null],
    [490, 144, "leaf", null,             side==="a"?"currency · LBP":"currency · CHF"],

    [490, 180, "leaf", marks.religion,   side==="a"?"religion · Islam 63%, Christian 29%":"religion · Christian 65%, none 30%"],
    [490, 208, "leaf", marks.languages,  side==="a"?"languages · Arabic, French":"languages · German, French, Italian"],
    [490, 236, "leaf", marks.pop,        side==="a"?"population · 5,364,482":"population · 8,776,300"],
  ].filter(it => it[4] != null);

  // Lines from parents → children (simple visual)
  const lines = [
    // country -> groups
    [50, 33, 120, 12],
    [50, 33, 120, 50],
    [50, 33, 120, 88],
    [50, 33, 120, 126],
    [50, 33, 120, 164],
    [50, 33, 120, 202],
    // identity -> leaves
    [180, 12, 250, 12],
    [180, 12, 250, 40],
    // geography
    [180, 50, 250, 72],
    [180, 50, 250, 100],
    [180, 50, 250, 128],
    [180, 50, 250, 156],
    // government
    [180, 88, 250, 188],
    [180, 88, 250, 216],
    [180, 88, 250, 244],
    // economy
    [200, 126, 490, 72],
    [200, 126, 490, 100],
    [200, 126, 490, 128],
    [200, 126, 490, 156],
    // demographics
    [200, 164, 490, 192],
    [200, 164, 490, 220],
    [200, 164, 490, 248],
  ];

  return (
    <div className="mtree" style={{ left: 16, top: 18 }}>
      <svg style={{ position:"absolute", inset:0, pointerEvents:"none", width: 700, height: 280 }}>
        {lines.map((l, i) => (
          <path key={i}
            d={`M${l[0]} ${l[1]+10} C ${l[0]+30} ${l[1]+10}, ${l[2]-30} ${l[3]+10}, ${l[2]} ${l[3]+10}`}
            stroke="#bdb4a1" strokeWidth="1.2" fill="none" />
        ))}
      </svg>
      {items.map((it, i) => (
        <MockNode key={i} x={it[0]} y={it[1]} kind={it[2]} mark={it[3]}>{it[4]}</MockNode>
      ))}
    </div>
  );
}

function ScreenCompareResult({ go, c1pre, c2pre }) {
  const c1 = c1pre || COMPARE_DATA.country1;
  const c2 = c2pre || COMPARE_DATA.country2;
  const [dir, setDir] = useState("forward");
  const ops = COMPARE_DATA.script;

  // Hand-tuned marks so the panes "react"
  const marks = {
    capital: "relabel",
    area: "relabel",
    govtype: "relabel",
    gdp: "relabel",
    religion: "relabel",
    languages: "relabel",
    pop: "relabel",
    geography: "relabel",
    government: "relabel",
    economy: "relabel",
    demographics: "relabel",
  };

  return (
    <div className="screen">
      <div className="crumb">
        <a onClick={(e) => { e.preventDefault(); go({ name: "compare-form" }); }}>Compare</a>
        <span className="sep">›</span>
        <span className="cur">{c1} ↔ {c2}</span>
      </div>

      <div className="page-head">
        <div>
          <div className="eyebrow">Tree-edit diff</div>
          <h1><code style={{ fontSize: 22 }}>{c1}</code> <span className="muted">↔</span> <code style={{ fontSize: 22 }}>{c2}</code></h1>
          <p className="lede">
            algorithm <code>{COMPARE_DATA.algorithm}</code> · cost
            model <code>{COMPARE_DATA.cost_model}</code> ·{" "}
            <span className="tag accent dot">from cache</span>
          </p>
        </div>
        <div className="page-head-meta">
          <div className="page-stat">
            <span className="v">{COMPARE_DATA.forward_cost.toFixed(2)}</span>
            <span className="k">A → B cost</span>
          </div>
          <div className="page-stat">
            <span className="v">{COMPARE_DATA.reverse_cost.toFixed(2)}</span>
            <span className="k">B → A cost</span>
          </div>
          <div className="page-stat">
            <span className="v">{ops.length}</span>
            <span className="k">edit ops</span>
          </div>
        </div>
      </div>

      <div className="row between mb-2">
        <div className="row">
          <div className="btn-group">
            <button className={`btn sm ${dir==="forward"?"active":""}`} onClick={() => setDir("forward")}>A → B</button>
            <button className={`btn sm ${dir==="reverse"?"active":""}`} onClick={() => setDir("reverse")}>B → A</button>
          </div>
          <button className="btn sm"><Icon name="expand" size={12}/> Expand</button>
          <button className="btn sm"><Icon name="reset"  size={12}/> Reset</button>
          <button className="btn sm"><Icon name="fit"    size={12}/> Fit</button>
        </div>
        <DiffLegend />
      </div>

      <div className="compare-grid">
        <div>
          <div className="tree-side-header">
            <span className="who">
              <span className="who-tag">A</span>
              <strong>{c1}</strong>
            </span>
            <span className="stats mono">142 nodes · height 4</span>
          </div>
          <div className="tree-canvas">
            <MockTreePane side="a" marks={marks} />
          </div>
        </div>
        <div>
          <div className="tree-side-header b">
            <span className="who">
              <span className="who-tag">B</span>
              <strong>{c2}</strong>
            </span>
            <span className="stats mono">156 nodes · height 4</span>
          </div>
          <div className="tree-canvas">
            <MockTreePane side="b" marks={marks} />
          </div>
        </div>
      </div>

      <div className="escript mt-4">
        <div className="row between mb-2">
          <h3>Edit-script operations <span className="muted mono" style={{ fontSize:13, fontWeight:400 }}>· {ops.length} of {ops.length}</span></h3>
          <span className="row gap-12">
            <span className="row gap-6 mono" style={{ fontSize:11.5, color:"var(--muted)" }}>
              <span className="op delete">{COMPARE_DATA.forward_ops.delete}</span> delete
              <span className="op insert">{COMPARE_DATA.forward_ops.insert}</span> insert
              <span className="op relabel">{COMPARE_DATA.forward_ops.relabel}</span> relabel
            </span>
            <button className="btn sm"><Icon name="json" size={12}/> Export JSON</button>
          </span>
        </div>
        <div className="card">
          <table>
            <thead>
              <tr>
                <th style={{ width: 90 }}>op</th>
                <th>path</th>
                <th>before</th>
                <th>after</th>
                <th style={{ textAlign:"right" }}>cost</th>
              </tr>
            </thead>
            <tbody>
              {ops.map((o, i) => (
                <tr key={i}>
                  <td>
                    <span className={`op ${o.op}`}>
                      {o.op === "delete" ? "✗" : o.op === "insert" ? "+" : "~"} {o.op}
                    </span>
                  </td>
                  <td><FieldPath path={o.path} /></td>
                  <td>{o.from ? <span className="mono">{o.from}</span> : <span className="muted">∅</span>}</td>
                  <td>
                    {o.to
                      ? <span className="mono">
                          <span className="arrow">→</span> {o.to}
                        </span>
                      : <span className="muted">∅</span>}
                  </td>
                  <td style={{ textAlign:"right" }} className="mono">{o.cost.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ----- patch screen ----- */
function ScreenPatch({ go, c1pre }) {
  const [src, setSrc] = useState("paste");
  const [country, setCountry] = useState(c1pre || "Lebanon");
  const [useReverse, setUseReverse] = useState(false);

  return (
    <div className="screen">
      <div className="page-head">
        <div>
          <div className="eyebrow">Edit-script application</div>
          <h1>Apply a patch to a country tree</h1>
          <p className="lede">
            Re-derive what a country tree would look like under the operations
            from a cached comparison, or any JSON edit script you paste.
          </p>
        </div>
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"460px 1fr", gap:24 }}>
        <div>
          <div className="card">
            <div className="card-body">
              <div className="field mb-4">
                <label>Source country</label>
                <select className="select" value={country} onChange={e => setCountry(e.target.value)}>
                  {COUNTRIES.map(([n]) => <option key={n}>{n}</option>)}
                </select>
              </div>

              <div className="field" style={{ gap: 8 }}>
                <label>Edit script</label>
                <div className="seg">
                  <span className={`opt ${src==="paste"?"active":""}`}  onClick={() => setSrc("paste")}>Paste JSON</span>
                  <span className={`opt ${src==="upload"?"active":""}`} onClick={() => setSrc("upload")}>Upload file</span>
                  <span className={`opt ${src==="cached"?"active":""}`} onClick={() => setSrc("cached")}>Cached</span>
                </div>
              </div>

              <div className="mt-4">
                {src === "paste" && (
                  <textarea className="input mono" rows={11}
                    defaultValue={'{\n  "source": "Lebanon",\n  "target": "Switzerland",\n  "total_cost": 40.13,\n  "operations": [\n    { "op": "relabel", "path": "geography.capital", "from": "Beirut", "to": "Bern" },\n    { "op": "delete",  "path": "economy.inflation" },\n    { "op": "insert",  "path": "geography.elevation.max", "to": "4634" }\n  ]\n}'} />
                )}
                {src === "upload" && (
                  <div style={{ border:"1.5px dashed var(--line-2)", borderRadius: 6,
                                padding: 24, textAlign:"center", background:"#fdfcf6" }}>
                    <div style={{ fontSize: 26, color: "var(--muted-2)" }}>⤓</div>
                    <p className="mono muted" style={{ fontSize: 12 }}>
                      Drop a <code>.json</code> file here or click to choose
                    </p>
                    <button className="btn sm">Browse files…</button>
                  </div>
                )}
                {src === "cached" && (
                  <Fragment>
                    <select className="select mono" style={{ fontSize: 12 }}>
                      <option>Lebanon → Switzerland (chawathe / symmetric, 43 ops)</option>
                      <option>France → Germany (chawathe / symmetric, 22 ops)</option>
                      <option>Brazil → Argentina (nierman_jagadish / symmetric, 27 ops)</option>
                      <option>Egypt → Saudi Arabia (chawathe / asymmetric, 31 ops)</option>
                    </select>
                    <label className="row mt-2" style={{ fontSize: 12, gap: 8, cursor:"pointer" }}>
                      <input type="checkbox" className="checkbox"
                             checked={useReverse} onChange={(e) => setUseReverse(e.target.checked)}/>
                      <span className="muted mono">Use reverse direction (target → source)</span>
                    </label>
                  </Fragment>
                )}
              </div>

              <div className="row mt-6 between">
                <button className="btn primary lg"><Icon name="play" size={12}/> Apply</button>
                <span className="mono muted" style={{ fontSize: 12 }}>
                  <span className="op insert" style={{ fontWeight:600 }}>+ 12</span>
                  <span className="op delete" style={{ fontWeight:600, marginLeft:8 }}>✗ 8</span>
                  <span className="op relabel" style={{ fontWeight:600, marginLeft:8 }}>~ 23</span>
                </span>
              </div>
            </div>
          </div>

          <div className="alert info mt-4">
            <span className="icon">i</span>
            <div>
              <strong>Tip.</strong> A reverse-direction patch turns the target
              tree back into the source by inverting every op
              (<code>insert</code> ↔ <code>delete</code>).
            </div>
          </div>
        </div>

        <div>
          <div className="tree-side-header">
            <span className="who">
              <span className="who-tag">↻</span>
              <strong>{country}</strong> · patched preview
            </span>
            <span className="stats mono">156 nodes · height 4</span>
          </div>
          <div className="tree-canvas">
            <MockTreePane side="b" marks={{
              capital: "insert", area: "relabel", govtype: "relabel",
              gdp: "relabel", religion: "relabel", languages: "relabel",
              pop: "relabel"
            }} />
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ScreenCompareForm, ScreenCompareResult, ScreenPatch });
