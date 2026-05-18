/* Patch page — apply an edit script to a country tree.
 *
 * Three script sources: pasted JSON, uploaded file, cached comparison.
 * On apply, POSTs to /api/patch and renders the resulting tree.
 */
(function () {
  const countrySel = document.getElementById("patch-country");
  const textarea   = document.getElementById("script-json");
  const fileInput  = document.getElementById("script-file");
  const cachedSel  = document.getElementById("script-cached");
  const useReverse = document.getElementById("use-reverse");
  const statusEl   = document.getElementById("patch-status");
  const labelEl    = document.getElementById("patched-label");
  let scriptObj = null;

  const panes = {
    paste:  document.getElementById("pane-paste"),
    upload: document.getElementById("pane-upload"),
    cached: document.getElementById("pane-cached"),
  };
  function showPane(name) {
    Object.entries(panes).forEach(([k, el]) => {
      el.style.display = k === name ? "" : "none";
    });
  }
  document.getElementById("src-paste").addEventListener("click", (e) => { e.preventDefault(); showPane("paste"); });
  document.getElementById("src-upload").addEventListener("click", (e) => { e.preventDefault(); showPane("upload"); });
  document.getElementById("src-cached").addEventListener("click", (e) => { e.preventDefault(); showPane("cached"); });

  fileInput.addEventListener("change", () => {
    const f = fileInput.files[0];
    if (!f) return;
    f.text().then((t) => {
      try { scriptObj = JSON.parse(t); }
      catch (e) { setStatus("Invalid JSON: " + e.message, "danger"); }
    });
  });

  cachedSel.addEventListener("change", () => {
    const id = cachedSel.value;
    if (!id) return;
    fetch(`/api/scripts/${encodeURIComponent(id)}`)
      .then((r) => r.json())
      .then((doc) => {
        if (doc.error) throw new Error(doc.error);
        scriptObj = useReverse.checked ? doc.reverse : doc.forward;
        // Preselect the matching country.
        const opt = cachedSel.options[cachedSel.selectedIndex];
        if (opt) {
          const target = useReverse.checked ? opt.dataset.c2 : opt.dataset.c1;
          if (target) countrySel.value = target;
        }
        setStatus(`Loaded ${scriptObj.operations.length} ops from cache.`, "muted");
      })
      .catch((e) => setStatus("Failed: " + e.message, "danger"));
  });

  useReverse.addEventListener("change", () => {
    // Trigger a reload of the selected cached script.
    if (cachedSel.value) cachedSel.dispatchEvent(new Event("change"));
  });

  document.getElementById("btn-apply").addEventListener("click", () => {
    const country = countrySel.value;
    if (!country) { setStatus("Pick a country.", "danger"); return; }

    let script = scriptObj;
    if (!script) {
      try {
        script = JSON.parse(textarea.value);
      } catch (e) {
        setStatus("Script JSON is invalid: " + e.message, "danger");
        return;
      }
    }
    if (!script || !script.operations) {
      setStatus("No script provided.", "danger");
      return;
    }

    setStatus("Applying…", "muted");
    fetch("/api/patch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ country, script }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.error) throw new Error(data.error);
        labelEl.innerHTML = `Patched · <code>${country}</code> · ` +
          `${data.size} nodes after ` +
          `${data.ops.relabel}r/${data.ops.delete}d/${data.ops.insert}i (cost ${data.cost.toFixed(2)})`;
        TreeView.fromData(
          "tree-canvas-patched",
          { root: data.patched },
          { initialDepth: 1 }
        );
        setStatus("Done.", "success");
      })
      .catch((e) => setStatus("Failed: " + e.message, "danger"));
  });

  function setStatus(msg, kind) {
    const cls = { success: "text-success", danger: "text-danger", muted: "text-muted" }[kind] || "";
    statusEl.className = "ms-3 small " + cls;
    statusEl.textContent = msg;
  }
})();
