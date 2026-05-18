/* ============================================================
   IDPA — shared components
   ============================================================ */
const { useState, useEffect, useMemo, useRef, useLayoutEffect, Fragment } = React;

/* small UI primitives */
function Icon({ name, size = 14, stroke = 1.6 }) {
  const s = size;
  const common = { width: s, height: s, viewBox: "0 0 24 24", fill: "none",
                   stroke: "currentColor", strokeWidth: stroke,
                   strokeLinecap: "round", strokeLinejoin: "round" };
  switch (name) {
    case "search": return <svg {...common}><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>;
    case "arrow-right": return <svg {...common}><path d="M5 12h14M13 6l6 6-6 6"/></svg>;
    case "arrow-left":  return <svg {...common}><path d="M19 12H5M11 6l-6 6 6 6"/></svg>;
    case "plus":   return <svg {...common}><path d="M12 5v14M5 12h14"/></svg>;
    case "x":      return <svg {...common}><path d="M6 6l12 12M18 6L6 18"/></svg>;
    case "check":  return <svg {...common}><path d="m5 12 5 5L20 7"/></svg>;
    case "map":    return <svg {...common}><path d="M3 6v15l6-3 6 3 6-3V3l-6 3-6-3-6 3z"/><path d="M9 3v15M15 6v15"/></svg>;
    case "scatter":return <svg {...common}><circle cx="6" cy="18" r="1.4"/><circle cx="10" cy="13" r="1.4"/><circle cx="14" cy="16" r="1.4"/><circle cx="17" cy="8" r="1.4"/><circle cx="9" cy="7" r="1.4"/><path d="M3 21V3"/><path d="M3 21h18"/></svg>;
    case "tree":   return <svg {...common}><circle cx="12" cy="4" r="1.5"/><circle cx="6" cy="12" r="1.5"/><circle cx="18" cy="12" r="1.5"/><circle cx="4" cy="20" r="1.5"/><circle cx="9" cy="20" r="1.5"/><circle cx="15" cy="20" r="1.5"/><circle cx="20" cy="20" r="1.5"/><path d="M12 5.5v3M10.5 11.2 11 9M13.5 11.2 13 9M5 13.4l-.6 5M7 13.4l1.6 5M17 13.4l-1.6 5M19 13.4l.6 5"/></svg>;
    case "list":   return <svg {...common}><path d="M8 6h13M8 12h13M8 18h13"/><circle cx="4" cy="6" r="0.8" fill="currentColor"/><circle cx="4" cy="12" r="0.8" fill="currentColor"/><circle cx="4" cy="18" r="0.8" fill="currentColor"/></svg>;
    case "diff":   return <svg {...common}><path d="M12 3v18M9 6l-3 3 3 3M15 18l3-3-3-3"/></svg>;
    case "expand": return <svg {...common}><path d="M7 3H3v4M17 3h4v4M21 17v4h-4M3 17v4h4"/></svg>;
    case "fit":    return <svg {...common}><path d="M3 9V3h6M21 9V3h-6M3 15v6h6M21 15v6h-6"/></svg>;
    case "reset":  return <svg {...common}><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8M21 4v4h-4"/><path d="M21 12a9 9 0 0 1-15.5 6.2L3 16M3 20v-4h4"/></svg>;
    case "play":   return <svg {...common}><path d="M6 4l14 8-14 8z" fill="currentColor"/></svg>;
    case "json":   return <svg {...common}><path d="M8 4a3 3 0 0 0-3 3v3a2 2 0 0 1-2 2 2 2 0 0 1 2 2v3a3 3 0 0 0 3 3"/><path d="M16 4a3 3 0 0 1 3 3v3a2 2 0 0 0 2 2 2 2 0 0 0-2 2v3a3 3 0 0 1-3 3"/></svg>;
    case "globe":  return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>;
    case "settings":return <svg {...common}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>;
    case "external":return <svg {...common}><path d="M14 3h7v7M21 3l-9 9M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"/></svg>;
    case "filter": return <svg {...common}><path d="M3 5h18l-7 9v6l-4-2v-4z"/></svg>;
    case "history":return <svg {...common}><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></svg>;
    case "info":   return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="M12 8v.01M11 12h1v5h1"/></svg>;
  }
  return null;
}

/* type badge */
function TypeBadge({ type }) {
  return <span className={`tbadge ${type || ""}`}>{type || "?"}</span>;
}

/* path with monospace separators */
function FieldPath({ path }) {
  const parts = (path || "").split(".");
  return (
    <span className="path">
      {parts.map((p, i) => (
        <Fragment key={i}>
          {i > 0 && <span className="sep">.</span>}
          <span className={i === parts.length - 1 ? "last" : ""}>{p}</span>
        </Fragment>
      ))}
    </span>
  );
}

/* nicely formatted values */
function fmtCurrency(n) {
  const a = Math.abs(n);
  const s = n < 0 ? "-" : "";
  if (a >= 1e12) return `${s}$${(a/1e12).toFixed(2)}T`;
  if (a >= 1e9)  return `${s}$${(a/1e9).toFixed(2)}B`;
  if (a >= 1e6)  return `${s}$${(a/1e6).toFixed(2)}M`;
  if (a >= 1e3)  return `${s}$${(a/1e3).toFixed(1)}K`;
  return `${s}$${a.toFixed(2)}`;
}
function fmtNumber(n) {
  if (Number.isInteger(n)) return n.toLocaleString();
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}
function Trend({ t }) {
  if (t == null) return null;
  const cls = t > 0 ? "up" : t < 0 ? "down" : "flat";
  const g   = t > 0 ? "▲" : t < 0 ? "▼" : "▬";
  return <span className={`trend ${cls}`}>{g}</span>;
}

/* render one leaf row */
function LeafRow({ leaf }) {
  let val;
  if (leaf.value == null)                   val = <span className="muted">∅</span>;
  else if (leaf.type === "currency")        val = <strong>{fmtCurrency(leaf.value)}</strong>;
  else if (leaf.type === "number")          val = <strong>{fmtNumber(leaf.value)}</strong>;
  else if (leaf.type === "percent")         val = <strong>{fmtNumber(leaf.value)}%</strong>;
  else if (leaf.type === "year")            val = <strong>{leaf.value}</strong>;
  else if (leaf.type === "date")            val = <strong>{leaf.value}</strong>;
  else if (leaf.type === "coordinates")     val = <strong>{leaf.value[0].toFixed(4)}, {leaf.value[1].toFixed(4)}</strong>;
  else if (leaf.type === "distribution")    val = <DistributionChips items={leaf.value} />;
  else if (leaf.type === "wikilink")        val = <a href="#">{leaf.value}</a>;
  else                                       val = leaf.value;
  return (
    <li className="leaf-row">
      <span className="leaf-label">{leaf.label}</span>
      <TypeBadge type={leaf.type} />
      <span className="leaf-value">
        {val}
        {leaf.unit && <span className="unit">{leaf.unit}</span>}
      </span>
      <Trend t={leaf.trend} />
    </li>
  );
}

function DistributionChips({ items }) {
  return (
    <span className="dist">
      {items.map((it, i) => (
        <span className="chip" key={i}>
          <span className="swatch" style={{ background: DIST_PALETTE[i % DIST_PALETTE.length] }}></span>
          {it.path.join(" › ")}
          <span className="pct">{(it.weight * 100).toFixed(0)}%</span>
        </span>
      ))}
    </span>
  );
}

/* Diff legend with glyphs */
function DiffLegend() {
  return (
    <span className="mark-legend">
      <span className="glyph"><span className="gbox delete">✗</span> delete</span>
      <span className="glyph"><span className="gbox relabel">~</span> relabel</span>
      <span className="glyph"><span className="gbox insert">+</span> insert</span>
    </span>
  );
}

/* tiny sparkline of group activation */
function GroupSpark({ on, total }) {
  return (
    <span className="g-spark">
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={i < on ? "on" : ""} style={{ height: 4 + i * 1 }}></span>
      ))}
    </span>
  );
}

Object.assign(window, {
  Icon, TypeBadge, FieldPath, LeafRow, DistributionChips, Trend,
  DiffLegend, GroupSpark, fmtCurrency, fmtNumber,
});
