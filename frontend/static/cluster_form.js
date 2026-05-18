// Cluster form wiring (redesign):
// - algorithm picker is a segmented control (.seg .opt[data-algo]),
// - feature-row is a <label> wrapping checkbox+inputs (no manual checkbox
//   targeting — clicking anywhere on the row toggles),
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

  // ------------------------------------------------- feature-row toggle + weight enable
  function syncRow(label) {
    const cb = $(".field-check", label);
    const w  = $(".field-weight", label);
    label.classList.toggle("on", cb.checked);
    label.classList.toggle("off", !cb.checked);
    if (w) w.disabled = !cb.checked;
  }
  $$(".feature-row").forEach((label) => {
    const cb = $(".field-check", label);
    cb.addEventListener("change", () => { syncRow(label); refreshGroup(label); refreshSummary(); });
    syncRow(label);
  });
  // Stop the weight number input from also toggling the checkbox when
  // clicked (since the whole row is a <label for=…>).
  $$(".field-weight").forEach((w) => {
    w.addEventListener("click", (e) => e.preventDefault());
    w.addEventListener("input", refreshSummary);
  });

  // ------------------------------------------------- group counter + spark
  function refreshGroup(label) {
    const group = label.closest(".feature-group");
    if (!group) return;
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
  $$(".feature-group").forEach((group) => {
    const first = $(".feature-row", group);
    if (first) refreshGroup(first);
  });

  // ------------------------------------------------- bulk controls
  function applyBulk(predicate) {
    $$(".feature-row").forEach((label) => {
      const cb = $(".field-check", label);
      const should = predicate(cb.dataset.path);
      if (cb.checked !== should) cb.checked = should;
      syncRow(label);
      refreshGroup(label);
    });
    refreshSummary();
  }
  $("#select-all-fields")?.addEventListener("click", () => applyBulk(() => true));
  $("#select-none-fields")?.addEventListener("click", () => applyBulk(() => false));
  $("#select-preset")?.addEventListener("click", () => {
    const preset = new Set([
      "government.type",
      "demographics.religion",
      "economy.gdp_ppp.per_capita",
      "economy.hdi.value",
    ]);
    applyBulk((p) => preset.has(p));
  });

  // ------------------------------------------------- live summary in run-bar
  function refreshSummary() {
    const onRows = $$(".feature-row").filter((r) => $(".field-check", r).checked);
    const total  = $$(".feature-row").length;
    const sumW   = onRows.reduce((a, r) => {
      const w = $(".field-weight", r);
      return a + (w ? parseFloat(w.value || "0") : 0);
    }, 0);
    $("#feature-count").textContent = `${onRows.length}/${total} on`;
    $("#feature-weight-sum").textContent = sumW.toFixed(1);
    $("#bar-features").textContent = onRows.length;
    $("#bar-weight").textContent = sumW.toFixed(1);

    const algo = algoHidden.value;
    $("#bar-algo").textContent = algo;
    const kInput = algo === "kmedoids"
      ? form.elements["k_kmedoids"]
      : form.elements["k_agg"];
    $("#bar-k").textContent = kInput ? kInput.value : "—";
    $("#bar-cost").textContent = costSelect.value;
  }
  form.addEventListener("input", refreshSummary);
  costSelect.addEventListener("change", refreshSummary);
  refreshSummary();

  // ------------------------------------------------- submit
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const algo = algoHidden.value;
    const fd = new FormData(form);
    const cost_model = fd.get("cost_model");

    const fields = [];
    const weights = {};
    $$(".feature-row").forEach((r) => {
      const cb = $(".field-check", r);
      if (!cb.checked) return;
      const path = cb.dataset.path;
      fields.push(path);
      const w = $(".field-weight", r);
      if (w) weights[path] = parseFloat(w.value || "1.0");
    });
    if (fields.length === 0) {
      showStatus("Pick at least one feature.", "warn");
      return;
    }

    const params = {};
    if (algo === "kmedoids") {
      params.k = parseInt(fd.get("k_kmedoids"), 10);
      params.init = fd.get("init");
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
    showStatus(`Running ${algo} on ${fields.length} fields…`, "info");

    try {
      const res = await fetch("/api/cluster/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          algorithm: algo, fields, weights, cost_model, params,
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
