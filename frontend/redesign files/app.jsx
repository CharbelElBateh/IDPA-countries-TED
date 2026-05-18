/* ============================================================
   IDPA — App shell + router
   ============================================================ */

function Navbar({ route, go, counts }) {
  const tabs = [
    { id: "countries",     label: "Countries", count: counts.countries, screens: ["countries","country"] },
    { id: "compare-form",  label: "Compare",   count: counts.compares,  screens: ["compare-form","compare-result"] },
    { id: "patch",         label: "Patch",     count: null,             screens: ["patch"] },
    { id: "cluster-form",  label: "Cluster",   count: counts.runs,      screens: ["cluster-form","cluster-result"] },
  ];
  return (
    <nav className="nav">
      <div className="nav-inner">
        <a className="brand" onClick={(e) => { e.preventDefault(); go({ name: "countries" }); }}>
          <span className="brand-mark">IDPA</span>
          <span className="brand-sub">Country Explorer</span>
        </a>
        <ul className="nav-tabs">
          {tabs.map(t => (
            <li key={t.id}
                className={`nav-tab ${t.screens.includes(route.name) ? "active" : ""}`}
                onClick={() => go({ name: t.id })}>
              {t.label}{t.count != null && <span className="count">{t.count}</span>}
            </li>
          ))}
        </ul>
        <span className="nav-spacer"></span>
        <span className="nav-meta">
          <span><span className="dot"></span>mongo · idpa@v2</span>
          <span>last sync 14:08</span>
        </span>
      </div>
    </nav>
  );
}

function App() {
  const [route, setRoute] = useState({ name: "countries" });
  const go = (r) => {
    setRoute(r);
    window.scrollTo({ top: 0, behavior: "instant" });
  };

  const counts = { countries: 192, compares: 4, runs: RECENT_RUNS.length };

  let screen;
  switch (route.name) {
    case "countries":      screen = <ScreenCountries     go={go} />; break;
    case "country":        screen = <ScreenCountryDetail go={go} country={route.country} />; break;
    case "compare-form":   screen = <ScreenCompareForm   go={go} c1pre={route.c1} c2pre={route.c2} />; break;
    case "compare-result": screen = <ScreenCompareResult go={go} c1pre={route.c1} c2pre={route.c2} />; break;
    case "patch":          screen = <ScreenPatch         go={go} c1pre={route.c1} />; break;
    case "cluster-form":   screen = <ScreenClusterForm   go={go} />; break;
    case "cluster-result": screen = <ScreenClusterResult go={go} />; break;
    default:               screen = <ScreenCountries     go={go} />;
  }

  return (
    <div className="app">
      <Navbar route={route} go={go} counts={counts} />
      <main className="shell-main">{screen}</main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
