/* ============================================================
   IDPA — Countries list + Country detail screens
   ============================================================ */

function ScreenCountries({ go }) {
  const [q, setQ] = useState("");
  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    return COUNTRIES.filter(([n]) => n.toLowerCase().includes(s));
  }, [q]);

  const grouped = useMemo(() => {
    const m = {};
    filtered.forEach(([n, iso]) => {
      const L = n[0].toUpperCase();
      (m[L] = m[L] || []).push([n, iso]);
    });
    return m;
  }, [filtered]);

  const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
  const present = new Set(Object.keys(grouped));

  return (
    <div className="screen">
      <div className="page-head">
        <div>
          <div className="eyebrow">Index</div>
          <h1>Countries</h1>
          <p className="lede">
            {COUNTRIES.length} UN member states indexed from Wikipedia infoboxes.
            Each card opens the country's full structural tree.
          </p>
        </div>
        <div className="page-head-meta">
          <div className="page-stat"><span className="v">{COUNTRIES.length}</span><span className="k">countries</span></div>
          <div className="page-stat"><span className="v">132,418</span><span className="k">leaves indexed</span></div>
          <div className="page-stat"><span className="v">8.4</span><span className="k">avg height</span></div>
        </div>
      </div>

      <div className="row mb-4" style={{ gap: 12 }}>
        <div className="search flex-1" style={{ maxWidth: 480 }}>
          <span className="search-icon"><Icon name="search" size={14}/></span>
          <input className="input" value={q} onChange={e => setQ(e.target.value)}
                 placeholder="Filter by name…" autoFocus />
          <span className="kbd-hint">/</span>
        </div>
        <span className="muted mono" style={{ fontSize: 12 }}>
          {filtered.length === COUNTRIES.length
            ? `showing all ${COUNTRIES.length}`
            : `${filtered.length} of ${COUNTRIES.length} match`}
        </span>
        <span className="flex-1"></span>
        <span className="seg">
          <span className="opt active">A–Z</span>
          <span className="opt">By region</span>
          <span className="opt">By cluster</span>
        </span>
      </div>

      <div className="alpha-rail">
        {letters.map(L => (
          <span key={L} className={`letter ${present.has(L) ? "" : "disabled"}`}>{L}</span>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="empty">
          <div className="em-glyph">⌕</div>
          No country matches <code>{q}</code>.
        </div>
      ) : letters.filter(L => grouped[L]).map(L => (
        <div className="alpha-group" key={L}>
          <h4>{L}</h4>
          <div className="country-grid">
            {grouped[L].map(([n, iso]) => (
              <a className="country-card" key={n} onClick={(e) => { e.preventDefault(); go({ name: "country", country: n }); }}>
                <span className="cc-name">{n}</span>
                <span className="cc-iso">{iso}</span>
              </a>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ----- country detail ----- */
function ScreenCountryDetail({ go, country }) {
  const tree = LEBANON_TREE; // mock: any country shows the Lebanon tree
  const name = country || "Lebanon";
  const groups = tree.root.children;

  const [active, setActive] = useState("geography");
  return (
    <div className="screen">
      <div className="crumb">
        <a onClick={(e) => { e.preventDefault(); go({ name: "countries" }); }}>Countries</a>
        <span className="sep">›</span>
        <span className="cur">{name}</span>
      </div>

      <div className="page-head">
        <div>
          <div className="eyebrow">Country tree · <span>iso {tree.iso}</span></div>
          <h1>{name}</h1>
          <p className="lede">
            Wikipedia infobox parsed into a rooted ordered labeled tree.
            Click any structural node to collapse · click a leaf for raw value.
          </p>
        </div>
        <div className="page-head-meta">
          <div className="page-stat"><span className="v">{tree.size}</span><span className="k">nodes</span></div>
          <div className="page-stat"><span className="v">{tree.height}</span><span className="k">height</span></div>
          <div className="page-stat"><span className="v">{groups.length}</span><span className="k">groups</span></div>
          <a className="btn sm" href="#"><Icon name="json" size={12}/> view JSON</a>
        </div>
      </div>

      <div className="detail-layout">
        {/* TOC */}
        <nav className="detail-toc">
          <h4>Sections</h4>
          {groups.map(g => (
            <a key={g.label} onClick={(e) => { e.preventDefault(); setActive(g.label); }}
               className={active === g.label ? "active" : ""}>
              <span>{g.label}</span>
              <span className="ct">{g.count}</span>
            </a>
          ))}
          <h4 style={{ marginTop: 22 }}>Tools</h4>
          <a onClick={(e) => { e.preventDefault(); go({ name: "compare-form", c1: name }); }}>
            <span>Compare with…</span>
          </a>
          <a onClick={(e) => { e.preventDefault(); go({ name: "patch", c1: name }); }}>
            <span>Apply patch…</span>
          </a>
        </nav>

        {/* Tree body */}
        <div>
          {groups.map((g, i) => (
            <details className="struct-block" key={g.label} open={i < 3}>
              <summary>
                <span className="struct-label">{g.label}</span>
                <span className="struct-count">{g.count} fields</span>
              </summary>
              <div className="struct-body">
                <ul className="leaf-list">
                  {g.leaves.map(l => <LeafRow key={l.label} leaf={l} />)}
                </ul>
              </div>
            </details>
          ))}
        </div>

        {/* Right sidebar */}
        <aside className="side-card">
          <div className="card">
            <div className="card-header"><h3>Cluster membership</h3></div>
            <div className="card-body tight">
              <div className="cluster-chip active" style={{ padding: "6px 0" }}>
                <span className="swatch" style={{ background: "var(--c2)" }}></span>
                <div className="label">
                  <span className="name">Cluster 2 · Egypt</span>
                  <span className="meta">27 members · last run May 17</span>
                </div>
                <span className="ct">k=5</span>
              </div>
              <p className="muted mono" style={{ fontSize: 11, marginTop: 8 }}>
                Grouped on government.type · religion · gdp_per_capita.
              </p>
            </div>
          </div>

          <div className="card">
            <div className="card-header"><h3>Nearest neighbours</h3></div>
            <div className="card-body tight">
              {[
                ["Jordan",     0.182],
                ["Syria",      0.214],
                ["Tunisia",    0.296],
                ["Egypt",      0.318],
                ["Morocco",    0.342],
              ].map(([n, d]) => (
                <div key={n} style={{ display:"grid", gridTemplateColumns:"1fr auto",
                                       padding:"4px 0", borderBottom:"1px dashed var(--line)",
                                       fontFamily:"var(--font-mono)", fontSize:12 }}>
                  <a onClick={(e) => { e.preventDefault(); go({ name: "compare-result", c1: name, c2: n }); }}>{n}</a>
                  <span className="muted">{d.toFixed(3)}</span>
                </div>
              ))}
              <p className="muted mono" style={{ fontSize: 11, marginTop: 6 }}>
                tree-edit distance · symmetric cost · chawathe
              </p>
            </div>
          </div>

          <div className="card">
            <div className="card-header"><h3>Type composition</h3></div>
            <div className="card-body tight">
              {[
                ["number",       18, "var(--tb-number)",   "var(--tb-number-bg)"],
                ["text",         12, "var(--tb-text)",     "var(--tb-text-bg)"],
                ["wikilink",      9, "var(--tb-link)",     "var(--tb-link-bg)"],
                ["currency",      5, "var(--tb-currency)", "var(--tb-currency-bg)"],
                ["percent",       4, "var(--tb-number)",   "var(--tb-number-bg)"],
                ["distribution",  2, "var(--tb-dist)",     "var(--tb-dist-bg)"],
                ["coordinates",   1, "var(--tb-coord)",    "var(--tb-coord-bg)"],
              ].map(([t, n, fg, bg]) => (
                <div key={t} style={{ display:"flex", alignItems:"center", gap:8, padding:"3px 0" }}>
                  <span className={`tbadge ${t}`} style={{ minWidth: 84 }}>{t}</span>
                  <div style={{ flex:1, height:6, background:"var(--paper-2)",
                                borderRadius:3, overflow:"hidden" }}>
                    <div style={{ height:"100%", width:`${n*5}%`, background: fg }}></div>
                  </div>
                  <span className="mono muted" style={{ fontSize:11, width:24, textAlign:"right" }}>{n}</span>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

Object.assign(window, { ScreenCountries, ScreenCountryDetail });
