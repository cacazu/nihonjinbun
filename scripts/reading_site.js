/* Reading preferences only. No network, analytics, or reading-history storage. */
(() => {
  "use strict";
  const root = document.documentElement;
  const controls = document.querySelector(".reader-controls");
  if (!controls) return;
  const key = "nihonjinbun-reader-settings-v1";
  const allowed = { mode: ["ja", "parallel"], size: ["small", "medium", "large"] };
  const settings = { mode: "ja", size: "medium" };
  function readSettings() {
    try {
      const saved = JSON.parse(localStorage.getItem(key));
      // Validate the complete pair before applying it. Bad or blocked storage
      // must not replace choices already active in this restored document.
      if (!saved || typeof saved !== "object" || Array.isArray(saved) ||
          !Object.keys(allowed).every(name => allowed[name].includes(saved[name]))) return;
      for (const name of Object.keys(allowed)) settings[name] = saved[name];
    } catch (_) { /* Preserve current settings when storage is unavailable. */ }
  }
  function apply(save = false) {
    for (const name of Object.keys(settings)) {
      root.dataset[name] = settings[name];
      controls.querySelectorAll(`[data-${name}]`).forEach(button => {
        button.setAttribute("aria-pressed", String(button.dataset[name] === settings[name]));
      });
    }
    if (save) {
      try { localStorage.setItem(key, JSON.stringify(settings)); } catch (_) { /* Keep controls usable. */ }
    }
  }
  function showAnchor(hash) {
    let id;
    try { id = decodeURIComponent(hash.slice(1)); } catch (_) { return; }
    const target = document.getElementById(id);
    if (target && target.closest(".source-column") && settings.mode !== "parallel") {
      settings.mode = "parallel";
      apply(true);
      requestAnimationFrame(() => target.scrollIntoView({ block: "center" }));
    }
  }
  controls.addEventListener("click", event => {
    const button = event.target.closest("button");
    if (!button) return;
    for (const name of Object.keys(allowed)) {
      if (allowed[name].includes(button.dataset[name])) settings[name] = button.dataset[name];
    }
    apply(true);
  });
  // Reveal source anchors before the browser follows note backlinks, even twice.
  document.addEventListener("click", event => {
    const link = event.target.closest('a[href^="#"]');
    if (link) showAnchor(link.hash);
  });
  window.addEventListener("hashchange", () => showAnchor(location.hash));
  window.addEventListener("pageshow", () => {
    // BFCache restores this closure as-is, so another page's changes need a read.
    readSettings();
    apply(false);
    showAnchor(location.hash);
  });
  readSettings();
  apply();
  controls.hidden = false;
  showAnchor(location.hash);
})();
