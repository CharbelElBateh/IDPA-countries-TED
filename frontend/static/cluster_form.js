// Cluster form wiring:
// - algorithm picker is a segmented control (.seg .opt[data-algo]),
// - feature-row is a <label> wrapping a single radio (name="feature");
//   exactly one feature can be selected — no per-feature weights,
// - group <details> shows a count + spark in its summary,
// - sticky run-bar shows a live summary of selection.

(function () {
  const $  = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

  const form        = $("#cluster-form");
  const algoHidden  = $("#algorithm");
  const algoSeg     = $("#algo-seg");
  const costSelect  = $("#cost_model");
  const runBtn      = $("#run-btn");
  const statusBox   = $("#status");

  // ------------------------------------------------- algorithm picker (seg)
  function setAlgo(algo) {
    algoHidden.value = algo;
    $$(".opt", algoSeg).forEach((o) =>
      o.classList.toggle("active", o.dataset.algo === algo));
    $$(".params-row.algo-knobs").forEach((row) => {
      row.style.display = row.classList.contains(algo) ? "" : "none";
    });
    refreshSummary();
  }
  $$(".opt", algoSeg).forEach((o) =>
    o.addEventListener("click", () => setAlgo(o.dataset.algo)));

  // ------------------------------------------------- single-feature select
  function selectedPath() {
    const r = $('.field-check:checked');
    return r ? r.dataset.path : null;
  }
  function syncRows() {
    $$(".feature-row").forEach((label) => {
      const cb = $(".field-check", label);
      label.classList.toggle("on", cb.checked);
      label.classList.toggle("off", !cb.checked);
    });
  }
  $$(".feature-row .field-check").forEach((cb) => {
    cb.addEventListener("change", () => {
      syncRows();
      $$(".feature-group").forEach(refreshGroup);
      refreshSummary();
    });
  });

  // ------------------------------------------------- group counter + spark
  function refreshGroup(group) {
    const rows = $$(".feature-row", group);
    const on = rows.filter((r) => $(".field-check", r).checked).length;
    const ct = $(".g-ct", group);
    if (ct) {
      ct.textContent = `${on}/${rows.length}`;
      ct.classList.toggle("has", on > 0);
    }
    const sparks = $$(".g-spark span", group);
    sparks.forEach((s, i) => s.classList.toggle("on", i < on));
  }
  $$(".feature-group").forEach(refreshGroup);

  // ------------------------------------------------- live summary in run-bar
  function refreshSummary() {
    const path = selectedPath();
    $("#feature-count").textContent = path || "none selected";
    $("#bar-features").textContent = path || "none";

    const algo = algoHidden.value;
    $("#bar-algo").textContent = algo;
    const kInput = algo === "kmeans"
      ? form.elements["k_kmeans"]
      : form.elements["k_agg"];
    $("#bar-k").textContent = kInput ? kInput.value : "—";
    $("#bar-cost").textContent = costSelect.value;
  }
  form.addEventListener("input", refreshSummary);
  costSelect.addEventListener("change", refreshSummary);
  syncRows();
  refreshSummary();

  // ------------------------------------------------- submit
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const algo = algoHidden.value;
    const fd = new FormData(form);
    const cost_model = fd.get("cost_model");

    const path = selectedPath();
    if (!path) {
      showStatus("Pick one feature to cluster on.", "warn");
      return;
    }
    const fields = [path];

    const params = {};
    if (algo === "kmeans") {
      params.k = parseInt(fd.get("k_kmeans"), 10);
      params.n_init = parseInt(fd.get("n_init"), 10);
      params.max_iter = parseInt(fd.get("max_iter"), 10);
      params.random_seed = parseInt(fd.get("random_seed"), 10);
    } else if (algo === "hierarchical_agglomerative") {
      const dt = fd.get("distance_threshold");
      if (dt && dt.toString().trim() !== "") {
        params.distance_threshold = parseFloat(dt);
      } else {
        params.k = parseInt(fd.get("k_agg"), 10);
      }
      params.linkage = fd.get("linkage");
    }

    setRunning(true);
    showStatus(`Running ${algo} on ${path}…`, "info");

    try {
      const res = await fetch("/api/cluster/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          algorithm: algo, fields, weights: {}, cost_model, params,
        }),
      });
      const body = await res.json();
      if (!res.ok) {
        showStatus(`Error: ${body.error || res.statusText}`, "danger");
        setRunning(false);
        return;
      }
      window.location.href = `/cluster/${encodeURIComponent(body.id)}`;
    } catch (err) {
      showStatus(`Request failed: ${err.message}`, "danger");
      setRunning(false);
    }
  });

  function setRunning(running) {
    runBtn.disabled = running;
    runBtn.textContent = running ? "Running…" : "▶ Run clustering";
  }
  function showStatus(msg, level) {
    statusBox.className = `alert ${level} mt-4`;
    statusBox.textContent = msg;
    statusBox.style.display = "";
  }
})();
